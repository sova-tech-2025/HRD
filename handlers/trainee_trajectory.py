"""
Обработчики для прохождения траекторий стажерами.
Включает просмотр траектории, выбор этапов, сессий и прохождение тестов.
"""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from database.db import (
    get_trainee_learning_path, get_trainee_stage_progress,
    get_stage_session_progress, get_learning_path_stages,
    complete_stage_for_trainee, complete_session_for_trainee,
    get_user_test_result, get_user_by_tg_id, get_user_by_id, check_user_permission,
    get_trainee_attestation_status
)
from handlers.auth import check_auth
from keyboards.keyboards import get_main_menu_keyboard, get_mentor_contact_keyboard
from utils.logger import log_user_action, log_user_error
from utils.test_progress_formatters import get_test_status_icon, format_test_line

router = Router()


async def format_trajectory_info(user, trainee_path=None, header="ВЫБОР ЭТАПА") -> str:
    """Формирование информации о траектории для отображения"""
    if not trainee_path:
        return (
            "🗺️ <b>ТРАЕКТОРИЯ ОБУЧЕНИЯ</b> 🗺️\n\n"
            "❌ <b>Траектория не назначена</b>\n\n"
            "Обратись к своему наставнику для назначения траектории, пока курс не выбран"
        )
    
    # Форматирование username
    username_display = f"@{user.username}" if user.username else "Не указан"
    
    # Получаем роль и группу
    primary_role = user.roles[0].name if user.roles else "Не указана"
    group_name = user.groups[0].name if user.groups else "Не указана"
    
    # Объекты
    internship_obj = user.internship_object.name if user.internship_object else "Не указан"
    work_obj = user.work_object.name if user.work_object else "Не указан"
    
    return f"""🗺️ <b>ТРАЕКТОРИЯ ОБУЧЕНИЯ</b> 🗺️
<b>{header}</b>

🦸🏻‍♂️ <b>Пользователь:</b> {user.full_name}

<b>Телефон:</b> {user.phone_number}
<b>Username:</b> {username_display}
<b>Номер:</b> #{user.id}
<b>Дата регистрации:</b> {user.registration_date.strftime('%d.%m.%Y %H:%M')}

━━━━━━━━━━━━

🗂️ <b>Статус:</b>
<b>Группа:</b> {group_name}
<b>Роль:</b> {primary_role}

━━━━━━━━━━━━

📍 <b>Объект:</b>
<b>Стажировки:</b> {internship_obj}
<b>Работы:</b> {work_obj}

━━━━━━━━━━━━

<b>Название траектории:</b> {trainee_path.learning_path.name if trainee_path.learning_path else 'Не найдена'}

"""


@router.message(Command("trajectory"))
async def cmd_trajectory_slash(message: Message, state: FSMContext, session: AsyncSession):
    """Обработчик команды /trajectory для стажеров"""
    await cmd_trajectory(message, state, session)


