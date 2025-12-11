"""
Обработчики для назначения наставников стажерам рекрутерами.
Включает выбор стажера, выбор наставника и подтверждение назначения.
"""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from database.db import (
    get_trainees_without_mentor, get_available_mentors_for_trainee,
    assign_mentor_to_trainee, check_user_permission, get_user_by_tg_id,
    ensure_company_id
)
from handlers.auth import check_auth
from states.states import MentorAssignmentStates
from keyboards.keyboards import get_main_menu_keyboard, get_keyboard_by_role
from utils.logger import log_user_action, log_user_error

router = Router()


@router.message(F.text == "Назначить наставника")
async def cmd_assign_mentor(message: Message, state: FSMContext, session: AsyncSession):
    """Обработчик команды 'Назначить наставника'"""
    try:
        # Проверка авторизации
        is_auth = await check_auth(message, state, session)
        if not is_auth:
            return

        # Получение пользователя
        user = await get_user_by_tg_id(session, message.from_user.id)
        if not user:
            await message.answer("Ты не зарегистрирован в системе.")
            return

        # Проверка прав доступа (только рекрутеры)
        has_permission = await check_user_permission(session, user.id, "manage_groups")
        if not has_permission:
            await message.answer(
                "❌ <b>Недостаточно прав</b>\n\n"
                "У тебя нет прав для назначения наставников.\n"
                "Обратись к администратору.",
                parse_mode="HTML"
            )
            log_user_error(user.tg_id, "mentor_assignment_access_denied", "Попытка доступа без прав")
            return

        # Получаем список стажеров без наставника
        trainees_without_mentor = await get_trainees_without_mentor(session, company_id=user.company_id)

        if not trainees_without_mentor:
            await message.answer(
                "👥 <b>Назначение наставника</b>\n\n"
                "📊 <b>Статистика системы:</b>\n"
                "• Стажеров без наставника: 0\n"
                "• Требуется назначение наставников\n\n"
                "🎯 <b>Все стажеры уже имеют наставников!</b>\n\n"
                "Все активные стажеры уже назначены наставникам.",
                reply_markup=get_main_menu_keyboard(),
                parse_mode="HTML"
            )
            log_user_action(user.tg_id, "no_trainees_without_mentor", "Все стажеры имеют наставников")
            return

        # Статистика системы
        trainees_count = len(trainees_without_mentor)

        # Формируем сообщение со статистикой
        stats_message = (
            "👥 <b>Назначение наставника</b>\n\n"
            "📊 <b>Статистика системы:</b>\n"
            f"• Стажеров без наставника: {trainees_count}\n"
            "• Требуется назначение наставников\n\n"
            "🎯 <b>Твоя задача:</b> Назначить наставника каждому стажеру для:\n"
            "• Персонального сопровождения\n"
            "• Контроля прогресса обучения\n"
            "• Помощи в адаптации\n"
            "• Предоставления доступа к тестам\n\n"
            "👇 <b>Выбери стажера для назначения наставника:</b>"
        )

        # Создаем клавиатуру со списком стажеров
        keyboard = InlineKeyboardMarkup(inline_keyboard=[])

        for trainee in trainees_without_mentor:
            keyboard.inline_keyboard.append([
                InlineKeyboardButton(
                    text=f"{trainee.full_name}",
                    callback_data=f"select_trainee:{trainee.id}"
                )
            ])

        # Кнопка отмены
        keyboard.inline_keyboard.append([
            InlineKeyboardButton(text="🚫 Отменить", callback_data="cancel_mentor_assignment")
        ])

        await message.answer(
            stats_message,
            reply_markup=keyboard,
            parse_mode="HTML"
        )

        await state.set_state(MentorAssignmentStates.selecting_trainee)
        log_user_action(user.tg_id, "mentor_assignment_started", f"Начат процесс назначения наставников. Стажеров без наставника: {trainees_count}")

    except Exception as e:
        await message.answer("Произошла ошибка при открытии меню назначения наставников")
        log_user_error(message.from_user.id, "mentor_assignment_error", str(e))


