from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime

from database.db import (
    get_all_users, get_user_by_id, get_all_roles, 
    add_user_role, remove_user_role, get_user_roles, get_all_trainees,
    get_user_by_tg_id, check_user_permission, get_trainee_mentor,
    get_user_test_results, get_test_by_id
)
from keyboards.keyboards import (
    get_user_selection_keyboard, get_user_action_keyboard, 
    get_role_change_keyboard, get_confirmation_keyboard
)
from states.states import AdminStates
from utils.logger import log_user_action, log_user_error, logger
from handlers.auth import check_auth

router = Router()


async def check_admin_permission(message: Message, state: FSMContext, session: AsyncSession, permission: str = "manage_users") -> bool:
    """Проверяет, имеет ли пользователь указанное право доступа """

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
    company_id = data.get('company_id')
    users = await get_all_users(session, company_id)
    
    if not users:
        await message.answer("В системе пока нет зарегистрированных пользователей.")
        return
    

    keyboard = get_user_selection_keyboard(users)
    
    await message.answer(
        "Выбери пользователя для управления:",
        reply_markup=keyboard
    )
    
    await state.set_state(AdminStates.waiting_for_user_selection)
    
    log_user_action(message.from_user.id, message.from_user.username, "opened user management panel")


@router.callback_query(AdminStates.waiting_for_user_selection, F.data.startswith("user:"))
async def process_user_selection(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Обработчик выбора пользователя из списка"""
    user_id = int(callback.data.split(':')[1])
    
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
        company_id = data.get('company_id')
        mentor = await get_trainee_mentor(session, user.id, company_id=company_id)
        results = await get_user_test_results(session, user.id, company_id=company_id)
        passed_count = sum(1 for r in results if r.is_passed)
        avg_score = sum(r.score for r in results) / len(results) if results else 0
        
        extra_info = f"""
    <b>Статистика стажера:</b>
    👨‍🏫 Наставник: {mentor.full_name if mentor else 'Не назначен'}
    ✅ Пройдено тестов: {passed_count}/{len(results)}
    📊 Средний балл: {avg_score:.1f}
    """

    user_info = f"""
    👤 <b>Информация о пользователе</b>
    
    🧑 ФИО: {user.full_name}
    📞 Телефон: {user.phone_number}
    🆔 Telegram ID: {user.tg_id}
    👤 Username: @{user.username or "не указан"}
    📅 Дата регистрации: {user.registration_date.strftime('%d.%m.%Y %H:%M')}
    👑 Роли: {roles_str}
    {extra_info}
    """

    keyboard = get_user_action_keyboard(user.id)

    await callback.message.edit_text(
        user_info,
        reply_markup=keyboard,
        parse_mode="HTML"
    )

    await state.set_state(AdminStates.waiting_for_user_action)
    await state.update_data(selected_user_id=user.id)

    await callback.answer()
    
    log_user_action(
        callback.from_user.id, 
        callback.from_user.username, 
        "selected user for management", 
        {"selected_user_id": user.id}
    )

@router.callback_query(AdminStates.waiting_for_user_action, F.data.startswith("change_role:"))
async def process_change_role(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Обработчик кнопки изменения роли пользователя"""
    user_id = int(callback.data.split(':')[1])
    
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
    
    await callback.message.edit_text(
        f"Выбери новую роль для пользователя {user.full_name}:",
        reply_markup=keyboard
    )

    await state.set_state(AdminStates.waiting_for_role_change)

    await callback.answer()
    
    log_user_action(
        callback.from_user.id, 
        callback.from_user.username, 
        "opened role change menu", 
        {"target_user_id": user.id}
    )


@router.callback_query(AdminStates.waiting_for_role_change, F.data.startswith("set_role:"))
async def process_set_role(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Обработчик выбора новой роли для пользователя"""
    # Извлекаем данные из callback
    parts = callback.data.split(':')
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
        reply_markup=get_confirmation_keyboard(user.id, role_name, action)
    )

    await state.set_state(AdminStates.waiting_for_confirmation)
    await state.update_data(
        user_id=user.id, 
        role_name=role_name, 
        action=action,
        current_roles=current_role_names
    )

    await callback.answer()
    
    log_user_action(
        callback.from_user.id, 
        callback.from_user.username, 
        f"requested role change confirmation", 
        {"target_user_id": user.id, "role": role_name, "action": action}
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
            parse_mode="HTML"
        )
        await callback.answer()
        return
    
    parts = callback.data.split(':')
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
            f"✅ Роль '{role_name}' успешно {action_text} для пользователя {user.full_name}.\n"
            f"Текущие роли: {roles_str}"
        )
        
        log_user_action(
            callback.from_user.id, 
            callback.from_user.username, 
            f"role {action} confirmed", 
            {"target_user_id": user.id, "role": role_name}
        )
    else:
        await callback.message.answer(f"❌ Не удалось изменить роль для пользователя {user.full_name}.")
        log_user_error(
            callback.from_user.id, 
            callback.from_user.username, 
            "role change failed", 
            {"target_user_id": user.id, "role": role_name, "action": action}
        )

    await show_user_list(callback.message, state, session)

    await callback.answer()


@router.callback_query(F.data.startswith("cancel_role_change:"))
async def process_cancel_role_change(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Обработчик отмены изменения роли"""
    user_id = int(callback.data.split(':')[1])
    
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
        📅 Дата регистрации: {user.registration_date.strftime('%d.%m.%Y %H:%M')}
        👑 Роли: {roles_str}
        """

        await callback.message.edit_text(
            user_info,
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        
        await state.set_state(AdminStates.waiting_for_user_action)
    else:
        await show_user_list(callback.message, state, session)
    
    await callback.answer()
    
    log_user_action(
        callback.from_user.id, 
        callback.from_user.username, 
        "cancelled role change", 
        {"target_user_id": user_id, "role": role_name}
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
    user_id = int(callback.data.split(':')[1])

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
    📅 Дата регистрации: {user.registration_date.strftime('%d.%m.%Y %H:%M')}
    👑 Роли: {roles_str}
    """

    keyboard = get_user_action_keyboard(user.id)

    await callback.message.edit_text(
        user_info,
        reply_markup=keyboard,
        parse_mode="HTML"
    )

    await callback.answer()
    
    log_user_action(
        callback.from_user.id, 
        callback.from_user.username, 
        "viewed user profile", 
        {"viewed_user_id": user.id}
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
    from keyboards.keyboards import get_trainees_list_keyboard
    
    data = await state.get_data()
    company_id = data.get('company_id')
    trainees = await get_all_trainees(session, company_id)
    
    if not trainees:
        await message.answer("В системе пока нет зарегистрированных Стажеров.")
        return

    await message.answer(
        "📋 <b>Список стажеров:</b>",
        parse_mode="HTML",
        reply_markup=get_trainees_list_keyboard(trainees, page=page)
    )
    
    log_user_action(message.from_user.id, message.from_user.username, "viewed trainees list")


@router.callback_query(F.data.startswith("trainees_page:"))
async def callback_trainees_page(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Обработчик пагинации списка стажеров"""
    try:
        from keyboards.keyboards import get_trainees_list_keyboard
        
        page = int(callback.data.split(":")[1])
        data = await state.get_data()
        company_id = data.get('company_id')
        trainees = await get_all_trainees(session, company_id)
        
        if not trainees:
            await callback.message.edit_text("В системе пока нет зарегистрированных Стажеров.")
            await callback.answer()
            return

        await callback.message.edit_text(
            "📋 <b>Список стажеров:</b>",
            parse_mode="HTML",
            reply_markup=get_trainees_list_keyboard(trainees, page=page)
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
        from keyboards.keyboards import get_trainees_list_keyboard
        
        data = await state.get_data()
        company_id = data.get('company_id')
        trainees = await get_all_trainees(session, company_id)
        
        if not trainees:
            await callback.message.edit_text("В системе пока нет зарегистрированных Стажеров.")
            await callback.answer()
            return

        await callback.message.edit_text(
            "📋 <b>Список стажеров:</b>",
            parse_mode="HTML",
            reply_markup=get_trainees_list_keyboard(trainees, page=0)
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка возврата к списку стажеров: {e}")
        await callback.answer("Ошибка при загрузке списка", show_alert=True)


async def show_trainee_detail(callback: CallbackQuery, session: AsyncSession, trainee_id: int):
    """Показать детальную информацию о стажере"""
    from keyboards.keyboards import get_trainee_detail_keyboard
    from database.db import get_trainee_learning_path
    
    # Получаем информацию о стажере
    trainee = await get_user_by_id(session, trainee_id)
    if not trainee:
        await callback.answer("Стажер не найден", show_alert=True)
        return
    
    # Получаем траекторию стажера с изоляцией по компании
    company_id = trainee.company_id
    trainee_path = await get_trainee_learning_path(session, trainee_id, company_id=company_id)
    trajectory_name = trainee_path.learning_path.name if trainee_path else "не выбрано"
    
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
        message_text += f"<b>Стажировки:</b> {trainee.internship_object.name if trainee.internship_object else 'Не указан'}\n"
    message_text += f"<b>Работы:</b> {trainee.work_object.name if trainee.work_object else 'Не указан'}"
    
    await callback.message.edit_text(
        message_text,
        parse_mode="HTML",
        reply_markup=get_trainee_detail_keyboard(trainee_id)
    )
    
    log_user_action(callback.from_user.id, callback.from_user.username, "viewed trainee detail", {"trainee_id": trainee_id})


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
    from keyboards.keyboards import get_trainee_progress_keyboard
    from database.db import get_user_test_results, get_test_by_id
    
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
    days_as_trainee = (datetime.now() - trainee.role_assigned_date).days
    
    # Формируем сообщение согласно ТЗ
    message_text = f"🦸🏻‍♂️<b>Стажер:</b> {trainee.full_name}\n\n"
    message_text += f"<b>Телефон:</b> {trainee.phone_number}\n"
    message_text += f"<b>В статусе стажера:</b> {days_as_trainee} дней\n"
    message_text += f"<b>Объект стажировки:</b> {trainee.internship_object.name if trainee.internship_object else 'Не указан'}\n"
    message_text += f"<b>Объект работы:</b> {trainee.work_object.name if trainee.work_object else 'Не указан'}\n\n"
    message_text += "━━━━━━━━━━━━\n\n"
    message_text += "📊 <b>Общая статистика</b>\n"
    
    # Подсчитываем статистику тестов
    total_tests = len(test_results)
    passed_tests = sum(1 for result in test_results if result.is_passed)
    success_rate = (passed_tests / total_tests * 100) if total_tests > 0 else 0.0
    
    message_text += f"• <b>Пройдено тестов:</b> {passed_tests}/{total_tests}\n"
    message_text += f"• <b>Процент успеха:</b> {success_rate:.1f}%\n\n"
    
    message_text += "🧾 <b>Детальные результаты</b>\n"
    
    if test_results:
        for result in test_results:
            # Получаем информацию о тесте с изоляцией
            test = await get_test_by_id(session, result.test_id, company_id=company_id)
            test_name = test.name if test else "Неизвестный тест"
            
            # Рассчитываем процент
            percentage = (result.score / result.max_possible_score * 100) if result.max_possible_score > 0 else 0.0
            
            # Статус
            status = "пройден" if result.is_passed else "не пройден"
            
            # Время выполнения
            if result.start_time and result.end_time:
                time_spent = int((result.end_time - result.start_time).total_seconds())
                time_str = f"{time_spent} сек"
            else:
                time_str = "неизвестно"
            
            message_text += f"<b>Тест:</b> {test_name}\n"
            message_text += f"• <b>Баллы:</b> {result.score:.1f}/{result.max_possible_score:.1f} ({percentage:.1f}%)\n"
            message_text += f"• <b>Статус:</b> {status}\n"
            message_text += f"• <b>Дата:</b> {result.created_date.strftime('%d.%m.%Y %H:%M')}\n"
            message_text += f"• <b>Время:</b> {time_str}\n\n"
    else:
        message_text += "Нет пройденных тестов\n\n"
    
    await callback.message.edit_text(
        message_text,
        parse_mode="HTML",
        reply_markup=get_trainee_progress_keyboard(trainee_id)
    )
    
    log_user_action(callback.from_user.id, callback.from_user.username, "viewed trainee progress", {"trainee_id": trainee_id}) 