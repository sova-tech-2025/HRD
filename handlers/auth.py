import os
import time
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from database.db import get_user_by_tg_id, get_user_roles
from keyboards.keyboards import get_keyboard_by_role, get_welcome_keyboard
from states.states import AuthStates, RegistrationStates
from utils.logger import log_user_action, log_user_error
from utils.bot_commands import set_bot_commands

router = Router()

@router.message(Command("login"))
async def cmd_login(message: Message, state: FSMContext, session: AsyncSession, bot):
    try:
        user = await get_user_by_tg_id(session, message.from_user.id)
        
        if not user:
            await message.answer("Ты не зарегистрирован в системе. Используй команду /register для регистрации.")
            log_user_action(message.from_user.id, message.from_user.username, "failed login attempt - not registered")
            return
        
        if not user.is_active:
            await message.answer("Твой аккаунт деактивирован. Обратись к администратору.")
            log_user_error(message.from_user.id, message.from_user.username, "login failed - account deactivated")
            return
        
        roles = await get_user_roles(session, user.id)
        
        if not roles:
            await message.answer("У тебя нет назначенных ролей. Обратись к рекрутеру.")
            log_user_error(message.from_user.id, message.from_user.username, "login failed - no roles assigned")
            return
        
        primary_role = roles[0].name
        
        await message.answer(
            f"Добро пожаловать, {user.full_name}! Ты вошел как {primary_role}.",
            reply_markup=get_keyboard_by_role(primary_role)
        )
        
        await set_bot_commands(bot, primary_role)
        
        await state.update_data(
            user_id=user.id,
            role=primary_role,
            is_authenticated=True,
            auth_time=message.date.timestamp()
        )

        log_user_action(
            message.from_user.id,
            message.from_user.username,
            "successful login",
            {"role": primary_role, "user_id": user.id}
        )

        # не очищаем состояние после успешного логина
        # await state.clear()
    except Exception as e:
        log_user_error(message.from_user.id, message.from_user.username, "login error", e)
        await message.answer("Произошла ошибка при входе в систему. Пожалуйста, попробуй позже.")

async def check_auth(message: Message, state: FSMContext, session: AsyncSession) -> bool:
    try:
        data = await state.get_data()
        is_authenticated = data.get("is_authenticated", False)
        auth_time = data.get("auth_time", 0)
        
        if is_authenticated and auth_time and (time.time() - auth_time) > 28800:  # 8 часов (рабочий день)
            await state.clear()
            await message.answer("Сессия истекла. Пожалуйста, войдите заново командой /login.")
            return False
        
        if is_authenticated:
            user = await get_user_by_tg_id(session, message.from_user.id)
            if not user or not user.is_active:
                await state.clear()
                await message.answer("Твой аккаунт деактивирован. Обратись к администратору.")
                return False
            return True
        
        user = await get_user_by_tg_id(session, message.from_user.id)
        
        if not user:
            await message.answer("Ты не зарегистрирован в системе. Используй команду /register для регистрации.")
            return False
        
        if not user.is_active:
            await message.answer("Твой аккаунт деактивирован. Обратись к администратору.")
            return False
        
        auto_auth_allowed = os.getenv("ALLOW_AUTO_AUTH", "true").lower() == "true"
        if not auto_auth_allowed:
            await message.answer("Пожалуйста, выполни команду /login для входа.")
            return False
        
        roles = await get_user_roles(session, user.id)
        
        if not roles:
            await message.answer("У тебя нет назначенных ролей. Обратись к рекрутеру.")
            return False
        
        primary_role = roles[0].name
        
        await state.update_data(
            user_id=user.id,
            role=primary_role,
            is_authenticated=True,
            auth_time=message.date.timestamp()
        )
        
        log_user_action(
            message.from_user.id, 
            message.from_user.username, 
            "auto authentication", 
            {"role": primary_role, "user_id": user.id}
        )
        
        return True
    except Exception as e:
        log_user_error(message.from_user.id, message.from_user.username, "authentication check error", e)
        await message.answer("Произошла ошибка при проверке авторизации. Пожалуйста, попробуй позже.")
        return False

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
            {"role": role, "user_id": user_id} if user_id else None
        )
    except Exception as e:
        log_user_error(message.from_user.id, message.from_user.username, "logout error", e)
        await message.answer("Произошла ошибка при выходе из системы. Пожалуйста, попробуй еще раз.")

