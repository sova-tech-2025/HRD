from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.db import get_user_by_tg_id
from bot.handlers.company.company import callback_back_to_company_join_welcome
from bot.keyboards.keyboards import get_company_selection_keyboard
from bot.states.states import RegistrationStates
from bot.utils.auth.auth import validate_user_access
from bot.utils.bot.commands import set_bot_commands
from bot.utils.handlers.menu import send_role_welcome
from bot.utils.logger import log_user_action, log_user_error

router = Router()


@router.callback_query(F.data == "login_again")
async def callback_login_again(callback: CallbackQuery, state: FSMContext, session: AsyncSession, bot):
    """Кнопка быстрого входа заново после истечения сессии"""
    await cmd_login(callback.message, state, session, bot, tg_user=callback.from_user)
    await callback.answer()


@router.message(Command("login"))
async def cmd_login(message: Message, state: FSMContext, session: AsyncSession, bot, tg_user=None):
    try:
        actor = tg_user or message.from_user
        user = await get_user_by_tg_id(session, actor.id)

        if not user:
            await message.answer(
                "Привет! Добро пожаловать в чат-бот.\n\n🏢 Выбери действие:",
                reply_markup=get_company_selection_keyboard(),
            )
            log_user_action(actor.id, actor.username, "failed login attempt - not registered")
            return

        is_valid, error_msg, primary_role = await validate_user_access(session, user)
        if not is_valid:
            await message.answer(error_msg)
            log_user_error(actor.id, actor.username, "login failed - access denied")
            return

        await send_role_welcome(message, user, primary_role)
        await set_bot_commands(bot, primary_role)

        await state.update_data(
            user_id=user.id,
            role=primary_role,
            is_authenticated=True,
            auth_time=message.date.timestamp(),
            company_id=user.company_id,
        )

        log_user_action(
            actor.id,
            actor.username,
            "successful login",
            {"role": primary_role, "user_id": user.id, "company_id": user.company_id},
        )
    except Exception as e:
        log_user_error(actor.id, actor.username, "login error", e)
        await message.answer("Произошла ошибка при входе в систему. Пожалуйста, попробуй позже.")


@router.message(Command("logout"))
async def cmd_logout(message: Message, state: FSMContext, bot):
    try:
        data = await state.get_data()
        user_id = data.get("user_id")
        role = data.get("role")

        await state.clear()
        await set_bot_commands(bot)
        await message.answer("Ты вышел из системы. Используй /login для входа.")

        log_user_action(
            message.from_user.id,
            message.from_user.username,
            "logout",
            {"role": role, "user_id": user_id} if user_id else None,
        )
    except Exception as e:
        log_user_error(message.from_user.id, message.from_user.username, "logout error", e)
        await message.answer("Произошла ошибка при выходе из системы. Пожалуйста, попробуй еще раз.")


@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext, session: AsyncSession, bot):
    try:
        await state.clear()
        user = await get_user_by_tg_id(session, message.from_user.id)

        if not user:
            await set_bot_commands(bot)
            await message.answer(
                "Привет! Добро пожаловать в чат-бот.\n\n🏢 Выбери действие:",
                reply_markup=get_company_selection_keyboard(),
            )
            log_user_action(
                message.from_user.id,
                message.from_user.username,
                "started bot - not registered",
            )
            return

        is_valid, error_msg, primary_role = await validate_user_access(session, user)
        if not is_valid:
            await message.answer(error_msg)
            log_user_error(
                message.from_user.id,
                message.from_user.username,
                "start failed - access denied",
            )
            return

        log_user_action(
            message.from_user.id,
            message.from_user.username,
            "started bot - already registered",
        )

        await send_role_welcome(message, user, primary_role)
        await set_bot_commands(bot, primary_role)

        await state.update_data(
            user_id=user.id,
            role=primary_role,
            is_authenticated=True,
            auth_time=message.date.timestamp(),
            company_id=user.company_id,
        )

        log_user_action(
            message.from_user.id,
            message.from_user.username,
            "successful login from start",
            {"role": primary_role, "user_id": user.id, "company_id": user.company_id},
        )
    except Exception as e:
        log_user_error(message.from_user.id, message.from_user.username, "start command error", e)
        await message.answer("Произошла ошибка при запуске бота. Пожалуйста, попробуй позже.")


@router.callback_query(F.data == "register:normal")
async def callback_register_normal(callback: CallbackQuery, state: FSMContext):
    """Обработчик обычной регистрации"""
    # Проверяем, присоединяется ли пользователь к компании
    user_data = await state.get_data()
    company_id = user_data.get("company_id")

    # Выбираем правильный callback для кнопки "Назад"
    back_callback = "back_to_company_join_welcome" if company_id else "back_to_welcome"

    await callback.message.edit_text(
        "Начинаем регистрацию 🚩\nПожалуйста, введи свою фамилию и имя\n\nПример: Иванов Иван",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="⬅️ Назад", callback_data=back_callback)]]
        ),
    )
    await state.set_state(RegistrationStates.waiting_for_full_name)
    log_user_action(
        callback.from_user.id,
        callback.from_user.username,
        "started normal registration",
    )
    await callback.answer()


@router.callback_query(F.data == "back_to_welcome")
async def callback_back_to_welcome(callback: CallbackQuery, state: FSMContext):
    """Обработчик возврата к стартовому экрану"""
    # Проверяем, присоединяется ли пользователь к компании
    user_data = await state.get_data()
    company_id = user_data.get("company_id")

    if company_id:
        callback.data = "back_to_company_join_welcome"
        await callback_back_to_company_join_welcome(callback, state)
        return

    # Обычный возврат - очищаем состояние
    await state.clear()
    await callback.message.edit_text(
        "Привет! Добро пожаловать в чат-бот.\n\n🏢 Выбери действие:",
        reply_markup=get_company_selection_keyboard(),
    )
    log_user_action(callback.from_user.id, callback.from_user.username, "returned to welcome screen")
    await callback.answer()
