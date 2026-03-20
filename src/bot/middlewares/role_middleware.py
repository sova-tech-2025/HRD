from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import Message, TelegramObject
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.db import check_user_permission, get_user_by_tg_id


class RoleMiddleware(BaseMiddleware):
    """Middleware для проверки ролей и прав пользователя"""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        if not isinstance(event, Message):
            return await handler(event, data)

        session = data.get("session")
        if not session or not isinstance(session, AsyncSession):
            return await handler(event, data)

        user = await get_user_by_tg_id(session, event.from_user.id)

        if not user:
            return await handler(event, data)

        data["user"] = user

        required_permission = data.get("required_permission")
        if required_permission:
            has_permission = await check_user_permission(session, user.id, required_permission)
            if not has_permission:
                await event.answer("У тебя нет прав для выполнения этого действия.")
                return None

        return await handler(event, data)
