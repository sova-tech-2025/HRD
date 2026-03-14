from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.db import (
    add_user_role,
    assign_attestation_to_trainee,
    check_user_permission,
    get_all_roles,
    get_all_trainees,
    get_all_users,
    get_attestation_by_id,
    get_managers_for_attestation,
    get_test_by_id,
    get_trainee_attestation_status,
    get_trainee_learning_path,
    get_trainee_mentor,
    get_user_by_id,
    get_user_by_tg_id,
    get_user_roles,
    get_user_test_results,
    remove_user_role,
)
from bot.keyboards.keyboards import (
    get_confirmation_keyboard,
    get_role_change_keyboard,
    get_user_action_keyboard,
    get_user_selection_keyboard,
)
from bot.states.states import AdminStates, RecruiterAttestationStates
from bot.utils.auth.auth import check_auth
from bot.utils.logger import log_user_action, log_user_error, logger
from bot.utils.timezone import moscow_now

router = Router()


async def check_admin_permission(
    message: Message, state: FSMContext, session: AsyncSession, permission: str = "manage_users"
) -> bool:
    """Проверяет, имеет ли пользователь указанное право доступа"""

    is_auth = await check_auth(message, state, session)
    if not is_auth:
        return False

    user = await get_user_by_tg_id(session, message.from_user.id)
    if not user:
        await message.answer("Ты не зарегистрирован в системе.")
        return False

    has_permission = await check_user_permission(session, user.id, permission)

    if not has_permission:
        await message.answer("У тебя нет прав для выполнения этой команды.")
        return False

    return True


@router.message(Command("manage_users"))
async def cmd_manage_users(message: Message, state: FSMContext, session: AsyncSession):
    """Обработчик команды управления пользователями"""
    if not await check_admin_permission(message, state, session):
        return

    await show_user_list(message, state, session)


@router.message(F.text == "Управление пользователями")
async def button_manage_users(message: Message, state: FSMContext, session: AsyncSession):
    """Обработчик кнопки управления пользователями"""
    await cmd_manage_users(message, state, session)


async def show_user_list(message: Message, state: FSMContext, session: AsyncSession):
    """Отображает список пользователей с возможностью выбора"""
    data = await state.get_data()
    company_id = data.get("company_id")
    users = await get_all_users(session, company_id)

    if not users:
        await message.answer("В системе пока нет зарегистрированных пользователей.")
        return

    keyboard = get_user_selection_keyboard(users)

    await message.answer("Выбери пользователя для управления:", reply_markup=keyboard)

    await state.set_state(AdminStates.waiting_for_user_selection)

    log_user_action(message.from_user.id, message.from_user.username, "opened user management panel")


