"""Получение источника фото для меню по конфиг-переменным."""

from aiogram.types import FSInputFile

from bot.config import (
    MAIN_MENU_IMAGE_FILE_ID,
    MAIN_MENU_IMAGE_PATH,
    MAIN_MENU_IMAGE_URL,
    MENTOR_MENU_IMAGE_FILE_ID,
    MENTOR_MENU_IMAGE_PATH,
    TRAINEE_MENU_IMAGE_FILE_ID,
    TRAINEE_MENU_IMAGE_PATH,
)
from bot.utils.logger import logger


def _resolve_photo(file_id: str | None, path: str | None, url: str | None = None):
    """Возвращает источник фото по приоритету: file_id -> url -> path -> None."""
    if file_id:
        return file_id
    if url:
        return url
    if path:
        try:
            return FSInputFile(path)
        except Exception as e:
            logger.warning(f"Не удалось загрузить изображение из файла: {e}")
    return None


def get_mentor_menu_photo():
    return _resolve_photo(MENTOR_MENU_IMAGE_FILE_ID, MENTOR_MENU_IMAGE_PATH)


def get_trainee_menu_photo():
    return _resolve_photo(TRAINEE_MENU_IMAGE_FILE_ID, TRAINEE_MENU_IMAGE_PATH)


def get_main_menu_photo():
    return _resolve_photo(MAIN_MENU_IMAGE_FILE_ID, MAIN_MENU_IMAGE_PATH, MAIN_MENU_IMAGE_URL)
