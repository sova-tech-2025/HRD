from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from database.db import get_user_by_tg_id
from keyboards.keyboards import get_fallback_keyboard
from utils.logger import log_user_action
from utils.messages.fallback import send_fallback_message

router = Router()


@router.message(F.text)
async def handle_unexpected_input_with_state(message: Message, state: FSMContext, session: AsyncSession):
    """Универсальный обработчик для неожиданного ввода в любых состояниях"""
    user = await get_user_by_tg_id(session, message.from_user.id)
    if not user:
        from keyboards.keyboards import get_company_selection_keyboard

        await message.answer(
            "Привет! Добро пожаловать в чат-бот.\n\n🏢 Выбери действие:", reply_markup=get_company_selection_keyboard()
        )
        log_user_action(message.from_user.id, message.from_user.username, "unregistered user sent text")
        return

    current_state = await state.get_state()

    if current_state:
        await message.answer(
            "👀 <b>Команда не распознана</b>\n\n"
            "Бот не знает такую команду. Похоже, ты ввел что-то случайно…\n\n"
            "Вот что можно сделать дальше:",
            parse_mode="HTML",
            reply_markup=get_fallback_keyboard(),
        )

        log_user_action(
            message.from_user.id,
            message.from_user.username,
            "unexpected_input",
            {"state": current_state, "input": message.text[:100]},
        )
    else:
        await send_fallback_message(message, state)


@router.callback_query(F.data & ~F.data.in_(["main_menu", "fallback_back"]))
async def handle_unexpected_callback(callback: CallbackQuery, state: FSMContext):
    """Обработчик для неожиданных callback запросов"""
    current_state = await state.get_state()

    await callback.message.edit_text(
        "👀 <b>Команда не распознана</b>\n\n"
        "Бот не знает такую команду. Похоже, ты ввел что-то случайно…\n\n"
        "Вот что можно сделать дальше:",
        parse_mode="HTML",
        reply_markup=get_fallback_keyboard(),
    )

    await callback.answer("👀 Команда не распознана", show_alert=True)

    log_user_action(
        callback.from_user.id,
        callback.from_user.username,
        "unexpected_callback",
        {"state": current_state, "data": callback.data},
    )