@router.message(F.text.in_(["Траектория", "📖 Траектория обучения", "Траектория обучения 📖"]))
async def cmd_trajectory(message: Message, state: FSMContext, session: AsyncSession):
    """Обработчик команды 'Траектория' для стажеров"""
    try:
        # Проверка авторизации
        is_auth = await check_auth(message, state, session)
        if not is_auth:
            return

        # Получение пользователя
        from database.db import get_user_by_tg_id
        user = await get_user_by_tg_id(session, message.from_user.id)
        if not user:
            await message.answer("Ты не зарегистрирован в системе.")
            return

        # КРИТИЧЕСКАЯ ПРОВЕРКА: Траектории доступны ТОЛЬКО стажерам
        user_roles = [role.name for role in user.roles]
        if "Стажер" not in user_roles:
            await message.answer(
                "❌ <b>Доступ запрещен</b>\n\n"
                "Траектории обучения доступны только стажерам.\n"
                "После перехода в сотрудники ты получаешь доступ к тестам от рекрутера через рассылку.",
                parse_mode="HTML"
            )
            log_user_action(user.tg_id, "trajectory_access_denied", f"Пользователь с ролью {user_roles} попытался получить доступ к траектории")
            return

        # Получаем траекторию стажера
        company_id = user.company_id
        trainee_path = await get_trainee_learning_path(session, user.id, company_id=company_id)

        if not trainee_path:
            await message.answer(
                await format_trajectory_info(user, None),
                parse_mode="HTML",
                reply_markup=get_mentor_contact_keyboard()
            )
            log_user_action(user.tg_id, "trajectory_not_assigned", "Стажер попытался открыть траекторию, но она не назначена")
            return

        # Получаем этапы траектории
        stages_progress = await get_trainee_stage_progress(session, trainee_path.id, company_id=company_id)

        # Формируем информацию о траектории согласно ТЗ
        trajectory_info = await format_trajectory_info(user, trainee_path)

        # Формируем информацию об этапах согласно ТЗ
        stages_info = ""

        for stage_progress in stages_progress:
            stage = stage_progress.stage
            
            # Получаем информацию о сессиях для определения статуса этапа
            sessions_progress_for_stage = await get_stage_session_progress(session, stage_progress.id)
            
            # Определяем статус этапа: 🟢 если все сессии пройдены, 🟡 если открыт, ⏺️ если закрыт
            # ИСПРАВЛЕНИЕ: проверяем завершенность только если этап открыт
            all_sessions_completed = False
            if stage_progress.is_opened and sessions_progress_for_stage:
                all_sessions_completed = True
                for sp in sessions_progress_for_stage:
                    if hasattr(sp.session, 'tests') and sp.session.tests:
                        session_tests_passed = True
                        for test in sp.session.tests:
                            test_result = await get_user_test_result(session, user.id, test.id, company_id=user.company_id)
                            if not (test_result and test_result.is_passed):
                                session_tests_passed = False
                                break
                        if not session_tests_passed:
                            all_sessions_completed = False
                            break
            
            if all_sessions_completed and sessions_progress_for_stage:
                status_icon = "✅"  # Все сессии пройдены
            elif stage_progress.is_opened:
                status_icon = "🟡"  # Этап открыт
            else:
                status_icon = "⛔️"  # Этап закрыт

            stages_info += f"{status_icon}<b>Этап {stage.order_number}:</b> {stage.name}\n"

            # Используем уже полученные сессии
            for session_progress in sessions_progress_for_stage:
                # Определяем статус сессии: 🟢 если все тесты пройдены, 🟡 если этап открыт, ⏺️ если этап закрыт
                if hasattr(session_progress.session, 'tests') and session_progress.session.tests:
                    # ИСПРАВЛЕНИЕ: проверяем пройденность только если этап открыт
                    all_tests_passed = False
                    if stage_progress.is_opened:
                        all_tests_passed = True
                        for test in session_progress.session.tests:
                            test_result = await get_user_test_result(session, user.id, test.id, company_id=user.company_id)
                            if not (test_result and test_result.is_passed):
                                all_tests_passed = False
                                break
                    
                    if all_tests_passed and stage_progress.is_opened:
                        session_status_icon = "✅"  # Все тесты пройдены (только если этап открыт)
                    elif stage_progress.is_opened:
                        session_status_icon = "🟡"  # Этап открыт, сессия доступна
                    else:
                        session_status_icon = "⛔️"  # Этап закрыт
                else:
                    session_status_icon = "⛔️"  # Нет тестов
                stages_info += f"{session_status_icon}<b>Сессия {session_progress.session.order_number}:</b> {session_progress.session.name}\n"

                # Показываем тесты в сессии
                for test_num, test in enumerate(session_progress.session.tests, 1):
                    test_result = await get_user_test_result(session, user.id, test.id, company_id=user.company_id)
                    is_passed = bool(test_result and test_result.is_passed)
                    icon = get_test_status_icon(is_passed, stage_progress.is_opened)
                    stages_info += format_test_line(test_num, test.name, icon)
            
            # Добавляем пустую строку после этапа
            stages_info += "\n"

        # Добавляем информацию об аттестации
        stages_info += await format_attestation_status(session, user.id, trainee_path)

        available_stages = [sp for sp in stages_progress if sp.is_opened and not sp.is_completed]

        # Создаем клавиатуру с доступными этапами согласно ТЗ
        keyboard_buttons = []

        if available_stages:
            stages_info += "Выбери этап траектории👇"
            for stage_progress in available_stages:
                keyboard_buttons.append([
                    InlineKeyboardButton(
                        text=f"Этап {stage_progress.stage.order_number}",
                        callback_data=f"select_stage:{stage_progress.stage.id}"
                    )
                ])
        else:
            stages_info += "❌ Нет открытых этапов для прохождения"

        # Добавляем кнопку "Главное меню"
        keyboard_buttons.append([
            InlineKeyboardButton(
                text="≡ Главное меню",
                callback_data="main_menu"
            )
        ])

        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)

        await message.answer(
            trajectory_info + stages_info,
            reply_markup=keyboard,
            parse_mode="HTML"
        )

        log_user_action(user.tg_id, "trajectory_opened", f"Открыта траектория {trainee_path.learning_path.name}")

    except Exception as e:
        await message.answer("Произошла ошибка при открытии траектории")
        log_user_error(message.from_user.id, "trajectory_error", str(e))