@router.callback_query(F.data.startswith("select_trainee:"), MentorAssignmentStates.selecting_trainee)
async def callback_select_trainee(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Обработчик выбора стажера"""
    try:
        await callback.answer()

        trainee_id = int(callback.data.split(":")[1])

        # Получаем данные стажера
        trainee = await get_user_by_tg_id(session, trainee_id)
        if not trainee:
            await callback.message.edit_text("Стажер не найден")
            return

        # Получаем доступных наставников для этого стажера
        available_mentors = await get_available_mentors_for_trainee(session, trainee_id, company_id=trainee.company_id)

        if not available_mentors:
            await callback.message.edit_text(
                f"❌ <b>Нет доступных наставников</b>\n\n"
                f"👤 <b>Стажер:</b> {trainee.full_name}\n\n"
                "Для этого стажера нет доступных наставников.\n"
                "Возможно, нет сотрудников, работающих на том же объекте.",
                parse_mode="HTML"
            )
            return

        # Сохраняем выбранного стажера в состоянии
        await state.update_data(selected_trainee_id=trainee_id)

        # Формируем информацию о стажере
        trainee_info = (
            f"👤 <b>Выбран стажер:</b> {trainee.full_name}\n"
            f"📍<b>1️⃣Объект стажировки:</b> {trainee.internship_object.name if trainee.internship_object else 'Не указан'}\n"
            f"📍<b>2️⃣Объект работы:</b> {trainee.work_object.name if trainee.work_object else 'Не указан'}\n"
            f"📞 <b>Телефон:</b> {trainee.phone_number}\n"
            f"📅 <b>Дата регистрации:</b> {trainee.registration_date.strftime('%d.%m.%Y')}\n\n"
            "👨‍🏫 <b>Доступные наставники:</b>\n"
        )

        # Создаем клавиатуру с доступными наставниками
        keyboard = InlineKeyboardMarkup(inline_keyboard=[])

        for mentor in available_mentors:
            mentor_info = (
                f"👤 {mentor.full_name}\n"
                f"📍<b>2️⃣Объект работы:</b> {mentor.work_object.name if mentor.work_object else 'Не указан'}\n"
                f"📞 {mentor.phone_number}\n"
                f"📧 @{mentor.username if mentor.username else 'не указан'}"
            )

            keyboard.inline_keyboard.append([
                InlineKeyboardButton(
                    text=mentor.full_name,
                    callback_data=f"select_mentor:{mentor.id}"
                )
            ])

        # Кнопка отмены
        keyboard.inline_keyboard.append([
            InlineKeyboardButton(text="🚫 Отменить", callback_data="cancel_mentor_assignment")
        ])

        await callback.message.edit_text(
            trainee_info + "\n<b>Выбери наставника для этого стажера:</b>",
            reply_markup=keyboard,
            parse_mode="HTML"
        )

        await state.set_state(MentorAssignmentStates.selecting_mentor)
        log_user_action(callback.from_user.id, "trainee_selected", f"Выбран стажер {trainee.full_name} (ID: {trainee_id})")

    except Exception as e:
        await callback.message.edit_text("Произошла ошибка при выборе стажера")
        log_user_error(callback.from_user.id, "select_trainee_error", str(e))


@router.callback_query(F.data.startswith("select_mentor:"), MentorAssignmentStates.selecting_mentor)
async def callback_select_mentor(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Обработчик выбора наставника"""
    try:
        await callback.answer()

        mentor_id = int(callback.data.split(":")[1])

        # Получаем данные из состояния
        state_data = await state.get_data()
        trainee_id = state_data.get("selected_trainee_id")

        if not trainee_id:
            await callback.message.edit_text("Ошибка: стажер не выбран")
            return

        # Получаем данные стажера и наставника
        trainee = await get_user_by_tg_id(session, trainee_id)
        mentor = await get_user_by_tg_id(session, mentor_id)

        if not trainee or not mentor:
            await callback.message.edit_text("Ошибка: данные не найдены")
            return

        # Сохраняем выбранного наставника в состоянии
        await state.update_data(selected_mentor_id=mentor_id)

        # Формируем сообщение подтверждения
        confirmation_message = (
            "🤝 <b>Подтверждение назначения наставника</b>\n\n"
            "👤 <b>Стажер:</b>\n"
            f"   • ФИО: {trainee.full_name}\n"
            f"📍<b>1️⃣Объект стажировки:</b> {trainee.internship_object.name if trainee.internship_object else 'Не указан'}\n"
            f"📍<b>2️⃣Объект работы:</b> {trainee.work_object.name if trainee.work_object else 'Не указан'}\n"
            f"   • Телефон: {trainee.phone_number}\n"
            f"   • Дата регистрации: {trainee.registration_date.strftime('%d.%m.%Y')}\n\n"
            "👨‍🏫 <b>Наставник:</b>\n"
            f"   • ФИО: {mentor.full_name}\n"
            f"📍<b>2️⃣Объект работы:</b> {mentor.work_object.name if mentor.work_object else 'Не указан'}\n"
            f"   • Телефон: {mentor.phone_number}\n"
            f"   • Текущих стажеров: 0\n\n"  # Здесь можно добавить логику подсчета текущих стажеров
            "❓ <b>Подтвердите назначение наставника:</b>"
        )

        # Клавиатура подтверждения
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Подтвердить", callback_data="confirm_mentor_assignment"),
                InlineKeyboardButton(text="🚫 Отменить", callback_data="cancel_mentor_assignment")
            ]
        ])

        await callback.message.edit_text(
            confirmation_message,
            reply_markup=keyboard,
            parse_mode="HTML"
        )

        await state.set_state(MentorAssignmentStates.confirming_assignment)
        log_user_action(callback.from_user.id, "mentor_selected", f"Выбран наставник {mentor.full_name} (ID: {mentor_id}) для стажера {trainee.full_name}")

    except Exception as e:
        await callback.message.edit_text("Произошла ошибка при выборе наставника")
        log_user_error(callback.from_user.id, "select_mentor_error", str(e))


