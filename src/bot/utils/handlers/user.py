"""Хелперы для получения и валидации пользователей."""

from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.db import get_user_by_id, get_user_by_tg_id, get_user_roles


async def get_validated_user(session: AsyncSession, callback: CallbackQuery):
    """Получает пользователя, проверяет доступ, возвращает user или None при ошибке."""
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

    return user


async def get_current_user(message: Message, state: FSMContext, session: AsyncSession):
    """Получает текущего пользователя по message.from_user.id или из FSM state.

    Нужен потому что callback.message.from_user — это бот, а не пользователь.
    """
    user = await get_user_by_tg_id(session, message.from_user.id)
    if not user:
        data = await state.get_data()
        user_id = data.get("user_id")
        if user_id:
            user = await get_user_by_id(session, user_id)
    return user
