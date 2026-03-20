from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject


class BotMiddleware(BaseMiddleware):
    """Middleware для автоматического добавления bot instance в data"""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        # Добавляем bot в data для всех типов событий
        if hasattr(event, "bot"):
            data["bot"] = event.bot
        elif hasattr(event, "message") and hasattr(event.message, "bot"):
            data["bot"] = event.message.bot

        return await handler(event, data)
