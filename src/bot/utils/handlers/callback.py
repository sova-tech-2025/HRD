"""Хелперы для работы с callback-запросами."""

from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.db import get_user_by_tg_id, get_user_roles
from bot.utils.timezone import moscow_now


async def ensure_callback_auth(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> bool:
    """Восстанавливает FSM state для callback-обработчиков.

    callback.message.from_user — бот, поэтому check_auth/get_current_user
    не найдут пользователя без user_id в FSM. Этот хелпер его восстанавливает.
    """
    data = await state.get_data()
    if data.get("is_authenticated") and data.get("user_id"):
        return True

    user = await get_user_by_tg_id(session, callback.from_user.id)
    if not user or not user.is_active:
        await callback.answer("Используй /start для входа", show_alert=True)
        return False

    roles = await get_user_roles(session, user.id)
    primary_role = roles[0].name
    await state.update_data(
        user_id=user.id,
        role=primary_role,
        is_authenticated=True,
        auth_time=moscow_now().timestamp(),
        company_id=user.company_id,
    )
    return True


async def cleanup_callback(callback: CallbackQuery, state: FSMContext):
    """Удаляет старое inline-сообщение и очищает состояние."""
    try:
        await callback.message.delete()
    except Exception:
        pass
    await state.clear()
    await callback.answer()
