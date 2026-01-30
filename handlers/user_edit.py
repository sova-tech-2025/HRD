from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.filters import StateFilter
from sqlalchemy.ext.asyncio import AsyncSession

from database.db import (
    check_user_permission, get_all_activated_users, get_users_by_group, get_users_by_object,
    get_user_with_details, get_user_by_id, get_user_by_tg_id, get_user_by_phone,
    update_user_full_name, update_user_phone_number, update_user_role,
    update_user_group, update_user_groups, update_user_internship_object, update_user_work_object,
    get_all_groups, get_all_objects, get_object_by_id, get_group_by_id, get_user_roles,
    get_role_change_warnings, delete_user, search_activated_users_by_name, ensure_company_id
)
from handlers.auth import check_auth
from states.states import UserEditStates
from keyboards.keyboards import (
    get_user_editor_keyboard, get_edit_confirmation_keyboard,
    get_role_selection_keyboard, get_group_selection_keyboard,
    get_object_selection_keyboard, get_users_filter_keyboard,
    get_group_filter_keyboard, get_object_filter_keyboard,
    get_users_list_keyboard, get_user_info_keyboard,
    get_user_deletion_confirmation_keyboard, get_user_groups_multiselect_keyboard
)
from utils.logger import log_user_action, log_user_error
from utils.validators import validate_full_name, validate_phone_number

router = Router()


def format_user_groups(user) -> str:
    """Форматирование списка групп пользователя для отображения.

    Args:
        user: Объект пользователя с загруженными группами

    Returns:
        Строка с названиями групп через запятую или 'Нет группы'
    """
    if user.groups:
        return ", ".join(g.name for g in user.groups)
    return "Нет группы"


def get_groups_label(user) -> str:
    """Возвращает 'Группа' или 'Группы' в зависимости от количества групп."""
    if user.groups and len(user.groups) > 1:
        return "Группы"
    return "Группа"


async def show_user_info_detail(callback: CallbackQuery, user_id: int, session: AsyncSession, filter_type: str = "all", company_id: int = None):
    """Общая функция для отображения детальной информации о пользователе"""
    user = await get_user_with_details(session, user_id, company_id=company_id)
    if not user:
        await callback.answer("Пользователь не найден", show_alert=True)
        return False
    
    # Формируем информацию о пользователе
    role_name = user.roles[0].name if user.roles else "Нет роли"
    group_name = format_user_groups(user)
    groups_label = get_groups_label(user)

    text = (
        f"🦸🏻‍♂️ <b>Пользователь:</b> {user.full_name}\n\n"
        f"<b>Телефон:</b> {user.phone_number}\n"
        f"<b>Username:</b> @{user.username if user.username else 'Не указан'}\n"
        f"<b>Номер:</b> #{user.id}\n"
        f"<b>Дата регистрации:</b> {user.registration_date.strftime('%d.%m.%Y %H:%M') if user.registration_date else 'Не указана'}\n\n"
        f"━━━━━━━━━━━━\n\n"
        f"🗂️ <b>Статус:</b>\n"
        f"<b>{groups_label}:</b> {group_name}\n"
        f"<b>Роль:</b> {role_name}\n\n"
        f"━━━━━━━━━━━━\n\n"
        f"📍 <b>Объект:</b>\n"
    )
    
    if role_name in ["Стажер", "Стажёр"]:
        if user.internship_object:
            text += f"<b>Стажировки:</b> {user.internship_object.name}\n"
        else:
            text += f"<b>Стажировки:</b> Не указан\n"
    
    if user.work_object:
        text += f"<b>Работы:</b> {user.work_object.name}\n"
    else:
        text += f"<b>Работы:</b> Не указан\n"
    
    keyboard = get_user_info_keyboard(user_id, filter_type)
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    return True


@router.message(F.text.in_(["Все пользователи", "Все пользователи 🚸"]))
async def cmd_all_users(message: Message, session: AsyncSession, state: FSMContext):
    """Отображение фильтров для выбора пользователей"""
    # Проверяем авторизацию
    is_auth = await check_auth(message, state, session)
    if not is_auth:
        return

    # Получаем пользователя и проверяем права
    user = await get_user_by_tg_id(session, message.from_user.id)
    if not user:
        await message.answer("Пользователь не найден")
        return

    if not await check_user_permission(session, user.id, "manage_groups"):
        await message.answer("❌ У тебя нет прав для управления пользователями")
        log_user_error(message.from_user.id, "all_users_access_denied", "Insufficient permissions")
        return
        
    # Получение company_id из контекста (добавлен CompanyMiddleware)
    company_id = await ensure_company_id(session, state, message.from_user.id)
    # Получаем группы и объекты для фильтров
    groups = await get_all_groups(session, company_id)
    objects = await get_all_objects(session, company_id)
    
    # Проверяем, есть ли пользователи вообще
    users = await get_all_activated_users(session, company_id=company_id)
    if not users:
        await message.answer("📭 Нет активированных пользователей в системе")
        return
        
    text = (
        f"<b>🚸 Всего пользователей в системе: {len(users)}</b>\n"
        f"Доступно групп: {len(groups)}\n"
        f"Доступно объектов: {len(objects)}\n\n"
        "Выбери способ фильтрации пользователей:"
    )
    
    keyboard = get_users_filter_keyboard(groups, objects)
    
    await message.answer(text, reply_markup=keyboard, parse_mode="HTML")
    await state.set_state(UserEditStates.waiting_for_filter_selection)
    
    log_user_action(message.from_user.id, "opened_user_filters", f"Available: {len(users)} users, {len(groups)} groups, {len(objects)} objects")


# ===================== НОВЫЕ ОБРАБОТЧИКИ ФИЛЬТРАЦИИ =====================

