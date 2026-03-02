from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from database.db import (
    get_all_roles, get_role_permissions, get_all_permissions,
    add_permission_to_role, remove_permission_from_role,
    get_role_by_name, get_permission_by_name, check_user_permission,
    get_user_by_tg_id
)
from keyboards.keyboards import (
    get_role_management_keyboard, get_permission_action_keyboard,
    get_permission_selection_keyboard, get_permission_confirmation_keyboard
)
from states.states import AdminStates
from utils.logger import log_user_action, log_user_error
from handlers.core.auth import check_auth

router = Router()

@router.message(Command("manage_permissions"))
async def cmd_manage_permissions(message: Message, state: FSMContext, session: AsyncSession):
    """Обработчик команды управления правами ролей"""
    is_auth = await check_auth(message, state, session)
    if not is_auth:
        return
    
    user = await get_user_by_tg_id(session, message.from_user.id)
    if not user:
        await message.answer("Ты не зарегистрирован в системе.")
        return
    
    has_permission = await check_user_permission(session, user.id, "manage_roles")
    
    if not has_permission:
        await message.answer("У тебя нет прав для управления правами ролей.")
        return
    
    await show_roles_list(message, state, session)

@router.message(F.text == "Управление правами ролей")
async def button_manage_permissions(message: Message, state: FSMContext, session: AsyncSession):
    """Обработчик кнопки управления правами ролей"""
    await cmd_manage_permissions(message, state, session)

async def show_roles_list(message: Message, state: FSMContext, session: AsyncSession):
    """
    Отображает список ролей для управления правами
    
    Args:
        message (Message): Сообщение от пользователя
        state (FSMContext): Контекст состояния
        session (AsyncSession): Сессия БД
    """
    roles = await get_all_roles(session)
    
    if not roles:
        await message.answer("В системе пока нет настроенных ролей.")
        return
    
    keyboard = get_role_management_keyboard(roles)
    
    await message.answer(
        "Выбери роль для управления правами:",
        reply_markup=keyboard
    )
    
    await state.set_state(AdminStates.waiting_for_role_selection)
    
    log_user_action(message.from_user.id, message.from_user.username, "opened role permissions management")

