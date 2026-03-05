"""Общие хелперы для callback-хэндлеров."""
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from database.db import get_user_by_tg_id, get_user_roles
from keyboards.keyboards import get_keyboard_by_role
from utils.roles import get_primary_role


async def get_user_with_keyboard(session: AsyncSession, callback: CallbackQuery):
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


async def cleanup_callback(callback: CallbackQuery, state: FSMContext):
    """Удаляет старое inline-сообщение и очищает состояние."""
    try:
        await callback.message.delete()
    except Exception:
        pass
    await state.clear()
    await callback.answer()