@router.callback_query(F.data == "confirm_mentor_assignment", MentorAssignmentStates.confirming_assignment)
async def callback_confirm_mentor_assignment(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Обработчик подтверждения назначения наставника"""
    try:
        await callback.answer()

        # Получаем данные из состояния
        state_data = await state.get_data()
        trainee_id = state_data.get("selected_trainee_id")
        mentor_id = state_data.get("selected_mentor_id")
        recruiter_id = callback.from_user.id

        # Получаем company_id с fallback на recruiter.company_id для надежности
        recruiter = await get_user_by_tg_id(session, recruiter_id)
        if not recruiter:
            await callback.message.edit_text("Ошибка: пользователь не найден")
            return

        company_id = await ensure_company_id(session, state, callback.from_user.id)
        if not company_id:
            company_id = recruiter.company_id

        if not trainee_id or not mentor_id:
            await callback.message.edit_text("Ошибка: данные не найдены")
            return

        # Назначаем наставника
        from main import bot
        success = await assign_mentor_to_trainee(session, trainee_id, mentor_id, recruiter_id, bot, company_id)

        if success:
            # Получаем обновленные данные для отображения
            trainee = await get_user_by_tg_id(session, trainee_id)
            mentor = await get_user_by_tg_id(session, mentor_id)
            recruiter = await get_user_by_tg_id(session, recruiter_id)

            success_message = (
                "✅ <b>Наставник успешно назначен!</b>\n\n"
                f"👤 <b>Стажер:</b> {trainee.full_name}\n"
                f"👨‍🏫 <b>Наставник:</b> {mentor.full_name}\n\n"
                f"📅 <b>Дата назначения:</b> {trainee.registration_date.strftime('%d.%m.%Y %H:%M')}\n"
                f"👤 <b>Назначил:</b> {recruiter.full_name} - Рекрутер\n\n"
                "📬 <b>Уведомления отправлены:</b>\n"
                "• ✅ Стажер получил контакты наставника\n"
                f"• 📞 Телефон: {mentor.phone_number}\n"
                f"• 📧 Telegram: @{mentor.username if mentor.username else 'не указан'}\n\n"
                "🎯 <b>Стажер может сразу связаться с наставником для знакомства!</b>"
            )

            # Клавиатура для продолжения работы
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(text="👨‍🏫 Назначить наставника", callback_data="assign_mentor"),
                    InlineKeyboardButton(text="≡ Главное меню", callback_data="main_menu")
                ]
            ])

            await callback.message.edit_text(
                success_message,
                reply_markup=keyboard,
                parse_mode="HTML"
            )

            log_user_action(recruiter_id, "mentor_assigned_success",
                          f"Назначен наставник {mentor.full_name} (ID: {mentor_id}) стажеру {trainee.full_name} (ID: {trainee_id})")

        else:
            await callback.message.edit_text(
                "❌ <b>Ошибка назначения наставника</b>\n\n"
                "Произошла ошибка при назначении наставника.\n"
                "Попробуй позже или обратись к администратору.",
                parse_mode="HTML"
            )
            log_user_error(recruiter_id, "mentor_assignment_failed", f"Ошибка назначения наставника {mentor_id} стажеру {trainee_id}")

        # Очищаем состояние
        await state.clear()

    except Exception as e:
        await callback.message.edit_text("Произошла ошибка при подтверждении назначения")
        log_user_error(callback.from_user.id, "confirm_mentor_assignment_error", str(e))


@router.callback_query(F.data == "cancel_mentor_assignment")
async def callback_cancel_mentor_assignment(callback: CallbackQuery, state: FSMContext):
    """Обработчик отмены назначения наставника"""
    try:
        await callback.answer()

        await callback.message.edit_text(
            "🚫 <b>Назначение наставника отменено</b>\n\n"
            "Ты можешь вернуться к этому позже через главное меню.",
            reply_markup=get_main_menu_keyboard(),
            parse_mode="HTML"
        )

        await state.clear()
        log_user_action(callback.from_user.id, "mentor_assignment_cancelled", "Отменено назначение наставника")

    except Exception as e:
        log_user_error(callback.from_user.id, "cancel_mentor_assignment_error", str(e))


@router.callback_query(F.data == "assign_mentor")
async def callback_assign_mentor(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Обработчик кнопки 'Назначить наставника' из успешного сообщения"""
    try:
        await callback.answer()

        # Получаем пользователя
        user = await get_user_by_tg_id(session, callback.from_user.id)
        if not user:
            await callback.message.edit_text("Ты не зарегистрирован в системе.")
            return

        # Проверка прав доступа
        has_permission = await check_user_permission(session, user.id, "manage_groups")
        if not has_permission:
            await callback.message.edit_text(
                "❌ <b>Недостаточно прав</b>",
                parse_mode="HTML"
            )
            return

        # Получаем список стажеров без наставника
        trainees_without_mentor = await get_trainees_without_mentor(session, company_id=user.company_id)

        if not trainees_without_mentor:
            await callback.message.edit_text(
                "🎯 <b>Все стажеры уже имеют наставников!</b>",
                reply_markup=get_main_menu_keyboard(),
                parse_mode="HTML"
            )
            return

        # Перенаправляем на начало процесса
        await cmd_assign_mentor(callback.message, state, session)

    except Exception as e:
        await callback.message.edit_text("Произошла ошибка")
        log_user_error(callback.from_user.id, "assign_mentor_redirect_error", str(e))