@router.callback_query(AdminStates.waiting_for_user_selection, F.data.startswith("user:"))
async def process_user_selection(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Обработчик выбора пользователя из списка"""
    user_id = int(callback.data.split(":")[1])

    user = await get_user_by_id(session, user_id)

    if not user:
        await callback.message.answer("Пользователь не найден.")
        await callback.answer()
        return

    user_roles = await get_user_roles(session, user.id)
    roles_str = ", ".join([role.name for role in user_roles])

    extra_info = ""
    if "Стажер" in roles_str:
        # ИЗОЛЯЦИЯ: получаем company_id из состояния
        data = await state.get_data()
        company_id = data.get("company_id")
        mentor = await get_trainee_mentor(session, user.id, company_id=company_id)
        results = await get_user_test_results(session, user.id, company_id=company_id)
        passed_count = sum(1 for r in results if r.is_passed)
        avg_score = sum(r.score for r in results) / len(results) if results else 0

        extra_info = f"""
    <b>Статистика стажера:</b>
    👨‍🏫 Наставник: {mentor.full_name if mentor else "Не назначен"}
    ✅ Пройдено тестов: {passed_count}/{len(results)}
    📊 Средний балл: {avg_score:.1f}
    """

    user_info = f"""
    👤 <b>Информация о пользователе</b>
    
    🧑 ФИО: {user.full_name}
    📞 Телефон: {user.phone_number}
    🆔 Telegram ID: {user.tg_id}
    👤 Username: @{user.username or "не указан"}
    📅 Дата регистрации: {user.registration_date.strftime("%d.%m.%Y %H:%M")}
    👑 Роли: {roles_str}
    {extra_info}
    """

    keyboard = get_user_action_keyboard(user.id)

    await callback.message.edit_text(user_info, reply_markup=keyboard, parse_mode="HTML")

    await state.set_state(AdminStates.waiting_for_user_action)
    await state.update_data(selected_user_id=user.id)

    await callback.answer()

    log_user_action(
        callback.from_user.id,
        callback.from_user.username,
        "selected user for management",
        {"selected_user_id": user.id},
    )


@router.callback_query(AdminStates.waiting_for_user_action, F.data.startswith("change_role:"))
async def process_change_role(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Обработчик кнопки изменения роли пользователя"""
    user_id = int(callback.data.split(":")[1])

    user = await get_user_by_id(session, user_id)

    if not user:
        await callback.message.answer("Пользователь не найден.")
        await callback.answer()
        return

    roles = await get_all_roles(session)

    if not roles:
        await callback.message.answer("В системе не настроены роли.")
        await callback.answer()
        return

    keyboard = get_role_change_keyboard(user.id, roles)

    await callback.message.edit_text(f"Выбери новую роль для пользователя {user.full_name}:", reply_markup=keyboard)

    await state.set_state(AdminStates.waiting_for_role_change)

    await callback.answer()

    log_user_action(
        callback.from_user.id, callback.from_user.username, "opened role change menu", {"target_user_id": user.id}
    )


@router.callback_query(AdminStates.waiting_for_role_change, F.data.startswith("set_role:"))
async def process_set_role(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Обработчик выбора новой роли для пользователя"""
    # Извлекаем данные из callback
    parts = callback.data.split(":")
    user_id = int(parts[1])
    role_name = parts[2]

    user = await get_user_by_id(session, user_id)

    if not user:
        await callback.message.answer("Пользователь не найден.")
        await callback.answer()
        return

    current_roles = await get_user_roles(session, user.id)
    current_role_names = [role.name for role in current_roles]

    action = "remove" if role_name in current_role_names else "add"
    action_text = "удалить" if action == "remove" else "добавить"

    await callback.message.edit_text(
        f"Ты хочешь {action_text} роль '{role_name}' для пользователя {user.full_name}?\n\n"
        f"Текущие роли: {', '.join(current_role_names)}",
        reply_markup=get_confirmation_keyboard(user.id, role_name, action),
    )

    await state.set_state(AdminStates.waiting_for_confirmation)
    await state.update_data(user_id=user.id, role_name=role_name, action=action, current_roles=current_role_names)

    await callback.answer()

    log_user_action(
        callback.from_user.id,
        callback.from_user.username,
        "requested role change confirmation",
        {"target_user_id": user.id, "role": role_name, "action": action},
    )


@router.callback_query(AdminStates.waiting_for_confirmation, F.data.startswith("confirm:"))
async def process_confirm_role_change(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Обработчик подтверждения изменения роли"""
    # КРИТИЧЕСКАЯ ПРОВЕРКА ПРАВ!
    current_user = await get_user_by_tg_id(session, callback.from_user.id)
    if not current_user:
        await callback.answer("❌ Пользователь не найден.", show_alert=True)
        return

    has_permission = await check_user_permission(session, current_user.id, "manage_users")
    if not has_permission:
        await callback.message.edit_text(
            "❌ <b>Недостаточно прав</b>\n\n"
            "У тебя нет прав для изменения ролей пользователей.\n"
            "Обратись к администратору.",
            parse_mode="HTML",
        )
        await callback.answer()
        return

    parts = callback.data.split(":")
    action = parts[1]
    user_id = int(parts[2])
    role_name = parts[3]

    user = await get_user_by_id(session, user_id)

    if not user:
        await callback.message.answer("Пользователь не найден.")
        await callback.answer()
        return

    if action == "add":
        success = await add_user_role(session, user.id, role_name)
        action_text = "добавлена"
    else:
        success = await remove_user_role(session, user.id, role_name)
        action_text = "удалена"

    if success:
        updated_roles = await get_user_roles(session, user.id)
        roles_str = ", ".join([role.name for role in updated_roles])

        await callback.message.answer(
            f"✅ Роль '{role_name}' успешно {action_text} для пользователя {user.full_name}.\nТекущие роли: {roles_str}"
        )

        log_user_action(
            callback.from_user.id,
            callback.from_user.username,
            f"role {action} confirmed",
            {"target_user_id": user.id, "role": role_name},
        )
    else:
        await callback.message.answer(f"❌ Не удалось изменить роль для пользователя {user.full_name}.")
        log_user_error(
            callback.from_user.id,
            callback.from_user.username,
            "role change failed",
            {"target_user_id": user.id, "role": role_name, "action": action},
        )

    await show_user_list(callback.message, state, session)

    await callback.answer()


@router.callback_query(F.data.startswith("cancel_role_change:"))
async def process_cancel_role_change(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Обработчик отмены изменения роли"""
    user_id = int(callback.data.split(":")[1])

    data = await state.get_data()
    role_name = data.get("role_name")

    await callback.message.answer(f"Изменение роли '{role_name}' отменено.")

    user = await get_user_by_id(session, user_id)
    if user:
        keyboard = get_user_action_keyboard(user.id)

        user_roles = await get_user_roles(session, user.id)
        roles_str = ", ".join([role.name for role in user_roles])

        user_info = f"""
        👤 <b>Информация о пользователе</b>
        
        🧑 ФИО: {user.full_name}
        📞 Телефон: {user.phone_number}
        🆔 Telegram ID: {user.tg_id}
        👤 Username: @{user.username or "не указан"}
        📅 Дата регистрации: {user.registration_date.strftime("%d.%m.%Y %H:%M")}
        👑 Роли: {roles_str}
        """

        await callback.message.edit_text(user_info, reply_markup=keyboard, parse_mode="HTML")

        await state.set_state(AdminStates.waiting_for_user_action)
    else:
        await show_user_list(callback.message, state, session)

    await callback.answer()

    log_user_action(
        callback.from_user.id,
        callback.from_user.username,
        "cancelled role change",
        {"target_user_id": user_id, "role": role_name},
    )


@router.callback_query(F.data == "back_to_users")
async def process_back_to_users(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Обработчик кнопки возврата к списку пользователей"""
    await show_user_list(callback.message, state, session)
    await callback.answer()


@router.callback_query(F.data == "cancel")
async def process_cancel(callback: CallbackQuery, state: FSMContext):
    """Обработчик кнопки отмены"""
    await state.clear()
    await callback.message.edit_text("Операция отменена.")
    await callback.answer()

    log_user_action(callback.from_user.id, callback.from_user.username, "cancelled admin operation")


@router.callback_query(F.data.startswith("view_profile:"))
async def process_view_profile(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Обработчик просмотра профиля пользователя"""
    user_id = int(callback.data.split(":")[1])

    user = await get_user_by_id(session, user_id)

    if not user:
        await callback.message.answer("Пользователь не найден.")
        await callback.answer()
        return

    user_roles = await get_user_roles(session, user.id)
    roles_str = ", ".join([role.name for role in user_roles])

    user_info = f"""
    👤 <b>Профиль пользователя</b>
    
    🧑 ФИО: {user.full_name}
    📞 Телефон: {user.phone_number}
    🆔 Telegram ID: {user.tg_id}
    👤 Username: @{user.username or "не указан"}
    📅 Дата регистрации: {user.registration_date.strftime("%d.%m.%Y %H:%M")}
    👑 Роли: {roles_str}
    """

    keyboard = get_user_action_keyboard(user.id)

    await callback.message.edit_text(user_info, reply_markup=keyboard, parse_mode="HTML")

    await callback.answer()

    log_user_action(
        callback.from_user.id, callback.from_user.username, "viewed user profile", {"viewed_user_id": user.id}
    )


@router.message(Command("trainees"))
async def cmd_trainees(message: Message, state: FSMContext, session: AsyncSession):
    """Обработчик команды просмотра списка Стажеров"""
    if not await check_admin_permission(message, state, session, permission="view_trainee_list"):
        return

    await show_trainees_list(message, session, page=0)


@router.message(F.text.in_(["Список Стажеров", "Стажеры 🐣"]))
async def button_trainees(message: Message, state: FSMContext, session: AsyncSession):
    """Обработчик кнопки просмотра списка Стажеров"""
    if not await check_admin_permission(message, state, session, permission="view_trainee_list"):
        return

    await show_trainees_list(message, state, session, page=0)


async def show_trainees_list(message: Message, state: FSMContext, session: AsyncSession, page: int = 0):
    """Показать список стажеров с пагинацией"""
    from bot.keyboards.keyboards import get_trainees_list_keyboard

    data = await state.get_data()
    company_id = data.get("company_id")
    trainees = await get_all_trainees(session, company_id)

    if not trainees:
        await message.answer("В системе пока нет зарегистрированных Стажеров.")
        return

    await message.answer(
        "📋 <b>Список стажеров:</b>", parse_mode="HTML", reply_markup=get_trainees_list_keyboard(trainees, page=page)
    )

    log_user_action(message.from_user.id, message.from_user.username, "viewed trainees list")


@router.callback_query(F.data.startswith("trainees_page:"))
async def callback_trainees_page(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Обработчик пагинации списка стажеров"""
    try:
        from bot.keyboards.keyboards import get_trainees_list_keyboard

        page = int(callback.data.split(":")[1])
        data = await state.get_data()
        company_id = data.get("company_id")
        trainees = await get_all_trainees(session, company_id)

        if not trainees:
            await callback.message.edit_text("В системе пока нет зарегистрированных Стажеров.")
            await callback.answer()
            return

        await callback.message.edit_text(
            "📋 <b>Список стажеров:</b>",
            parse_mode="HTML",
            reply_markup=get_trainees_list_keyboard(trainees, page=page),
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка обработки пагинации стажеров: {e}")
        await callback.answer("Ошибка при загрузке страницы", show_alert=True)


@router.callback_query(F.data.startswith("view_trainee:"))
async def callback_view_trainee(callback: CallbackQuery, session: AsyncSession):
    """Обработчик просмотра детальной информации о стажере"""
    try:
        trainee_id = int(callback.data.split(":")[1])
        await show_trainee_detail(callback, session, trainee_id)
    except Exception as e:
        logger.error(f"Ошибка просмотра стажера: {e}")
        await callback.answer("Ошибка при загрузке информации о стажере", show_alert=True)


@router.callback_query(F.data == "back_to_recruiter_trainees")
async def callback_back_to_recruiter_trainees(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Обработчик возврата к списку стажеров"""
    try:
        from bot.keyboards.keyboards import get_trainees_list_keyboard

        # Получаем company_id из пользователя (надёжнее чем из state)
        user = await get_user_by_tg_id(session, callback.from_user.id)
        company_id = user.company_id if user else None
        trainees = await get_all_trainees(session, company_id)

        if not trainees:
            await callback.message.edit_text("В системе пока нет зарегистрированных Стажеров.")
            await callback.answer()
            return

        await callback.message.edit_text(
            "📋 <b>Список стажеров:</b>", parse_mode="HTML", reply_markup=get_trainees_list_keyboard(trainees, page=0)
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка возврата к списку стажеров: {e}")
        await callback.answer("Ошибка при загрузке списка", show_alert=True)


async def show_trainee_detail(callback: CallbackQuery, session: AsyncSession, trainee_id: int):
    """Показать детальную информацию о стажере"""
    from bot.database.db import get_trainee_learning_path
    from bot.keyboards.keyboards import get_trainee_detail_keyboard

    # Получаем информацию о стажере
    trainee = await get_user_by_id(session, trainee_id)
    if not trainee:
        await callback.answer("Стажер не найден", show_alert=True)
        return

    # Получаем траекторию стажера с изоляцией по компании
    company_id = trainee.company_id
    trainee_path = await get_trainee_learning_path(session, trainee_id, company_id=company_id)
    trajectory_name = trainee_path.learning_path.name if trainee_path else "не выбрано"

    # Проверяем наличие аттестации у траектории И что она ещё не назначена
    has_attestation = False
    if (
        trainee_path is not None
        and trainee_path.learning_path is not None
        and trainee_path.learning_path.attestation is not None
    ):
        # Проверяем, не назначена ли уже аттестация
        attestation_status = await get_trainee_attestation_status(
            session, trainee_id, trainee_path.learning_path.attestation.id, company_id=company_id
        )
        # Показываем кнопку только если аттестация НЕ назначена (статус ⛔️)
        has_attestation = attestation_status == "⛔️"

    # Формируем сообщение согласно ТЗ
    message_text = f"🦸🏻‍♂️ <b>Стажер:</b> {trainee.full_name}\n"
    message_text += f"<b>Траектория:</b> {trajectory_name}\n\n"
    message_text += f"<b>Телефон:</b> {trainee.phone_number}\n"
    message_text += f"<b>Username:</b> @{trainee.username or 'нет юзернейма'}\n"
    message_text += f"<b>Номер:</b> #{trainee.id}\n"
    message_text += f"<b>Дата регистрации:</b> {trainee.registration_date.strftime('%d.%m.%Y %H:%M')}\n\n"
    message_text += "━━━━━━━━━━━━\n\n"
    message_text += "🗂️ <b>Статус:</b>\n"
    message_text += f"<b>Группа:</b> {trainee.groups[0].name if trainee.groups else 'Не назначена'}\n"
    message_text += f"<b>Роль:</b> {trainee.roles[0].name if trainee.roles else 'Не назначена'}\n\n"
    message_text += "━━━━━━━━━━━━\n\n"
    message_text += "📍 <b>Объект:</b>\n"
    if trainee.roles and trainee.roles[0].name == "Стажер":
        message_text += (
            f"<b>Стажировки:</b> {trainee.internship_object.name if trainee.internship_object else 'Не указан'}\n"
        )
    message_text += f"<b>Работы:</b> {trainee.work_object.name if trainee.work_object else 'Не указан'}"

    await callback.message.edit_text(
        message_text,
        parse_mode="HTML",
        reply_markup=get_trainee_detail_keyboard(trainee_id, has_attestation=has_attestation),
    )

    log_user_action(
        callback.from_user.id, callback.from_user.username, "viewed trainee detail", {"trainee_id": trainee_id}
    )


@router.callback_query(F.data.startswith("view_trainee_progress:"))
async def callback_view_trainee_progress(callback: CallbackQuery, session: AsyncSession):
    """Обработчик просмотра прогресса стажера"""
    try:
        trainee_id = int(callback.data.split(":")[1])
        await show_trainee_progress(callback, session, trainee_id)
    except Exception as e:
        logger.error(f"Ошибка просмотра прогресса стажера: {e}")
        await callback.answer("Ошибка при загрузке прогресса стажера", show_alert=True)


@router.callback_query(F.data.startswith("back_to_trainee_detail:"))
async def callback_back_to_trainee_detail(callback: CallbackQuery, session: AsyncSession):
    """Обработчик возврата к детальному просмотру стажера"""
    try:
        trainee_id = int(callback.data.split(":")[1])
        await show_trainee_detail(callback, session, trainee_id)
    except Exception as e:
        logger.error(f"Ошибка возврата к детальному просмотру стажера: {e}")
        await callback.answer("Ошибка при загрузке информации о стажере", show_alert=True)


async def show_trainee_progress(callback: CallbackQuery, session: AsyncSession, trainee_id: int):
    """Показать прогресс стажера"""
    from bot.database.db import get_user_test_results
    from bot.keyboards.keyboards import get_trainee_progress_keyboard

    # Получаем информацию о стажере
    trainee = await get_user_by_id(session, trainee_id)
    if not trainee:
        await callback.answer("Стажер не найден", show_alert=True)
        return

    # ИЗОЛЯЦИЯ: используем company_id стажера
    company_id = trainee.company_id

    # Получаем результаты тестов
    test_results = await get_user_test_results(session, trainee_id, company_id=company_id)

    # Рассчитываем количество дней в статусе стажера
    days_as_trainee = (moscow_now() - trainee.role_assigned_date).days

    # Формируем компактное сообщение (лимит Telegram 4096 символов)
    message_text = f"🦸🏻‍♂️ <b>Стажер:</b> {trainee.full_name}\n"
    message_text += f"📞 {trainee.phone_number} | 📅 {days_as_trainee} дн.\n"
    intern_obj = trainee.internship_object.name if trainee.internship_object else "—"
    work_obj = trainee.work_object.name if trainee.work_object else "—"
    message_text += f"🏢 Стажировка: {intern_obj}\n"
    message_text += f"🏢 Работа: {work_obj}\n\n"

    # Подсчитываем статистику тестов
    total_tests = len(test_results)
    passed_tests = sum(1 for result in test_results if result.is_passed)
    success_rate = (passed_tests / total_tests * 100) if total_tests > 0 else 0.0

    message_text += "━━━━━━━━━━━━\n"
    message_text += "📊 <b>Общая статистика</b>\n\n"
    message_text += f"• Пройдено тестов: {passed_tests}/{total_tests}\n"
    message_text += f"• Процент успеха: {success_rate:.1f}%\n\n"
    message_text += "━━━━━━━━━━━━\n"
    message_text += "🧾 <b>Детальные результаты:</b>\n\n"

    if test_results:
        for result in test_results:
            test = await get_test_by_id(session, result.test_id, company_id=company_id)
            test_name = test.name if test else "?"
            icon = "✅" if result.is_passed else "❌"
            score_str = f"{int(result.score)}/{int(result.max_possible_score)}"
            date_str = result.created_date.strftime("%d.%m.%Y")
            message_text += f"{icon} {test_name} | {score_str} | {date_str}\n"
    else:
        message_text += "Нет пройденных тестов"

    await callback.message.edit_text(
        message_text, parse_mode="HTML", reply_markup=get_trainee_progress_keyboard(trainee_id)
    )

    log_user_action(
        callback.from_user.id, callback.from_user.username, "viewed trainee progress", {"trainee_id": trainee_id}
    )


# ===============================
# Открытие аттестации рекрутером (без прохождения этапов)
# ===============================


@router.callback_query(F.data.startswith("recruiter_open_attestation:"))
async def callback_recruiter_open_attestation(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Обработчик кнопки 'Открыть аттестацию' - показывает список руководителей"""
    try:
        await callback.answer()

        trainee_id = int(callback.data.split(":")[1])

        # Получаем стажера
        trainee = await get_user_by_id(session, trainee_id)
        if not trainee:
            await callback.answer("Стажер не найден", show_alert=True)
            return

        company_id = trainee.company_id

        # Получаем траекторию с аттестацией
        trainee_path = await get_trainee_learning_path(session, trainee_id, company_id=company_id)
        if not trainee_path or not trainee_path.learning_path or not trainee_path.learning_path.attestation:
            await callback.answer("У стажера нет траектории с аттестацией", show_alert=True)
            return

        attestation = trainee_path.learning_path.attestation

        # Проверяем, не назначена ли уже аттестация
        attestation_status = await get_trainee_attestation_status(
            session, trainee_id, attestation.id, company_id=company_id
        )
        if attestation_status in ["🟡", "✅"]:
            status_text = "уже назначена" if attestation_status == "🟡" else "уже пройдена"
            await callback.answer(f"Аттестация {status_text}", show_alert=True)
            return

        # Получаем список руководителей
        group_id = trainee.groups[0].id if trainee.groups else None
        managers = await get_managers_for_attestation(session, group_id, company_id=company_id)

        if not managers:
            await callback.message.edit_text(
                "❌ Нет доступных руководителей для проведения аттестации.\nОбратитесь к администратору.",
                reply_markup=InlineKeyboardMarkup(
                    inline_keyboard=[[InlineKeyboardButton(text="⬅️ Назад", callback_data=f"view_trainee:{trainee_id}")]]
                ),
            )
            return

        # Сохраняем данные в состоянии
        await state.update_data(trainee_id=trainee_id, attestation_id=attestation.id)

        # Формируем сообщение
        message_text = (
            f"🦸🏻‍♂️ <b>Стажер:</b> {trainee.full_name}\n"
            f"<b>Траектория:</b> {trainee_path.learning_path.name}\n\n"
            f"<b>Телефон:</b> {trainee.phone_number}\n"
            f"<b>Username:</b> @{trainee.username or 'не указан'}\n"
            f"<b>Номер:</b> #{trainee_id}\n\n"
            "━━━━━━━━━━━━\n\n"
            f"🏁 <b>Аттестация:</b> {attestation.name}\n\n"
            "🟡 <b>Выберите руководителя для проведения аттестации:</b>"
        )

        # Создаем клавиатуру с руководителями
        keyboard = []
        for manager in managers:
            keyboard.append(
                [
                    InlineKeyboardButton(
                        text=f"{manager.full_name}", callback_data=f"recruiter_select_manager:{manager.id}"
                    )
                ]
            )

        keyboard.append([InlineKeyboardButton(text="⬅️ Назад", callback_data=f"view_trainee:{trainee_id}")])

        await callback.message.edit_text(
            message_text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
        )

        await state.set_state(RecruiterAttestationStates.selecting_manager)
        log_user_action(
            callback.from_user.id,
            callback.from_user.username,
            "recruiter_open_attestation_started",
            {"trainee_id": trainee_id},
        )

    except Exception as e:
        logger.error(f"Ошибка открытия меню аттестации рекрутером: {e}")
        await callback.answer("Произошла ошибка", show_alert=True)


@router.callback_query(F.data.startswith("recruiter_select_manager:"))
async def callback_recruiter_select_manager(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Обработчик выбора руководителя для аттестации рекрутером"""
    try:
        await callback.answer()

        manager_id = int(callback.data.split(":")[1])

        # Получаем данные из состояния
        state_data = await state.get_data()
        trainee_id = state_data.get("trainee_id")
        attestation_id = state_data.get("attestation_id")

        if not trainee_id or not attestation_id:
            await callback.message.edit_text("Ошибка: данные не найдены в состоянии")
            await state.clear()
            return

        # Получаем данные
        trainee = await get_user_by_id(session, trainee_id)
        manager = await get_user_by_id(session, manager_id)
        company_id = trainee.company_id if trainee else None
        attestation = await get_attestation_by_id(session, attestation_id, company_id=company_id)
        trainee_path = await get_trainee_learning_path(session, trainee_id, company_id=company_id)

        if not trainee or not manager or not attestation:
            await callback.message.edit_text("Ошибка: данные не найдены")
            await state.clear()
            return

        # Сохраняем выбранного руководителя
        await state.update_data(manager_id=manager_id)

        # Формируем сообщение подтверждения
        confirmation_text = (
            f"🦸🏻‍♂️ <b>Стажер:</b> {trainee.full_name}\n"
            f"<b>Траектория:</b> {trainee_path.learning_path.name if trainee_path else 'не выбрана'}\n\n"
            f"<b>Телефон:</b> {trainee.phone_number}\n"
            f"<b>Username:</b> @{trainee.username or 'не указан'}\n"
            f"<b>Номер:</b> #{trainee_id}\n\n"
            "━━━━━━━━━━━━\n\n"
            "🗂️ <b>Статус:</b>\n"
            f"<b>Группа:</b> {', '.join([group.name for group in trainee.groups]) if trainee.groups else 'Не указана'}\n"
            f"<b>Роль:</b> {', '.join([role.name for role in trainee.roles])}\n\n"
            "━━━━━━━━━━━━\n\n"
            f"🏁 <b>Аттестация:</b> {attestation.name}\n"
            f"🟢 <b>Руководитель:</b> {manager.full_name}\n\n"
            "🟡 <b>Открыть аттестацию для стажера?</b>\n\n"
            "<i>Стажер сможет пройти аттестацию без прохождения этапов траектории</i>"
        )

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text="✅ Да, открыть", callback_data="recruiter_confirm_attestation"),
                    InlineKeyboardButton(text="❌ Отмена", callback_data=f"recruiter_open_attestation:{trainee_id}"),
                ]
            ]
        )

        await callback.message.edit_text(confirmation_text, parse_mode="HTML", reply_markup=keyboard)

        await state.set_state(RecruiterAttestationStates.confirming_assignment)
        log_user_action(
            callback.from_user.id,
            callback.from_user.username,
            "recruiter_manager_selected",
            {"manager_id": manager_id, "trainee_id": trainee_id},
        )

    except Exception as e:
        logger.error(f"Ошибка выбора руководителя рекрутером: {e}")
        await callback.answer("Произошла ошибка при выборе руководителя", show_alert=True)


@router.callback_query(F.data == "recruiter_confirm_attestation")
async def callback_recruiter_confirm_attestation(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Обработчик подтверждения назначения аттестации рекрутером"""
    try:
        await callback.answer()

        # Получаем данные из состояния
        state_data = await state.get_data()
        trainee_id = state_data.get("trainee_id")
        attestation_id = state_data.get("attestation_id")
        manager_id = state_data.get("manager_id")

        if not trainee_id or not attestation_id or not manager_id:
            await callback.message.edit_text("Ошибка: данные не найдены в состоянии")
            await state.clear()
            return

        # Получаем данные
        trainee = await get_user_by_id(session, trainee_id)
        manager = await get_user_by_id(session, manager_id)
        recruiter = await get_user_by_tg_id(session, callback.from_user.id)

        if not trainee or not manager or not recruiter:
            await callback.message.edit_text("Ошибка: данные не найдены")
            await state.clear()
            return

        company_id = trainee.company_id
        attestation = await get_attestation_by_id(session, attestation_id, company_id=company_id)
        trainee_path = await get_trainee_learning_path(session, trainee_id, company_id=company_id)

        if not attestation:
            await callback.message.edit_text("Ошибка: аттестация не найдена")
            await state.clear()
            return

        # Назначаем аттестацию (assigned_by_id = recruiter.id)
        result = await assign_attestation_to_trainee(
            session=session,
            trainee_id=trainee_id,
            manager_id=manager_id,
            attestation_id=attestation_id,
            assigned_by_id=recruiter.id,
            company_id=company_id,
        )

        if not result:
            await callback.message.edit_text(
                "❌ Не удалось назначить аттестацию. Попробуйте позже.",
                reply_markup=InlineKeyboardMarkup(
                    inline_keyboard=[[InlineKeyboardButton(text="⬅️ Назад", callback_data=f"view_trainee:{trainee_id}")]]
                ),
            )
            await state.clear()
            return

        await session.commit()

        # Формируем сообщение об успехе
        success_text = (
            f"✅ <b>Аттестация открыта!</b>\n\n"
            f"🦸🏻‍♂️ <b>Стажер:</b> {trainee.full_name}\n"
            f"🏁 <b>Аттестация:</b> {attestation.name}\n"
            f"👨‍💼 <b>Руководитель:</b> {manager.full_name}\n\n"
            "Стажер и руководитель получили уведомления."
        )

        await callback.message.edit_text(
            success_text,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="⬅️ К стажеру", callback_data=f"view_trainee:{trainee_id}")],
                    [InlineKeyboardButton(text="📋 К списку стажеров", callback_data="back_to_recruiter_trainees")],
                ]
            ),
        )

        # Отправляем уведомление стажеру
        await send_attestation_notification_to_trainee(callback.bot, trainee, attestation, manager, trainee_path)

        # Отправляем уведомление руководителю
        await send_attestation_notification_to_manager(callback.bot, trainee, attestation, manager, recruiter)

        await state.clear()
        log_user_action(
            callback.from_user.id,
            callback.from_user.username,
            "recruiter_attestation_assigned",
            {"trainee_id": trainee_id, "attestation_id": attestation_id, "manager_id": manager_id},
        )

    except Exception as e:
        logger.error(f"Ошибка подтверждения аттестации рекрутером: {e}")
        await callback.answer("Произошла ошибка при назначении аттестации", show_alert=True)
        await state.clear()


async def send_attestation_notification_to_trainee(bot, trainee, attestation, manager, trainee_path):
    """Отправка уведомления стажеру об открытии аттестации"""
    try:
        notification_text = (
            f"🎉 <b>Тебе открыта аттестация!</b>\n\n"
            f"🏁 <b>Аттестация:</b> {attestation.name}\n"
            f"👨‍💼 <b>Руководитель:</b> {manager.full_name}\n"
            f"📚 <b>Траектория:</b> {trainee_path.learning_path.name if trainee_path else 'не указана'}\n\n"
            "❗️ <b>Свяжись с руководителем, чтобы согласовать дату и время аттестации</b>"
        )

        await bot.send_message(chat_id=trainee.tg_id, text=notification_text, parse_mode="HTML")
        logger.info(f"Уведомление об аттестации отправлено стажеру {trainee.id}")
    except Exception as e:
        logger.error(f"Ошибка отправки уведомления стажеру {trainee.id}: {e}")


async def send_attestation_notification_to_manager(bot, trainee, attestation, manager, recruiter):
    """Отправка уведомления руководителю о назначении стажера на аттестацию"""
    try:
        notification_text = (
            f"📋 <b>Новое назначение на аттестацию</b>\n\n"
            f"🦸🏻‍♂️ <b>Стажер:</b> {trainee.full_name}\n"
            f"📞 <b>Телефон:</b> {trainee.phone_number}\n"
            f"🏁 <b>Аттестация:</b> {attestation.name}\n"
            f"👤 <b>Назначил:</b> {recruiter.full_name} (рекрутер)\n\n"
            "• Стажер готов к прохождению аттестации\n"
            "• Свяжитесь со стажером для согласования даты"
        )

        await bot.send_message(chat_id=manager.tg_id, text=notification_text, parse_mode="HTML")
        logger.info(f"Уведомление об аттестации отправлено руководителю {manager.id}")
    except Exception as e:
        logger.error(f"Ошибка отправки уведомления руководителю {manager.id}: {e}")