@router.callback_query(F.data == "filter_all_users", UserEditStates.waiting_for_filter_selection)
async def callback_filter_all_users(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Показать всех пользователей без фильтрации"""
    try:
        await callback.answer()
        
        data = await state.get_data()
        company_id = data.get('company_id')
        users = await get_all_activated_users(session, company_id=company_id)
        
        if not users:
            await callback.message.edit_text("📭 Нет активированных пользователей в системе")
            return
        
        text = (
            f"<b>Найдено пользователей: {len(users)}</b>\n\n"
            "Выбери пользователя для просмотра и редактирования:"
        )
        
        keyboard = get_users_list_keyboard(users, 0, 5, "all")
        
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
        await state.set_state(UserEditStates.waiting_for_user_selection)
        await state.update_data(current_users=users, filter_type="all", current_page=0)
        
        log_user_action(callback.from_user.id, "filter_all_users", f"Showing {len(users)} users")
        
    except Exception as e:
        await callback.answer("Произошла ошибка")
        log_user_error(callback.from_user.id, "filter_all_users_error", str(e))


@router.callback_query(F.data == "filter_by_groups", UserEditStates.waiting_for_filter_selection)
async def callback_filter_by_groups(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Показать фильтр по группам"""
    try:
        await callback.answer()
        
        # Получение company_id из контекста (добавлен CompanyMiddleware)
        company_id = await ensure_company_id(session, state, callback.from_user.id)
        groups = await get_all_groups(session, company_id)
        
        if not groups:
            await callback.message.edit_text("📭 Нет доступных групп для фильтрации")
            return
        
        text = (
            f"🗂️ <b>ФИЛЬТР ПО ГРУППАМ</b> 🗂️\n\n"
            f"📊 Доступно групп: <b>{len(groups)}</b>\n\n"
            "Выбери группу, чтобы посмотреть пользователей:"
        )
        
        keyboard = get_group_filter_keyboard(groups, 0, 5)
        
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
        await state.update_data(available_groups=groups, filter_page=0)
        
        log_user_action(callback.from_user.id, "opened_group_filter", f"Available {len(groups)} groups")
        
    except Exception as e:
        await callback.answer("Произошла ошибка")
        log_user_error(callback.from_user.id, "filter_by_groups_error", str(e))


@router.callback_query(F.data == "filter_by_objects", UserEditStates.waiting_for_filter_selection)
async def callback_filter_by_objects(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Показать фильтр по объектам"""
    try:
        await callback.answer()
        
        # Получение company_id из контекста (добавлен CompanyMiddleware)
        company_id = await ensure_company_id(session, state, callback.from_user.id)
        objects = await get_all_objects(session, company_id)
        
        if not objects:
            await callback.message.edit_text("📭 Нет доступных объектов для фильтрации")
            return
        
        text = (
            f"📍 <b>ФИЛЬТР ПО ОБЪЕКТАМ</b> 📍\n\n"
            f"📊 Доступно объектов: <b>{len(objects)}</b>\n\n"
            "Выбери объект для просмотра связанных с ним пользователей:"
        )
        
        keyboard = get_object_filter_keyboard(objects, 0, 5)
        
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
        await state.update_data(available_objects=objects, filter_page=0)
        
        log_user_action(callback.from_user.id, "opened_object_filter", f"Available {len(objects)} objects")
        
    except Exception as e:
        await callback.answer("Произошла ошибка")
        log_user_error(callback.from_user.id, "filter_by_objects_error", str(e))


@router.callback_query(F.data.startswith("filter_group:"), UserEditStates.waiting_for_filter_selection)
async def callback_filter_group(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Показать пользователей выбранной группы"""
    try:
        await callback.answer()
        
        user = await get_user_by_tg_id(session, callback.from_user.id)
        if not user:
            await callback.answer("❌ Ты не зарегистрирован в системе.", show_alert=True)
            return
        
        group_id = int(callback.data.split(":")[1])
        group = await get_group_by_id(session, group_id, company_id=user.company_id)
        
        if not group:
            await callback.answer("Группа не найдена", show_alert=True)
            return
        
        users = await get_users_by_group(session, group_id, company_id=user.company_id)
        
        text = (
            f"🗂️ <b>ГРУППА: {group.name}</b> 🗂️\n\n"
            f"📊 Пользователей в группе: <b>{len(users)}</b>\n\n"
        )
        
        if users:
            text += "Выбери пользователя для просмотра и редактирования:"
            keyboard = get_users_list_keyboard(users, 0, 5, f"group:{group_id}")
            await state.set_state(UserEditStates.waiting_for_user_selection)
            await state.update_data(current_users=users, filter_type=f"group:{group_id}", current_page=0)
        else:
            text += "В данной группе пока нет пользователей."
            company_id = await ensure_company_id(session, state, callback.from_user.id)
            keyboard = get_users_filter_keyboard(await get_all_groups(session, company_id), await get_all_objects(session, company_id))
            await state.set_state(UserEditStates.waiting_for_filter_selection)
        
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
        
        log_user_action(callback.from_user.id, "filter_by_group", f"Group: {group.name}, Users: {len(users)}")
        
    except Exception as e:
        await callback.answer("Произошла ошибка")
        log_user_error(callback.from_user.id, "filter_group_error", str(e))


@router.callback_query(F.data.startswith("filter_object:"), UserEditStates.waiting_for_filter_selection)
async def callback_filter_object(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Показать пользователей выбранного объекта"""
    try:
        await callback.answer()
        
        user = await get_user_by_tg_id(session, callback.from_user.id)
        if not user:
            await callback.answer("❌ Ты не зарегистрирован в системе.", show_alert=True)
            return
        
        object_id = int(callback.data.split(":")[1])
        obj = await get_object_by_id(session, object_id, company_id=user.company_id)
        
        if not obj:
            await callback.answer("Объект не найден", show_alert=True)
            return
        
        users = await get_users_by_object(session, object_id, company_id=user.company_id)
        
        text = (
            f"📍 <b>ОБЪЕКТ: {obj.name}</b> 📍\n\n"
            f"📊 Пользователей на объекте: <b>{len(users)}</b>\n\n"
        )
        
        if users:
            text += "Выбери пользователя для просмотра и редактирования:"
            keyboard = get_users_list_keyboard(users, 0, 5, f"object:{object_id}")
            await state.set_state(UserEditStates.waiting_for_user_selection)
            await state.update_data(current_users=users, filter_type=f"object:{object_id}", current_page=0)
        else:
            text += "К данному объекту пока не привязаны пользователи."
            company_id = await ensure_company_id(session, state, callback.from_user.id)
            keyboard = get_users_filter_keyboard(await get_all_groups(session, company_id), await get_all_objects(session, company_id))
            await state.set_state(UserEditStates.waiting_for_filter_selection)
        
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
        
        log_user_action(callback.from_user.id, "filter_by_object", f"Object: {obj.name}, Users: {len(users)}")
        
    except Exception as e:
        await callback.answer("Произошла ошибка")
        log_user_error(callback.from_user.id, "filter_object_error", str(e))


# ===================== ОБРАБОТЧИКИ ПОИСКА ПО ФИО =====================

@router.callback_query(F.data == "search_all_users", UserEditStates.waiting_for_filter_selection)
async def callback_start_search_all_users(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Начать поиск пользователей по ФИО"""
    try:
        await callback.answer()
        
        await callback.message.edit_text(
            "🔍 <b>Поиск пользователей</b>\n\n"
            "Введи ФИО для поиска (минимум 2 символа):",
            parse_mode="HTML"
        )
        
        await state.set_state(UserEditStates.waiting_for_search_query)
        await state.update_data(search_context='all_users')
        
        log_user_action(callback.from_user.id, "start_search_all_users", "Search initiated")
        
    except Exception as e:
        await callback.answer("Произошла ошибка")
        log_user_error(callback.from_user.id, "start_search_error", str(e))


@router.message(UserEditStates.waiting_for_search_query)
async def process_search_query_all_users(message: Message, state: FSMContext, session: AsyncSession):
    """Обработка поискового запроса для всех пользователей"""
    try:
        query = message.text.strip()
        
        # Валидация: минимум 2 символа
        if len(query) < 2:
            await message.answer(
                "❌ Запрос слишком короткий\n\n"
                "Пожалуйста, введи минимум 2 символа для поиска:",
                parse_mode="HTML"
            )
            return
        
        # Выполняем поиск
        data = await state.get_data()
        company_id = data.get('company_id')
        users = await search_activated_users_by_name(session, query, company_id=company_id)
        
        if not users:
            # Пользователи не найдены
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Повторить поиск", callback_data="retry_search_all_users")],
                [InlineKeyboardButton(text="↩️ Назад к фильтрам", callback_data="back_to_filters")]
            ])
            
            await message.answer(
                f"🔍 <b>Результаты поиска</b>\n\n"
                f"По запросу <b>'{query}'</b> ничего не найдено.\n\n"
                "Попробуй изменить запрос или вернись к фильтрам.",
                reply_markup=keyboard,
                parse_mode="HTML"
            )
            
            log_user_action(message.from_user.id, "search_all_users_no_results", f"Query: '{query}'")
            return
        
        # Пользователи найдены - показываем с пагинацией
        text = (
            f"🔍 <b>Результаты поиска: '{query}'</b>\n\n"
            f"📊 <b>Найдено пользователей:</b> {len(users)}\n\n"
            "Выбери пользователя для просмотра и редактирования:"
        )
        
        keyboard = get_users_list_keyboard(users, 0, 5, "search")
        
        await message.answer(text, reply_markup=keyboard, parse_mode="HTML")
        
        await state.set_state(UserEditStates.waiting_for_user_selection)
        await state.update_data(current_users=users, filter_type="search", search_query=query, current_page=0)
        
        log_user_action(message.from_user.id, "search_all_users_success", f"Query: '{query}', Found: {len(users)}")
        
    except Exception as e:
        await message.answer("❌ Произошла ошибка при поиске. Попробуй еще раз.")
        log_user_error(message.from_user.id, "search_query_error", str(e))


@router.callback_query(F.data == "retry_search_all_users")
async def callback_retry_search_all_users(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Повторить поиск пользователей"""
    try:
        await callback.answer()
        
        await callback.message.edit_text(
            "🔍 <b>Поиск пользователей</b>\n\n"
            "Введи ФИО для поиска (минимум 2 символа):",
            parse_mode="HTML"
        )
        
        await state.set_state(UserEditStates.waiting_for_search_query)
        await state.update_data(search_context='all_users')
        
    except Exception as e:
        await callback.answer("Произошла ошибка")
        log_user_error(callback.from_user.id, "retry_search_error", str(e))


@router.callback_query(F.data.startswith("view_user:"), UserEditStates.waiting_for_user_selection)
async def callback_view_user(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Просмотр информации о пользователе"""
    try:
        await callback.answer()
        
        user_id = int(callback.data.split(":")[1])
        
        data = await state.get_data()
        filter_type = data.get('filter_type', 'all')
        
        # Используем общую функцию для отображения информации
        data = await state.get_data()
        company_id = data.get('company_id')
        success = await show_user_info_detail(callback, user_id, session, filter_type, company_id=company_id)
        
        if success:
            await state.set_state(UserEditStates.viewing_user_info)
            await state.update_data(viewing_user_id=user_id)
            
            user = await get_user_by_id(session, user_id)
            log_user_action(callback.from_user.id, "view_user_info", f"User: {user.full_name if user else 'Unknown'} (ID: {user_id})")
        
    except Exception as e:
        await callback.answer("Произошла ошибка")
        log_user_error(callback.from_user.id, "view_user_error", str(e))


@router.callback_query(F.data.startswith("edit_user:"), UserEditStates.viewing_user_info)
async def callback_edit_user(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Переход к редактированию пользователя"""
    try:
        await callback.answer()
        
        user_id = int(callback.data.split(":")[1])
        data = await state.get_data()
        company_id = data.get('company_id')
        user = await get_user_with_details(session, user_id, company_id=company_id)
        
        if not user:
            await callback.answer("Пользователь не найден", show_alert=True)
            return
        
        # Формируем меню редактора
        role_name = user.roles[0].name if user.roles else "Нет роли"
        group_name = format_user_groups(user)
        groups_label = get_groups_label(user)
        is_trainee = role_name in ["Стажер", "Стажёр"]

        text = (
            f"🦸🏻‍♂️ <b>Пользователь:</b> {user.full_name}\n\n"
            f"<b>Телефон:</b> {user.phone_number}\n"
            f"<b>Username:</b> @{user.username if user.username else 'Не указан'}\n"
            f"<b>Номер:</b> #{user.id}\n"
            f"<b>Дата регистрации:</b> {user.registration_date.strftime('%d.%m.%Y %H:%M') if user.registration_date else 'Не указана'}\n\n"
            f"━━━━━━━━━━━━\n\n"
            f"🗂️ <b>Статус:</b>\n"
            f"<b>{groups_label}:</b> {group_name}\n"
            f"<b>Роль:</b> {role_name}\n\n"
            f"━━━━━━━━━━━━\n\n"
            f"📍 <b>Объект:</b>\n"
        )
        
        # Добавляем объект стажировки только для стажеров
        if role_name in ["Стажер", "Стажёр"]:
            if user.internship_object:
                text += f"<b>Стажировки:</b> {user.internship_object.name}\n"
            else:
                text += f"<b>Стажировки:</b> Не указан\n"
            
        # Объект работы
        if user.work_object:
            text += f"<b>Работы:</b> {user.work_object.name}\n"
        else:
            text += f"<b>Работы:</b> Не указан\n"
        
        text += "\n<b>Выбери параметр для изменения:</b>"
        
        keyboard = get_user_editor_keyboard(is_trainee)
        
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
        await state.update_data(editing_user_id=user_id)
        
        log_user_action(callback.from_user.id, "start_edit_user", f"User: {user.full_name} (ID: {user_id})")
        
    except Exception as e:
        await callback.answer("Произошла ошибка")
        log_user_error(callback.from_user.id, "edit_user_error", str(e))


@router.callback_query(F.data == "back_to_filters")
async def callback_back_to_filters(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Возврат к фильтрам пользователей"""
    try:
        await callback.answer()
        
        # Получение company_id из контекста (добавлен CompanyMiddleware)
        company_id = await ensure_company_id(session, state, callback.from_user.id)
        # Получаем группы и объекты для фильтров
        groups = await get_all_groups(session, company_id)
        objects = await get_all_objects(session, company_id)
        users = await get_all_activated_users(session, company_id=company_id)
        
        text = (
            "👥 <b>УПРАВЛЕНИЕ ПОЛЬЗОВАТЕЛЯМИ</b> 👥\n\n"
            f"📊 Всего пользователей в системе: <b>{len(users)}</b>\n"
            f"🗂️ Доступно групп: <b>{len(groups)}</b>\n"
            f"📍 Доступно объектов: <b>{len(objects)}</b>\n\n"
            "Выбери способ фильтрации пользователей:"
        )
        
        keyboard = get_users_filter_keyboard(groups, objects)
        
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
        await state.set_state(UserEditStates.waiting_for_filter_selection)
        
        log_user_action(callback.from_user.id, "back_to_filters", "Returned to user filters")
        
    except Exception as e:
        await callback.answer("Произошла ошибка")
        log_user_error(callback.from_user.id, "back_to_filters_error", str(e))


@router.callback_query(F.data.startswith("back_to_users:"))
async def callback_back_to_users(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Возврат к списку пользователей"""
    try:
        await callback.answer()
        
        filter_type = callback.data.split(":", 1)[1]
        data = await state.get_data()
        users = data.get('current_users', [])
        current_page = data.get('current_page', 0)
        
        if filter_type == "all":
            text = f"👥 <b>ВСЕ ПОЛЬЗОВАТЕЛИ</b> 👥\n\n📊 Найдено пользователей: <b>{len(users)}</b>\n\nВыбери пользователя для просмотра и редактирования:"
        elif filter_type.startswith("group:"):
            user = await get_user_by_tg_id(session, callback.from_user.id)
            if user:
                group_id = int(filter_type.split(":")[1])
                group = await get_group_by_id(session, group_id, company_id=user.company_id)
                text = f"🗂️ <b>ГРУППА: {group.name if group else 'Неизвестная'}</b> 🗂️\n\n📊 Пользователей в группе: <b>{len(users)}</b>\n\nВыбери пользователя для просмотра и редактирования:"
            else:
                text = f"👥 <b>СПИСОК ПОЛЬЗОВАТЕЛЕЙ</b> 👥\n\n📊 Найдено пользователей: <b>{len(users)}</b>\n\nВыбери пользователя для просмотра и редактирования:"
        elif filter_type.startswith("object:"):
            user = await get_user_by_tg_id(session, callback.from_user.id)
            if user:
                object_id = int(filter_type.split(":")[1])
                obj = await get_object_by_id(session, object_id, company_id=user.company_id)
                text = f"📍 <b>ОБЪЕКТ: {obj.name if obj else 'Неизвестный'}</b> 📍\n\n📊 Пользователей на объекте: <b>{len(users)}</b>\n\nВыбери пользователя для просмотра и редактирования:"
            else:
                text = f"👥 <b>СПИСОК ПОЛЬЗОВАТЕЛЕЙ</b> 👥\n\n📊 Найдено пользователей: <b>{len(users)}</b>\n\nВыбери пользователя для просмотра и редактирования:"
        else:
            text = f"👥 <b>СПИСОК ПОЛЬЗОВАТЕЛЕЙ</b> 👥\n\n📊 Найдено пользователей: <b>{len(users)}</b>\n\nВыбери пользователя для просмотра и редактирования:"
        
        keyboard = get_users_list_keyboard(users, current_page, 5, filter_type)
        
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
        await state.set_state(UserEditStates.waiting_for_user_selection)
        
        log_user_action(callback.from_user.id, "back_to_users", f"Filter: {filter_type}")
        
    except Exception as e:
        await callback.answer("Произошла ошибка")
        log_user_error(callback.from_user.id, "back_to_users_error", str(e))


# ===================== ОБРАБОТЧИКИ ПАГИНАЦИИ =====================

@router.callback_query(F.data.startswith("users_page:"))
async def callback_users_pagination(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Обработка пагинации списка пользователей"""
    try:
        await callback.answer()
        
        # Парсим данные: users_page:{filter_type}:{page}
        # filter_type может содержать двоеточие (например, "group:1")
        parts = callback.data.split(":")
        if len(parts) == 3:
            # Простой случай: users_page:all:0
            filter_type = parts[1]
            page = int(parts[2])
        else:
            # Сложный случай: users_page:group:1:0 или users_page:object:2:1
            filter_type = ":".join(parts[1:-1])  # Все части кроме первой и последней
            page = int(parts[-1])  # Последняя часть - номер страницы
        
        data = await state.get_data()
        users = data.get('current_users', [])
        
        if filter_type == "all":
            text = f"👥 <b>ВСЕ ПОЛЬЗОВАТЕЛИ</b> 👥\n\n📊 Найдено пользователей: <b>{len(users)}</b>\n\nВыбери пользователя для просмотра и редактирования:"
        elif filter_type == "search":
            search_query = data.get('search_query', '')
            text = f"🔍 <b>Результаты поиска: '{search_query}'</b>\n\n📊 Найдено пользователей: <b>{len(users)}</b>\n\nВыбери пользователя для просмотра и редактирования:"
        elif filter_type.startswith("group"):
            user = await get_user_by_tg_id(session, callback.from_user.id)
            if user:
                group_id = int(filter_type.split(":")[1]) if ":" in filter_type else 0
                group = await get_group_by_id(session, group_id, company_id=user.company_id) if group_id else None
                text = f"🗂️ <b>ГРУППА: {group.name if group else 'Неизвестная'}</b> 🗂️\n\n📊 Пользователей в группе: <b>{len(users)}</b>\n\nВыбери пользователя для просмотра и редактирования:"
            else:
                text = f"👥 <b>СПИСОК ПОЛЬЗОВАТЕЛЕЙ</b> 👥\n\n📊 Найдено пользователей: <b>{len(users)}</b>\n\nВыбери пользователя для просмотра и редактирования:"
        elif filter_type.startswith("object"):
            user = await get_user_by_tg_id(session, callback.from_user.id)
            if user:
                object_id = int(filter_type.split(":")[1]) if ":" in filter_type else 0
                obj = await get_object_by_id(session, object_id, company_id=user.company_id) if object_id else None
                text = f"📍 <b>ОБЪЕКТ: {obj.name if obj else 'Неизвестный'}</b> 📍\n\n📊 Пользователей на объекте: <b>{len(users)}</b>\n\nВыбери пользователя для просмотра и редактирования:"
            else:
                text = f"👥 <b>СПИСОК ПОЛЬЗОВАТЕЛЕЙ</b> 👥\n\n📊 Найдено пользователей: <b>{len(users)}</b>\n\nВыбери пользователя для просмотра и редактирования:"
        else:
            text = f"👥 <b>СПИСОК ПОЛЬЗОВАТЕЛЕЙ</b> 👥\n\n📊 Найдено пользователей: <b>{len(users)}</b>\n\nВыбери пользователя для просмотра и редактирования:"
        
        keyboard = get_users_list_keyboard(users, page, 5, filter_type)
        
        await callback.message.edit_reply_markup(reply_markup=keyboard)
        await state.update_data(current_page=page)
        
        log_user_action(callback.from_user.id, "users_pagination", f"Page: {page}, Filter: {filter_type}")
        
    except Exception as e:
        await callback.answer("Произошла ошибка")
        log_user_error(callback.from_user.id, "users_pagination_error", str(e))


@router.callback_query(F.data.startswith("group_filter_page:"))
async def callback_group_filter_pagination(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Обработка пагинации списка групп для фильтрации"""
    try:
        await callback.answer()
        
        page = int(callback.data.split(":")[1])
        data = await state.get_data()
        groups = data.get('available_groups', [])
        
        if not groups:
            company_id = await ensure_company_id(session, state, callback.from_user.id)
            groups = await get_all_groups(session, company_id)
        
        keyboard = get_group_filter_keyboard(groups, page, 5)
        
        await callback.message.edit_reply_markup(reply_markup=keyboard)
        await state.update_data(filter_page=page)
        
        log_user_action(callback.from_user.id, "group_filter_pagination", f"Page: {page}")
        
    except Exception as e:
        await callback.answer("Произошла ошибка")
        log_user_error(callback.from_user.id, "group_filter_pagination_error", str(e))


@router.callback_query(F.data.startswith("object_filter_page:"))
async def callback_object_filter_pagination(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Обработка пагинации списка объектов для фильтрации"""
    try:
        await callback.answer()
        
        page = int(callback.data.split(":")[1])
        data = await state.get_data()
        objects = data.get('available_objects', [])
        
        if not objects:
            company_id = await ensure_company_id(session, state, callback.from_user.id)
            objects = await get_all_objects(session, company_id)
        
        keyboard = get_object_filter_keyboard(objects, page, 5)
        
        await callback.message.edit_reply_markup(reply_markup=keyboard)
        await state.update_data(filter_page=page)
        
        log_user_action(callback.from_user.id, "object_filter_pagination", f"Page: {page}")
        
    except Exception as e:
        await callback.answer("Произошла ошибка")
        log_user_error(callback.from_user.id, "object_filter_pagination_error", str(e))


# ===================== СТАРЫЙ ОБРАБОТЧИК ДЛЯ СОВМЕСТИМОСТИ =====================

@router.message(UserEditStates.waiting_for_user_number)
async def process_user_number(message: Message, session: AsyncSession, state: FSMContext):
    """Обработка выбора номера пользователя для редактирования"""
    try:
        user_id = int(message.text.strip())
    except ValueError:
        await message.answer("❌ Пожалуйста, введи корректный номер пользователя")
        return
        
    # Получаем company_id для изоляции
    data = await state.get_data()
    company_id = data.get('company_id')
    
    # Получаем пользователя для редактирования
    target_user = await get_user_with_details(session, user_id, company_id=company_id)
    
    if not target_user or not target_user.is_activated:
        await message.answer("❌ Пользователь не найден или не активирован")
        return
        
    # Сохраняем ID пользователя для редактирования
    await state.update_data(editing_user_id=user_id)
    
    # Показываем редактор
    await show_user_editor(message, session, target_user, state)
    

async def show_user_editor(message: Message, session: AsyncSession,
                          target_user, state: FSMContext):
    """Отображение редактора пользователя"""
    # Формируем информацию о пользователе
    role_name = target_user.roles[0].name if target_user.roles else "Нет роли"
    group_name = format_user_groups(target_user)
    groups_label = get_groups_label(target_user)

    user_info = f"""✏️<b>РЕДАКТОР ПОЛЬЗОВАТЕЛЯ</b>✏️

🧑 ФИО: {target_user.full_name}
📞 Телефон: {target_user.phone_number}
🆔 Telegram ID: {target_user.tg_id}
👤 Username: @{target_user.username if target_user.username else 'Не указан'}
📅 Дата регистрации: {target_user.registration_date.strftime('%d.%m.%Y %H:%M') if target_user.registration_date else 'Не указана'}
👑 Роли: {role_name}
🗂️{groups_label}: {group_name}"""
    
    # Добавляем объект стажировки только для стажеров
    if role_name in ["Стажер", "Стажёр"] and target_user.internship_object:
        user_info += f"\n📍1️⃣Объект стажировки: {target_user.internship_object.name}"
        
    # Объект работы
    if target_user.work_object:
        user_info += f"\n📍2️⃣Объект работы: {target_user.work_object.name}"
        
    user_info += f"\n🎱Номер пользователя: {target_user.id}"
    
    user_info += "\n\nКакую информацию ты хочешь изменить?\nВыбери кнопкой ниже👇"
    
    # Получаем клавиатуру редактора
    keyboard = get_user_editor_keyboard(role_name in ["Стажер", "Стажёр"])
    
    await message.answer(user_info, reply_markup=keyboard, parse_mode="HTML")
    await state.set_state(None)  # Сбрасываем состояние, ждем выбора действия


@router.callback_query(F.data == "edit_full_name")
async def process_edit_full_name(callback: CallbackQuery, session: AsyncSession, state: FSMContext):
    """Начало редактирования ФИО"""
    data = await state.get_data()
    editing_user_id = data.get('editing_user_id')
    
    if not editing_user_id:
        await callback.answer("❌ Ошибка: не выбран пользователь")
        return
        
    data = await state.get_data()
    company_id = data.get('company_id')
    target_user = await get_user_with_details(session, editing_user_id, company_id=company_id)
    if not target_user:
        await callback.answer("❌ Пользователь не найден")
        return
        
    message_text = f"""Введи новые <b>ФАМИЛИЯ И ИМЯ</b> для пользователя:

🧑 ФИО: {target_user.full_name}"""
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="cancel_edit")]
    ])
    
    await callback.message.edit_text(message_text, reply_markup=keyboard, parse_mode="HTML")
    await state.set_state(UserEditStates.waiting_for_new_full_name)
    await state.update_data(edit_type="full_name")
    await callback.answer()


@router.message(UserEditStates.waiting_for_new_full_name)
async def process_new_full_name(message: Message, session: AsyncSession, state: FSMContext):
    """Обработка нового ФИО"""
    new_full_name = message.text.strip()
    
    # Валидация
    is_valid, error_message = validate_full_name(new_full_name)
    if not is_valid:
        await message.answer(f"❌ {error_message}")
        return
        
    data = await state.get_data()
    editing_user_id = data.get('editing_user_id')
    
    data = await state.get_data()
    company_id = data.get('company_id')
    target_user = await get_user_with_details(session, editing_user_id, company_id=company_id)
    if not target_user:
        await message.answer("❌ Пользователь не найден")
        await state.clear()
        return
        
    # Сохраняем новое значение и показываем подтверждение
    await state.update_data(new_value=new_full_name, old_value=target_user.full_name)
    
    confirmation_text = f"""⚠️НОВОЕ ФИО:
⚠️{new_full_name}

Для пользователя:
🧑 ФИО: {target_user.full_name}
📞 Телефон: {target_user.phone_number}
🆔 Telegram ID: {target_user.tg_id}
👤 Username: @{target_user.username if target_user.username else 'Не указан'}"""
    
    keyboard = get_edit_confirmation_keyboard()
    await message.answer(confirmation_text, reply_markup=keyboard)
    await state.set_state(UserEditStates.waiting_for_change_confirmation)


@router.callback_query(F.data == "edit_phone")
async def process_edit_phone(callback: CallbackQuery, session: AsyncSession, state: FSMContext):
    """Начало редактирования телефона"""
    data = await state.get_data()
    editing_user_id = data.get('editing_user_id')
    
    if not editing_user_id:
        await callback.answer("❌ Ошибка: не выбран пользователь")
        return
        
    data = await state.get_data()
    company_id = data.get('company_id')
    target_user = await get_user_with_details(session, editing_user_id, company_id=company_id)
    if not target_user:
        await callback.answer("❌ Пользователь не найден")
        return
        
    message_text = f"""Введи новый <b>ТЕЛЕФОН</b> для пользователя:

🧑 ФИО: {target_user.full_name}"""
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="cancel_edit")]
    ])
    
    await callback.message.edit_text(message_text, reply_markup=keyboard, parse_mode="HTML")
    await state.set_state(UserEditStates.waiting_for_new_phone)
    await state.update_data(edit_type="phone")
    await callback.answer()


