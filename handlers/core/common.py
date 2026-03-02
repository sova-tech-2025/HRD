from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy.ext.asyncio import AsyncSession

from config import MAIN_MENU_IMAGE_FILE_ID, MAIN_MENU_IMAGE_URL, MAIN_MENU_IMAGE_PATH
from database.db import get_user_by_tg_id, get_user_roles, check_user_permission
from handlers.core.auth import check_auth
from keyboards.keyboards import format_help_message, get_keyboard_by_role
from utils.logger import logger, log_user_action
from utils.roles import get_primary_role

router = Router()


async def format_profile_text(user, session: AsyncSession) -> str:
    """Универсальная функция формирования текста профиля для всех ролей"""
    roles = await get_user_roles(session, user.id)
    primary_role = get_primary_role(roles)

    groups_str = ", ".join([group.name for group in user.groups]) if user.groups else "Не указана"
    groups_label = "Группы" if user.groups and len(user.groups) > 1 else "Группа"

    internship_obj = user.internship_object.name if user.internship_object else "Не указан"
    work_obj = user.work_object.name if user.work_object else "Не указан"

    username_display = f"@{user.username}" if user.username else "Не указан"

    profile_text = f"""🦸🏻‍♂️ <b>Пользователь:</b> {user.full_name}

<b>Телефон:</b> {user.phone_number}
<b>Username:</b> {username_display}
<b>Номер:</b> #{user.id}
<b>Дата регистрации:</b> {user.registration_date.strftime('%d.%m.%Y %H:%M')}

━━━━━━━━━━━━

🗂️ <b>Статус ▾</b>
<b>{groups_label}:</b> {groups_str}
<b>Роль:</b> {primary_role}

━━━━━━━━━━━━

📍 <b>Объект ▾</b>"""

    if primary_role == "Стажер":
        profile_text += f"""
<b>Стажировки:</b> {internship_obj}
<b>Работы:</b> {work_obj}"""
    else:
        profile_text += f"""
<b>Работы:</b> {work_obj}"""

    return profile_text


@router.message(Command("help"))
async def cmd_help(message: Message, state: FSMContext, session: AsyncSession):
    """Показывает справку в зависимости от роли"""
    is_auth = await check_auth(message, state, session)
    if not is_auth:
        await message.answer(format_help_message("Неавторизованный"))
        return

    data = await state.get_data()
    role = data.get("role")

    if not role:
        user = await get_user_by_tg_id(session, message.from_user.id)
        if user:
            roles = await get_user_roles(session, user.id)
            role = get_primary_role(roles)
        else:
            role = "Неавторизованный"

    await message.answer(format_help_message(role))


@router.message(Command("profile"))
async def cmd_profile(message: Message, state: FSMContext, session: AsyncSession):
    is_auth = await check_auth(message, state, session)
    if not is_auth:
        return

    user = await get_user_by_tg_id(session, message.from_user.id)

    has_permission = await check_user_permission(session, user.id, "view_profile")
    if not has_permission:
        await message.answer("У тебя нет прав для просмотра профиля.")
        return

    profile_text = await format_profile_text(user, session)
    profile_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="≡ Главное меню", callback_data="main_menu")]
    ])
    await message.answer(profile_text, parse_mode="HTML", reply_markup=profile_keyboard)


@router.message(F.text.in_(["Мой профиль", "🦸🏻‍♂️ Мой профиль", "Мой профиль 🦸🏻‍♂️"]))
async def button_profile(message: Message, state: FSMContext, session: AsyncSession):
    await cmd_profile(message, state, session)


@router.message(F.text.in_(["Помощь", "❓ Помощь", "Помощь ❓"]))
async def button_help(message: Message, state: FSMContext, session: AsyncSession):
    await cmd_help(message, state, session)


async def _get_user_with_keyboard(session: AsyncSession, callback: CallbackQuery):
    """Получает пользователя, проверяет доступ, возвращает (user, keyboard) или None при ошибке."""
    user = await get_user_by_tg_id(session, callback.from_user.id)
    if not user:
        await callback.answer("❌ Пользователь не найден", show_alert=True)
        return None

    if not user.is_active:
        await callback.answer("❌ Твой аккаунт деактивирован", show_alert=True)
        return None

    roles = await get_user_roles(session, user.id)
    if not roles:
        await callback.answer("❌ Роли не назначены", show_alert=True)
        return None

    primary_role = get_primary_role(roles)
    keyboard = get_keyboard_by_role(primary_role)

    return user, keyboard


async def _cleanup_callback(callback: CallbackQuery, state: FSMContext):
    """Удаляет старое inline-сообщение и очищает состояние."""
    try:
        await callback.message.delete()
    except Exception:
        pass
    await state.clear()
    await callback.answer()


@router.callback_query(F.data == "main_menu")
async def process_main_menu(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Универсальный обработчик возврата в главное меню с обновлением клавиатуры согласно роли"""
    try:
        result = await _get_user_with_keyboard(session, callback)
        if not result:
            return
        _, keyboard = result

        main_menu_text = (
            "≡ Главное меню\n\n"
            "Используй команды бота или кнопки клавиатуры для навигации по системе."
        )

        # Отправляем изображение главного меню, если оно настроено
        message_sent = False
        photo_source = None
        if MAIN_MENU_IMAGE_FILE_ID:
            photo_source = MAIN_MENU_IMAGE_FILE_ID
        elif MAIN_MENU_IMAGE_URL:
            photo_source = MAIN_MENU_IMAGE_URL
        elif MAIN_MENU_IMAGE_PATH:
            try:
                photo_source = FSInputFile(MAIN_MENU_IMAGE_PATH)
            except Exception as file_error:
                logger.warning(f"Не удалось загрузить изображение главного меню из файла: {file_error}")

        if photo_source:
            try:
                await callback.message.answer_photo(
                    photo=photo_source,
                    caption=main_menu_text,
                    parse_mode="HTML",
                    reply_markup=keyboard
                )
                message_sent = True
            except Exception as photo_error:
                logger.warning(f"Не удалось отправить изображение главного меню: {photo_error}")

        if not message_sent:
            await callback.message.answer(
                main_menu_text,
                parse_mode="HTML",
                reply_markup=keyboard
            )

        await _cleanup_callback(callback, state)
        log_user_action(callback.from_user.id, callback.from_user.username, "returned_to_main_menu")

    except Exception as e:
        logger.error(f"Ошибка в process_main_menu: {e}")
        await callback.answer("❌ Ошибка при возврате в главное меню", show_alert=True)


@router.callback_query(F.data == "reload_menu")
async def process_reload_menu(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Обработчик кнопки 'Перезагрузка' - обновляет клавиатуру согласно роли пользователя"""
    try:
        result = await _get_user_with_keyboard(session, callback)
        if not result:
            return
        _, keyboard = result

        await callback.message.answer(
            "🔄 <b>Клавиатура обновлена</b>\n\n"
            "Твоя клавиатура обновлена согласно текущей роли. Используй кнопки для навигации по системе.",
            parse_mode="HTML",
            reply_markup=keyboard
        )

        await _cleanup_callback(callback, state)
        log_user_action(callback.from_user.id, callback.from_user.username, "reloaded_menu")

    except Exception as e:
        logger.error(f"Ошибка в process_reload_menu: {e}")
        await callback.answer("❌ Ошибка при обновлении клавиатуры", show_alert=True)
