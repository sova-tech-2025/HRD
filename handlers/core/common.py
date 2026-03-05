from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy.ext.asyncio import AsyncSession

from database.db import get_user_by_tg_id, get_user_roles, check_user_permission
from utils.auth.auth import check_auth
from keyboards.keyboards import format_help_message, get_menu_by_role
from utils.handlers.user import get_validated_user
from utils.handlers.callback import cleanup_callback
from utils.logger import logger, log_user_action
from utils.messages.common import format_profile_text, get_main_menu_text, get_reload_menu_text, get_reload_inline_menu_text
from utils.bot.roles import get_primary_role

router = Router()


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
        [InlineKeyboardButton(text="☰ Главное меню", callback_data="main_menu")]
    ])
    await message.answer(profile_text, parse_mode="HTML", reply_markup=profile_keyboard)


@router.message(F.text.in_(["Мой профиль", "🦸🏻‍♂️ Мой профиль", "Мой профиль 🦸🏻‍♂️"]))
async def button_profile(message: Message, state: FSMContext, session: AsyncSession):
    await cmd_profile(message, state, session)


@router.message(F.text.in_(["Помощь", "❓ Помощь", "Помощь ❓"]))
async def button_help(message: Message, state: FSMContext, session: AsyncSession):
    await cmd_help(message, state, session)

@router.message(F.text == "☰ Главное меню")
async def cmd_inline_main_menu(message: Message, state: FSMContext, session: AsyncSession):
    """Обработчик reply-кнопки 'Главное меню' для наставника и стажера"""
    is_auth = await check_auth(message, state, session)
    if not is_auth:
        return

    user = await get_user_by_tg_id(session, message.from_user.id)
    if not user:
        return

    roles = await get_user_roles(session, user.id)
    primary_role = get_primary_role(roles)

    is_inline = primary_role in ("Стажер", "Наставник")
    main_menu_text = get_main_menu_text(is_inline=is_inline)
    keyboard, photo_source = get_menu_by_role(primary_role)

    if photo_source:
        try:
            await message.answer_photo(
                photo=photo_source,
                caption=main_menu_text,
                parse_mode="HTML",
                reply_markup=keyboard
            )
        except Exception as e:
            logger.warning(f"Не удалось отправить фото меню: {e}")
            await message.answer(main_menu_text, parse_mode="HTML", reply_markup=keyboard)
    else:
        await message.answer(main_menu_text, parse_mode="HTML", reply_markup=keyboard)

    await state.clear()
    log_user_action(message.from_user.id, message.from_user.username, "opened_inline_main_menu")


@router.callback_query(F.data == "main_menu")
async def process_main_menu(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Универсальный обработчик возврата в главное меню с обновлением клавиатуры согласно роли"""
    try:
        user = await get_validated_user(session, callback)
        if not user:
            return

        roles = await get_user_roles(session, user.id)
        primary_role = get_primary_role(roles)

        is_inline = primary_role in ("Наставник", "Стажер")
        main_menu_text = get_main_menu_text(is_inline=is_inline)
        keyboard, photo_source = get_menu_by_role(primary_role)

        if is_inline:
            try:
                await callback.message.delete()
            except Exception:
                pass

        message_sent = False

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

        await cleanup_callback(callback, state)
        log_user_action(callback.from_user.id, callback.from_user.username, "returned_to_main_menu")

    except Exception as e:
        logger.error(f"Ошибка в process_main_menu: {e}")
        await callback.answer("❌ Ошибка при возврате в главное меню", show_alert=True)


@router.callback_query(F.data == "reload_menu")
async def process_reload_menu(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Обработчик кнопки 'Перезагрузка' - обновляет клавиатуру согласно роли пользователя"""
    try:
        user = await get_validated_user(session, callback)
        if not user:
            return

        roles = await get_user_roles(session, user.id)
        primary_role = get_primary_role(roles)

        is_inline = primary_role in ("Наставник", "Стажер")
        keyboard, _ = get_menu_by_role(primary_role)
        reload_text = get_reload_inline_menu_text() if is_inline else get_reload_menu_text()

        if is_inline:
            try:
                await callback.message.delete()
            except Exception:
                pass

        await callback.message.answer(
            reload_text,
            parse_mode="HTML",
            reply_markup=keyboard
        )

        await cleanup_callback(callback, state)
        log_user_action(callback.from_user.id, callback.from_user.username, "reloaded_menu")

    except Exception as e:
        logger.error(f"Ошибка в process_reload_menu: {e}")
        await callback.answer("❌ Ошибка при обновлении клавиатуры", show_alert=True)


@router.callback_query(F.data == "trainee_profile")
async def callback_trainee_profile(callback: CallbackQuery, session: AsyncSession):
    """Обработчик 'Мой профиль' из инлайн-меню стажера"""
    user = await get_validated_user(session, callback)
    if not user:
        return

    profile_text = await format_profile_text(user, session)

    try:
        await callback.message.delete()
    except Exception as e:
        logger.warning(f"Не удалось удалить сообщение: {e}")

    await callback.message.answer(
        profile_text,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="☰ Главное меню", callback_data="main_menu")]
        ])
    )
    await callback.answer()


@router.callback_query(F.data == "trainee_help")
async def callback_trainee_help(callback: CallbackQuery, session: AsyncSession):
    """Обработчик 'Помощь' из инлайн-меню стажера"""
    user = await get_validated_user(session, callback)
    if not user:
        return

    roles = await get_user_roles(session, user.id)
    role_name = get_primary_role(roles)

    help_text = format_help_message(role_name)

    try:
        await callback.message.delete()
    except Exception as e:
        logger.warning(f"Не удалось удалить сообщение: {e}")

    await callback.message.answer(
        help_text,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="☰ Главное меню", callback_data="main_menu")]
        ])
    )
    await callback.answer()