@router.callback_query(F.data == "trajectory_command")
async def callback_trajectory_command(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Обработчик возврата к выбору этапов траектории"""
    try:
        await callback.answer()
        
        # Получение пользователя
        from database.db import get_user_by_tg_id
        user = await get_user_by_tg_id(session, callback.from_user.id)
        if not user:
            await callback.message.edit_text("Ты не зарегистрирован в системе.")
            return

        # Получаем траекторию стажера
        company_id = user.company_id
        trainee_path = await get_trainee_learning_path(session, user.id, company_id=company_id)

        if not trainee_path:
            await callback.message.edit_text(
                await format_trajectory_info(user, None),
                parse_mode="HTML",
                reply_markup=get_mentor_contact_keyboard()
            )
            log_user_action(user.tg_id, "trajectory_not_assigned", "Стажер попытался открыть траектории, но она не назначена")
            return

        # Получаем этапы траектории
        stages_progress = await get_trainee_stage_progress(session, trainee_path.id, company_id=company_id)

        # Формируем информацию о траектории согласно ТЗ
        trajectory_info = await format_trajectory_info(user, trainee_path)

        stages_info = ""

        for stage_progress in stages_progress:
            stage = stage_progress.stage
            
            # Получаем информацию о сессиях для определения статуса этапа
            sessions_progress = await get_stage_session_progress(session, stage_progress.id)
            
            # Определяем статус этапа: 🟢 если все сессии пройдены, 🟡 если открыт, ⏺️ если закрыт
            # ИСПРАВЛЕНИЕ: проверяем завершенность только если этап открыт
            all_sessions_completed = False
            if stage_progress.is_opened and sessions_progress:
                all_sessions_completed = True
                for sp in sessions_progress:
                    if hasattr(sp.session, 'tests') and sp.session.tests:
                        session_tests_passed = True
                        for test in sp.session.tests:
                            test_result = await get_user_test_result(session, user.id, test.id, company_id=user.company_id)
                            if not (test_result and test_result.is_passed):
                                session_tests_passed = False
                                break
                        if not session_tests_passed:
                            all_sessions_completed = False
                            break
            
            if all_sessions_completed and sessions_progress:
                stage_status_icon = "✅"  # Все сессии пройдены
            elif stage_progress.is_opened:
                stage_status_icon = "🟡"  # Этап открыт
            else:
                stage_status_icon = "⛔️"  # Этап закрыт

            stages_info += f"{stage_status_icon}<b>Этап {stage.order_number}:</b> {stage.name}\n"

            # Получаем информацию о сессиях
            sessions_progress = await get_stage_session_progress(session, stage_progress.id)

            for session_progress in sessions_progress:
                # Определяем статус сессии: 🟢 если все тесты пройдены, 🟡 если этап открыт, ⏺️ если этап закрыт
                if hasattr(session_progress.session, 'tests') and session_progress.session.tests:
                    # ИСПРАВЛЕНИЕ: проверяем пройденность только если этап открыт
                    all_tests_passed = False
                    if stage_progress.is_opened:
                        all_tests_passed = True
                        for test in session_progress.session.tests:
                            test_result = await get_user_test_result(session, user.id, test.id, company_id=user.company_id)
                            if not (test_result and test_result.is_passed):
                                all_tests_passed = False
                                break
                    
                    if all_tests_passed and stage_progress.is_opened:
                        session_status_icon = "✅"  # Все тесты пройдены (только если этап открыт)
                    elif stage_progress.is_opened:
                        session_status_icon = "🟡"  # Этап открыт, сессия доступна
                    else:
                        session_status_icon = "⛔️"  # Этап закрыт
                else:
                    session_status_icon = "⛔️"  # Нет тестов
                stages_info += f"{session_status_icon}<b>Сессия {session_progress.session.order_number}:</b> {session_progress.session.name}\n"

                # Показываем тесты в сессии
                for test_num, test in enumerate(session_progress.session.tests, 1):
                    test_result = await get_user_test_result(session, user.id, test.id, company_id=user.company_id)
                    is_passed = bool(test_result and test_result.is_passed)
                    icon = get_test_status_icon(is_passed, stage_progress.is_opened)
                    stages_info += format_test_line(test_num, test.name, icon)
            
            # Добавляем пустую строку после этапа
            stages_info += "\n"

        # Добавляем информацию об аттестации
        stages_info += await format_attestation_status(session, user.id, trainee_path)

        available_stages = [sp for sp in stages_progress if sp.is_opened and not sp.is_completed]

        # Создаем клавиатуру с доступными этапами согласно ТЗ
        keyboard_buttons = []

        if available_stages:
            stages_info += "Выбери этап траектории👇"
            for stage_progress in available_stages:
                keyboard_buttons.append([
                    InlineKeyboardButton(
                        text=f"Этап {stage_progress.stage.order_number}",
                        callback_data=f"select_stage:{stage_progress.stage.id}"
                    )
                ])
        else:
            stages_info += "❌ Нет открытых этапов для прохождения"

        # Добавляем кнопку "Главное меню"
        keyboard_buttons.append([
            InlineKeyboardButton(
                text="≡ Главное меню",
                callback_data="main_menu"
            )
        ])

        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)

        await callback.message.edit_text(
            trajectory_info + stages_info,
            reply_markup=keyboard,
            parse_mode="HTML"
        )

        log_user_action(user.tg_id, "trajectory_opened", f"Открыта траектория {trainee_path.learning_path.name}")

    except Exception as e:
        await callback.message.edit_text("Произошла ошибка при открытии траектории")
        log_user_error(callback.from_user.id, "trajectory_command_error", str(e))


@router.callback_query(F.data.startswith("select_stage:"))
async def callback_select_stage(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Обработчик выбора этапа траектории"""
    try:
        await callback.answer()

        stage_id = int(callback.data.split(":")[1])

        # Получаем пользователя
        from database.db import get_user_by_tg_id
        user = await get_user_by_tg_id(session, callback.from_user.id)
        if not user:
            await callback.message.edit_text("Пользователь не найден")
            return

        # Получаем траекторию стажера
        company_id = user.company_id
        trainee_path = await get_trainee_learning_path(session, user.id, company_id=company_id)
        if not trainee_path:
            await callback.message.edit_text("Траектория не найдена")
            return

        # Получаем прогресс по этапу
        stages_progress = await get_trainee_stage_progress(session, trainee_path.id, company_id=company_id)
        stage_progress = next((sp for sp in stages_progress if sp.stage_id == stage_id), None)

        if not stage_progress or not stage_progress.is_opened:
            await callback.message.edit_text("Этап не доступен для прохождения")
            return

        # Получаем сессии этапа
        sessions_progress = await get_stage_session_progress(session, stage_progress.id)

        # Формируем информацию об этапе согласно ТЗ
        stage_info = await format_trajectory_info(user, trainee_path, "ВЫБОР СЕССИИ")

        # Формируем полную информацию о траектории согласно ТЗ
        full_trajectory_info = stage_info

        # Добавляем этапы и сессии согласно ТЗ
        for sp in stages_progress:
            # Получаем сессии для определения статуса этапа
            stage_sessions_progress = await get_stage_session_progress(session, sp.id)
            
            # Определяем статус этапа: 🟢 если все сессии пройдены, 🟡 если открыт, ⏺️ если закрыт
            # ИСПРАВЛЕНИЕ: проверяем завершенность только если этап открыт
            all_sessions_completed = False
            if sp.is_opened and stage_sessions_progress:
                all_sessions_completed = True
                for session_prog in stage_sessions_progress:
                    if hasattr(session_prog.session, 'tests') and session_prog.session.tests:
                        session_tests_passed = True
                        for test in session_prog.session.tests:
                            test_result = await get_user_test_result(session, user.id, test.id, company_id=user.company_id)
                            if not (test_result and test_result.is_passed):
                                session_tests_passed = False
                                break
                        if not session_tests_passed:
                            all_sessions_completed = False
                            break
            
            if all_sessions_completed and stage_sessions_progress:
                stage_icon = "✅"  # Все сессии пройдены
            elif sp.is_opened:
                stage_icon = "🟡"  # Этап открыт
            else:
                stage_icon = "⛔️"  # Этап закрыт
                
            full_trajectory_info += f"{stage_icon}<b>Этап {sp.stage.order_number}:</b> {sp.stage.name}\n"

            for session_progress in stage_sessions_progress:
                # Определяем статус сессии: 🟢 если все тесты пройдены, 🟡 если этап открыт, ⏺️ если этап закрыт
                if hasattr(session_progress.session, 'tests') and session_progress.session.tests:
                    all_tests_passed = True
                    for test in session_progress.session.tests:
                        test_result = await get_user_test_result(session, user.id, test.id, company_id=user.company_id)
                        if not (test_result and test_result.is_passed):
                            all_tests_passed = False
                            break
                    
                    if all_tests_passed:
                        session_icon = "✅"  # Все тесты пройдены
                    elif sp.is_opened:
                        session_icon = "🟡"  # Этап открыт, сессия доступна
                    else:
                        session_icon = "⛔️"  # Этап закрыт
                else:
                    session_icon = "⛔️"  # Нет тестов
                    
                full_trajectory_info += f"{session_icon}<b>Сессия {session_progress.session.order_number}:</b> {session_progress.session.name}\n"

                # Показываем тесты в сессии
                for test_num, test in enumerate(session_progress.session.tests, 1):
                    test_result = await get_user_test_result(session, user.id, test.id, company_id=user.company_id)
                    is_passed = bool(test_result and test_result.is_passed)
                    icon = get_test_status_icon(is_passed, sp.is_opened)
                    full_trajectory_info += format_test_line(test_num, test.name, icon)
            
            # Добавляем пустую строку после этапа
            full_trajectory_info += "\n"

        # Добавляем аттестацию
        attestation = trainee_path.learning_path.attestation if trainee_path.learning_path else None
        full_trajectory_info += await format_attestation_status_simple(session, user.id, attestation)

        available_sessions = [sp for sp in sessions_progress if sp.is_opened and not sp.is_completed]

        # Создаем клавиатуру с доступными сессиями согласно ТЗ
        keyboard_buttons = []

        full_trajectory_info += "Выбери сессию в этапе\n\n"

        if available_sessions:
            for session_progress in available_sessions:
                keyboard_buttons.append([
                    InlineKeyboardButton(
                        text=f"Сессия {session_progress.session.order_number}",
                        callback_data=f"select_session:{session_progress.session.id}"
                    )
                ])
        else:
            full_trajectory_info += "❌ Нет открытых сессий для прохождения"

        # Добавляем кнопку "Назад"
        keyboard_buttons.append([
            InlineKeyboardButton(
                text="⬅️ Назад (к выбору этапа)",
                callback_data="trajectory_command"
            )
        ])

        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)

        await callback.message.edit_text(
            full_trajectory_info,
            reply_markup=keyboard,
            parse_mode="HTML"
        )

        log_user_action(callback.from_user.id, "stage_selected", f"Выбран этап {stage_progress.stage.name}")

    except Exception as e:
        await callback.message.edit_text("Произошла ошибка при выборе этапа")
        log_user_error(callback.from_user.id, "select_stage_error", str(e))