@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext, session: AsyncSession, bot):
    try:
        user = await get_user_by_tg_id(session, message.from_user.id)
        
        if not user:
            await set_bot_commands(bot)
            await message.answer(
                "Привет! Добро пожаловать в чат-бот.\n\n"
                "Ты ещё не зарегистрирован. Давай подключим тебе доступ.",
                reply_markup=get_welcome_keyboard()
            )
            log_user_action(message.from_user.id, message.from_user.username, "started bot - not registered")
            return
        
        log_user_action(message.from_user.id, message.from_user.username, "started bot - already registered")
        
        roles = await get_user_roles(session, user.id)
        
        if not roles:
            await message.answer("У тебя нет назначенных ролей. Обратись к рекрутеру.")
            log_user_error(message.from_user.id, message.from_user.username, "login failed - no roles assigned")
            return
        
        primary_role = roles[0].name
        
        await message.answer(
            f"Добро пожаловать, {user.full_name}! Ты вошел как {primary_role}.",
            reply_markup=get_keyboard_by_role(primary_role)
        )
        
        await set_bot_commands(bot, primary_role)
        
        await state.update_data(
            user_id=user.id,
            role=primary_role,
            is_authenticated=True,
            auth_time=message.date.timestamp()
        )
        
        log_user_action(
            message.from_user.id, 
            message.from_user.username, 
            "successful login from start", 
            {"role": primary_role, "user_id": user.id}
        )
    except Exception as e:
        log_user_error(message.from_user.id, message.from_user.username, "start command error", e)
        await message.answer("Произошла ошибка при запуске бота. Пожалуйста, попробуй позже.")


@router.callback_query(F.data == "register:normal")
async def callback_register_normal(callback: CallbackQuery, state: FSMContext):
    """Обработчик обычной регистрации"""
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    
    await callback.message.edit_text(
        "Начинаем регистрацию 🚩\nПожалуйста, введи свою фамилию и имя\n\nПример: Иванов Иван",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_welcome")]
        ])
    )
    await state.set_state(RegistrationStates.waiting_for_full_name)
    log_user_action(callback.from_user.id, callback.from_user.username, "started normal registration")
    await callback.answer()


@router.callback_query(F.data == "register:with_code")
async def callback_register_with_code(callback: CallbackQuery, state: FSMContext):
    """Обработчик регистрации с кодом"""
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    
    # Помечаем, что это регистрация с кода (токен сначала)
    await state.update_data(registration_flow="code_first")
    
    await callback.message.edit_text(
        "Если ты сюда попал случайно, просто вернись назад ⬅️\n"
        "Этот шаг нужен только тем, кому рекрутер выдал специальный код\n\n"
        "Если есть код, введи его ниже",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_welcome")]
        ])
    )
    await state.set_state(RegistrationStates.waiting_for_admin_token)
    log_user_action(callback.from_user.id, callback.from_user.username, "started registration with code")
    await callback.answer()


@router.callback_query(F.data == "back_to_welcome")
async def callback_back_to_welcome(callback: CallbackQuery, state: FSMContext):
    """Обработчик возврата к стартовому экрану"""
    await state.clear()
    await callback.message.edit_text(
        "Привет! Добро пожаловать в чат-бот.\n\n"
        "Ты ещё не зарегистрирован. Давай подключим тебе доступ.",
        reply_markup=get_welcome_keyboard()
    )
    log_user_action(callback.from_user.id, callback.from_user.username, "returned to welcome screen")
    await callback.answer() 