@router.message(UserEditStates.waiting_for_new_phone)
async def process_new_phone(message: Message, session: AsyncSession, state: FSMContext):
    """Обработка нового телефона"""
    new_phone = message.text.strip()
    
    # Валидация и нормализация
    is_valid, result = validate_phone_number(new_phone)
    if not is_valid:
        await message.answer(f"❌ {result}")
        return
        
    normalized_phone = result
    
    data = await state.get_data()
    editing_user_id = data.get('editing_user_id')
    
    data = await state.get_data()
    company_id = data.get('company_id')
    target_user = await get_user_with_details(session, editing_user_id, company_id=company_id)
    if not target_user:
        await message.answer("❌ Пользователь не найден")
        await state.clear()
        return
        
    # Сохраняем новое значение и показываем подтверждение
    await state.update_data(new_value=normalized_phone, old_value=target_user.phone_number)
    
    confirmation_text = f"""⚠️НОВЫЙ ТЕЛЕФОН:
⚠️{normalized_phone}

Для пользователя:
🧑 ФИО: {target_user.full_name}
📞 Телефон: {target_user.phone_number}
🆔 Telegram ID: {target_user.tg_id}
👤 Username: @{target_user.username if target_user.username else 'Не указан'}"""
    
    keyboard = get_edit_confirmation_keyboard()
    await message.answer(confirmation_text, reply_markup=keyboard)
    await state.set_state(UserEditStates.waiting_for_change_confirmation)