@router.callback_query(F.data.startswith("select_session:"))
async def callback_select_session(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Обработчик выбора сессии этапа"""
    try:
        await callback.answer()

        session_id = int(callback.data.split(":")[1])

        # Получаем пользователя
        from database.db import get_user_by_tg_id
        user = await get_user_by_tg_id(session, callback.from_user.id)
        if not user:
            await callback.message.edit_text("Пользователь не найден")
            return

        # Получаем траекторию стажера
        company_id = user.company_id
        trainee_path = await get_trainee_learning_path(session, user.id, company_id=company_id)
        if not trainee_path:
            await callback.message.edit_text("Траектория не найдена")
            return

        # Получаем сессию с тестами
        from database.db import get_session_with_tests
        selected_session = await get_session_with_tests(session, session_id, company_id=company_id)

        if not selected_session:
            await callback.message.edit_text("Сессия не найдена")
            return

        # Получаем тесты сессии
        tests = selected_session.tests if hasattr(selected_session, 'tests') and selected_session.tests else []

        # Формируем полную информацию о траектории согласно ТЗ
        session_info = await format_trajectory_info(user, trainee_path, "ВЫБОР ТЕСТА")

        # Формируем полную информацию о траектории согласно ТЗ
        full_trajectory_info = session_info

        # Получаем все этапы и сессии для отображения полной структуры
        stages_progress = await get_trainee_stage_progress(session, trainee_path.id)

        for sp in stages_progress:
            # Получаем сессии для определения статуса этапа
            stage_sessions_progress = await get_stage_session_progress(session, sp.id)
            
            # Определяем статус этапа: 🟢 если все сессии пройдены, 🟡 если открыт, ⏺️ если закрыт
            # ИСПРАВЛЕНИЕ: проверяем завершенность только если этап открыт
            all_sessions_completed = False
            if sp.is_opened and stage_sessions_progress:
                all_sessions_completed = True
                for session_prog in stage_sessions_progress:
                    if hasattr(session_prog.session, 'tests') and session_prog.session.tests:
                        session_tests_passed = True
                        for test in session_prog.session.tests:
                            test_result = await get_user_test_result(session, user.id, test.id, company_id=user.company_id)
                            if not (test_result and test_result.is_passed):
                                session_tests_passed = False
                                break
                        if not session_tests_passed:
                            all_sessions_completed = False
                            break
            
            if all_sessions_completed and stage_sessions_progress:
                stage_icon = "✅"  # Все сессии пройдены
            elif sp.is_opened:
                stage_icon = "🟡"  # Этап открыт
            else:
                stage_icon = "⛔️"  # Этап закрыт
                
            full_trajectory_info += f"{stage_icon}<b>Этап {sp.stage.order_number}:</b> {sp.stage.name}\n"

            for session_progress in stage_sessions_progress:
                if session_progress.session:
                    # Определяем статус сессии: 🟢 если все тесты пройдены, 🟡 если этап открыт, ⏺️ если этап закрыт
                    if hasattr(session_progress.session, 'tests') and session_progress.session.tests:
                        # ИСПРАВЛЕНИЕ: проверяем пройденность только если этап открыт
                        all_tests_passed = False
                        if sp.is_opened:
                            all_tests_passed = True
                            for test in session_progress.session.tests:
                                test_result = await get_user_test_result(session, user.id, test.id, company_id=user.company_id)
                                if not (test_result and test_result.is_passed):
                                    all_tests_passed = False
                                    break
                        
                        if all_tests_passed and sp.is_opened:
                            session_icon = "✅"  # Все тесты пройдены (только если этап открыт)
                        elif sp.is_opened:
                            session_icon = "🟡"  # Этап открыт, сессия доступна
                        else:
                            session_icon = "⛔️"  # Этап закрыт
                    else:
                        session_icon = "⛔️"  # Нет тестов
                        
                    full_trajectory_info += f"{session_icon}<b>Сессия {session_progress.session.order_number}:</b> {session_progress.session.name}\n"

                    # Показываем тесты в сессии
                    if hasattr(session_progress.session, 'tests') and session_progress.session.tests:
                        for test_num, test in enumerate(session_progress.session.tests, 1):
                            test_result = await get_user_test_result(session, user.id, test.id, company_id=user.company_id)
                            is_passed = bool(test_result and test_result.is_passed)
                            icon = get_test_status_icon(is_passed, sp.is_opened)
                            full_trajectory_info += format_test_line(test_num, test.name, icon)
                    else:
                        full_trajectory_info += "   📝 Тесты не найдены\n"
                else:
                    full_trajectory_info += "⛔️<b>Сессия:</b> Данные не загружены\n"
            
            # Добавляем пустую строку после этапа
            full_trajectory_info += "\n"

        # Добавляем аттестацию
        attestation = trainee_path.learning_path.attestation if trainee_path.learning_path else None
        full_trajectory_info += await format_attestation_status_simple(session, user.id, attestation)

        # Создаем клавиатуру с тестами согласно ТЗ
        keyboard_buttons = []

        if tests:
            for i, test in enumerate(tests, 1):
                keyboard_buttons.append([
                    InlineKeyboardButton(
                        text=f"Тест {i}",
                        callback_data=f"take_test:{session_id}:{test.id}"
                    )
                ])

        # Добавляем кнопку "Назад" для возврата к выбору сессий
        keyboard_buttons.append([
            InlineKeyboardButton(
                text="⬅️ Назад (к выбору сессии)",
                callback_data=f"select_stage:{selected_session.stage_id}"
            )
        ])

        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)

        await callback.message.edit_text(
            full_trajectory_info,
            reply_markup=keyboard,
            parse_mode="HTML"
        )

        log_user_action(callback.from_user.id, "session_selected", f"Выбрана сессия {selected_session.name}")

    except Exception as e:
        await callback.message.edit_text("Произошла ошибка при выборе сессии")
        log_user_error(callback.from_user.id, "select_session_error", str(e))


@router.callback_query(F.data.startswith("take_test:"))
async def callback_take_test(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Обработчик начала прохождения теста из траектории"""
    try:
        await callback.answer()

        # Парсим callback_data: take_test:{session_id}:{test_id}
        parts = callback.data.split(":")
        
        # Обрабатываем только формат с 3 частями (из траектории)
        # Формат с 2 частями (из уведомлений) должен обрабатываться в test_taking.py
        if len(parts) != 3:
            return
        
        # Удаляем медиа-файл с материалами, если он был отправлен
        data = await state.get_data()
        if 'material_message_id' in data:
            try:
                await callback.bot.delete_message(
                    chat_id=callback.message.chat.id,
                    message_id=data['material_message_id']
                )
            except Exception:
                pass  # Сообщение уже удалено или недоступно
        
        # Очищаем сохраненные message_id
        await state.update_data(material_message_id=None, material_text_message_id=None)
        
        user = await get_user_by_tg_id(session, callback.from_user.id)
        if not user:
            await callback.message.edit_text("❌ Ты не зарегистрирован в системе.")
            return
            
        session_id = int(parts[1])
        test_id = int(parts[2])

        # Получаем тест
        from database.db import get_test_by_id
        test = await get_test_by_id(session, test_id, company_id=user.company_id)

        if not test:
            await callback.message.edit_text("Тест не найден")
            return

        # Формируем информацию о тесте
        test_info = f"""📌 <b>{test.name}</b>

<b>Порог:</b> {test.threshold_score:.1f}/{test.max_score:.1f} б.

{test.description or 'Описание отсутствует'}

Если есть сомнения по теме, сначала прочти прикреплённые обучающие материалы, а потом переходи к тесту"""

        # Клавиатура действий
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="▶️ Начать тест", callback_data=f"start_test:{test_id}"),
                InlineKeyboardButton(text="📚 Материалы", callback_data=f"show_materials:{session_id}:{test_id}")
            ],
            [
                InlineKeyboardButton(text="⬅️ Назад", callback_data=f"back_to_session:{session_id}"),
                InlineKeyboardButton(text="≡ Главное меню", callback_data="main_menu")
            ]
        ])

        await callback.message.edit_text(
            test_info,
            reply_markup=keyboard,
            parse_mode="HTML"
        )

        log_user_action(callback.from_user.id, "test_selected", f"Выбран тест {test.name}")

    except Exception as e:
        await callback.message.edit_text("Произошла ошибка при открытии теста")
        log_user_error(callback.from_user.id, "take_test_error", str(e))


