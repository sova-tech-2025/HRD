import json
import random

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.db import (
    can_user_take_test,
    check_test_access,
    check_user_permission,
    complete_session_for_trainee,
    complete_stage_for_trainee,
    ensure_company_id,
    get_stage_session_progress,
    get_test_by_id,
    get_test_questions,
    get_trainee_attestation_status,
    get_trainee_available_tests,
    get_trainee_learning_path,
    get_trainee_stage_progress,
    get_user_broadcast_tests,
    get_user_by_id,
    get_user_by_tg_id,
    get_user_mentor,
    get_user_roles,
    get_user_test_attempts_count,
    get_user_test_result,
    get_user_test_results,
    save_test_result,
)
from handlers.training.mentorship import get_days_word
from handlers.training.trainee_trajectory import build_trajectory_text, get_no_trajectory_text
from keyboards.keyboards import (
    get_mentor_contact_keyboard,
    get_test_results_keyboard,
    get_test_selection_for_taking_keyboard,
    get_test_start_keyboard,
)
from states.states import TestTakingStates
from utils.auth.auth import check_auth
from utils.handlers.callback import ensure_callback_auth
from utils.handlers.user import get_current_user
from utils.logger import log_user_action, log_user_error, logger
from utils.timezone import moscow_now

router = Router()


@router.message(Command("my_tests"))
async def cmd_my_tests_command(message: Message, state: FSMContext, session: AsyncSession):
    """Обработчик команды /my_tests"""
    await cmd_trajectory_tests(message, state, session)


@router.message(Command("all_tests"))
async def cmd_all_tests_command(message: Message, state: FSMContext, session: AsyncSession):
    """Обработчик команды /all_tests"""
    # Для команды all_tests используем функцию cmd_list_tests из tests.py
    # Но импортируем её туда, где она нужна
    from handlers.tests.tests import cmd_list_tests

    await cmd_list_tests(message, state, session)


@router.message(F.text.in_(["Доступные тесты", "Тесты траектории 🗺️"]))
async def cmd_trajectory_tests(message: Message, state: FSMContext, session: AsyncSession):
    """Обработчик команды тестов траектории для стажеров"""
    is_auth = await check_auth(message, state, session)
    if not is_auth:
        return

    user = await get_current_user(message, state, session)
    if not user:
        await message.answer("Ты не зарегистрирован в системе.")
        return

    has_permission = await check_user_permission(session, user.id, "take_tests")
    if not has_permission:
        await message.answer("У тебя нет прав для прохождения тестов.")
        return

    # Получаем company_id с fallback на ensure_company_id для безопасности
    company_id = user.company_id
    if company_id is None:
        company_id = await ensure_company_id(session, state, message.from_user.id)
    if company_id is None:
        await message.answer("❌ Не удалось определить компанию. Обратись к администратору.")
        return

    # Получаем ТОЛЬКО тесты траектории (от наставника), исключая тесты рассылки от рекрутера
    available_tests = await get_trainee_available_tests(session, user.id, company_id=company_id)

    if not available_tests:
        await message.answer(
            "Твой наставник пока не назначил тебе тесты 🥹\n\n"
            "Как только он это сделает, ты сможешь приступить к ним. "
            "Если хочешь ускорить процесс — свяжись с наставником напрямую",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[[InlineKeyboardButton(text="≡ Главное меню", callback_data="main_menu")]]
            ),
        )
        return

    # Пагинация: показываем по 5 тестов на страницу
    page = 0
    per_page = 5
    start_index = page * per_page
    end_index = start_index + per_page
    page_tests = available_tests[start_index:end_index]

    tests_list = []
    for i, test in enumerate(page_tests, 1):
        # Получаем company_id для изоляции
        company_id = user.company_id

        # Получаем результат последнего прохождения
        test_result = await get_user_test_result(session, user.id, test.id, company_id=company_id)

        # Номер с учетом глобального индекса
        global_index = start_index + i
        test_line = f"#<b>{global_index}</b> <b>{test.name}</b>\n"
        test_line += f"🎯 Порог прохождения: {test.threshold_score:.1f}/{test.max_score:.1f}\n"

        # Если тест был пройден, но не получен балл порога - показываем последнюю попытку
        if test_result and not test_result.is_passed:
            test_line += f"❌ Последняя попытка: {test_result.score:.1f}/{test_result.max_possible_score:.1f}\n"

        test_line += f"\n{test.description or 'Описание не указано'}"
        tests_list.append(test_line)

    tests_display = "\n━━━━━━━━━━━━\n\n".join(tests_list)

    # Информация о странице
    total_pages = (len(available_tests) + per_page - 1) // per_page
    page_info = f"\n\n📄 Страница {page + 1}/{total_pages}" if total_pages > 1 else ""

    await message.answer(
        f"🗺️ <b>Тесты траектории</b>\n\n"
        f"Сейчас у тебя есть доступ к <b>{len(available_tests)}</b> тестам{page_info}\n"
        f"━━━━━━━━━━━━\n\n"
        f"{tests_display}\n\n"
        "Выбери тест для прохождения:",
        parse_mode="HTML",
        reply_markup=get_test_selection_for_taking_keyboard(available_tests, page, per_page, "trajectory_tests_page"),
    )

    # Сохраняем список тестов в state для пагинации
    await state.update_data(trajectory_tests=available_tests, trajectory_page=page)

    # КРИТИЧЕСКИ ВАЖНО: Устанавливаем контекст "taking" для стажера
    await state.update_data(test_context="taking")
    await state.set_state(TestTakingStates.waiting_for_test_selection)

    log_user_action(message.from_user.id, message.from_user.username, "opened trajectory tests")


async def format_my_tests_display(
    session: AsyncSession, user, available_tests: list, page: int = 0, per_page: int = 5
) -> tuple[str, InlineKeyboardMarkup]:
    """
    Универсальная функция для форматирования списка "Мои тесты" с пагинацией

    Args:
        session: Сессия БД
        user: Объект пользователя
        available_tests: Список доступных тестов
        page: Номер страницы (начиная с 0)
        per_page: Количество тестов на страницу

    Returns:
        tuple: (текст сообщения, клавиатура)
    """
    # Определяем роль пользователя
    user_roles = await get_user_roles(session, user.id)
    role_names = [role.name for role in user_roles]
    is_trainee = "Стажер" in role_names
    is_mentor = "Наставник" in role_names
    is_employee = "Сотрудник" in role_names
    is_recruiter = "Рекрутер" in role_names
    is_manager = "Руководитель" in role_names

    # Получаем company_id для изоляции с проверкой на None
    company_id = user.company_id
    if company_id is None:
        # Если company_id не установлен, это критическая ошибка для изоляции
        logger.error(f"У пользователя {user.id} не установлен company_id")
        # Возвращаем пустой список для безопасности
        return "❌ Ошибка: не удалось определить компанию. Обратись к администратору.", InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="≡ Главное меню", callback_data="main_menu")]]
        )

    # Пагинация: показываем только тесты текущей страницы
    start_index = page * per_page
    end_index = start_index + per_page
    page_tests = available_tests[start_index:end_index]

    # Импортируем TraineeTestAccess для получения даты назначения
    from sqlalchemy import select

    from database.models import TraineeTestAccess

    # Формируем список тестов согласно макету 4.2
    tests_list = []
    for i, test in enumerate(page_tests, 1):
        # Получаем дату назначения теста из TraineeTestAccess
        access_query = select(TraineeTestAccess).where(
            TraineeTestAccess.trainee_id == user.id,
            TraineeTestAccess.test_id == test.id,
            TraineeTestAccess.is_active == True,
        )
        if company_id is not None:
            access_query = access_query.where(TraineeTestAccess.company_id == company_id)
        access_result = await session.execute(access_query)
        access = access_result.scalar_one_or_none()
        assigned_date_str = ""
        if access and access.granted_date:
            assigned_date_str = f"Назначен: {access.granted_date.strftime('%d.%m.%Y')}\n"

        # Получаем результат последнего прохождения
        test_result = await get_user_test_result(session, user.id, test.id, company_id=company_id)

        # Формируем строку теста согласно макету (номер с учетом глобального индекса)
        global_index = start_index + i
        test_line = f"#<b>{global_index}</b> <b>{test.name}</b>\n"
        if assigned_date_str:
            test_line += assigned_date_str + "\n"  # Добавляем дополнительный перенос строки после даты
        test_line += f"🎯 Порог прохождения: {test.threshold_score:.1f}/{test.max_score:.1f}\n"

        # Если тест был пройден, но не получен балл порога - показываем последнюю попытку
        if test_result and not test_result.is_passed:
            test_line += f"❌ Последняя попытка: {test_result.score:.1f}/{test_result.max_possible_score:.1f}\n"

        tests_list.append(test_line)

    tests_display = "\n━━━━━━━━━━━━\n\n".join(tests_list)

    # Информация о странице
    total_pages = (len(available_tests) + per_page - 1) // per_page
    page_info = f"\n\n📄 Страница {page + 1}/{total_pages}" if total_pages > 1 else ""

    # Формируем итоговое сообщение согласно макету 4.1-4.2 (без заголовка "Мои ТЕСТЫ" - он в caption фото)
    message_text = (
        f"<b>Тесты, доступные для прохождения</b>\n"
        f"Всего: {len(available_tests)}{page_info}\n\n"
        f"{tests_display}\n\n"
        "Выбери тест для прохождения:"
    )

    keyboard = get_test_selection_for_taking_keyboard(available_tests, page, per_page)

    return message_text, keyboard


@router.message(F.text.in_(["Мои тесты 📋"]))
async def cmd_trainee_broadcast_tests(message: Message, state: FSMContext, session: AsyncSession):
    """Обработчик команды 'Мои тесты 📋' для стажеров и наставников - тесты от рекрутера + индивидуальные от наставника"""
    try:
        # Проверка авторизации
        is_auth = await check_auth(message, state, session)
        if not is_auth:
            return

        # Получение пользователя
        user = await get_current_user(message, state, session)
        if not user:
            await message.answer("Ты не зарегистрирован в системе.")
            return

        # Проверяем что пользователь имеет право проходить тесты
        has_permission = await check_user_permission(session, user.id, "take_tests")
        if not has_permission:
            await message.answer("❌ У тебя нет прав для прохождения тестов.")
            return

        # Получаем company_id с fallback на ensure_company_id для безопасности
        company_id = user.company_id
        if company_id is None:
            company_id = await ensure_company_id(session, state, message.from_user.id)
        if company_id is None:
            await message.answer("❌ Не удалось определить компанию. Обратись к администратору.")
            return

        # Получаем тесты ВМЕСТЕ: от рекрутера через рассылку + индивидуальные от наставника (исключая тесты траектории)
        available_tests = await get_user_broadcast_tests(
            session, user.id, exclude_completed=False, company_id=company_id
        )

        if not available_tests:
            no_tests_message = "❌ Пока новых тестов нет\nКогда появятся, тебе придёт уведомление"
            await message.answer(
                no_tests_message,
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(
                    inline_keyboard=[[InlineKeyboardButton(text="≡ Главное меню", callback_data="main_menu")]]
                ),
            )
            return

        # Используем универсальную функцию для форматирования с пагинацией
        page = 0
        message_text, keyboard = await format_my_tests_display(session, user, available_tests, page=page)

        # Сохраняем список тестов в state для пагинации
        await state.update_data(available_tests=available_tests, current_page=page)

        # Согласно макету 4.1: отправляем баннер SOVA для "Мои тесты", если настроен
        from aiogram.types import FSInputFile

        from config import MY_TESTS_IMAGE_FILE_ID, MY_TESTS_IMAGE_PATH, MY_TESTS_IMAGE_URL

        photo_source = None
        if MY_TESTS_IMAGE_FILE_ID:
            photo_source = MY_TESTS_IMAGE_FILE_ID
        elif MY_TESTS_IMAGE_URL:
            photo_source = MY_TESTS_IMAGE_URL
        elif MY_TESTS_IMAGE_PATH:
            try:
                photo_source = FSInputFile(MY_TESTS_IMAGE_PATH)
            except Exception as file_error:
                logger.warning(f"Не удалось загрузить изображение для 'Мои тесты': {file_error}")

        if photo_source:
            try:
                # Caption содержит только текст списка (без "Мои ТЕСТЫ" - оно на баннере)
                await message.answer_photo(
                    photo=photo_source, caption=message_text, parse_mode="HTML", reply_markup=keyboard
                )
            except Exception as photo_error:
                logger.warning(f"Не удалось отправить изображение для 'Мои тесты': {photo_error}")
                await message.answer(message_text, reply_markup=keyboard, parse_mode="HTML")
        else:
            await message.answer(message_text, reply_markup=keyboard, parse_mode="HTML")

        # КРИТИЧЕСКИ ВАЖНО: Устанавливаем контекст "taking" для наставника и сотрудника
        await state.update_data(test_context="taking")
        await state.set_state(TestTakingStates.waiting_for_test_selection)

        # Логирование
        log_user_action(user.tg_id, "my_tests_viewed", f"Просмотрел мои тесты: {len(available_tests)}")

    except Exception as e:
        await message.answer("Произошла ошибка при получении списка тестов")
        log_user_error(message.from_user.id, "my_tests_error", str(e))