@router.callback_query(AdminStates.waiting_for_role_selection, F.data.startswith("manage_role_permissions:"))
async def process_role_selection(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Обработчик выбора роли из списка"""
    role_id = int(callback.data.split(':')[1])
    
    role = None
    roles = await get_all_roles(session)
    for r in roles:
        if r.id == role_id:
            role = r
            break
    
    if not role:
        await callback.message.answer("Роль не найдена.")
        await callback.answer()
        return
    
    role_perms = await get_role_permissions(session, role.id)
    
    readable_perms = []
    if role_perms:
        for perm in role_perms:
            if perm.description:
                readable_perms.append(perm.description)
    
    if readable_perms:
        perms_display = "\n".join([f"• {perm}" for perm in readable_perms])
    else:
        perms_display = "Нет назначенных прав"
    
    role_info = f"""👑 <b>Информация о роли</b>

📋 <b>Название:</b> {role.name}
📝 <b>Описание:</b> {role.description or "Нет описания"}

🔑 <b>Возможности роли:</b>
{perms_display}"""
    
    keyboard = get_permission_action_keyboard(role.id)
    
    await callback.message.edit_text(
        role_info,
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    
    await state.set_state(AdminStates.waiting_for_permission_action)
    await state.update_data(selected_role_id=role.id, role_name=role.name)
    
    await callback.answer()
    
    log_user_action(
        callback.from_user.id, 
        callback.from_user.username, 
        "selected role for permission management", 
        {"selected_role_id": role.id, "role_name": role.name}
    )

@router.callback_query(AdminStates.waiting_for_permission_action, F.data.startswith("add_permission:"))
async def process_add_permission(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Обработчик кнопки добавления права"""
    role_id = int(callback.data.split(':')[1])
    
    all_permissions = await get_all_permissions(session)
    
    current_permissions = await get_role_permissions(session, role_id)
    current_perm_names = [perm.name for perm in current_permissions]
    
    available_permissions = [perm for perm in all_permissions if perm.name not in current_perm_names]
    
    if not available_permissions:
        await callback.message.answer("Все доступные возможности уже добавлены этой роли.")
        await callback.answer()
        return
    
    keyboard = get_permission_selection_keyboard(available_permissions, role_id, "add")
    
    await callback.message.edit_text(
        "Выбери возможность, которую хочешь добавить этой роли:",
        reply_markup=keyboard
    )
    
    await state.set_state(AdminStates.waiting_for_permission_selection)
    
    await callback.answer()
    
    log_user_action(
        callback.from_user.id, 
        callback.from_user.username, 
        "opened add permission menu", 
        {"role_id": role_id}
    )

@router.callback_query(AdminStates.waiting_for_permission_action, F.data.startswith("remove_permission:"))
async def process_remove_permission(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Обработчик кнопки удаления права"""
    role_id = int(callback.data.split(':')[1])
    
    current_permissions = await get_role_permissions(session, role_id)
    
    if not current_permissions:
        await callback.message.answer("У этой роли нет возможностей, которые можно ограничить.")
        await callback.answer()
        return
    
    keyboard = get_permission_selection_keyboard(current_permissions, role_id, "remove")
    
    await callback.message.edit_text(
        "Выбери возможность, которую хочешь убрать у этой роли:",
        reply_markup=keyboard
    )
    
    await state.set_state(AdminStates.waiting_for_permission_selection)
    
    await callback.answer()
    
    log_user_action(
        callback.from_user.id, 
        callback.from_user.username, 
        "opened remove permission menu", 
        {"role_id": role_id}
    )

@router.callback_query(AdminStates.waiting_for_permission_selection, F.data.startswith("select_permission:"))
async def process_permission_selection(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Обработчик выбора права"""
    parts = callback.data.split(':')
    action = parts[1]
    role_id = int(parts[2])
    permission_name = parts[3]
    
    role = None
    roles = await get_all_roles(session)
    for r in roles:
        if r.id == role_id:
            role = r
            break
    
    permission = await get_permission_by_name(session, permission_name)
    
    if not role or not permission:
        await callback.message.answer("Роль или возможность не найдены.")
        await callback.answer()
        await state.set_state(AdminStates.waiting_for_permission_action)
        return
    
    action_text = "добавить" if action == "add" else "убрать"
    confirmation_text = f"Ты действительно хочешь {action_text} возможность '{permission.description}' для роли '{role.name}'?"
    
    keyboard = get_permission_confirmation_keyboard(action, role.id, permission.name)
    
    await callback.message.edit_text(
        confirmation_text,
        reply_markup=keyboard
    )
    
    await state.set_state(AdminStates.waiting_for_permission_confirmation)
    await state.update_data({
        "selected_role_id": role.id,
        "role_name": role.name,
        "permission_name": permission.name,
        "permission_description": permission.description,
        "action": action
    })
    
    await callback.answer()
    
    log_user_action(
        callback.from_user.id, 
        callback.from_user.username, 
        f"selected {action} permission", 
        {
            "role_id": role.id, 
            "role_name": role.name,
            "permission": permission.name
        }
    )

@router.callback_query(AdminStates.waiting_for_permission_confirmation, F.data.startswith("confirm_permission:"))
async def process_permission_confirmation(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Обработчик подтверждения действия над правом"""

    current_user = await get_user_by_tg_id(session, callback.from_user.id)
    if not current_user:
        await callback.answer("❌ Пользователь не найден.", show_alert=True)
        return
        
    has_permission = await check_user_permission(session, current_user.id, "manage_roles")
    if not has_permission:
        await callback.message.edit_text(
            "❌ <b>Недостаточно прав</b>\n\n"
            "У тебя нет прав для управления правами ролей.\n"
            "Обратись к администратору.",
            parse_mode="HTML"
        )
        await callback.answer()
        return
    
    data = await state.get_data()
    action = data.get("action")
    role_id = data.get("selected_role_id")
    role_name = data.get("role_name")
    permission_name = data.get("permission_name")
    permission_description = data.get("permission_description")
    
    success = False
    if action == "add":
        success = await add_permission_to_role(session, role_id, permission_name)
        result_text = f"✅ Возможность '{permission_description}' успешно расширена для роли."
        log_msg = "added permission to role"
    else:
        success = await remove_permission_from_role(session, role_id, permission_name)
        result_text = f"✅ Возможность '{permission_description}' успешно ограничена для роли."
        log_msg = "removed permission from role"
    
    if success:
        await callback.message.answer(result_text)
        log_user_action(
            callback.from_user.id, 
            callback.from_user.username, 
            log_msg, 
            {
                "role_id": role_id, 
                "role_name": role_name,
                "permission": permission_name
            }
        )
    else:
        await callback.message.answer("❌ Произошла ошибка при выполнении операции.")
        log_user_error(
            callback.from_user.id, 
            callback.from_user.username, 
            f"failed to {action} permission", 
            {
                "role_id": role_id, 
                "role_name": role_name,
                "permission": permission_name
            }
        )
    
    role = None
    roles = await get_all_roles(session)
    for r in roles:
        if r.id == role_id:
            role = r
            break
    
    if role:
        role_perms = await get_role_permissions(session, role.id)
        
        readable_perms = []
        if role_perms:
            for perm in role_perms:
                if perm.description:
                    readable_perms.append(perm.description)
        
        if readable_perms:
            perms_display = "\n".join([f"• {perm}" for perm in readable_perms])
        else:
            perms_display = "Нет назначенных прав"
        
        role_info = f"""👑 <b>Информация о роли</b>

📋 <b>Название:</b> {role.name}
📝 <b>Описание:</b> {role.description or "Нет описания"}

🔑 <b>Возможности роли:</b>
{perms_display}"""
        
        keyboard = get_permission_action_keyboard(role.id)
        
        await callback.message.edit_text(
            role_info,
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        
        await state.set_state(AdminStates.waiting_for_permission_action)
    else:
        await callback.message.edit_text("Роль не найдена. Вернитесь к списку ролей.")
    
    await callback.answer()

@router.callback_query(F.data.startswith("cancel_permission_selection:"))
async def process_cancel_permission_selection(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Обработчик отмены выбора права"""
    role_id = int(callback.data.split(':')[1])
    
    role = None
    roles = await get_all_roles(session)
    for r in roles:
        if r.id == role_id:
            role = r
            break
    
    if not role:
        await callback.message.answer("Роль не найдена.")
        await callback.answer()
        await state.clear()
        return
    
    role_perms = await get_role_permissions(session, role.id)
    
    readable_perms = []
    if role_perms:
        for perm in role_perms:
            if perm.description:
                readable_perms.append(perm.description)
    
    if readable_perms:
        perms_display = "\n".join([f"• {perm}" for perm in readable_perms])
    else:
        perms_display = "Нет назначенных прав"
    
    role_info = f"""👑 <b>Информация о роли</b>

📋 <b>Название:</b> {role.name}
📝 <b>Описание:</b> {role.description or "Нет описания"}

🔑 <b>Возможности роли:</b>
{perms_display}"""
    
    keyboard = get_permission_action_keyboard(role.id)
    
    await callback.message.edit_text(
        role_info,
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    
    await state.set_state(AdminStates.waiting_for_permission_action)
    await state.update_data(selected_role_id=role.id, role_name=role.name)
    
    await callback.answer()
    
    log_user_action(
        callback.from_user.id, 
        callback.from_user.username, 
        "cancelled permission selection", 
        {"role_id": role.id}
    )

@router.callback_query(F.data == "back_to_roles")
async def process_back_to_roles(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Обработчик возврата к списку ролей"""
    await show_roles_list(callback.message, state, session)
    await callback.answer()

@router.callback_query(F.data == "cancel")
async def process_cancel_role_management(callback: CallbackQuery, state: FSMContext):
    """Обработчик отмены управления ролями"""
    await state.clear()
    
    await callback.message.edit_text("Управление правами ролей завершено.")
    
    await callback.answer()
    
    log_user_action(
        callback.from_user.id, 
        callback.from_user.username, 
        "cancelled role management"
    )

@router.callback_query(F.data.startswith("cancel_permission_confirmation:"))
async def process_cancel_permission_confirmation(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Обработчик отмены подтверждения действия над правом"""
    parts = callback.data.split(':')
    action = parts[1]
    role_id = int(parts[2])
    
    permissions = await get_all_permissions(session)
    current_permissions = await get_role_permissions(session, role_id)
    current_perm_names = [perm.name for perm in current_permissions]
    
    if action == "add":
        available_permissions = [perm for perm in permissions if perm.name not in current_perm_names]
        if available_permissions:
            keyboard = get_permission_selection_keyboard(available_permissions, role_id, "add")
            await callback.message.edit_text(
                "Выбери возможность, которую хочешь добавить этой роли:",
                reply_markup=keyboard
            )
        else:
            await callback.message.answer("Все доступные возможности уже добавлены этой роли.")
            process_cancel_permission_selection(callback, state, session)
    else:
        if current_permissions:
            keyboard = get_permission_selection_keyboard(current_permissions, role_id, "remove")
            await callback.message.edit_text(
                "Выбери возможность, которую хочешь убрать у этой роли:",
                reply_markup=keyboard
            )
        else:
            await callback.message.answer("У этой роли нет возможностей, которые можно ограничить.")
            process_cancel_permission_selection(callback, state, session)
    
    await state.set_state(AdminStates.waiting_for_permission_selection)
    
    await callback.answer()
    
    log_user_action(
        callback.from_user.id, 
        callback.from_user.username, 
        "cancelled permission confirmation", 
        {"role_id": role_id, "action": action}
    )

@router.callback_query(F.data.startswith("cancel_role_change:"))
async def process_cancel_role_change(callback: CallbackQuery, state: FSMContext):
    """Обработчик отмены изменения роли пользователя"""
    await state.clear()
    
    await callback.message.edit_text("Изменение роли отменено.")
    
    await callback.answer()
    
    log_user_action(
        callback.from_user.id, 
        callback.from_user.username, 
        "cancelled role change"
    ) 