# Обработчик start_test: перенесен в test_taking.py для универсального использования


@router.callback_query(F.data.startswith("back_to_session:"))
async def callback_back_to_session(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Обработчик возврата к выбору тестов в сессии"""
    try:
        await callback.answer()

        session_id = int(callback.data.split(":")[1])

        # Получаем пользователя
        from database.db import get_user_by_tg_id
        user = await get_user_by_tg_id(session, callback.from_user.id)
        if not user:
            await callback.message.edit_text("Пользователь не найден")
            return

        # Получаем траекторию стажера
        company_id = user.company_id
        trainee_path = await get_trainee_learning_path(session, user.id, company_id=company_id)
        if not trainee_path:
            await callback.message.edit_text("Траектория не найдена")
            return

        # Получаем сессию с тестами
        from database.db import get_session_with_tests
        selected_session = await get_session_with_tests(session, session_id, company_id=company_id)

        if not selected_session:
            await callback.message.edit_text("Сессия не найдена")
            return

        # Получаем тесты сессии
        tests = selected_session.tests if hasattr(selected_session, 'tests') and selected_session.tests else []

        # Формируем полную информацию о траектории согласно ТЗ
        session_info = await format_trajectory_info(user, trainee_path, "ВЫБОР ТЕСТА")

        # Формируем полную информацию о траектории согласно ТЗ
        full_trajectory_info = session_info

        # Получаем все этапы и сессии для отображения полной структуры
        stages_progress = await get_trainee_stage_progress(session, trainee_path.id)

        for sp in stages_progress:
            # Получаем сессии для определения статуса этапа
            stage_sessions_progress = await get_stage_session_progress(session, sp.id)
            
            # Определяем статус этапа: 🟢 если все сессии пройдены, 🟡 если открыт, ⏺️ если закрыт
            # ИСПРАВЛЕНИЕ: проверяем завершенность только если этап открыт
            all_sessions_completed = False
            if sp.is_opened and stage_sessions_progress:
                all_sessions_completed = True
                for session_prog in stage_sessions_progress:
                    if hasattr(session_prog.session, 'tests') and session_prog.session.tests:
                        session_tests_passed = True
                        for test in session_prog.session.tests:
                            test_result = await get_user_test_result(session, user.id, test.id, company_id=user.company_id)
                            if not (test_result and test_result.is_passed):
                                session_tests_passed = False
                                break
                        if not session_tests_passed:
                            all_sessions_completed = False
                            break
            
            if all_sessions_completed and stage_sessions_progress:
                stage_icon = "✅"  # Все сессии пройдены
            elif sp.is_opened:
                stage_icon = "🟡"  # Этап открыт
            else:
                stage_icon = "⛔️"  # Этап закрыт
                
            full_trajectory_info += f"{stage_icon}<b>Этап {sp.stage.order_number}:</b> {sp.stage.name}\n"

            for session_progress in stage_sessions_progress:
                # Определяем статус сессии: 🟢 если все тесты пройдены, 🟡 если этап открыт, ⏺️ если этап закрыт
                if hasattr(session_progress.session, 'tests') and session_progress.session.tests:
                    all_tests_passed = True
                    for test in session_progress.session.tests:
                        test_result = await get_user_test_result(session, user.id, test.id, company_id=user.company_id)
                        if not (test_result and test_result.is_passed):
                            all_tests_passed = False
                            break
                    
                    if all_tests_passed:
                        session_icon = "✅"  # Все тесты пройдены
                    elif sp.is_opened:
                        session_icon = "🟡"  # Этап открыт, сессия доступна
                    else:
                        session_icon = "⛔️"  # Этап закрыт
                else:
                    session_icon = "⛔️"  # Нет тестов
                    
                full_trajectory_info += f"{session_icon}<b>Сессия {session_progress.session.order_number}:</b> {session_progress.session.name}\n"

                # Показываем тесты в сессии
                for test_num, test in enumerate(session_progress.session.tests, 1):
                    test_result = await get_user_test_result(session, user.id, test.id, company_id=user.company_id)
                    is_passed = bool(test_result and test_result.is_passed)
                    icon = get_test_status_icon(is_passed, sp.is_opened)
                    full_trajectory_info += format_test_line(test_num, test.name, icon)
            
            # Добавляем пустую строку после этапа
            full_trajectory_info += "\n"

        # Добавляем аттестацию
        attestation = trainee_path.learning_path.attestation if trainee_path.learning_path else None
        full_trajectory_info += await format_attestation_status_simple(session, user.id, attestation)

        # Создаем клавиатуру с тестами согласно ТЗ
        keyboard_buttons = []

        if tests:
            for i, test in enumerate(tests, 1):
                keyboard_buttons.append([
                    InlineKeyboardButton(
                        text=f"Тест {i}",
                        callback_data=f"take_test:{session_id}:{test.id}"
                    )
                ])

        # Добавляем кнопку "Назад" для возврата к выбору сессий
        keyboard_buttons.append([
            InlineKeyboardButton(
                text="⬅️ Назад (к выбору сессии)",
                callback_data=f"select_stage:{selected_session.stage_id}"
            )
        ])

        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)

        await callback.message.edit_text(
            full_trajectory_info,
            reply_markup=keyboard,
            parse_mode="HTML"
        )

        log_user_action(callback.from_user.id, "back_to_session", f"Возврат к сессии {selected_session.name}")

    except Exception as e:
        await callback.message.edit_text("Произошла ошибка при возврате к сессии")
        log_user_error(callback.from_user.id, "back_to_session_error", str(e))


@router.callback_query(F.data.startswith("show_materials:"))
async def callback_show_materials(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Обработчик показа материалов для теста"""
    try:
        await callback.answer()
        
        user = await get_user_by_tg_id(session, callback.from_user.id)
        if not user:
            await callback.message.edit_text("❌ Ты не зарегистрирован в системе.")
            return

        # Парсим callback_data: show_materials:{session_id}:{test_id}
        parts = callback.data.split(":")
        session_id = int(parts[1])
        test_id = int(parts[2])

        # Получаем тест
        from database.db import get_test_by_id
        test = await get_test_by_id(session, test_id, company_id=user.company_id)

        if not test:
            await callback.message.edit_text("Тест не найден")
            return

        # Если материалов нет
        if not test.material_link:
            await callback.message.edit_text(
                "📚 <b>Материалы для изучения</b>\n\n"
                "К этому тесту не прикреплены материалы.",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="▶️ Начать тест", callback_data=f"start_test:{test_id}")],
                    [InlineKeyboardButton(text="⬅️ Назад к тесту", callback_data=f"take_test:{session_id}:{test_id}")]
                ])
            )
            return

        # Если есть файл - отправляем по типу (используем file_id)
        if test.material_file_path:
            try:
                if test.material_type == "photo":
                    sent_media = await callback.bot.send_photo(
                        chat_id=callback.message.chat.id,
                        photo=test.material_file_path  # file_id
                    )
                elif test.material_type == "video":
                    sent_media = await callback.bot.send_video(
                        chat_id=callback.message.chat.id,
                        video=test.material_file_path  # file_id
                    )
                else:
                    sent_media = await callback.bot.send_document(
                        chat_id=callback.message.chat.id,
                        document=test.material_file_path  # file_id
                    )
                
                # Сохраняем message_id медиа-файла для последующего удаления
                await state.update_data(material_message_id=sent_media.message_id)

                # Отправляем кнопки отдельно
                sent_text = await callback.message.answer(
                    "📎 Материал отправлен выше.",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="▶️ Начать тест", callback_data=f"start_test:{test_id}")],
                        [InlineKeyboardButton(text="⬅️ Назад к тесту", callback_data=f"take_test:{session_id}:{test_id}")]
                    ])
                )
                # Сохраняем message_id текстового сообщения
                await state.update_data(material_text_message_id=sent_text.message_id)
            except Exception as e:
                # Ошибка отправки файла
                await callback.message.edit_text(
                    f"❌ <b>Ошибка загрузки файла</b>\n\n"
                    f"Не удалось загрузить материал.\n\n"
                    f"📌 <b>Тест:</b> {test.name}",
                    parse_mode="HTML",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="▶️ Начать тест", callback_data=f"start_test:{test_id}")],
                        [InlineKeyboardButton(text="⬅️ Назад к тесту", callback_data=f"take_test:{session_id}:{test_id}")]
                    ])
                )
        else:
            # Если это ссылка
            await callback.message.edit_text(
                f"📚 <b>Материалы для изучения</b>\n\n"
                f"📌 <b>Тест:</b> {test.name}\n\n"
                f"🔗 <b>Ссылка:</b>\n{test.material_link}\n\n"
                f"💡 Изучи материалы перед прохождением теста!",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="▶️ Начать тест", callback_data=f"start_test:{test_id}")],
                    [InlineKeyboardButton(text="⬅️ Назад к тесту", callback_data=f"take_test:{session_id}:{test_id}")]
                ])
            )

        log_user_action(callback.from_user.id, "materials_viewed", f"Просмотрены материалы для теста {test.name}")

    except Exception as e:
        await callback.message.edit_text("Произошла ошибка при показе материалов")
        log_user_error(callback.from_user.id, "show_materials_error", str(e))


