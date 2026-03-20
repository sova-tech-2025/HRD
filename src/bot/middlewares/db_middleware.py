from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import Message, TelegramObject

from bot.database.db import get_session
from bot.utils.logger import logger


class DatabaseMiddleware(BaseMiddleware):
    """Middleware для внедрения сессии БД"""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        user_id = getattr(event.from_user, "id", None) if hasattr(event, "from_user") else None
        event_type = type(event).__name__

        if user_id:
            logger.debug(f"Обработка {event_type} от пользователя {user_id}")

        async for session in get_session():
            data["session"] = session

            try:
                result = await handler(event, data)

                if user_id:
                    logger.debug(f"Успешно обработано {event_type} от пользователя {user_id}")

                return result
            except Exception as e:
                await session.rollback()

                if user_id:
                    logger.error(f"Ошибка обработки {event_type} от пользователя {user_id}: {str(e)}")

                if isinstance(event, Message):
                    try:
                        await event.answer("Произошла ошибка при обработке запроса. Пожалуйста, попробуй позже.")
                    except:
                        pass

                raise
