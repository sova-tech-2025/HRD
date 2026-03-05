import logging
import traceback
from aiogram import Router
from aiogram.types import ErrorEvent, Update
from aiogram.exceptions import TelegramAPIError, TelegramRetryAfter

from utils.logger import logger

router = Router()

@router.errors()
async def error_handler(error_event: ErrorEvent):
    """Глобальный обработчик исключений"""
    update = error_event.update
    exception = error_event.exception
    
    error_msg = f"Исключение: {exception}\n"
    error_msg += f"Обновление: {update}\n"
    error_msg += f"Трассировка: {traceback.format_exc()}"
    
    logger.error(error_msg)
    
    if isinstance(exception, TelegramRetryAfter):
        retry_after = exception.retry_after
        logger.warning(f"Превышен лимит API Telegram. Повторная попытка через {retry_after} секунд.")
        return True
    
    if isinstance(exception, TelegramAPIError):
        logger.warning(f"Ошибка API Telegram: {exception}")
        return True
    
    logger.error(f"Необработанное исключение: {exception}")
    return True 