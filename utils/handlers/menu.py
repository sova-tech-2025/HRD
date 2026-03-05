"""Хелперы для отправки меню с баннерами."""
from aiogram.types import Message, FSInputFile

from config import (
    MENTOR_MENU_IMAGE_FILE_ID, MENTOR_MENU_IMAGE_PATH,
    TRAINEE_MENU_IMAGE_FILE_ID, TRAINEE_MENU_IMAGE_PATH,
)
from keyboards.keyboards import get_mentor_inline_menu, get_trainee_inline_menu
from utils.logger import logger


async def send_mentor_menu(message: Message):
    """Отправляет главное меню наставника с баннером."""
    menu_text = (
        "☰ <b>Главное меню</b>\n\n"
        "Используй кнопки для навигации по системе"
    )
    photo_source = None
    if MENTOR_MENU_IMAGE_FILE_ID:
        photo_source = MENTOR_MENU_IMAGE_FILE_ID
    elif MENTOR_MENU_IMAGE_PATH:
        try:
            photo_source = FSInputFile(MENTOR_MENU_IMAGE_PATH)
        except Exception:
            pass

    if photo_source:
        try:
            await message.answer_photo(
                photo=photo_source,
                caption=menu_text,
                parse_mode="HTML",
                reply_markup=get_mentor_inline_menu()
            )
            return
        except Exception:
            pass

    await message.answer(
        menu_text,
        parse_mode="HTML",
        reply_markup=get_mentor_inline_menu()
    )


async def send_trainee_menu(message: Message):
    """Отправляет главное меню стажера с баннером."""
    menu_text = (
        "☰ <b>Главное меню</b>\n\n"
        "Используй кнопки для навигации по системе"
    )
    photo_source = None
    if TRAINEE_MENU_IMAGE_FILE_ID:
        photo_source = TRAINEE_MENU_IMAGE_FILE_ID
    elif TRAINEE_MENU_IMAGE_PATH:
        try:
            photo_source = FSInputFile(TRAINEE_MENU_IMAGE_PATH)
        except Exception as e:
            logger.warning(f"Не удалось загрузить изображение меню стажера из файла: {e}")

    if photo_source:
        try:
            await message.answer_photo(
                photo=photo_source,
                caption=menu_text,
                parse_mode="HTML",
                reply_markup=get_trainee_inline_menu()
            )
            return
        except Exception as e:
            logger.warning(f"Не удалось отправить изображение меню стажера: {e}")

    await message.answer(
        menu_text,
        parse_mode="HTML",
        reply_markup=get_trainee_inline_menu()
    )