async def show_user_test_scores(
    message: Message, session: AsyncSession, page: int = 0, state: FSMContext = None
) -> None:
    """Универсальная функция для показа результатов тестирования пользователя с пагинацией"""
    if state:
        user = await get_current_user(message, state, session)
    else:
        user = await get_user_by_tg_id(session, message.from_user.id)
    if not user:
        await message.answer("Ты не зарегистрирован в системе.")
        return

    has_permission = await check_user_permission(session, user.id, "view_test_results")
    if not has_permission:
        await message.answer("У тебя нет прав для просмотра результатов тестов.")
        return

    # Определяем роль пользователя
    user_roles = [role.name for role in user.roles]
    if "Стажер" in user_roles:
        user_role = "стажер"
    elif "Наставник" in user_roles:
        user_role = "наставник"
    elif "Рекрутер" in user_roles:
        user_role = "рекрутер"
    elif "Руководитель" in user_roles:
        user_role = "руководитель"
    else:
        user_role = "пользователь"

    # Получаем company_id для изоляции
    company_id = user.company_id
    if company_id is None:
        # Логируем ошибку, но не прерываем выполнение (показываем пустые результаты)
        logger.error(f"У пользователя {user.id} не установлен company_id при просмотре результатов")
        company_id = None  # Передаем None, функция должна обработать это корректно

    test_results = await get_user_test_results(session, user.id, company_id=company_id)

    if not test_results:
        await message.answer(
            "📊 <b>Твои результаты</b>\n\n"
            "Ты пока не проходил тестов.\n"
            "Используй кнопку 'Мои тесты 📋' для прохождения доступных тестов.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[[InlineKeyboardButton(text="☰ Главное меню", callback_data="main_menu")]]
            ),
        )
        return

    # Подсчитываем статистику по всем результатам
    total_score = 0
    passed_count = 0
    total_tests_taken = len(test_results)

    for result in test_results:
        total_score += result.score
        if result.is_passed:
            passed_count += 1

    success_rate = (passed_count / total_tests_taken * 100) if total_tests_taken > 0 else 0

    # Пагинация: показываем по 5 результатов на страницу
    per_page = 5
    start_index = page * per_page
    end_index = start_index + per_page
    page_results = test_results[start_index:end_index]

    # Формируем список результатов для текущей страницы
    results_list = []
    for result in page_results:
        test = await get_test_by_id(session, result.test_id, company_id=company_id)
        status = "пройден" if result.is_passed else "не пройден"
        percentage = (result.score / result.max_possible_score * 100) if result.max_possible_score > 0 else 0

        date_str = result.created_date.strftime("%d.%m.%Y %H:%M") if result.created_date else "Не указана"
        if result.end_time and result.start_time:
            time_str = f"{(result.end_time - result.start_time).total_seconds():.0f} сек"
        else:
            time_str = "Не указано"

        results_list.append(
            f"<b>Тест:</b> {test.name if test else 'Неизвестный тест'}\n"
            f"• Баллы: {result.score:.1f}/{result.max_possible_score:.1f} ({percentage:.1f}%)\n"
            f"• Статус: {status}\n"
            f"• Дата: {date_str}\n"
            f"• Время: {time_str}"
        )

    results_text = "\n\n".join(results_list)

    # Получаем наставника для стажера (если есть)
    mentor = None
    mentor_tg_id = None
    if user_role == "стажер":
        mentor = await get_user_mentor(session, user.id)
        if mentor:
            mentor_tg_id = mentor.tg_id

    # Формируем контекстную информацию о пользователе
    days_in_status = (moscow_now() - user.role_assigned_date).days if user.role_assigned_date else 0
    days_text = get_days_word(days_in_status)

    if user_role == "стажер":
        context_info = (
            f"🦸🏻‍♂️<b>Стажер:</b> {user.full_name}\n\n"
            f"<b>Телефон:</b> {user.phone_number}\n"
            f"<b>В статусе стажера:</b> {days_in_status} {days_text}\n"
            f"<b>Объект стажировки:</b> {user.internship_object.name if user.internship_object else 'Не указан'}\n"
            f"<b>Объект работы:</b> {user.work_object.name if user.work_object else 'Не указан'}\n\n"
            f"━━━━━━━━━━━━\n\n"
        )
    else:
        context_info = (
            f"👨‍🏫<b>Наставник:</b> {user.full_name}\n\n"
            f"<b>Телефон:</b> {user.phone_number}\n"
            f"<b>В статусе наставника:</b> {days_in_status} {days_text}\n"
            f"<b>Объект стажировки:</b> {user.internship_object.name if user.internship_object else 'Не указан'}\n"
            f"<b>Объект работы:</b> {user.work_object.name if user.work_object else 'Не указан'}\n\n"
            f"━━━━━━━━━━━━\n\n"
        )

    # Формируем сообщение в зависимости от роли
    total_pages = (len(test_results) + per_page - 1) // per_page
    page_info = f" (Страница {page + 1}/{total_pages})" if total_pages > 1 else ""

    if user_role == "стажер":
        message_text = (
            f"{context_info}"
            f"📊 <b>Общая статистика</b>\n"
            f"• Пройдено тестов: {passed_count}/{total_tests_taken}\n"
            f"• Процент успеха: {success_rate:.1f}%\n\n"
            f"🧾 <b>Детальные результаты{page_info}</b>\n{results_text}\n\n"
            f"💡 <b>Совет:</b>\nОбратись к наставнику для получения доступа к новым тестам!"
        )
    else:
        message_text = (
            f"{context_info}"
            f"📊 <b>Общая статистика</b>\n"
            f"• Пройдено тестов: {passed_count}/{total_tests_taken}\n"
            f"• Процент успеха: {success_rate:.1f}%\n\n"
            f"🧾 <b>Детальные результаты{page_info}</b>\n{results_text}\n\n"
            f"💡 <b>Совет:</b>\nПродолжайте развиваться и помогайте своим стажерам!"
        )

    # Формируем клавиатуру с пагинацией
    keyboard = get_test_results_keyboard(test_results, page, per_page, user_role, mentor_tg_id)

    await message.answer(message_text, parse_mode="HTML", reply_markup=keyboard)

    log_user_action(
        message.from_user.id, message.from_user.username, f"viewed test results as {user_role}, page {page + 1}"
    )