@router.callback_query(F.data.startswith("back_to_trajectory:"))
async def callback_back_to_trajectory(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Обработчик возврата к выбору этапа"""
    try:
        await callback.answer()

        user_id = int(callback.data.split(":")[1])

        # Получаем пользователя
        from database.db import get_user_by_id
        user = await get_user_by_id(session, user_id)
        if not user:
            await callback.message.edit_text("Пользователь не найден")
            return

        # Имитируем вызов команды траектории
        message = callback.message
        message.from_user = callback.from_user
        await cmd_trajectory(message, state, session)

    except Exception as e:
        await callback.message.edit_text("Произошла ошибка при возврате к траектории")
        log_user_error(callback.from_user.id, "back_to_trajectory_error", str(e))


@router.callback_query(F.data.startswith("back_to_stage:"))
async def callback_back_to_stage(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Обработчик возврата к выбору сессии"""
    try:
        await callback.answer()

        user_id = int(callback.data.split(":")[1])

        # Получаем пользователя
        from database.db import get_user_by_id
        user = await get_user_by_id(session, user_id)
        if not user:
            await callback.message.edit_text("Пользователь не найден")
            return

        # Получаем траекторию стажера
        company_id = user.company_id
        trainee_path = await get_trainee_learning_path(session, user.id, company_id=company_id)
        if not trainee_path:
            await callback.message.edit_text("Траектория не найдена")
            return

        # Получаем первый открытый этап
        stages_progress = await get_trainee_stage_progress(session, trainee_path.id, company_id=company_id)
        opened_stage = next((sp for sp in stages_progress if sp.is_opened and not sp.is_completed), None)

        if opened_stage:
            # Имитируем выбор этапа
            callback.data = f"select_stage:{opened_stage.stage_id}"
            await callback_select_stage(callback, state, session)
        else:
            await callback.message.edit_text("Нет открытых этапов")

    except Exception as e:
        await callback.message.edit_text("Произошла ошибка при возврате к этапу")
        log_user_error(callback.from_user.id, "back_to_stage_error", str(e))


# Вспомогательные функции для правильной индикации аттестации (Task 7)

async def format_attestation_status(session, user_id, trainee_path):
    """Форматирование статуса аттестации с правильной индикацией"""
    try:
        if trainee_path and trainee_path.learning_path.attestation:
            # Получаем company_id для изоляции
            user = await get_user_by_id(session, user_id)
            company_id = user.company_id if user else None
            
            attestation_status = await get_trainee_attestation_status(
                session, user_id, trainee_path.learning_path.attestation.id, company_id=company_id
            )
            return f"🏁<b>Аттестация:</b> {trainee_path.learning_path.attestation.name} {attestation_status}\n\n"
        else:
            return f"🏁<b>Аттестация:</b> Не указана ⛔️\n\n"
    except Exception as e:
        log_user_error(user_id, "format_attestation_status_error", str(e))
        return f"🏁<b>Аттестация:</b> Ошибка загрузки ⛔️\n\n"


async def format_attestation_status_simple(session, user_id, attestation):
    """Форматирование статуса аттестации (упрощенная версия)"""
    try:
        if attestation:
            # Получаем company_id для изоляции
            user = await get_user_by_id(session, user_id)
            company_id = user.company_id if user else None
            
            attestation_status = await get_trainee_attestation_status(session, user_id, attestation.id, company_id=company_id)
            return f"🏁<b>Аттестация:</b> {attestation.name} {attestation_status}\n\n"
        else:
            return f"🏁<b>Аттестация:</b> Не указана ⛔️\n\n"
    except Exception as e:
        log_user_error(user_id, "format_attestation_status_simple_error", str(e))
        return f"🏁<b>Аттестация:</b> Ошибка загрузки ⛔️\n\n"


@router.callback_query(F.data == "contact_mentor")
async def callback_contact_mentor(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Обработчик кнопки 'Связь с наставником'"""
    try:
        await callback.answer()
        
        # Получаем пользователя
        user = await get_user_by_tg_id(session, callback.from_user.id)
        if not user:
            await callback.message.edit_text("❌ Ты не зарегистрирован в системе.")
            return
        
        # Получаем наставника стажера
        from database.db import get_user_mentor
        mentor = await get_user_mentor(session, user.id)
        
        if not mentor:
            await callback.message.edit_text(
                "❌ <b>Наставник не назначен</b>\n\n"
                "Тебе еще не назначен наставник.\n"
                "Обратись к рекрутеру для назначения наставника.",
                parse_mode="HTML"
            )
            return
        
        # Формируем сообщение с контактами наставника
        mentor_info = f"""👨‍🏫 <b>Твой наставник</b>

🧑 <b>Имя:</b> {mentor.full_name}
📞 <b>Телефон:</b> {mentor.phone_number}
👤 <b>Username:</b> @{mentor.username or 'не указан'}

💬 <b>Свяжись с наставником для назначения траектории обучения</b>"""
        
        await callback.message.edit_text(
            mentor_info,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="≡ Главное меню", callback_data="main_menu")]
            ])
        )
        
        log_user_action(user.tg_id, "mentor_contact_viewed", f"Стажер просмотрел контакты наставника: {mentor.full_name}")
        
    except Exception as e:
        log_user_error(callback.from_user.id, "contact_mentor_error", str(e))
        await callback.message.edit_text("❌ Произошла ошибка при получении контактов наставника.")