@router.callback_query(F.data == "edit_role")
async def process_edit_role(callback: CallbackQuery, session: AsyncSession, state: FSMContext):
    """Начало редактирования роли"""
    data = await state.get_data()
    editing_user_id = data.get('editing_user_id')
    
    if not editing_user_id:
        await callback.answer("❌ Ошибка: не выбран пользователь")
        return
        
    data = await state.get_data()
    company_id = data.get('company_id')
    target_user = await get_user_with_details(session, editing_user_id, company_id=company_id)
    if not target_user:
        await callback.answer("❌ Пользователь не найден")
        return
        
    current_role = target_user.roles[0].name if target_user.roles else "Нет роли"
    
    message_text = f"""Выбери новую <b>РОЛЬ</b> для пользователя:

🧑 ФИО: {target_user.full_name}"""
    
    keyboard = get_role_selection_keyboard(is_editing=True)
    await callback.message.edit_text(message_text, reply_markup=keyboard, parse_mode="HTML")
    await state.set_state(UserEditStates.waiting_for_new_role)
    await state.update_data(edit_type="role", old_value=current_role)
    await callback.answer()


@router.callback_query(UserEditStates.waiting_for_new_role, F.data == "cancel_edit")
async def cancel_edit_role(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Отмена редактирования роли - возврат к редактору"""
    await callback_cancel_edit(callback, state, session)


@router.callback_query(UserEditStates.waiting_for_new_role, F.data.startswith("role:"))
async def process_new_role(callback: CallbackQuery, session: AsyncSession, state: FSMContext):
    """Обработка выбора новой роли"""
    new_role = callback.data.split(":")[1]
    
    data = await state.get_data()
    editing_user_id = data.get('editing_user_id')
    old_role = data.get('old_value')
    
    data = await state.get_data()
    company_id = data.get('company_id')
    target_user = await get_user_with_details(session, editing_user_id, company_id=company_id)
    if not target_user:
        await callback.answer("❌ Пользователь не найден")
        await state.clear()
        return
        
    # Сохраняем новое значение и показываем подтверждение
    await state.update_data(new_value=new_role)
    
    # Получаем текущую роль
    current_role = target_user.roles[0].name if target_user.roles else "Нет роли"
    
    # Получаем company_id для изоляции
    data = await state.get_data()
    company_id = data.get('company_id')
    
    # Формируем предупреждения о последствиях смены роли
    warnings = await get_role_change_warnings(session, target_user.id, current_role, new_role, company_id=company_id)
    
    confirmation_text = f"""🚩🚩🚩<b>ИЗМЕНЕНИЕ РОЛИ</b>🚩🚩🚩

<b>Пользователь:</b> {target_user.full_name}
<b>Телефон:</b> {target_user.phone_number}

🏚️ <b>Текущая роль:</b> {current_role}
🌱<b>Новая роль:</b> {new_role}

━━━━━━━━━━━━

{warnings}"""
    
    keyboard = get_edit_confirmation_keyboard()
    await callback.message.edit_text(confirmation_text, reply_markup=keyboard)
    await state.set_state(UserEditStates.waiting_for_change_confirmation)
    await callback.answer()


@router.callback_query(UserEditStates.waiting_for_new_role, F.data == "cancel_registration")
async def process_cancel_role_selection(callback: CallbackQuery, session: AsyncSession, state: FSMContext):
    """Отмена выбора роли"""
    await callback.message.edit_text("❌ ТЫ ОТМЕНИЛ РЕДАКТИРОВАНИЕ ПОЛЬЗОВАТЕЛЯ")
    await state.clear()
    await callback.answer()
    log_user_action(callback.from_user.id, "cancel_role_edit", "Cancelled role editing")


@router.callback_query(F.data == "edit_group")
async def process_edit_group(callback: CallbackQuery, session: AsyncSession, state: FSMContext):
    """Начало редактирования группы"""
    data = await state.get_data()
    editing_user_id = data.get('editing_user_id')

    if not editing_user_id:
        await callback.answer("❌ Ошибка: не выбран пользователь")
        return

    # Единственный источник company_id для всей функции
    company_id = await ensure_company_id(session, state, callback.from_user.id)

    target_user = await get_user_with_details(session, editing_user_id, company_id=company_id)
    if not target_user:
        await callback.answer("❌ Пользователь не найден")
        return

    # Получаем все группы
    groups = await get_all_groups(session, company_id)

    if not groups:
        await callback.message.edit_text("❌ В системе нет доступных групп")
        await callback.answer()
        return

    # Определяем роли пользователя
    role_names = [r.name for r in target_user.roles]

    # Наставникам показываем мультивыбор групп
    if "Наставник" in role_names:
        current_groups = format_user_groups(target_user)
        selected_group_ids = [g.id for g in target_user.groups]

        message_text = f"""Выбери <b>ГРУППЫ</b> для наставника:

🧑 ФИО: {target_user.full_name}
🗂️ Текущие группы: {current_groups}

Отметь галочками нужные группы и нажми "Сохранить"."""

        keyboard = get_user_groups_multiselect_keyboard(groups, selected_group_ids, page=0)

        await callback.message.edit_text(message_text, reply_markup=keyboard, parse_mode="HTML")
        await state.set_state(UserEditStates.waiting_for_new_group)
        await state.update_data(
            edit_type="groups",
            old_value=current_groups,
            selected_group_ids=selected_group_ids
        )
    else:
        # Для остальных ролей - одиночный выбор группы
        current_group = format_user_groups(target_user)

        message_text = f"""Выбери новую <b>ГРУППУ</b> для пользователя:

🧑 ФИО: {target_user.full_name}"""

        keyboard = get_group_selection_keyboard(groups, 0)

        await callback.message.edit_text(message_text, reply_markup=keyboard, parse_mode="HTML")
        await state.set_state(UserEditStates.waiting_for_new_group)
        await state.update_data(edit_type="group", old_value=current_group)

    await callback.answer()


@router.callback_query(UserEditStates.waiting_for_new_group)
async def process_new_group(callback: CallbackQuery, session: AsyncSession, state: FSMContext):
    """Обработка выбора новой группы (одиночный выбор или мультивыбор для наставников)"""
    data = await state.get_data()
    edit_type = data.get('edit_type')

    # === Мультивыбор групп для наставников ===
    if callback.data.startswith("user_edit_toggle_group:"):
        # Переключение выбора группы
        group_id = int(callback.data.split(":")[1])
        selected_group_ids = data.get('selected_group_ids', [])

        if group_id in selected_group_ids:
            selected_group_ids.remove(group_id)
        else:
            selected_group_ids.append(group_id)

        await state.update_data(selected_group_ids=selected_group_ids)

        # Перерисовываем клавиатуру с обновленным выбором
        company_id = await ensure_company_id(session, state, callback.from_user.id)
        groups = await get_all_groups(session, company_id)
        page = data.get('groups_page', 0)
        keyboard = get_user_groups_multiselect_keyboard(groups, selected_group_ids, page=page)
        await callback.message.edit_reply_markup(reply_markup=keyboard)
        await callback.answer()

    elif callback.data.startswith("user_edit_groups_page:"):
        # Пагинация мультивыбора групп
        page = int(callback.data.split(":")[1])
        selected_group_ids = data.get('selected_group_ids', [])
        await state.update_data(groups_page=page)

        company_id = await ensure_company_id(session, state, callback.from_user.id)
        groups = await get_all_groups(session, company_id)
        keyboard = get_user_groups_multiselect_keyboard(groups, selected_group_ids, page=page)
        await callback.message.edit_reply_markup(reply_markup=keyboard)
        await callback.answer()

    elif callback.data == "user_edit_save_groups":
        # Сохранение выбранных групп для наставника - показываем подтверждение
        selected_group_ids = data.get('selected_group_ids', [])
        editing_user_id = data.get('editing_user_id')
        company_id = data.get('company_id')
        old_groups = data.get('old_value', 'Нет групп')

        if not selected_group_ids:
            await callback.answer("❌ Выберите хотя бы одну группу", show_alert=True)
            return

        target_user = await get_user_with_details(session, editing_user_id, company_id=company_id)
        if not target_user:
            await callback.answer("❌ Пользователь не найден")
            await state.clear()
            return

        # Получаем названия выбранных групп
        groups = await get_all_groups(session, company_id)
        groups_dict = {g.id: g.name for g in groups}
        new_group_names = ", ".join(
            groups_dict.get(gid, f"ID:{gid}") for gid in selected_group_ids
        )

        confirmation_text = f"""⚠️НОВЫЕ ГРУППЫ:
⚠️{new_group_names}

Было: {old_groups}

Для пользователя:
🧑 ФИО: {target_user.full_name}
📞 Телефон: {target_user.phone_number}
🆔 Telegram ID: {target_user.tg_id}
👤 Username: @{target_user.username if target_user.username else 'Не указан'}"""

        await state.update_data(new_value=selected_group_ids, new_group_names=new_group_names)

        keyboard = get_edit_confirmation_keyboard()
        await callback.message.edit_text(confirmation_text, reply_markup=keyboard)
        await state.set_state(UserEditStates.waiting_for_change_confirmation)
        await callback.answer()

    # === Одиночный выбор группы (для всех кроме наставников) ===
    elif callback.data.startswith("select_group:"):
        group_id = int(callback.data.split(":")[1])

        editing_user_id = data.get('editing_user_id')
        company_id = data.get('company_id')
        target_user = await get_user_with_details(session, editing_user_id, company_id=company_id)
        if not target_user:
            await callback.answer("❌ Пользователь не найден")
            await state.clear()
            return

        # Получаем название группы
        group = await get_group_by_id(session, group_id, company_id=target_user.company_id)
        if not group:
            await callback.answer("❌ Группа не найдена")
            return

        # Сохраняем новое значение и показываем подтверждение
        await state.update_data(new_value=group_id, new_group_name=group.name)

        confirmation_text = f"""⚠️НОВАЯ ГРУППА:
⚠️{group.name}

Для пользователя:
🧑 ФИО: {target_user.full_name}
📞 Телефон: {target_user.phone_number}
🆔 Telegram ID: {target_user.tg_id}
👤 Username: @{target_user.username if target_user.username else 'Не указан'}"""

        keyboard = get_edit_confirmation_keyboard()
        await callback.message.edit_text(confirmation_text, reply_markup=keyboard)
        await state.set_state(UserEditStates.waiting_for_change_confirmation)
        await callback.answer()

    elif callback.data.startswith("groups_page:"):
        # Обработка пагинации (одиночный выбор)
        page = int(callback.data.split(":")[1])
        company_id = await ensure_company_id(session, state, callback.from_user.id)
        groups = await get_all_groups(session, company_id)
        keyboard = get_group_selection_keyboard(groups, page)
        await callback.message.edit_reply_markup(reply_markup=keyboard)
        await callback.answer()

    elif callback.data == "cancel_edit":
        # Обработка кнопки "Назад" - делегируем универсальному обработчику
        await callback_cancel_edit(callback, state, session)


@router.callback_query(F.data == "edit_internship_object")
async def process_edit_internship_object(callback: CallbackQuery, session: AsyncSession, state: FSMContext):
    """Начало редактирования объекта стажировки"""
    data = await state.get_data()
    editing_user_id = data.get('editing_user_id')
    
    if not editing_user_id:
        await callback.answer("❌ Ошибка: не выбран пользователь")
        return
        
    data = await state.get_data()
    company_id = data.get('company_id')
    target_user = await get_user_with_details(session, editing_user_id, company_id=company_id)
    if not target_user:
        await callback.answer("❌ Пользователь не найден")
        return
        
    current_object = target_user.internship_object.name if target_user.internship_object else "Не назначен"
    
    message_text = f"""Выбери новый <b>ОБЪЕКТ СТАЖИРОВКИ</b> для пользователя:

🧑 ФИО: {target_user.full_name}"""
    
    # Получение company_id из контекста (добавлен CompanyMiddleware)
    company_id = await ensure_company_id(session, state, callback.from_user.id)
    # Получаем все объекты
    objects = await get_all_objects(session, company_id)
    
    if not objects:
        await callback.message.edit_text("❌ В системе нет доступных объектов стажировки")
        await callback.answer()
        return
    
    keyboard = get_object_selection_keyboard(objects, 0, 5, "internship")
    
    await callback.message.edit_text(message_text, reply_markup=keyboard, parse_mode="HTML")
    await state.set_state(UserEditStates.waiting_for_new_internship_object)
    await state.update_data(edit_type="internship_object", old_value=current_object)
    await callback.answer()


@router.callback_query(UserEditStates.waiting_for_new_internship_object)
async def process_new_internship_object(callback: CallbackQuery, session: AsyncSession, state: FSMContext):
    """Обработка выбора нового объекта стажировки"""
    if callback.data.startswith("select_internship_object:"):
        object_id = int(callback.data.split(":")[1])
        
        data = await state.get_data()
        editing_user_id = data.get('editing_user_id')
        company_id = data.get('company_id')
        target_user = await get_user_with_details(session, editing_user_id, company_id=company_id)
        if not target_user:
            await callback.answer("❌ Пользователь не найден")
            await state.clear()
            return
            
        # Получаем название объекта
        obj = await get_object_by_id(session, object_id, company_id=target_user.company_id)
        if not obj:
            await callback.answer("❌ Объект не найден или неактивен")
            return
            
        # Сохраняем новое значение и показываем подтверждение
        await state.update_data(new_value=object_id, new_object_name=obj.name)
        
        confirmation_text = f"""⚠️НОВЫЙ ОБЪЕКТ СТАЖИРОВКИ:
⚠️{obj.name}

Для пользователя:
🧑 ФИО: {target_user.full_name}
📞 Телефон: {target_user.phone_number}
🆔 Telegram ID: {target_user.tg_id}
👤 Username: @{target_user.username if target_user.username else 'Не указан'}
📅 Дата регистрации: {target_user.registration_date.strftime('%d.%m.%Y %H:%M') if target_user.registration_date else 'Не указана'}
👑 Роли: {target_user.roles[0].name if target_user.roles else 'Нет роли'}
🗂️{get_groups_label(target_user)}: {format_user_groups(target_user)}
📍1️⃣Объект стажировки: {target_user.internship_object.name if target_user.internship_object else 'Не назначен'}"""

        keyboard = get_edit_confirmation_keyboard()
        await callback.message.edit_text(confirmation_text, reply_markup=keyboard)
        await state.set_state(UserEditStates.waiting_for_change_confirmation)
        await callback.answer()

    elif callback.data.startswith("internship_object_page:"):
        # Обработка пагинации
        page = int(callback.data.split(":")[1])
        company_id = await ensure_company_id(session, state, callback.from_user.id)
        objects = await get_all_objects(session, company_id)
        keyboard = get_object_selection_keyboard(objects, page, 5, "internship")
        await callback.message.edit_reply_markup(reply_markup=keyboard)
        await callback.answer()
    
    elif callback.data == "cancel_edit":
        # Обработка кнопки "Назад" - делегируем универсальному обработчику
        await callback_cancel_edit(callback, state, session)


@router.callback_query(F.data == "edit_work_object")
async def process_edit_work_object(callback: CallbackQuery, session: AsyncSession, state: FSMContext):
    """Начало редактирования объекта работы"""
    data = await state.get_data()
    editing_user_id = data.get('editing_user_id')
    
    if not editing_user_id:
        await callback.answer("❌ Ошибка: не выбран пользователь")
        return
        
    data = await state.get_data()
    company_id = data.get('company_id')
    target_user = await get_user_with_details(session, editing_user_id, company_id=company_id)
    if not target_user:
        await callback.answer("❌ Пользователь не найден")
        return
        
    current_object = target_user.work_object.name if target_user.work_object else "Не назначен"
    
    message_text = f"""Выбери новый <b>ОБЪЕКТ РАБОТЫ</b> для пользователя:

🧑 ФИО: {target_user.full_name}"""
    
    # Получение company_id из контекста (добавлен CompanyMiddleware)
    company_id = await ensure_company_id(session, state, callback.from_user.id)
    # Получаем все объекты
    objects = await get_all_objects(session, company_id)
    
    if not objects:
        await callback.message.edit_text("❌ В системе нет доступных объектов работы")
        await callback.answer()
        return
    
    keyboard = get_object_selection_keyboard(objects, 0, 5, "work")
    
    await callback.message.edit_text(message_text, reply_markup=keyboard, parse_mode="HTML")
    await state.set_state(UserEditStates.waiting_for_new_work_object)
    await state.update_data(edit_type="work_object", old_value=current_object)
    await callback.answer()


@router.callback_query(UserEditStates.waiting_for_new_work_object)
async def process_new_work_object(callback: CallbackQuery, session: AsyncSession, state: FSMContext):
    """Обработка выбора нового объекта работы"""
    if callback.data.startswith("select_work_object:"):
        object_id = int(callback.data.split(":")[1])
        
        data = await state.get_data()
        editing_user_id = data.get('editing_user_id')
        company_id = data.get('company_id')
        target_user = await get_user_with_details(session, editing_user_id, company_id=company_id)
        if not target_user:
            await callback.answer("❌ Пользователь не найден")
            await state.clear()
            return
            
        # Получаем название объекта
        obj = await get_object_by_id(session, object_id, company_id=target_user.company_id)
        if not obj:
            await callback.answer("❌ Объект не найден или неактивен")
            return
            
        # Сохраняем новое значение и показываем подтверждение
        await state.update_data(new_value=object_id, new_object_name=obj.name)
        
        current_role = target_user.roles[0].name if target_user.roles else "Нет роли"
        
        confirmation_text = f"""⚠️НОВЫЙ ОБЪЕКТ РАБОТЫ:
⚠️{obj.name}

Для пользователя:
🧑 ФИО: {target_user.full_name}
📞 Телефон: {target_user.phone_number}
🆔 Telegram ID: {target_user.tg_id}
👤 Username: @{target_user.username if target_user.username else 'Не указан'}
📅 Дата регистрации: {target_user.registration_date.strftime('%d.%m.%Y %H:%M') if target_user.registration_date else 'Не указана'}
👑 Роли: {current_role}
🗂️{get_groups_label(target_user)}: {format_user_groups(target_user)}
📍2️⃣Объект работы: {target_user.work_object.name if target_user.work_object else 'Не назначен'}"""
        
        keyboard = get_edit_confirmation_keyboard()
        await callback.message.edit_text(confirmation_text, reply_markup=keyboard)
        await state.set_state(UserEditStates.waiting_for_change_confirmation)
        await callback.answer()
        
    elif callback.data.startswith("work_object_page:"):
        # Обработка пагинации
        page = int(callback.data.split(":")[1])
        company_id = await ensure_company_id(session, state, callback.from_user.id)
        objects = await get_all_objects(session, company_id)
        keyboard = get_object_selection_keyboard(objects, page, 5, "work")
        await callback.message.edit_reply_markup(reply_markup=keyboard)
        await callback.answer()
    
    elif callback.data == "cancel_edit":
        # Обработка кнопки "Назад" - делегируем универсальному обработчику
        await callback_cancel_edit(callback, state, session)


@router.callback_query(UserEditStates.waiting_for_change_confirmation, F.data == "confirm_change")
async def process_confirm_change(callback: CallbackQuery, session: AsyncSession, state: FSMContext):
    """Подтверждение изменений"""
    data = await state.get_data()
    editing_user_id = data.get('editing_user_id')
    edit_type = data.get('edit_type')
    new_value = data.get('new_value')
    
    # Получаем ID рекрутера
    recruiter = await get_user_by_tg_id(session, callback.from_user.id)
    if not recruiter:
        await callback.answer("❌ Ошибка аутентификации")
        await state.clear()
        return
        
    # Выполняем соответствующее обновление
    success = False
    error_message = "Неизвестная ошибка"
    bot = callback.bot
    
    # Получаем company_id для изоляции
    company_id = data.get('company_id')
    
    if edit_type == "full_name":
        success = await update_user_full_name(session, editing_user_id, new_value, recruiter.id, bot, company_id=company_id)
        error_message = "❌ Ошибка при изменении ФИО"
    elif edit_type == "phone":
        # Дополнительная проверка для телефона
        existing_user = await get_user_by_phone(session, new_value)
        if existing_user and existing_user.id != editing_user_id:
            error_message = f"❌ Телефон {new_value} уже используется другим пользователем"
            success = False
        else:
            success = await update_user_phone_number(session, editing_user_id, new_value, recruiter.id, bot, company_id=company_id)
            error_message = "❌ Ошибка при изменении телефона"
    elif edit_type == "role":
        success = await update_user_role(session, editing_user_id, new_value, recruiter.id, bot, company_id=company_id)
        error_message = "❌ Ошибка при изменении роли"
    elif edit_type == "group":
        success = await update_user_group(session, editing_user_id, new_value, recruiter.id, bot, company_id=company_id)
        error_message = "❌ Ошибка при изменении группы"
    elif edit_type == "groups":
        # Мультивыбор групп для наставников
        success = await update_user_groups(session, editing_user_id, new_value, recruiter.id, bot, company_id=company_id)
        error_message = "❌ Ошибка при изменении групп"
    elif edit_type == "internship_object":
        success = await update_user_internship_object(session, editing_user_id, new_value, recruiter.id, bot, company_id=company_id)
        error_message = "❌ Ошибка при изменении объекта стажировки"
    elif edit_type == "work_object":
        success = await update_user_work_object(session, editing_user_id, new_value, recruiter.id, bot, company_id=company_id)
        error_message = "❌ Ошибка при изменении объекта работы"
        
    if success:
        # Получаем обновленного пользователя и показываем редактор снова
        target_user = await get_user_with_details(session, editing_user_id, company_id=company_id)
        if target_user:
            # Формируем полное сообщение как требует ТЗ
            role_name = target_user.roles[0].name if target_user.roles else "Нет роли"
            group_name = format_user_groups(target_user)
            groups_label = get_groups_label(target_user)

            success_message = f"""✅ <b>Данные изменены</b>

🦸🏻‍♂️ <b>Пользователь:</b> {target_user.full_name}

<b>Телефон:</b> {target_user.phone_number}
<b>Username:</b> @{target_user.username if target_user.username else 'Не указан'}
<b>Номер:</b> #{target_user.id}
<b>Дата регистрации:</b> {target_user.registration_date.strftime('%d.%m.%Y %H:%M') if target_user.registration_date else 'Не указана'}

━━━━━━━━━━━━

🗂️ <b>Статус:</b>
<b>{groups_label}:</b> {group_name}
<b>Роль:</b> {role_name}

━━━━━━━━━━━━

📍 <b>Объект:</b>
"""
            
            # Добавляем объект стажировки только для стажеров
            if role_name in ["Стажер", "Стажёр"]:
                if target_user.internship_object:
                    success_message += f"<b>Стажировки:</b> {target_user.internship_object.name}\n"
                else:
                    success_message += f"<b>Стажировки:</b> Не указан\n"
                
            # Объект работы
            if target_user.work_object:
                success_message += f"<b>Работы:</b> {target_user.work_object.name}\n"
            else:
                success_message += f"<b>Работы:</b> Не указан\n"
                
            success_message += "\n<b>Выбери параметр для изменения:</b>"
            
            # Получаем клавиатуру редактора
            keyboard = get_user_editor_keyboard(role_name in ["Стажер", "Стажёр"])
            
            await callback.message.edit_text(success_message, reply_markup=keyboard, parse_mode="HTML")
            
            # Устанавливаем правильное состояние и данные для корректной работы кнопки "Назад"
            await state.set_state(UserEditStates.viewing_user_info)
            await state.update_data(editing_user_id=editing_user_id, viewing_user_id=editing_user_id)
            
            log_user_action(callback.from_user.id, f"edit_user_{edit_type}", 
                          f"Changed {edit_type} for user {editing_user_id}")
    else:
        # Добавляем кнопку возврата к редактору при ошибке
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="↩️ Назад к редактору", callback_data=f"edit_user:{editing_user_id}")],
            [InlineKeyboardButton(text="≡ Главное меню", callback_data="main_menu")]
        ])
        
        await callback.message.edit_text(error_message, reply_markup=keyboard, parse_mode="HTML")
        log_user_error(callback.from_user.id, f"edit_user_{edit_type}_failed", 
                      f"Failed to change {edit_type} for user {editing_user_id}")
        await state.set_state(UserEditStates.viewing_user_info)
        await state.update_data(viewing_user_id=editing_user_id)
        
    await callback.answer()


@router.callback_query(UserEditStates.waiting_for_change_confirmation, F.data == "cancel_change")
async def process_cancel_change(callback: CallbackQuery, session: AsyncSession, state: FSMContext):
    """Отмена изменений - возврат к редактору"""
    try:
        data = await state.get_data()
        editing_user_id = data.get('editing_user_id')
        
        if not editing_user_id:
            await callback.answer("Пользователь не найден")
            return
        
        # Возвращаемся к редактору пользователя
        await callback_cancel_edit(callback, state, session)
        log_user_action(callback.from_user.id, "cancel_change", f"Returned to editor for user {editing_user_id}")
        
    except Exception as e:
        await callback.answer("Произошла ошибка")
        log_user_error(callback.from_user.id, "cancel_change_error", str(e))


@router.callback_query(F.data == "delete_user", UserEditStates.viewing_user_info)
async def callback_delete_user(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Начало процесса удаления пользователя"""
    try:
        data = await state.get_data()
        user_id = data.get("viewing_user_id")
        
        user = await get_user_by_id(session, user_id)
        if not user:
            await callback.answer("Пользователь не найден")
            return
        
        warning_text = (
            f"⚠️ <b>ПРЕДУПРЕЖДЕНИЕ</b> ⚠️\n\n"
            f"Ты собираешься ПОЛНОСТЬЮ УДАЛИТЬ пользователя:\n"
            f"👤 <b>{user.full_name}</b>\n"
            f"📞 {user.phone_number}\n"
            f"🆔 #{user.id}\n\n"
            f"⚠️ <b>ПОСЛЕДСТВИЯ УДАЛЕНИЯ:</b>\n\n"
            f"<b>ДЛЯ ПОЛЬЗОВАТЕЛЯ:</b>\n"
            f"• Аккаунт будет УДАЛЕН из системы\n"
            f"• При входе потребуется повторная регистрация\n"
            f"• ВСЕ прогресс и результаты будут ПОТЕРЯНЫ\n\n"
            f"<b>ДЛЯ СИСТЕМЫ:</b>\n"
            f"• Результаты тестов - УДАЛЕНЫ\n"
            f"• Результаты аттестаций - УДАЛЕНЫ\n"
            f"• Назначенные траектории - УДАЛЕНЫ\n"
            f"• Связи с наставниками - УДАЛЕНЫ\n"
            f"• История прогресса - УДАЛЕНА\n\n"
            f"ℹ️ <b>ВАЖНО:</b>\n"
            f"• Созданные им тесты, траектории, группы, объекты ОСТАНУТСЯ в системе\n"
            f"• Это действие НЕОБРАТИМО\n\n"
            f"<b>Ты уверен, что хочешь удалить этого пользователя?</b>"
        )
        
        await callback.message.edit_text(
            warning_text,
            reply_markup=get_user_deletion_confirmation_keyboard(user_id),
            parse_mode="HTML"
        )
        await callback.answer()
        
    except Exception as e:
        await callback.answer("Ошибка при подготовке удаления")
        log_user_error(callback.from_user.id, "delete_user_error", str(e))


@router.callback_query(F.data.startswith("confirm_delete_user:"))
async def callback_confirm_delete_user(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Подтверждение удаления пользователя"""
    try:
        user_id = int(callback.data.split(":")[1])
        
        user = await get_user_by_id(session, user_id)
        if not user:
            await callback.answer("Пользователь не найден")
            return
        
        user_name = user.full_name
        
        # Получаем текущего пользователя для проверки company_id
        current_user = await get_user_by_tg_id(session, callback.from_user.id)
        if not current_user:
            await callback.answer("❌ Ты не зарегистрирован в системе.", show_alert=True)
            return
        
        # Проверяем, что удаляемый пользователь принадлежит той же компании
        if user.company_id != current_user.company_id:
            await callback.answer("❌ Нельзя удалить пользователя из другой компании.", show_alert=True)
            return
        
        # Сохраняем filter_type перед удалением и очисткой состояния
        data = await state.get_data()
        filter_type = data.get('filter_type', 'all')
        
        # Выполняем удаление с проверкой company_id
        success = await delete_user(session, user_id, company_id=current_user.company_id)
        
        if success:
            await callback.message.edit_text(
                f"✅ <b>Пользователь успешно удален</b>\n\n"
                f"👤 {user_name}\n"
                f"🆔 #{user_id}\n\n"
                f"Все данные пользователя удалены из системы.",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="⬅️ Назад к фильтрам", callback_data="back_to_filters")],
                    [InlineKeyboardButton(text="≡ Главное меню", callback_data="main_menu")]
                ])
            )
            # Очищаем состояние, но сохраняем информацию для возврата
            await state.clear()
            await state.set_state(UserEditStates.waiting_for_filter_selection)
            log_user_action(callback.from_user.id, "user_deleted", f"Deleted user {user_id}: {user_name}")
        else:
            await callback.message.edit_text(
                f"❌ <b>Ошибка удаления</b>\n\n"
                f"Не удалось удалить пользователя {user_name}.\n"
                f"Попробуй позже или обратись к администратору.",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="⬅️ Назад к просмотру", callback_data=f"back_to_view_after_error:{user_id}")],
                    [InlineKeyboardButton(text="≡ Главное меню", callback_data="main_menu")]
                ])
            )
            # Устанавливаем состояние для корректной работы кнопки "Назад"
            await state.set_state(UserEditStates.viewing_user_info)
            await state.update_data(viewing_user_id=user_id, filter_type=filter_type)
        
        await callback.answer()
        
    except (ValueError, IndexError):
        await callback.answer("Ошибка при удалении пользователя")
        log_user_error(callback.from_user.id, "confirm_delete_user_error", f"Invalid data: {callback.data}")


@router.callback_query(F.data.startswith("cancel_delete_user:"))
async def callback_cancel_delete_user(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Отмена удаления пользователя - возврат к редактору"""
    try:
        user_id = int(callback.data.split(":")[1])
        
        # Получаем детальную информацию о пользователе для редактора
        user = await get_user_by_id(session, user_id)
        if not user:
            await callback.answer("Пользователь не найден")
            return
        
        roles = await get_user_roles(session, user.id)
        role_name = roles[0].name if roles else "Не назначена"
        group_name = format_user_groups(user)
        groups_label = get_groups_label(user)
        is_trainee = role_name in ["Стажер", "Стажёр"]

        # Формируем текст для редактора
        text = (
            f"🦸🏻‍♂️ <b>Пользователь:</b> {user.full_name}\n\n"
            f"<b>Телефон:</b> {user.phone_number}\n"
            f"<b>Username:</b> @{user.username if user.username else 'Не указан'}\n"
            f"<b>Номер:</b> #{user.id}\n"
            f"<b>Дата регистрации:</b> {user.registration_date.strftime('%d.%m.%Y %H:%M') if user.registration_date else 'Не указана'}\n\n"
            f"━━━━━━━━━━━━\n\n"
            f"🗂️ <b>Статус:</b>\n"
            f"<b>{groups_label}:</b> {group_name}\n"
            f"<b>Роль:</b> {role_name}\n\n"
            f"━━━━━━━━━━━━\n\n"
            f"📍 <b>Объект:</b>\n"
        )
        
        if is_trainee:
            if user.internship_object:
                text += f"<b>Стажировки:</b> {user.internship_object.name}\n"
            else:
                text += f"<b>Стажировки:</b> Не указан\n"
        
        if user.work_object:
            text += f"<b>Работы:</b> {user.work_object.name}\n"
        else:
            text += f"<b>Работы:</b> Не указан\n"
        
        text += "\n<b>Выбери параметр для изменения:</b>"
        
        await callback.message.edit_text(
            text,
            parse_mode="HTML",
            reply_markup=get_user_editor_keyboard(is_trainee)
        )
        await callback.answer("Удаление отменено")
        
    except (ValueError, IndexError):
        await callback.answer("Ошибка при отмене")
        log_user_error(callback.from_user.id, "cancel_delete_user_error", f"Invalid data: {callback.data}")


@router.callback_query(F.data == "back_to_view_user", UserEditStates.viewing_user_info)
async def callback_back_to_view_user(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Возврат к просмотру информации о пользователе из редактора"""
    try:
        data = await state.get_data()
        user_id = data.get("viewing_user_id")
        
        if not user_id:
            await callback.answer("Пользователь не найден")
            return
        
        filter_type = data.get('filter_type', 'all')
        
        # Используем общую функцию для отображения информации
        data = await state.get_data()
        company_id = data.get('company_id')
        success = await show_user_info_detail(callback, user_id, session, filter_type, company_id=company_id)
        if success:
            await callback.answer()
        
    except Exception as e:
        await callback.answer("Произошла ошибка")
        log_user_error(callback.from_user.id, "back_to_view_user_error", str(e))


@router.callback_query(F.data.startswith("back_to_view_after_error:"))
async def callback_back_to_view_after_error(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Возврат к просмотру пользователя после ошибки удаления"""
    try:
        user_id = int(callback.data.split(":")[1])
        
        data = await state.get_data()
        filter_type = data.get('filter_type', 'all')
        
        # Используем общую функцию для отображения информации
        data = await state.get_data()
        company_id = data.get('company_id')
        success = await show_user_info_detail(callback, user_id, session, filter_type, company_id=company_id)
        if success:
            await callback.answer()
        
    except (ValueError, IndexError):
        await callback.answer("Ошибка")
        log_user_error(callback.from_user.id, "back_to_view_after_error_error", f"Invalid data: {callback.data}")


@router.callback_query(F.data == "cancel_edit")
async def callback_cancel_edit(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Отмена редактирования - возврат к редактору пользователя"""
    try:
        data = await state.get_data()
        editing_user_id = data.get('editing_user_id')
        
        if not editing_user_id:
            await callback.answer("Ошибка: пользователь не найден")
            return
        
        # Получаем информацию о пользователе
        data = await state.get_data()
        company_id = data.get('company_id')
        target_user = await get_user_with_details(session, editing_user_id, company_id=company_id)
        if not target_user:
            await callback.answer("❌ Пользователь не найден")
            return
        
        # Формируем текст с информацией о пользователе
        role_name = target_user.roles[0].name if target_user.roles else "Нет роли"
        group_name = format_user_groups(target_user)
        groups_label = get_groups_label(target_user)

        text = (
            f"🦸🏻‍♂️ <b>Пользователь:</b> {target_user.full_name}\n\n"
            f"<b>Телефон:</b> {target_user.phone_number}\n"
            f"<b>Username:</b> @{target_user.username if target_user.username else 'Не указан'}\n"
            f"<b>Номер:</b> #{target_user.id}\n"
            f"<b>Дата регистрации:</b> {target_user.registration_date.strftime('%d.%m.%Y %H:%M') if target_user.registration_date else 'Не указана'}\n\n"
            f"━━━━━━━━━━━━\n\n"
            f"🗂️ <b>Статус:</b>\n"
            f"<b>{groups_label}:</b> {group_name}\n"
            f"<b>Роль:</b> {role_name}\n\n"
            f"━━━━━━━━━━━━\n\n"
            f"📍 <b>Объект:</b>\n"
        )
        
        # Добавляем объекты в зависимости от роли
        if role_name in ["Стажер", "Стажёр"]:
            if target_user.internship_object:
                text += f"<b>Стажировки:</b> {target_user.internship_object.name}\n"
            else:
                text += f"<b>Стажировки:</b> Не указан\n"
        
        if target_user.work_object:
            text += f"<b>Работы:</b> {target_user.work_object.name}\n"
        else:
            text += f"<b>Работы:</b> Не указан\n"
        
        text += "\n<b>Выбери параметр для изменения:</b>"
        
        is_trainee = role_name in ["Стажер", "Стажёр"]
        
        await callback.message.edit_text(
            text,
            reply_markup=get_user_editor_keyboard(is_trainee),
            parse_mode="HTML"
        )
        
        await state.set_state(UserEditStates.viewing_user_info)
        await callback.answer()
        log_user_action(callback.from_user.id, "cancel_edit", f"User: {editing_user_id}")
        
    except Exception as e:
        await callback.answer("Произошла ошибка")
        log_user_error(callback.from_user.id, "cancel_edit_error", str(e))