@router.callback_query(F.data.startswith("test_scores_page:"))
async def callback_test_scores_pagination(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Обработчик пагинации результатов тестов"""
    try:
        await callback.answer()
        page = int(callback.data.split(":")[1])

        # Используем message из callback для обновления
        # Создаем временный объект Message для совместимости с show_user_test_scores
        class TempMessage:
            def __init__(self, original_message):
                self.from_user = original_message.from_user
                self.answer = original_message.answer
                self.edit_text = original_message.edit_text

        temp_msg = TempMessage(callback.message)

        # Получаем пользователя для проверки прав
        user = await get_user_by_tg_id(session, callback.from_user.id)
        if not user:
            await callback.answer("❌ Пользователь не найден.", show_alert=True)
            return

        # Получаем все результаты для формирования сообщения
        company_id = user.company_id
        test_results = await get_user_test_results(session, user.id, company_id=company_id)

        if not test_results:
            await callback.message.edit_text("Ты пока не проходил тестов.")
            return

        # Определяем роль пользователя
        user_roles = [role.name for role in user.roles]
        if "Стажер" in user_roles:
            user_role = "стажер"
        elif "Наставник" in user_roles:
            user_role = "наставник"
        elif "Рекрутер" in user_roles:
            user_role = "рекрутер"
        elif "Руководитель" in user_roles:
            user_role = "руководитель"
        else:
            user_role = "пользователь"

        # Подсчитываем статистику
        total_score = 0
        passed_count = 0
        total_tests_taken = len(test_results)

        for result in test_results:
            total_score += result.score
            if result.is_passed:
                passed_count += 1

        success_rate = (passed_count / total_tests_taken * 100) if total_tests_taken > 0 else 0

        # Пагинация
        per_page = 5
        start_index = page * per_page
        end_index = start_index + per_page
        page_results = test_results[start_index:end_index]

        # Формируем список результатов для текущей страницы
        results_list = []
        for result in page_results:
            test = await get_test_by_id(session, result.test_id, company_id=company_id)
            status = "пройден" if result.is_passed else "не пройден"
            percentage = (result.score / result.max_possible_score * 100) if result.max_possible_score > 0 else 0

            date_str = result.created_date.strftime("%d.%m.%Y %H:%M") if result.created_date else "Не указана"
            if result.end_time and result.start_time:
                time_str = f"{(result.end_time - result.start_time).total_seconds():.0f} сек"
            else:
                time_str = "Не указано"

            results_list.append(
                f"<b>Тест:</b> {test.name if test else 'Неизвестный тест'}\n"
                f"• Баллы: {result.score:.1f}/{result.max_possible_score:.1f} ({percentage:.1f}%)\n"
                f"• Статус: {status}\n"
                f"• Дата: {date_str}\n"
                f"• Время: {time_str}"
            )

        results_text = "\n\n".join(results_list)

        # Получаем наставника для стажера
        mentor = None
        mentor_tg_id = None
        if user_role == "стажер":
            mentor = await get_user_mentor(session, user.id)
            if mentor:
                mentor_tg_id = mentor.tg_id

        # Формируем контекстную информацию
        days_in_status = (moscow_now() - user.role_assigned_date).days if user.role_assigned_date else 0
        days_text = get_days_word(days_in_status)

        if user_role == "стажер":
            context_info = (
                f"🦸🏻‍♂️<b>Стажер:</b> {user.full_name}\n\n"
                f"<b>Телефон:</b> {user.phone_number}\n"
                f"<b>В статусе стажера:</b> {days_in_status} {days_text}\n"
                f"<b>Объект стажировки:</b> {user.internship_object.name if user.internship_object else 'Не указан'}\n"
                f"<b>Объект работы:</b> {user.work_object.name if user.work_object else 'Не указан'}\n\n"
                f"━━━━━━━━━━━━\n\n"
            )
        else:
            context_info = (
                f"👨‍🏫<b>Наставник:</b> {user.full_name}\n\n"
                f"<b>Телефон:</b> {user.phone_number}\n"
                f"<b>В статусе наставника:</b> {days_in_status} {days_text}\n"
                f"<b>Объект стажировки:</b> {user.internship_object.name if user.internship_object else 'Не указан'}\n"
                f"<b>Объект работы:</b> {user.work_object.name if user.work_object else 'Не указан'}\n\n"
                f"━━━━━━━━━━━━\n\n"
            )

        # Формируем сообщение
        total_pages = (len(test_results) + per_page - 1) // per_page
        page_info = f" (Страница {page + 1}/{total_pages})" if total_pages > 1 else ""

        if user_role == "стажер":
            message_text = (
                f"{context_info}"
                f"📊 <b>Общая статистика</b>\n"
                f"• Пройдено тестов: {passed_count}/{total_tests_taken}\n"
                f"• Процент успеха: {success_rate:.1f}%\n\n"
                f"🧾 <b>Детальные результаты{page_info}</b>\n{results_text}\n\n"
                f"💡 <b>Совет:</b>\nОбратись к наставнику для получения доступа к новым тестам!"
            )
        else:
            message_text = (
                f"{context_info}"
                f"📊 <b>Общая статистика</b>\n"
                f"• Пройдено тестов: {passed_count}/{total_tests_taken}\n"
                f"• Процент успеха: {success_rate:.1f}%\n\n"
                f"🧾 <b>Детальные результаты{page_info}</b>\n{results_text}\n\n"
                f"💡 <b>Совет:</b>\nПродолжайте развиваться и помогайте своим стажерам!"
            )

        # Формируем клавиатуру
        keyboard = get_test_results_keyboard(test_results, page, per_page, user_role, mentor_tg_id)

        await callback.message.edit_text(message_text, parse_mode="HTML", reply_markup=keyboard)

        log_user_action(callback.from_user.id, "test_scores_pagination", f"Page: {page + 1}")

    except Exception as e:
        await callback.answer("Произошла ошибка при переключении страницы", show_alert=True)
        log_user_error(callback.from_user.id, "test_scores_pagination_error", str(e))


@router.message(F.text.in_(["Посмотреть баллы", "📊 Посмотреть баллы", "Посмотреть баллы 📊"]))
async def cmd_view_scores(message: Message, state: FSMContext, session: AsyncSession):
    """Обработчик команды просмотра баллов (универсальный для стажера и наставника)"""
    is_auth = await check_auth(message, state, session)
    if not is_auth:
        return

    await show_user_test_scores(message, session, state=state)


@router.callback_query(F.data == "trainee_trajectory_tests")
async def callback_trainee_trajectory_tests(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Обработчик инлайн-кнопки 'Тесты траектории 🗺️' из меню стажера"""
    if not await ensure_callback_auth(callback, state, session):
        return
    try:
        await callback.message.delete()
    except Exception as e:
        logger.warning(f"Не удалось удалить сообщение: {e}")

    await cmd_trajectory_tests(callback.message, state, session)
    await callback.answer()


@router.callback_query(F.data == "trainee_my_tests")
async def callback_trainee_my_tests(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Обработчик инлайн-кнопки 'Мои тесты 📋' из меню стажера"""
    if not await ensure_callback_auth(callback, state, session):
        return
    try:
        await callback.message.delete()
    except Exception as e:
        logger.warning(f"Не удалось удалить сообщение: {e}")

    await cmd_trainee_broadcast_tests(callback.message, state, session)
    await callback.answer()


@router.callback_query(F.data == "trainee_scores")
async def callback_trainee_scores(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Обработчик инлайн-кнопки 'Посмотреть баллы 📊' из меню стажера"""
    if not await ensure_callback_auth(callback, state, session):
        return
    try:
        await callback.message.delete()
    except Exception as e:
        logger.warning(f"Не удалось удалить сообщение: {e}")

    await show_user_test_scores(callback.message, session, state=state)
    await callback.answer()


@router.callback_query(F.data.startswith("my_tests_page:"))
async def callback_my_tests_pagination(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Обработчик пагинации для "Мои тесты" """
    try:
        await callback.answer()
        page = int(callback.data.split(":")[1])

        # Получаем пользователя
        user = await get_user_by_tg_id(session, callback.from_user.id)
        if not user:
            await callback.answer("❌ Пользователь не найден.", show_alert=True)
            return

        # Получаем список тестов из state или заново
        state_data = await state.get_data()
        available_tests = state_data.get("available_tests")

        # Если тестов нет в state, получаем заново
        if not available_tests:
            company_id = user.company_id
            if company_id is None:
                company_id = await ensure_company_id(session, state, callback.from_user.id)
            if company_id is None:
                await callback.answer("❌ Не удалось определить компанию.", show_alert=True)
                return

            available_tests = await get_user_broadcast_tests(
                session, user.id, exclude_completed=False, company_id=company_id
            )
            if not available_tests:
                await callback.message.edit_text(
                    "❌ Пока новых тестов нет\nКогда появятся, тебе придёт уведомление",
                    parse_mode="HTML",
                    reply_markup=InlineKeyboardMarkup(
                        inline_keyboard=[[InlineKeyboardButton(text="≡ Главное меню", callback_data="main_menu")]]
                    ),
                )
                return
            # Сохраняем загруженные тесты в state
            await state.update_data(available_tests=available_tests)

        # Формируем сообщение с пагинацией
        message_text, keyboard = await format_my_tests_display(session, user, available_tests, page=page)

        # Сохраняем текущую страницу в state
        await state.update_data(current_page=page)

        # Проверяем, есть ли баннер
        from aiogram.types import FSInputFile

        from config import MY_TESTS_IMAGE_FILE_ID, MY_TESTS_IMAGE_PATH, MY_TESTS_IMAGE_URL

        photo_source = None
        if MY_TESTS_IMAGE_FILE_ID:
            photo_source = MY_TESTS_IMAGE_FILE_ID
        elif MY_TESTS_IMAGE_URL:
            photo_source = MY_TESTS_IMAGE_URL
        elif MY_TESTS_IMAGE_PATH:
            try:
                photo_source = FSInputFile(MY_TESTS_IMAGE_PATH)
            except Exception:
                pass

        # Обновляем сообщение
        if callback.message.photo:
            # Если текущее сообщение - фото, редактируем caption
            try:
                await callback.message.edit_caption(caption=message_text, parse_mode="HTML", reply_markup=keyboard)
            except Exception:
                # Если не удалось отредактировать caption, отправляем новое сообщение
                try:
                    await callback.message.delete()
                except Exception:
                    pass
                if photo_source:
                    await callback.bot.send_photo(
                        chat_id=callback.message.chat.id,
                        photo=photo_source,
                        caption=message_text,
                        parse_mode="HTML",
                        reply_markup=keyboard,
                    )
                else:
                    await callback.message.answer(message_text, parse_mode="HTML", reply_markup=keyboard)
        else:
            # Если текстовое сообщение, редактируем текст
            try:
                await callback.message.edit_text(message_text, parse_mode="HTML", reply_markup=keyboard)
            except Exception:
                # Если не удалось отредактировать, отправляем новое
                await callback.message.answer(message_text, parse_mode="HTML", reply_markup=keyboard)

    except Exception as e:
        logger.error(f"Ошибка пагинации 'Мои тесты': {e}")
        await callback.answer("❌ Произошла ошибка при переключении страницы.", show_alert=True)


@router.callback_query(F.data.startswith("trajectory_tests_page:"))
async def callback_trajectory_tests_pagination(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Обработчик пагинации для "Тесты траектории" """
    try:
        await callback.answer()
        page = int(callback.data.split(":")[1])

        # Получаем пользователя
        user = await get_user_by_tg_id(session, callback.from_user.id)
        if not user:
            await callback.answer("❌ Пользователь не найден.", show_alert=True)
            return

        # Получаем список тестов из state или заново
        state_data = await state.get_data()
        available_tests = state_data.get("trajectory_tests")

        # Если тестов нет в state, получаем заново
        if not available_tests:
            company_id = user.company_id
            if company_id is None:
                company_id = await ensure_company_id(session, state, callback.from_user.id)
            if company_id is None:
                await callback.answer("❌ Не удалось определить компанию.", show_alert=True)
                return

            available_tests = await get_trainee_available_tests(session, user.id, company_id=company_id)
            if not available_tests:
                await callback.message.edit_text(
                    "Твой наставник пока не назначил тебе тесты 🥹\n\n"
                    "Как только он это сделает, ты сможешь приступить к ним. "
                    "Если хочешь ускорить процесс — свяжись с наставником напрямую",
                    parse_mode="HTML",
                    reply_markup=InlineKeyboardMarkup(
                        inline_keyboard=[[InlineKeyboardButton(text="≡ Главное меню", callback_data="main_menu")]]
                    ),
                )
                return
            # Сохраняем загруженные тесты в state
            await state.update_data(trajectory_tests=available_tests)

        # Пагинация: показываем по 5 тестов на страницу
        per_page = 5
        start_index = page * per_page
        end_index = start_index + per_page
        page_tests = available_tests[start_index:end_index]

        tests_list = []
        for i, test in enumerate(page_tests, 1):
            # Получаем результат последнего прохождения
            company_id = user.company_id
            test_result = await get_user_test_result(session, user.id, test.id, company_id=company_id)

            # Номер с учетом глобального индекса
            global_index = start_index + i
            test_line = f"#<b>{global_index}</b> <b>{test.name}</b>\n"
            test_line += f"🎯 Порог прохождения: {test.threshold_score:.1f}/{test.max_score:.1f}\n"

            # Если тест был пройден, но не получен балл порога - показываем последнюю попытку
            if test_result and not test_result.is_passed:
                test_line += f"❌ Последняя попытка: {test_result.score:.1f}/{test_result.max_possible_score:.1f}\n"

            test_line += f"{test.description or 'Описание не указано'}"
            tests_list.append(test_line)

        tests_display = "\n━━━━━━━━━━━━\n\n".join(tests_list)

        # Информация о странице
        total_pages = (len(available_tests) + per_page - 1) // per_page
        page_info = f"\n\n📄 Страница {page + 1}/{total_pages}" if total_pages > 1 else ""

        message_text = (
            f"🗺️ <b>Тесты траектории</b>\n\n"
            f"Сейчас у тебя есть доступ к <b>{len(available_tests)}</b> тестам{page_info}\n"
            f"━━━━━━━━━━━━\n\n"
            f"{tests_display}\n\n"
            "Выбери тест для прохождения:"
        )

        keyboard = get_test_selection_for_taking_keyboard(available_tests, page, per_page, "trajectory_tests_page")

        # Сохраняем текущую страницу в state
        await state.update_data(trajectory_page=page)

        # Обновляем сообщение
        try:
            await callback.message.edit_text(message_text, parse_mode="HTML", reply_markup=keyboard)
        except Exception:
            # Если не удалось отредактировать, отправляем новое
            await callback.message.answer(message_text, parse_mode="HTML", reply_markup=keyboard)

    except Exception as e:
        logger.error(f"Ошибка пагинации 'Тесты траектории': {e}")
        await callback.answer("❌ Произошла ошибка при переключении страницы.", show_alert=True)


@router.callback_query(TestTakingStates.waiting_for_test_selection, F.data.startswith("test:"))
async def process_test_selection_for_taking(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Обработчик выбора теста для прохождения"""
    user = await get_user_by_tg_id(session, callback.from_user.id)
    if not user:
        await callback.message.edit_text("❌ Ты не зарегистрирован в системе.")
        return

    # Получаем company_id с fallback на ensure_company_id для безопасности
    company_id = user.company_id
    if company_id is None:
        company_id = await ensure_company_id(session, state, callback.from_user.id)
    if company_id is None:
        await callback.message.edit_text("❌ Не удалось определить компанию. Обратись к администратору.")
        await callback.answer()
        return

    test_id = int(callback.data.split(":")[1])

    test = await get_test_by_id(session, test_id, company_id=company_id)
    if not test:
        await callback.message.answer("❌ Тест не найден.")
        await callback.answer()
        return

    # Проверяем доступ к тесту
    has_access = await check_test_access(session, user.id, test_id, company_id=company_id)

    if not has_access:
        # Логируем проблему для диагностики
        logger.warning(
            f"Доступ запрещен: user_id={user.id}, test_id={test_id}, company_id={company_id}, "
            f"user_company_id={user.company_id}"
        )
        # Сообщение с кнопкой теста могло быть с фото (caption). edit_text на фото падает: "no text in the message to edit"
        deny_text = "❌ <b>Доступ запрещен</b>\n\nУ тебя нет доступа к этому тесту. Обратись к наставнику."
        try:
            if callback.message.photo:
                await callback.message.edit_caption(deny_text, parse_mode="HTML")
            else:
                await callback.message.edit_text(deny_text, parse_mode="HTML")
        except Exception as e:
            logger.warning(f"Не удалось отредактировать сообщение при отказе доступа: {e}")
            await callback.message.answer(deny_text, parse_mode="HTML")
        await callback.answer()
        return

    # Проверяем количество попыток
    attempts_count = await get_user_test_attempts_count(session, user.id, test_id, company_id=company_id)

    # Проверяем, есть ли уже результат
    existing_result = await get_user_test_result(session, user.id, test_id, company_id=company_id)

    # Формируем текст карточки теста согласно макету 4.5
    # Название теста - всегда
    test_info = f"<b>{test.name}</b>"

    # Описание - только если есть (макет 4.5: вариант 2 - без описания)
    if test.description and test.description.strip():
        test_info += f"\n\n{test.description}"

    # Совет - только если есть материал (макет 4.5: вариант 4 - без материала)
    has_material = bool(test.material_link or test.material_file_path)
    if has_material:
        test_info += "\n\n💡 <b>Совет:</b>\nЕсли есть сомнения по теме, сначала прочти прикреплённые обучающие материалы, а потом переходи к тесту"

    # Согласно макету 4.5: отправляем фото с текстом в одном сообщении, если есть
    has_photo = test.material_file_path and test.material_type == "photo"

    # Показываем индикатор загрузки для быстрого отклика
    await callback.answer()

    if has_photo:
        try:
            # Сначала отправляем новое сообщение с фото теста, затем удаляем старое
            sent_message = await callback.bot.send_photo(
                chat_id=callback.message.chat.id,
                photo=test.material_file_path,
                caption=test_info,
                parse_mode="HTML",
                reply_markup=get_test_start_keyboard(test_id, bool(existing_result), has_material),
            )
            # Удаляем старое сообщение после отправки нового (не ждем завершения)
            try:
                await callback.message.delete()
            except Exception:
                pass
        except Exception as photo_error:
            logger.warning(f"Не удалось отправить фото к тесту {test_id}: {photo_error}")
            # Fallback: отправляем только текст
            try:
                if callback.message.photo:
                    # Если исходное сообщение - фото, удаляем и отправляем новое
                    try:
                        await callback.message.delete()
                    except Exception:
                        pass
                    await callback.message.answer(
                        test_info,
                        parse_mode="HTML",
                        reply_markup=get_test_start_keyboard(test_id, bool(existing_result), has_material),
                    )
                else:
                    # Если текстовое, редактируем
                    await callback.message.edit_text(
                        test_info,
                        parse_mode="HTML",
                        reply_markup=get_test_start_keyboard(test_id, bool(existing_result), has_material),
                    )
            except Exception:
                # Если не удалось отредактировать, отправляем новое сообщение
                await callback.message.answer(
                    test_info,
                    parse_mode="HTML",
                    reply_markup=get_test_start_keyboard(test_id, bool(existing_result), has_material),
                )
    else:
        # Если фото теста нет, проверяем тип исходного сообщения
        if callback.message.photo:
            # Если исходное сообщение - фото (баннер "Мои тесты"), удаляем и отправляем новое текстовое
            # Сначала отправляем новое, затем удаляем старое для быстрого отклика
            sent_message = await callback.message.answer(
                test_info,
                parse_mode="HTML",
                reply_markup=get_test_start_keyboard(test_id, bool(existing_result), has_material),
            )
            # Удаляем старое сообщение после отправки нового
            try:
                await callback.message.delete()
            except Exception:
                pass
        else:
            # Если текстовое сообщение, редактируем текст (быстро, без удаления)
            try:
                await callback.message.edit_text(
                    test_info,
                    parse_mode="HTML",
                    reply_markup=get_test_start_keyboard(test_id, bool(existing_result), has_material),
                )
            except Exception:
                # Если не удалось отредактировать, отправляем новое сообщение
                await callback.message.answer(
                    test_info,
                    parse_mode="HTML",
                    reply_markup=get_test_start_keyboard(test_id, bool(existing_result), has_material),
                )

    await state.update_data(selected_test_id=test_id)
    await state.set_state(TestTakingStates.waiting_for_test_start)

    log_user_action(
        callback.from_user.id, callback.from_user.username, "selected test for taking", {"test_id": test_id}
    )


async def start_test(callback: CallbackQuery, state: FSMContext, session: AsyncSession, test_id: int):
    """Функция начала прохождения теста для траекторий"""
    # Передаем test_id напрямую, без изменения callback.data
    await process_start_test(callback, state, session, test_id)


async def process_start_test(callback: CallbackQuery, state: FSMContext, session: AsyncSession, test_id: int = None):
    """Обработчик начала прохождения теста"""
    user = await get_user_by_tg_id(session, callback.from_user.id)
    if not user:
        await callback.message.edit_text("❌ Ты не зарегистрирован в системе.")
        return

    # Получаем company_id с fallback на ensure_company_id для безопасности
    company_id = user.company_id
    if company_id is None:
        company_id = await ensure_company_id(session, state, callback.from_user.id)
    if company_id is None:
        await callback.message.edit_text("❌ Не удалось определить компанию. Обратись к администратору.")
        await state.clear()
        return

    if test_id is None:
        test_id = int(callback.data.split(":")[1])

    test = await get_test_by_id(session, test_id, company_id=company_id)
    if not test:
        await callback.message.edit_text("❌ Тест не найден.")
        await state.clear()
        return

    # Проверяем, может ли пользователь пройти тест (с учетом ограничений попыток)
    can_take, error_message = await can_user_take_test(session, user.id, test_id, company_id=company_id)
    if not can_take:
        attempts_count = await get_user_test_attempts_count(session, user.id, test_id, company_id=company_id)
        attempts_info = ""
        if test.max_attempts > 0:
            attempts_info = f"\n🔢 <b>Попытки:</b> {attempts_count}/{test.max_attempts}"

        await callback.message.edit_text(
            f"🚫 <b>Тест недоступен для прохождения</b>\n\n"
            f"📋 <b>Тест:</b> {test.name}\n"
            f"❌ <b>Причина:</b> {error_message}{attempts_info}\n\n"
            f"💡 <b>Что делать:</b>\n"
            f"{'• Обратись к наставнику для увеличения лимита попыток' if test.max_attempts > 0 else '• Этот тест можно пройти только один раз'}\n"
            f"• Изучи материалы к тесту более внимательно\n"
            f"• Просмотри свои ошибки в предыдущих попытках",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[[InlineKeyboardButton(text="📋 К списку тестов", callback_data="back_to_test_list")]]
            ),
        )
        await state.clear()
        await callback.answer()
        return

    questions = await get_test_questions(session, test_id, company_id=company_id)
    if not questions:
        await callback.message.edit_text("❌ В этом тесте нет вопросов. Обратись к наставнику.")
        await state.clear()
        return

    # Перемешиваем вопросы, если настройка включена
    questions_list = list(questions)
    if test.shuffle_questions:
        random.shuffle(questions_list)

    await state.update_data(
        test_id=test_id,
        questions=questions_list,
        current_question_index=0,
        user_answers={},
        answers_details=[],
        start_time=moscow_now(),
        shuffle_enabled=test.shuffle_questions,
        user_id=callback.from_user.id,  # Сохраняем Telegram ID пользователя
    )

    await show_question(callback.message, state)
    await callback.answer()


async def show_question(message: Message, state: FSMContext):
    """Отображает текущий вопрос"""
    data = await state.get_data()
    questions = data["questions"]
    index = data["current_question_index"]
    shuffle_enabled = data.get("shuffle_enabled", False)

    question = questions[index]

    # Засекаем время начала показа вопроса
    await state.update_data(question_start_time=moscow_now())

    # Подготавливаем варианты ответов для текущего вопроса
    current_options = None
    keyboard = []

    if question.question_type == "single_choice":
        options = list(question.options)
        # Перемешиваем варианты только если включена настройка перемешивания
        if shuffle_enabled:
            random.shuffle(options)

        current_options = options
        # Сохраняем порядок вариантов для корректного сопоставления ответов
        await state.update_data(current_options_order=options)

        for i, option in enumerate(options):
            keyboard.append([InlineKeyboardButton(text=option, callback_data=f"answer:{i}")])
    elif question.question_type == "multiple_choice":
        options = list(question.options)
        # Перемешиваем варианты только если включена настройка перемешивания
        if shuffle_enabled:
            random.shuffle(options)

        current_options = options
        # Сохраняем порядок вариантов для корректного сопоставления ответов
        await state.update_data(current_options_order=options)

        # Для множественного выбора не показываем кнопки - пользователь вводит ответы текстом
    elif question.question_type == "yes_no":
        keyboard.append(
            [
                InlineKeyboardButton(text="👍 Да", callback_data="answer:Да"),
                InlineKeyboardButton(text="👎 Нет", callback_data="answer:Нет"),
            ]
        )

    keyboard.append([InlineKeyboardButton(text="❌ Прервать тест", callback_data=f"cancel_test:{question.test_id}")])

    question_text = f"<b>Вопрос {index + 1}/{len(questions)}:</b>\n\n{question.question_text}"

    if question.question_type == "text" or question.question_type == "number":
        question_text += "\n\n<i>Отправь свой ответ сообщением.</i>"
    elif question.question_type == "multiple_choice":
        # Показываем варианты ответов в тексте - используем текущие варианты для этого вопроса
        options_text = "\n".join([f"{i + 1}. {option}" for i, option in enumerate(current_options)])
        question_text += f"\n\n<b>Варианты ответов:</b>\n{options_text}"
        question_text += "\n\n<i>Отправь номера правильных ответов через запятую (например: 1, 3)</i>"

    # Пытаемся отредактировать сообщение, если не получается - отправляем новое
    try:
        sent_message = await message.edit_text(
            question_text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
        )
        # Сохраняем ID последнего сообщения бота для будущего редактирования
        await state.update_data(last_bot_message_id=sent_message.message_id)
    except Exception:
        # Если не можем отредактировать (например, это текстовый ответ пользователя),
        # отправляем новое сообщение
        sent_message = await message.answer(
            question_text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
        )
        # Сохраняем ID нового сообщения бота
        await state.update_data(last_bot_message_id=sent_message.message_id)

    await state.set_state(TestTakingStates.taking_test)


@router.message(TestTakingStates.taking_test)
async def process_text_answer(message: Message, state: FSMContext, session: AsyncSession):
    """Обработка текстового, числового или множественного ответа"""
    bot = message.bot  # Получаем bot из message
    data = await state.get_data()
    questions = data["questions"]
    index = data["current_question_index"]
    question = questions[index]

    # Рассчитываем время ответа
    start_time = data.get("question_start_time", moscow_now())
    time_spent = (moscow_now() - start_time).total_seconds()

    user_answers = data.get("user_answers", {})
    answers_details = data.get("answers_details", [])

    user_answer = message.text.strip()

    if question.question_type == "number":
        try:
            float(user_answer)
        except ValueError:
            await message.answer("❌ Пожалуйста, введи число.")
            return
    elif question.question_type == "multiple_choice":
        # Обработка множественного выбора
        current_options = data.get("current_options_order", question.options)
        selected_answers = []

        # Сначала пробуем обработать как номера вариантов
        try:
            # Разделяем по запятым и пытаемся преобразовать в числа
            parts = [part.strip() for part in user_answer.split(",")]
            indices = [int(part) - 1 for part in parts]

            # Проверяем, что все индексы в допустимом диапазоне
            for idx in indices:
                if 0 <= idx < len(current_options):
                    selected_answers.append(current_options[idx])

            if len(selected_answers) != len(indices):
                raise ValueError("Некоторые номера вне диапазона")

        except (ValueError, IndexError):
            # Если не получилось как номера, пробуем как сами варианты ответов
            parts = [part.strip() for part in user_answer.split(",")]
            selected_answers = []

            for part in parts:
                # Ищем точное совпадение среди вариантов
                matching_option = None
                for option in current_options:
                    if part.lower() == option.lower():  # Сравниваем без учета регистра
                        matching_option = option
                        break

                if matching_option:
                    selected_answers.append(matching_option)

            # Если не нашли ни одного совпадения, показываем ошибку
            if not selected_answers:
                await message.answer(
                    "❌ Пожалуйста, введи:\n"
                    "• Номера вариантов через запятую (например: 1, 3)\n"
                    "• Или сами варианты ответов через запятую"
                )
                return

        user_answer = selected_answers

    user_answers[index] = user_answer

    # Проверка правильности ответа
    is_correct = False
    if question.question_type == "multiple_choice":
        # Для множественного выбора сравниваем списки
        try:
            correct_answers = (
                json.loads(question.correct_answer)
                if isinstance(question.correct_answer, str)
                else question.correct_answer
            )
            is_correct = set(user_answer) == set(correct_answers)
        except Exception as e:
            logger.error(f"Ошибка обработки множественного выбора для вопроса {question.id}: {e}")
            is_correct = user_answer == question.correct_answer
    else:
        is_correct = user_answer == question.correct_answer

    answers_details.append(
        {"question_id": question.id, "answer": user_answer, "is_correct": is_correct, "time_spent": time_spent}
    )

    await state.update_data(user_answers=user_answers, answers_details=answers_details)

    await process_next_step(message, state, session, bot)


@router.callback_query(TestTakingStates.taking_test, F.data.startswith("answer:"))
async def process_answer_selection(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Обработка ответа на вопрос с выбором"""
    bot = callback.message.bot  # Получаем bot из callback
    data = await state.get_data()
    questions = data["questions"]
    index = data["current_question_index"]
    question = questions[index]

    # Рассчитываем время ответа
    start_time = data.get("question_start_time", moscow_now())
    time_spent = (moscow_now() - start_time).total_seconds()

    # Сохраняем ответ
    user_answers = data.get("user_answers", {})
    answers_details = data.get("answers_details", [])

    if question.question_type == "single_choice":
        selected_option_index = int(callback.data.split(":")[1])
        # Используем сохраненный порядок вариантов
        current_options = data.get("current_options_order", question.options)
        user_answers[index] = current_options[selected_option_index]
    elif question.question_type == "yes_no":
        user_answers[index] = callback.data.split(":")[1]
    elif question.question_type == "multiple_choice":
        # Multiple choice должен обрабатываться только через текстовый ввод
        await callback.answer("❌ Для множественного выбора отправь номера вариантов сообщением.", show_alert=True)
        return

    # Проверка правильности ответа (multiple_choice не попадает сюда)
    is_correct = user_answers[index] == question.correct_answer

    answers_details.append(
        {"question_id": question.id, "answer": user_answers[index], "is_correct": is_correct, "time_spent": time_spent}
    )

    await state.update_data(user_answers=user_answers, answers_details=answers_details)

    await process_next_step(callback.message, state, session, bot)
    await callback.answer()


async def process_next_step(message: Message, state: FSMContext, session: AsyncSession, bot=None):
    """Переходит к следующему вопросу или завершает тест"""
    data = await state.get_data()
    index = data["current_question_index"]
    questions = data["questions"]

    new_index = index + 1
    if new_index < len(questions):
        await state.update_data(current_question_index=new_index)
        await show_question(message, state)
    else:
        await finish_test(message, state, session, bot)


async def finish_test(message: Message, state: FSMContext, session: AsyncSession, bot=None):
    """Завершение теста и подсчет результатов"""
    data = await state.get_data()
    questions = data["questions"]
    user_answers = data["user_answers"]
    test_id = data["test_id"]

    score = 0
    wrong_answers_data = []

    # Используем уже собранные правильные answers_details из состояния
    answers_details = data.get("answers_details", [])

    # Подсчитываем очки на основе уже правильно рассчитанных answers_details
    for answer_detail in answers_details:
        question_id = answer_detail["question_id"]
        is_correct = answer_detail["is_correct"]

        # Находим соответствующий вопрос
        question = next((q for q in questions if q.id == question_id), None)
        if not question:
            continue

        if is_correct:
            score += question.points
        else:
            score -= question.penalty_points
            # Добавляем в список ошибок
            # Форматируем правильный ответ для удобного отображения
            correct_answer_display = question.correct_answer
            if question.question_type == "multiple_choice":
                try:
                    correct_answers = (
                        json.loads(question.correct_answer)
                        if isinstance(question.correct_answer, str)
                        else question.correct_answer
                    )
                    if isinstance(correct_answers, list):
                        correct_answer_display = ", ".join(correct_answers)
                except Exception:
                    pass  # Если не удается распарсить, оставляем как есть

            # Форматируем пользовательский ответ для удобного отображения
            user_answer_display = answer_detail["answer"]
            if question.question_type == "multiple_choice" and isinstance(user_answer_display, list):
                user_answer_display = ", ".join(user_answer_display)

            wrong_answers_data.append(
                {
                    "question": question.question_text,
                    "user_answer": user_answer_display,
                    "correct_answer": correct_answer_display,
                }
            )

    # Получаем пользователя и используем его внутренний ID (ПЕРЕД использованием user.company_id)
    user_tg_id = data.get("user_id")  # Получаем Telegram ID из состояния
    if not user_tg_id:
        # Fallback для старых сессий
        user_tg_id = message.from_user.id if hasattr(message, "from_user") and message.from_user else None

    if not user_tg_id:
        await message.answer(
            "❌ <b>Ошибка сохранения результата</b>\n\nНе удалось определить пользователя. Обратись к администратору.",
            parse_mode="HTML",
        )
        await state.clear()
        return

    user = await get_user_by_tg_id(session, user_tg_id)
    if not user:
        await message.answer(
            "❌ <b>Ошибка сохранения результата</b>\n\nПользователь не найден в системе. Обратись к администратору.",
            parse_mode="HTML",
        )
        await state.clear()
        return

    # Получаем company_id с fallback на ensure_company_id для безопасности
    company_id = user.company_id
    if company_id is None:
        company_id = await ensure_company_id(session, state, user_tg_id)
    if company_id is None:
        await message.answer(
            "❌ <b>Ошибка сохранения результата</b>\n\nНе удалось определить компанию. Обратись к администратору.",
            parse_mode="HTML",
        )
        await state.clear()
        return

    test = await get_test_by_id(session, test_id, company_id=company_id)
    score = max(0, score)  # Не уходим в минус
    is_passed = score >= test.threshold_score

    # Сохраняем результат
    result_data = {
        "user_id": user.id,  # Используем внутренний ID пользователя из БД
        "test_id": test_id,
        "score": score,
        "max_possible_score": test.max_score,
        "is_passed": is_passed,
        "start_time": data["start_time"],
        "end_time": moscow_now(),
        "answers_details": data.get("answers_details", []),
        "wrong_answers": wrong_answers_data,
    }
    result = await save_test_result(session, result_data, company_id=company_id)

    if not result:
        await message.answer(
            "❌ <b>Ошибка сохранения результата</b>\n\n"
            "Не удалось сохранить результат теста. Обратись к администратору.",
            parse_mode="HTML",
        )
        await state.clear()
        return

    # ВАЖНО: Проверяем завершение этапа ТОЛЬКО для тестов траектории (не для рассылки)
    stage_completion_message = ""
    if is_passed:
        # Проверяем, является ли тест частью траектории (любого этапа)
        is_trajectory_test = await is_test_from_trajectory(session, user.id, test_id, company_id=company_id)
        if is_trajectory_test:
            logger.info(f"Тест {test_id} - это тест ТРАЕКТОРИИ, проверяем завершение этапа")
            stage_completion_message = await check_and_notify_stage_completion(session, user.id, test_id, bot)
        else:
            logger.info(f"Тест {test_id} - это тест РАССЫЛКИ, пропускаем проверку траектории")

    # Формируем текст результата согласно макету 4.9-4.11
    status_text = "✅ <b>Тест успешно пройден!</b>" if is_passed else "❌ <b>Тест не пройден</b>"

    keyboard = []

    # ВАЖНО: Показываем прогресс траектории ТОЛЬКО для тестов траектории (не для рассылки)
    progress_info = ""
    test_keyboard = keyboard.copy()

    # Для непройденных тестов добавляем кнопки согласно макету 4.9-4.10
    if not is_passed:
        test_keyboard.append([InlineKeyboardButton(text="Пройти еще раз 🔄", callback_data=f"test:{test_id}")])
        test_keyboard.append([InlineKeyboardButton(text="≡ Главное меню", callback_data="main_menu")])
    elif is_passed:
        # company_id уже получен выше с проверкой на None
        # Проверяем роль пользователя для дополнительной безопасности
        user_roles = await get_user_roles(session, user.id)
        role_names = [role.name for role in user_roles]
        is_trainee = "Стажер" in role_names

        # Проверяем, является ли тест частью траектории
        is_trajectory_test = await is_test_from_trajectory(session, user.id, test_id, company_id=company_id)
        if not is_trajectory_test or not is_trainee:
            # Если тест не из траектории ИЛИ пользователь не стажер - не показываем прогресс траектории
            if not is_trajectory_test:
                logger.info(f"Тест {test_id} - рассылка, НЕ показываем прогресс траектории")
            elif not is_trainee:
                logger.info(f"Пользователь {user.id} не является стажером, НЕ показываем прогресс траектории")
            trainee_path = None
            # Для пройденных тестов из рассылки добавляем кнопку главного меню согласно макету 4.11
            test_keyboard.append([InlineKeyboardButton(text="≡ Главное меню", callback_data="main_menu")])
        else:
            # Получаем траекторию стажера только для тестов траектории И только для стажеров
            trainee_path = await get_trainee_learning_path(session, user.id, company_id=company_id)

        if trainee_path:
            stages_progress = await get_trainee_stage_progress(session, trainee_path.id, company_id=company_id)

            progress_info = "\n\n🏆<b>Твой прогресс</b>\n"
            progress_info += f"📚<b>Название траектории:</b> {trainee_path.learning_path.name}\n\n"

            for stage_progress in stages_progress:
                stage = stage_progress.stage

                # Получаем сессии для определения статуса этапа
                sessions_progress = await get_stage_session_progress(session, stage_progress.id)

                # Определяем статус этапа: 🟢 если все сессии пройдены, 🟡 если открыт, ⏺️ если закрыт
                all_sessions_completed = True
                for sp in sessions_progress:
                    if hasattr(sp.session, "tests") and sp.session.tests:
                        session_tests_passed = True
                        for test_item in sp.session.tests:
                            test_result = await get_user_test_result(
                                session, user.id, test_item.id, company_id=company_id
                            )
                            if not (test_result and test_result.is_passed):
                                session_tests_passed = False
                                break
                        if not session_tests_passed:
                            all_sessions_completed = False
                            break

                if all_sessions_completed and sessions_progress:
                    stage_icon = "✅"  # Все сессии пройдены
                elif stage_progress.is_opened:
                    stage_icon = "🟡"  # Этап открыт
                else:
                    stage_icon = "⛔️"  # Этап закрыт

                progress_info += f"{stage_icon}<b>Этап {stage.order_number}:</b> {stage.name}\n"

                for session_progress in sessions_progress:
                    # Определяем статус сессии: 🟢 если все тесты пройдены, 🟡 если этап открыт, ⏺️ если этап закрыт
                    if hasattr(session_progress.session, "tests") and session_progress.session.tests:
                        all_tests_passed = True
                        for trajectory_test in session_progress.session.tests:
                            test_result = await get_user_test_result(
                                session, user.id, trajectory_test.id, company_id=company_id
                            )
                            if not (test_result and test_result.is_passed):
                                all_tests_passed = False
                                break

                        if all_tests_passed:
                            session_icon = "✅"  # Все тесты пройдены
                        elif stage_progress.is_opened:
                            session_icon = "🟡"  # Этап открыт, сессия доступна
                        else:
                            session_icon = "⛔️"  # Этап закрыт
                    else:
                        session_icon = "⛔️"  # Нет тестов

                    progress_info += f"{session_icon}<b>Сессия {session_progress.session.order_number}:</b> {session_progress.session.name}\n"

                    # Показываем тесты
                    for test_num, test_item in enumerate(session_progress.session.tests, 1):
                        # Определяем статус теста
                        test_result = await get_user_test_result(session, user.id, test_item.id, company_id=company_id)
                        if test_result and test_result.is_passed:
                            test_icon = "✅"  # Тест пройден
                        elif stage_progress.is_opened:
                            test_icon = "🟡"  # Этап открыт, тест доступен
                        else:
                            test_icon = "⛔️"  # Этап закрыт
                        # Добавляем процент для пройденных тестов
                        percentage_text = ""
                        if test_result and test_result.is_passed:
                            percentage = (test_result.score / test_result.max_possible_score) * 100
                            percentage_text = f" - {percentage:.0f}%"
                        progress_info += f"{test_icon}<b>Тест {test_num}:</b> {test_item.name}{percentage_text}\n"

                # Добавляем пустую строку после этапа
                progress_info += "\n"

            # Добавляем аттестацию с правильным статусом
            attestation = trainee_path.learning_path.attestation
            if attestation:
                attestation_status = await get_trainee_attestation_status(
                    session, user.id, attestation.id, company_id=company_id
                )
                progress_info += f"🏁<b>Аттестация:</b> {attestation.name} {attestation_status}\n\n"
            else:
                progress_info += "🏁<b>Аттестация:</b> Не указана ⛔️\n\n"

            # Уведомление о завершении этапа отправляется через check_and_notify_stage_completion
            # Здесь только показываем прогресс без дублированного уведомления

            # Добавляем кнопки для навигации согласно ТЗ
            # Получаем текущую сессию и ее тесты
            current_session = None
            for stage_progress in stages_progress:
                # Получаем ВСЕ сессии для этого этапа (не только открытые)
                from database.db import get_all_stage_sessions_progress

                stage_sessions_progress = await get_all_stage_sessions_progress(session, stage_progress.id)
                for session_progress in stage_sessions_progress:
                    if session_progress.session and hasattr(session_progress.session, "tests"):
                        for test_item in session_progress.session.tests:
                            if test_item.id == test_id:
                                current_session = session_progress.session
                                break
                    if current_session:
                        break
                if current_session:
                    break

            if current_session:
                # Добавляем кнопки для всех тестов в сессии
                for i, test_item in enumerate(current_session.tests, 1):
                    test_keyboard.append(
                        [
                            InlineKeyboardButton(
                                text=test_item.name, callback_data=f"take_test:{current_session.id}:{test_item.id}"
                            )
                        ]
                    )

            # Добавляем кнопки траектории и главного меню
            test_keyboard.extend(
                [
                    [InlineKeyboardButton(text="🗺️ Траектория", callback_data="trajectory")],
                    [InlineKeyboardButton(text="≡ Главное меню", callback_data="main_menu")],
                ]
            )

    # Формируем текст результата согласно макету 4.9-4.11
    result_text = (
        f"{status_text}\n"
        f"Твой результат: <b>{score:.1f}</b> из <b>{test.max_score:.1f}</b> баллов. Проходной балл: {test.threshold_score:.1f}"
    )

    try:
        await message.edit_text(
            f"{result_text}{progress_info}{stage_completion_message}",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=test_keyboard),
        )
    except Exception:
        # Если не можем отредактировать сообщение (например, это текстовый ответ пользователя),
        # отправляем новое сообщение
        await message.answer(
            f"{result_text}{progress_info}{stage_completion_message}",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=test_keyboard),
        )
    await state.clear()


@router.callback_query(F.data.startswith("view_materials:"))
async def process_view_materials(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Обработчик просмотра материалов к тесту"""
    user = await get_user_by_tg_id(session, callback.from_user.id)
    if not user:
        await callback.message.edit_text("❌ Ты не зарегистрирован в системе.")
        return

    # Получаем company_id с fallback на ensure_company_id для безопасности
    company_id = user.company_id
    if company_id is None:
        company_id = await ensure_company_id(session, state, callback.from_user.id)
    if company_id is None:
        await callback.message.edit_text("❌ Не удалось определить компанию. Обратись к администратору.")
        await callback.answer()
        return

    test_id = int(callback.data.split(":")[1])

    test = await get_test_by_id(session, test_id, company_id=company_id)
    if not test or not test.material_link:
        await callback.message.edit_text(
            "📚 <b>Материалы для изучения</b>\n\nК этому тесту не прикреплены материалы для изучения.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="⬅️ Назад к тесту", callback_data=f"take_test:{test_id}")],
                    [InlineKeyboardButton(text="📋 К списку тестов", callback_data="back_to_test_list")],
                ]
            ),
        )
        await callback.answer()
        return

    if test.material_file_path:
        # Если есть прикрепленный файл - отправляем его
        try:
            # Определяем тип и используем правильный метод
            if test.material_type == "photo":
                sent_media = await callback.bot.send_photo(
                    chat_id=callback.message.chat.id, photo=test.material_file_path
                )
            elif test.material_type == "video":
                sent_media = await callback.bot.send_video(
                    chat_id=callback.message.chat.id, video=test.material_file_path
                )
            else:
                sent_media = await callback.bot.send_document(
                    chat_id=callback.message.chat.id, document=test.material_file_path
                )

            # Сохраняем message_id медиа-файла для последующего удаления
            await state.update_data(material_message_id=sent_media.message_id)

            sent_text = await callback.message.answer(
                "📎 Материал отправлен выше.",
                reply_markup=InlineKeyboardMarkup(
                    inline_keyboard=[
                        [InlineKeyboardButton(text="⬅️ Назад к тесту", callback_data=f"take_test:{test_id}")],
                        [InlineKeyboardButton(text="📋 К списку тестов", callback_data="back_to_test_list")],
                    ]
                ),
            )
            # Сохраняем message_id текстового сообщения
            await state.update_data(material_text_message_id=sent_text.message_id)
        except Exception:
            await callback.message.edit_text(
                f"❌ <b>Ошибка загрузки файла</b>\n\n"
                f"Не удалось загрузить прикрепленный файл.\n"
                f"Обратись к наставнику.\n\n"
                f"📌 <b>Тест:</b> {test.name}",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(
                    inline_keyboard=[
                        [InlineKeyboardButton(text="⬅️ Назад к тесту", callback_data=f"take_test:{test_id}")],
                        [InlineKeyboardButton(text="📋 К списку тестов", callback_data="back_to_test_list")],
                    ]
                ),
            )
    else:
        # Если это ссылка
        await callback.message.edit_text(
            f"📚 <b>Материалы для изучения</b>\n\n"
            f"📌 <b>Тест:</b> {test.name}\n\n"
            f"🔗 <b>Ссылка на материалы:</b>\n{test.material_link}\n\n"
            f"💡 <b>Рекомендация:</b> Внимательно изучите материалы перед прохождением теста!",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="⬅️ Назад к тесту", callback_data=f"take_test:{test_id}")],
                    [InlineKeyboardButton(text="📋 К списку тестов", callback_data="back_to_test_list")],
                ]
            ),
        )

    await callback.answer()

    log_user_action(callback.from_user.id, callback.from_user.username, "viewed test materials", {"test_id": test_id})


@router.callback_query(F.data == "back_to_test_list")
async def process_back_to_test_list(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Умный возврат к списку тестов (определяет откуда пришёл тест)"""
    user = await get_user_by_tg_id(session, callback.from_user.id)
    if not user:
        await callback.message.edit_text("❌ Ты не зарегистрирован в системе.")
        await callback.answer()
        return

    # Получаем company_id с fallback на ensure_company_id для безопасности
    company_id = user.company_id
    if company_id is None:
        company_id = await ensure_company_id(session, state, callback.from_user.id)
    if company_id is None:
        await callback.message.edit_text("❌ Не удалось определить компанию. Обратись к администратору.")
        await callback.answer()
        return

    # Получаем данные состояния, чтобы узнать test_id
    state_data = await state.get_data()
    test_id = state_data.get("test_id")

    # Определяем, из какого списка был тест
    is_from_trajectory = False
    if test_id:
        is_from_trajectory = await is_test_from_trajectory(session, user.id, test_id, company_id=company_id)

    if is_from_trajectory:
        # ТЕСТЫ ТРАЕКТОРИИ
        available_tests = await get_trainee_available_tests(session, user.id, company_id=company_id)

        if not available_tests:
            await callback.message.edit_text(
                "Твой наставник пока не назначил тебе тесты 🥹\n\n"
                "Как только он это сделает, ты сможешь приступить к ним. "
                "Если хочешь ускорить процесс — свяжись с наставником напрямую",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(
                    inline_keyboard=[[InlineKeyboardButton(text="≡ Главное меню", callback_data="main_menu")]]
                ),
            )
            await callback.answer()
            return

        # Пагинация: показываем по 5 тестов на страницу
        page = 0
        per_page = 5
        start_index = page * per_page
        end_index = start_index + per_page
        page_tests = available_tests[start_index:end_index]

        tests_list = []
        for i, test in enumerate(page_tests, 1):
            # Получаем результат последнего прохождения
            company_id = user.company_id
            test_result = await get_user_test_result(session, user.id, test.id, company_id=company_id)

            # Номер с учетом глобального индекса
            global_index = start_index + i
            test_line = f"#<b>{global_index}</b> <b>{test.name}</b>\n"
            test_line += f"🎯 Порог прохождения: {test.threshold_score:.1f}/{test.max_score:.1f}\n"

            # Если тест был пройден, но не получен балл порога - показываем последнюю попытку
            if test_result and not test_result.is_passed:
                test_line += f"❌ Последняя попытка: {test_result.score:.1f}/{test_result.max_possible_score:.1f}\n"

            test_line += f"{test.description or 'Описание не указано'}"
            tests_list.append(test_line)

        tests_display = "\n━━━━━━━━━━━━\n\n".join(tests_list)

        # Информация о странице
        total_pages = (len(available_tests) + per_page - 1) // per_page
        page_info = f"\n\n📄 Страница {page + 1}/{total_pages}" if total_pages > 1 else ""

        await callback.message.edit_text(
            f"🗺️ <b>Тесты траектории</b>\n\n"
            f"Сейчас у тебя есть доступ к <b>{len(available_tests)}</b> тестам{page_info}\n"
            f"━━━━━━━━━━━━\n\n"
            f"{tests_display}\n\n"
            "Выбери тест для прохождения:",
            parse_mode="HTML",
            reply_markup=get_test_selection_for_taking_keyboard(
                available_tests, page, per_page, "trajectory_tests_page"
            ),
        )

        # Сохраняем список тестов в state для пагинации
        await state.update_data(trajectory_tests=available_tests, trajectory_page=page)

        # КРИТИЧЕСКИ ВАЖНО: Устанавливаем контекст "taking" для возврата к траектории
        await state.update_data(test_context="taking")
    else:
        # МОИ ТЕСТЫ (индивидуальные) - для стажеров, сотрудников и наставников
        available_tests = await get_user_broadcast_tests(
            session, user.id, exclude_completed=False, company_id=company_id
        )

        if not available_tests:
            no_tests_message = "❌ Пока новых тестов нет\nКогда появятся, тебе придёт уведомление"
            await callback.message.edit_text(
                no_tests_message,
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(
                    inline_keyboard=[[InlineKeyboardButton(text="≡ Главное меню", callback_data="main_menu")]]
                ),
            )
            await callback.answer()
            return

        # Используем универсальную функцию для форматирования с пагинацией
        page = 0
        message_text, keyboard = await format_my_tests_display(session, user, available_tests, page=page)

        # Сохраняем список тестов в state для пагинации
        await state.update_data(available_tests=available_tests, current_page=page)

        # Согласно макету 4.1: отправляем баннер SOVA для "Мои тесты", если настроен
        from aiogram.types import FSInputFile

        from config import MY_TESTS_IMAGE_FILE_ID, MY_TESTS_IMAGE_PATH, MY_TESTS_IMAGE_URL

        photo_source = None
        if MY_TESTS_IMAGE_FILE_ID:
            photo_source = MY_TESTS_IMAGE_FILE_ID
        elif MY_TESTS_IMAGE_URL:
            photo_source = MY_TESTS_IMAGE_URL
        elif MY_TESTS_IMAGE_PATH:
            try:
                photo_source = FSInputFile(MY_TESTS_IMAGE_PATH)
            except Exception as file_error:
                logger.warning(f"Не удалось загрузить изображение для 'Мои тесты': {file_error}")

        # Показываем индикатор загрузки для быстрого отклика
        await callback.answer()

        if photo_source:
            try:
                # Сначала отправляем новое сообщение с баннером, затем удаляем старое
                sent_message = await callback.bot.send_photo(
                    chat_id=callback.message.chat.id,
                    photo=photo_source,
                    caption=message_text,
                    parse_mode="HTML",
                    reply_markup=keyboard,
                )
                # Удаляем старое сообщение после отправки нового
                try:
                    await callback.message.delete()
                except Exception:
                    pass
            except Exception as photo_error:
                logger.warning(f"Не удалось отправить изображение для 'Мои тесты': {photo_error}")
                # Fallback: отправляем только текст
                if callback.message.photo:
                    # Если исходное сообщение - фото, удаляем и отправляем новое
                    try:
                        await callback.message.delete()
                    except Exception:
                        pass
                    await callback.message.answer(message_text, parse_mode="HTML", reply_markup=keyboard)
                else:
                    # Если текстовое, редактируем
                    try:
                        await callback.message.edit_text(message_text, parse_mode="HTML", reply_markup=keyboard)
                    except Exception:
                        # Если не удалось отредактировать, отправляем новое сообщение
                        await callback.message.answer(message_text, parse_mode="HTML", reply_markup=keyboard)
        else:
            # Если баннер не настроен, используем обычный текст
            if callback.message.photo:
                # Если исходное сообщение - фото, удаляем и отправляем новое текстовое
                try:
                    await callback.message.delete()
                except Exception:
                    pass
                await callback.message.answer(message_text, parse_mode="HTML", reply_markup=keyboard)
            else:
                # Если текстовое сообщение, редактируем текст
                try:
                    await callback.message.edit_text(message_text, parse_mode="HTML", reply_markup=keyboard)
                except Exception:
                    # Если не удалось отредактировать, отправляем новое сообщение
                    await callback.message.answer(message_text, parse_mode="HTML", reply_markup=keyboard)

        # КРИТИЧЕСКИ ВАЖНО: Устанавливаем контекст "taking" для возврата
        await state.update_data(test_context="taking")

    await state.set_state(TestTakingStates.waiting_for_test_selection)


@router.callback_query(F.data.startswith("cancel_test:"))
async def process_cancel_test(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Обработчик отмены/прерывания теста"""
    user = await get_user_by_tg_id(session, callback.from_user.id)
    if not user:
        await callback.message.edit_text("❌ Ты не зарегистрирован в системе.")
        return

    # Получаем company_id с fallback на ensure_company_id для безопасности
    company_id = user.company_id
    if company_id is None:
        company_id = await ensure_company_id(session, state, callback.from_user.id)
    if company_id is None:
        await callback.message.edit_text("❌ Не удалось определить компанию. Обратись к администратору.")
        await callback.answer()
        return

    test_id = int(callback.data.split(":")[1])

    test = await get_test_by_id(session, test_id, company_id=company_id)
    test_name = test.name if test else "Неизвестный тест"

    await callback.message.edit_text(
        f"❌ <b>Тест прерван</b>\n\n"
        f"Прохождение теста <b>«{test_name}»</b> было прервано.\n"
        "Ты можешь вернуться к прохождению в любое время.",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Попробовать снова", callback_data=f"take_test:{test_id}")],
                [InlineKeyboardButton(text="📋 К списку тестов", callback_data="back_to_test_list")],
            ]
        ),
    )

    await state.clear()
    await callback.answer()

    log_user_action(callback.from_user.id, callback.from_user.username, "cancelled test", {"test_id": test_id})


@router.callback_query(F.data == "cancel")
async def process_general_cancel(callback: CallbackQuery, state: FSMContext):
    """Обработчик общей отмены в контексте прохождения тестов"""
    await callback.message.edit_text(
        "❌ <b>Операция отменена</b>\n\nИспользуй команды бота или кнопки клавиатуры для навигации.", parse_mode="HTML"
    )
    await state.clear()
    await callback.answer()


@router.callback_query(TestTakingStates.waiting_for_test_start, F.data.startswith("take_test:"))
async def process_back_to_test_details(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Обработчик возврата к деталям теста"""
    await process_test_selection_for_taking(callback, state, session)


@router.callback_query(TestTakingStates.waiting_for_test_start, F.data.startswith("start_test:"))
async def process_start_test_button(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Обработчик кнопки 'Начать тест' для всех ролей"""
    test_id = int(callback.data.split(":")[1])
    await process_start_test(callback, state, session, test_id)


@router.callback_query(F.data.startswith("take_test:"))
async def process_take_test_from_notification(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Обработчик кнопки 'Перейти к тесту' из уведомления"""
    parts = callback.data.split(":")

    # Удаляем медиа-файл с материалами, если он был отправлен
    data = await state.get_data()
    if "material_message_id" in data:
        try:
            await callback.bot.delete_message(chat_id=callback.message.chat.id, message_id=data["material_message_id"])
        except Exception:
            pass  # Сообщение уже удалено или недоступно

    # Очищаем сохраненные message_id
    await state.update_data(material_message_id=None, material_text_message_id=None)

    # Поддерживаем два формата:
    # take_test:{test_id} - из уведомлений
    # take_test:{session_id}:{test_id} - из траектории
    if len(parts) == 2:
        test_id = int(parts[1])
    elif len(parts) == 3:
        test_id = int(parts[2])
    else:
        await callback.answer("Неверный формат данных", show_alert=True)
        return

    # Получаем пользователя ПЕРЕД использованием user.company_id
    user = await get_user_by_tg_id(session, callback.from_user.id)
    if not user:
        await callback.message.edit_text("❌ Пользователь не найден.")
        await callback.answer()
        return

    # Получаем company_id с fallback на ensure_company_id для безопасности
    company_id = user.company_id
    if company_id is None:
        company_id = await ensure_company_id(session, state, callback.from_user.id)
    if company_id is None:
        error_text = "❌ Не удалось определить компанию. Обратись к администратору."
        if callback.message.photo:
            try:
                await callback.message.edit_caption(caption=error_text)
            except Exception:
                await callback.message.answer(error_text)
        else:
            try:
                await callback.message.edit_text(error_text)
            except Exception:
                await callback.message.answer(error_text)
        await callback.answer()
        return

    test = await get_test_by_id(session, test_id, company_id=company_id)
    if not test:
        error_text = "❌ Тест не найден."
        if callback.message.photo:
            try:
                await callback.message.edit_caption(caption=error_text)
            except Exception:
                await callback.message.answer(error_text)
        else:
            try:
                await callback.message.edit_text(error_text)
            except Exception:
                await callback.message.answer(error_text)
        await callback.answer()
        return

    # Проверяем доступ к тесту
    has_access = await check_test_access(session, user.id, test_id, company_id=company_id)

    if not has_access:
        error_text = "❌ <b>Доступ запрещен</b>\n\nУ тебя нет доступа к этому тесту. Обратись к наставнику."
        if callback.message.photo:
            try:
                await callback.message.edit_caption(caption=error_text, parse_mode="HTML")
            except Exception:
                await callback.message.answer(error_text, parse_mode="HTML")
        else:
            try:
                await callback.message.edit_text(error_text, parse_mode="HTML")
            except Exception:
                await callback.message.answer(error_text, parse_mode="HTML")
        await callback.answer()
        return

    # Проверяем количество попыток
    attempts_count = await get_user_test_attempts_count(session, user.id, test_id, company_id=company_id)

    # Проверяем, есть ли уже результат
    existing_result = await get_user_test_result(session, user.id, test_id, company_id=company_id)

    # Формируем текст карточки теста согласно макету 4.5
    # Название теста - всегда
    test_info = f"<b>{test.name}</b>"

    # Описание - только если есть (макет 4.5: вариант 2 - без описания)
    if test.description and test.description.strip():
        test_info += f"\n\n{test.description}"

    # Совет - только если есть материал (макет 4.5: вариант 4 - без материала)
    has_material = bool(test.material_link or test.material_file_path)
    if has_material:
        test_info += "\n\n💡 <b>Совет:</b>\nЕсли есть сомнения по теме, сначала прочти прикреплённые обучающие материалы, а потом переходи к тесту"

    # Согласно макету 4.5: отправляем фото с текстом в одном сообщении, если есть
    has_photo = test.material_file_path and test.material_type == "photo"

    # Показываем индикатор загрузки для быстрого отклика
    await callback.answer()

    if has_photo:
        try:
            # Сначала отправляем новое сообщение с фото теста, затем удаляем старое
            sent_message = await callback.bot.send_photo(
                chat_id=callback.message.chat.id,
                photo=test.material_file_path,
                caption=test_info,
                parse_mode="HTML",
                reply_markup=get_test_start_keyboard(test_id, bool(existing_result), has_material),
            )
            # Удаляем старое сообщение после отправки нового (не ждем завершения)
            try:
                await callback.message.delete()
            except Exception:
                pass
        except Exception as photo_error:
            logger.warning(f"Не удалось отправить фото к тесту {test_id}: {photo_error}")
            # Fallback: отправляем только текст
            try:
                if callback.message.photo:
                    # Если исходное сообщение - фото, удаляем и отправляем новое
                    try:
                        await callback.message.delete()
                    except Exception:
                        pass
                    await callback.message.answer(
                        test_info,
                        parse_mode="HTML",
                        reply_markup=get_test_start_keyboard(test_id, bool(existing_result), has_material),
                    )
                else:
                    # Если текстовое, редактируем
                    await callback.message.edit_text(
                        test_info,
                        parse_mode="HTML",
                        reply_markup=get_test_start_keyboard(test_id, bool(existing_result), has_material),
                    )
            except Exception:
                # Если не удалось отредактировать, отправляем новое сообщение
                await callback.message.answer(
                    test_info,
                    parse_mode="HTML",
                    reply_markup=get_test_start_keyboard(test_id, bool(existing_result), has_material),
                )
    else:
        # Если фото теста нет, проверяем тип исходного сообщения
        if callback.message.photo:
            # Если исходное сообщение - фото (баннер "Мои тесты"), удаляем и отправляем новое текстовое
            # Сначала отправляем новое, затем удаляем старое для быстрого отклика
            sent_message = await callback.message.answer(
                test_info,
                parse_mode="HTML",
                reply_markup=get_test_start_keyboard(test_id, bool(existing_result), has_material),
            )
            # Удаляем старое сообщение после отправки нового
            try:
                await callback.message.delete()
            except Exception:
                pass
        else:
            # Если текстовое сообщение, редактируем текст (быстро, без удаления)
            try:
                await callback.message.edit_text(
                    test_info,
                    parse_mode="HTML",
                    reply_markup=get_test_start_keyboard(test_id, bool(existing_result), has_material),
                )
            except Exception:
                # Если не удалось отредактировать, отправляем новое сообщение
                await callback.message.answer(
                    test_info,
                    parse_mode="HTML",
                    reply_markup=get_test_start_keyboard(test_id, bool(existing_result), has_material),
                )

    await state.update_data(selected_test_id=test_id)
    await state.set_state(TestTakingStates.waiting_for_test_start)

    log_user_action(
        callback.from_user.id, callback.from_user.username, "took test from notification", {"test_id": test_id}
    )


@router.callback_query(F.data == "trajectory_tests_shortcut")
async def process_trajectory_tests_shortcut(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Обработчик быстрого перехода к тестам траектории из уведомления"""
    user = await get_user_by_tg_id(session, callback.from_user.id)
    if not user:
        await callback.message.edit_text("❌ Пользователь не найден.")
        await callback.answer()
        return

    # Проверяем права
    has_permission = await check_user_permission(session, user.id, "take_tests")
    if not has_permission:
        await callback.message.edit_text("❌ У тебя нет прав для прохождения тестов.")
        await callback.answer()
        return

    # Получаем company_id для изоляции
    company_id = await ensure_company_id(session, state, callback.from_user.id)
    if company_id is None and user.company_id:
        company_id = user.company_id
    if company_id is None:
        await callback.message.edit_text("❌ Не удалось определить компанию. Обнови сессию командой /start.")
        await callback.answer()
        await state.clear()
        log_user_error(callback.from_user.id, "trajectory_tests_company_missing", "company_id not resolved")
        return

    available_tests = await get_trainee_available_tests(session, user.id, company_id=company_id)

    if not available_tests:
        await callback.message.edit_text(
            "Твой наставник пока не назначил тебе тесты 🥹\n\n"
            "Как только он это сделает, ты сможешь приступить к ним. "
            "Если хочешь ускорить процесс — свяжись с наставником напрямую",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[[InlineKeyboardButton(text="≡ Главное меню", callback_data="main_menu")]]
            ),
        )
        await callback.answer()
        return

    # Пагинация: показываем по 5 тестов на страницу
    page = 0
    per_page = 5
    start_index = page * per_page
    end_index = start_index + per_page
    page_tests = available_tests[start_index:end_index]

    tests_list = []
    for i, test in enumerate(page_tests, 1):
        # Получаем результат последнего прохождения
        company_id = user.company_id
        test_result = await get_user_test_result(session, user.id, test.id, company_id=company_id)

        # Номер с учетом глобального индекса
        global_index = start_index + i
        test_line = f"#<b>{global_index}</b> <b>{test.name}</b>\n"
        test_line += f"🎯 Порог прохождения: {test.threshold_score:.1f}/{test.max_score:.1f}\n"

        # Если тест был пройден, но не получен балл порога - показываем последнюю попытку
        if test_result and not test_result.is_passed:
            test_line += f"❌ Последняя попытка: {test_result.score:.1f}/{test_result.max_possible_score:.1f}\n"

        test_line += f"\n{test.description or 'Описание не указано'}"
        tests_list.append(test_line)

    tests_display = "\n━━━━━━━━━━━━\n\n".join(tests_list)

    # Информация о странице
    total_pages = (len(available_tests) + per_page - 1) // per_page
    page_info = f"\n\n📄 Страница {page + 1}/{total_pages}" if total_pages > 1 else ""

    await callback.message.edit_text(
        f"🗺️ <b>Тесты траектории</b>\n\n"
        f"Сейчас у тебя есть доступ к <b>{len(available_tests)}</b> тестам{page_info}\n"
        f"━━━━━━━━━━━━\n\n"
        f"{tests_display}\n\n"
        "Выбери тест для прохождения:",
        parse_mode="HTML",
        reply_markup=get_test_selection_for_taking_keyboard(available_tests, page, per_page, "trajectory_tests_page"),
    )

    # Сохраняем список тестов в state для пагинации
    await state.update_data(trajectory_tests=available_tests, trajectory_page=page)

    # КРИТИЧЕСКИ ВАЖНО: Устанавливаем контекст "taking" для стажера
    await state.update_data(test_context="taking")
    await state.set_state(TestTakingStates.waiting_for_test_selection)
    await callback.answer()

    log_user_action(callback.from_user.id, callback.from_user.username, "opened trajectory tests from notification")


@router.callback_query(F.data == "my_broadcast_tests_shortcut")
async def process_my_broadcast_tests_shortcut(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Обработчик быстрого перехода к индивидуальным тестам из уведомления"""
    user = await get_user_by_tg_id(session, callback.from_user.id)
    if not user:
        await callback.message.edit_text("❌ Пользователь не найден.")
        await callback.answer()
        return

    # Получаем company_id с fallback на ensure_company_id для безопасности
    company_id = user.company_id
    if company_id is None:
        company_id = await ensure_company_id(session, state, callback.from_user.id)
    if company_id is None:
        await callback.message.edit_text("❌ Не удалось определить компанию. Обратись к администратору.")
        await callback.answer()
        return

    # Получаем тесты от рекрутера через рассылку + индивидуальные от наставника (исключая тесты траектории)
    available_tests = await get_user_broadcast_tests(session, user.id, exclude_completed=False, company_id=company_id)

    if not available_tests:
        await callback.message.edit_text(
            "❌ Пока новых тестов нет\nКогда появятся, тебе придёт уведомление",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[[InlineKeyboardButton(text="≡ Главное меню", callback_data="main_menu")]]
            ),
        )
        await callback.answer()
        return

    # Используем универсальную функцию для форматирования с пагинацией
    page = 0
    message_text, keyboard = await format_my_tests_display(session, user, available_tests, page=page)

    # Сохраняем список тестов в state для пагинации
    await state.update_data(available_tests=available_tests, current_page=page)

    # Согласно макету 4.1: отправляем баннер SOVA для "Мои тесты", если настроен
    from aiogram.types import FSInputFile

    from config import MY_TESTS_IMAGE_FILE_ID, MY_TESTS_IMAGE_PATH, MY_TESTS_IMAGE_URL

    photo_source = None
    if MY_TESTS_IMAGE_FILE_ID:
        photo_source = MY_TESTS_IMAGE_FILE_ID
    elif MY_TESTS_IMAGE_URL:
        photo_source = MY_TESTS_IMAGE_URL
    elif MY_TESTS_IMAGE_PATH:
        try:
            photo_source = FSInputFile(MY_TESTS_IMAGE_PATH)
        except Exception as file_error:
            logger.warning(f"Не удалось загрузить изображение для 'Мои тесты': {file_error}")

    # Показываем индикатор загрузки для быстрого отклика
    await callback.answer()

    if photo_source:
        try:
            # Caption содержит только текст списка (без "Мои ТЕСТЫ" - оно на баннере)
            # Сначала отправляем новое сообщение с баннером, затем удаляем старое
            sent_message = await callback.bot.send_photo(
                chat_id=callback.message.chat.id,
                photo=photo_source,
                caption=message_text,
                parse_mode="HTML",
                reply_markup=keyboard,
            )
            # Удаляем старое сообщение после отправки нового
            try:
                await callback.message.delete()
            except Exception:
                pass
        except Exception as photo_error:
            logger.warning(f"Не удалось отправить изображение для 'Мои тесты': {photo_error}")
            # Fallback: отправляем только текст
            if callback.message.photo:
                # Если исходное сообщение - фото, удаляем и отправляем новое
                try:
                    await callback.message.delete()
                except Exception:
                    pass
                await callback.message.answer(message_text, parse_mode="HTML", reply_markup=keyboard)
            else:
                # Если текстовое, редактируем
                try:
                    await callback.message.edit_text(message_text, parse_mode="HTML", reply_markup=keyboard)
                except Exception:
                    # Если не удалось отредактировать, отправляем новое сообщение
                    await callback.message.answer(message_text, parse_mode="HTML", reply_markup=keyboard)
    else:
        # Если баннер не настроен, используем обычный текст
        if callback.message.photo:
            # Если исходное сообщение - фото, удаляем и отправляем новое текстовое
            try:
                await callback.message.delete()
            except Exception:
                pass
            await callback.message.answer(message_text, parse_mode="HTML", reply_markup=keyboard)
        else:
            # Если текстовое сообщение, редактируем текст
            try:
                await callback.message.edit_text(message_text, parse_mode="HTML", reply_markup=keyboard)
            except Exception:
                # Если не удалось отредактировать, отправляем новое сообщение
                await callback.message.answer(message_text, parse_mode="HTML", reply_markup=keyboard)

    # КРИТИЧЕСКИ ВАЖНО: Устанавливаем контекст и состояние
    await state.update_data(test_context="taking")
    await state.set_state(TestTakingStates.waiting_for_test_selection)

    log_user_action(callback.from_user.id, callback.from_user.username, "opened broadcast tests from notification")


# ===== ФУНКЦИИ ДЛЯ ПРОХОЖДЕНИЯ ТРАЕКТОРИЙ =====


async def is_test_from_trajectory(session: AsyncSession, user_id: int, test_id: int, company_id: int = None) -> bool:
    """
    Проверяет, является ли тест частью траектории или это тест вне траектории (с изоляцией по компании)

    Args:
        session: Сессия БД
        user_id: ID пользователя
        test_id: ID теста
        company_id: ID компании для изоляции

    Returns:
        True - тест из траектории (открыт через этапы)
        False - тест вне траектории (рассылка от рекрутера ИЛИ индивидуальный от наставника)
    """
    try:
        from database.models import Role, TraineeTestAccess, user_roles

        # Получаем company_id пользователя для изоляции, если не передан
        if company_id is None:
            user = await get_user_by_id(session, user_id)
            if user:
                company_id = user.company_id

        # КРИТИЧЕСКАЯ ПРОВЕРКА: Если company_id все еще None, логируем и возвращаем False для безопасности
        if company_id is None:
            logger.warning(
                f"Не удалось определить company_id для пользователя {user_id} в is_test_from_trajectory. Возвращаем False для безопасности."
            )
            return False

        # Получаем роль рекрутера
        recruiter_role_result = await session.execute(select(Role).where(Role.name == "Рекрутер"))
        recruiter_role = recruiter_role_result.scalar_one_or_none()
        if not recruiter_role:
            logger.error("Роль 'Рекрутер' не найдена")
            return False

        # Получаем запись доступа к тесту
        access_query = (
            select(TraineeTestAccess)
            .outerjoin(user_roles, TraineeTestAccess.granted_by_id == user_roles.c.user_id)
            .where(
                TraineeTestAccess.trainee_id == user_id,
                TraineeTestAccess.test_id == test_id,
                TraineeTestAccess.is_active == True,
            )
        )

        # Изоляция по компании - КРИТИЧЕСКИ ВАЖНО!
        if company_id is not None:
            access_query = access_query.where(TraineeTestAccess.company_id == company_id)

        access_result = await session.execute(access_query)
        access = access_result.scalar_one_or_none()

        if not access:
            logger.warning(f"Доступ к тесту {test_id} для пользователя {user_id} не найден")
            return False

        # НОВАЯ ЛОГИКА: Проверяем, входит ли тест в траекторию (через этапы/сессии)
        from database.models import (
            LearningPath,
            LearningSession,
            TraineeLearningPath,
            TraineeSessionProgress,
            TraineeStageProgress,
            User,
            session_tests,
        )

        # Получаем траекторию стажера
        trainee_path_query = (
            select(TraineeLearningPath)
            .join(User, TraineeLearningPath.trainee_id == User.id)
            .join(LearningPath, TraineeLearningPath.learning_path_id == LearningPath.id)
            .where(TraineeLearningPath.trainee_id == user_id, TraineeLearningPath.is_active == True)
        )

        # Изоляция по компании - КРИТИЧЕСКИ ВАЖНО!
        if company_id is not None:
            trainee_path_query = trainee_path_query.where(
                User.company_id == company_id, LearningPath.company_id == company_id
            )

        trainee_path_result = await session.execute(trainee_path_query)
        trainee_path = trainee_path_result.scalar_one_or_none()

        if not trainee_path:
            return False

        # Проверяем, входит ли тест в сессии траектории (любого этапа)
        trajectory_test_result = await session.execute(
            select(session_tests.c.test_id)
            .join(LearningSession, LearningSession.id == session_tests.c.session_id)
            .join(TraineeSessionProgress, TraineeSessionProgress.session_id == LearningSession.id)
            .join(TraineeStageProgress, TraineeSessionProgress.stage_progress_id == TraineeStageProgress.id)
            .where(TraineeStageProgress.trainee_path_id == trainee_path.id, session_tests.c.test_id == test_id)
        )
        trajectory_test = trajectory_test_result.first()

        # Если тест найден в траектории - возвращаем True
        return trajectory_test is not None

    except Exception as e:
        logger.error(f"Ошибка проверки типа теста {test_id} для пользователя {user_id}: {e}")
        return False


async def check_and_notify_stage_completion(session: AsyncSession, user_id: int, test_id: int, bot=None) -> str:
    """
    Проверяет завершение этапа траектории и отправляет уведомление наставнику
    ТОЛЬКО для стажеров! Сотрудники не имеют траекторий.
    """
    try:
        # КРИТИЧЕСКАЯ ПРОВЕРКА: Функция должна работать только для стажеров
        user_roles = await get_user_roles(session, user_id)
        role_names = [role.name for role in user_roles]

        if "Стажер" not in role_names:
            # Это не стажер - пропускаем проверку траектории
            return ""

        from database.models import LearningPath, LearningSession, LearningStage, session_tests

        # Получаем company_id для изоляции
        user = await get_user_by_id(session, user_id)
        company_id = user.company_id if user else None

        # Получаем траекторию стажера
        trainee_path = await get_trainee_learning_path(session, user_id, company_id=company_id)
        if not trainee_path:
            logger.warning(f"Стажер {user_id} не имеет назначенной траектории")
            return ""  # Стажер не имеет назначенной траектории

        # Находим сессию, содержащую данный тест
        session_query = (
            select(LearningSession)
            .join(session_tests)
            .join(LearningStage, LearningSession.stage_id == LearningStage.id)
            .join(LearningPath, LearningStage.learning_path_id == LearningPath.id)
            .where(session_tests.c.test_id == test_id, LearningStage.learning_path_id == trainee_path.learning_path_id)
        )

        # Изоляция по компании - КРИТИЧЕСКИ ВАЖНО!
        if company_id is not None:
            session_query = session_query.where(LearningPath.company_id == company_id)

        session_result = await session.execute(session_query)
        test_session = session_result.scalar_one_or_none()

        if not test_session:
            logger.warning(f"Тест {test_id} не найден в траектории стажера {user_id}")
            return ""  # Тест не принадлежит траектории стажера

        # Получаем все тесты в этой сессии
        session_tests_result = await session.execute(
            select(session_tests.c.test_id).where(session_tests.c.session_id == test_session.id)
        )
        session_test_ids = [row[0] for row in session_tests_result.all()]

        # Проверяем, все ли тесты в сессии пройдены стажером
        completed_tests_count = 0
        # Получаем пользователя для company_id
        trainee_user = await get_user_by_id(session, user_id)
        company_id = trainee_user.company_id if trainee_user else None
        for session_test_id in session_test_ids:
            test_result = await get_user_test_result(session, user_id, session_test_id, company_id=company_id)
            if test_result and test_result.is_passed:
                completed_tests_count += 1

        # Если все тесты в сессии пройдены, отмечаем сессию как завершенную
        if completed_tests_count == len(session_test_ids):
            session_completed = await complete_session_for_trainee(
                session, user_id, test_session.id, company_id=company_id
            )
            if session_completed:
                logger.info(f"Сессия {test_session.id} отмечена как завершенная для стажера {user_id}")

                # Проверяем, все ли сессии в этапе завершены
                stage_progress = await get_trainee_stage_progress(session, trainee_path.id, company_id=company_id)
                current_stage_progress = next(
                    (sp for sp in stage_progress if sp.stage_id == test_session.stage_id), None
                )

                if current_stage_progress:
                    # Получаем все сессии этапа
                    stage_sessions_progress = await get_stage_session_progress(session, current_stage_progress.id)

                    # Проверяем, все ли сессии завершены (на основе прохождения тестов)
                    all_sessions_completed = True
                    for sp in stage_sessions_progress:
                        if hasattr(sp.session, "tests") and sp.session.tests:
                            session_tests_passed = True
                            for test_item in sp.session.tests:
                                test_result = await get_user_test_result(
                                    session, user_id, test_item.id, company_id=company_id
                                )
                                if not (test_result and test_result.is_passed):
                                    session_tests_passed = False
                                    break
                            if not session_tests_passed:
                                all_sessions_completed = False
                                break

                    if all_sessions_completed:
                        # Отмечаем этап как завершенный
                        # Получаем пользователя для company_id
                        trainee_user = await get_user_by_id(session, user_id)
                        company_id = trainee_user.company_id if trainee_user else None
                        stage_completed = await complete_stage_for_trainee(
                            session, user_id, current_stage_progress.stage_id, company_id=company_id
                        )
                        if stage_completed:
                            logger.info(
                                f"Этап {current_stage_progress.stage_id} отмечен как завершенный для стажера {user_id}"
                            )

                            # Отправляем уведомление наставнику
                            # Получаем company_id стажера для изоляции
                            trainee_user = await get_user_by_id(session, user_id)
                            company_id = trainee_user.company_id if trainee_user else None
                            await send_stage_completion_notification(
                                session, user_id, current_stage_progress.stage_id, bot, company_id
                            )

                            # Возвращаем информацию о завершении этапа
                            stage_name = (
                                current_stage_progress.stage.name
                                if hasattr(current_stage_progress, "stage")
                                else f"Этап {current_stage_progress.stage_id}"
                            )
                            return f"\n\n✅ <b>Ты завершил {stage_name}!</b>\nОбратись к своему наставнику, чтобы получить доступ к следующему этапу"

        return ""  # Этап не завершен

    except Exception as e:
        logger.error(f"Ошибка при проверке завершения этапа для стажера {user_id}: {e}")
        return ""


async def send_stage_completion_notification(
    session: AsyncSession, trainee_id: int, stage_id: int, bot=None, company_id: int = None
) -> None:
    """
    Отправляет уведомление наставнику о завершении этапа стажером (с изоляцией по компании)
    """
    try:
        from database.models import LearningStage, Mentorship

        # Получаем стажера
        trainee = await get_user_by_id(session, trainee_id)
        if not trainee:
            return

        # Изоляция по компании - проверяем принадлежность стажера
        if company_id is not None and trainee.company_id != company_id:
            logger.error(f"Стажер {trainee_id} не принадлежит компании {company_id}")
            return

        # Получаем company_id для изоляции, если не передан
        if company_id is None:
            company_id = trainee.company_id

        # Получаем этап
        stage_result = await session.execute(select(LearningStage).where(LearningStage.id == stage_id))
        stage = stage_result.scalar_one_or_none()
        if not stage:
            return

        # Получаем наставника стажера с проверкой изоляции по компании
        mentorship_query = select(Mentorship).where(Mentorship.trainee_id == trainee_id, Mentorship.is_active == True)

        # Изоляция по компании - КРИТИЧЕСКИ ВАЖНО!
        if company_id is not None:
            mentorship_query = mentorship_query.where(Mentorship.company_id == company_id)

        mentorship_result = await session.execute(mentorship_query)
        mentorship = mentorship_result.scalar_one_or_none()
        if not mentorship:
            return

        mentor = await get_user_by_id(session, mentorship.mentor_id)
        if not mentor:
            return

        # Изоляция по компании - проверяем принадлежность наставника
        if company_id is not None and mentor.company_id != company_id:
            logger.error(f"Наставник {mentor.id} не принадлежит компании {company_id}")
            return

        # Формируем уведомление согласно ТЗ
        notification_message = (
            f"🧑 <b>ФИО:</b> {trainee.full_name}\n"
            f"👑 <b>Роли:</b> {', '.join([role.name for role in trainee.roles]) if trainee.roles else 'Стажёр'}\n"
            f"🗂️<b>Группа:</b> {', '.join([group.name for group in trainee.groups]) if trainee.groups else 'Не указана'}\n"
            f"📍<b>1️⃣Объект стажировки:</b> {trainee.internship_object.name if trainee.internship_object else 'Не указан'}\n"
            f"📍<b>2️⃣Объект работы:</b> {trainee.work_object.name if trainee.work_object else 'Не указан'}\n\n"
            "✅<b>Твой стажёр успешно завершил этап траектории!</b>\n\n"
            "Откройте ему следующий этап"
        )

        # Клавиатура с быстрым доступом
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="👥 Мои стажёры", callback_data="my_trainees")],
                [InlineKeyboardButton(text="≡ Главное меню", callback_data="main_menu")],
            ]
        )

        # Отправляем уведомление наставнику
        if not bot:
            logger.warning("Bot instance not provided to send_stage_completion_notification")
            return
        try:
            await bot.send_message(mentor.tg_id, notification_message, parse_mode="HTML", reply_markup=keyboard)
            logger.info(
                f"Отправлено уведомление наставнику {mentor.full_name} о завершении этапа {stage.name} стажером {trainee.full_name}"
            )
        except Exception as e:
            logger.error(f"Не удалось отправить уведомление наставнику {mentor.tg_id}: {e}")

    except Exception as e:
        logger.error(f"Ошибка отправки уведомления о завершении этапа: {e}")


@router.callback_query(F.data == "trajectory")
async def callback_trajectory_from_test(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Обработчик кнопки 'Траектория' из результатов теста - перенаправляет к выбору этапа"""
    try:
        await callback.answer()

        # Получаем пользователя
        user = await get_user_by_tg_id(session, callback.from_user.id)
        if not user:
            await callback.message.edit_text("Пользователь не найден")
            return

        # Получаем company_id с fallback на ensure_company_id для безопасности
        company_id = user.company_id
        if company_id is None:
            company_id = await ensure_company_id(session, state, callback.from_user.id)
        if company_id is None:
            await callback.message.edit_text("❌ Не удалось определить компанию. Обратись к администратору.")
            await callback.answer()
            return

        # Получаем траекторию стажера
        trainee_path = await get_trainee_learning_path(session, user.id, company_id=company_id)

        if not trainee_path:
            await callback.message.edit_text(
                get_no_trajectory_text(), parse_mode="HTML", reply_markup=get_mentor_contact_keyboard()
            )
            return

        trajectory_text, stages_progress = await build_trajectory_text(session, user, trainee_path, company_id)

        available_stages = [sp for sp in stages_progress if sp.is_opened and not sp.is_completed]

        keyboard_buttons = []
        if available_stages:
            trajectory_text += "Выбери этап траектории 👇"
            for stage_progress in available_stages:
                keyboard_buttons.append(
                    [
                        InlineKeyboardButton(
                            text=f"Этап {stage_progress.stage.order_number}",
                            callback_data=f"select_stage:{stage_progress.stage.id}",
                        )
                    ]
                )
        else:
            trajectory_text += "❌ Нет открытых этапов для прохождения"

        keyboard_buttons.append([InlineKeyboardButton(text="☰ Главное меню", callback_data="main_menu")])

        await callback.message.edit_text(
            trajectory_text, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_buttons), parse_mode="HTML"
        )

    except Exception as e:
        await callback.message.edit_text("Произошла ошибка при открытии траектории")
        log_user_error(callback.from_user.id, "trajectory_from_test_error", str(e))
