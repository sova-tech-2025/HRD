"""Хелперы для отправки меню с баннерами."""
from aiogram.types import Message, FSInputFile, ReplyKeyboardRemove

from config import (
    MENTOR_MENU_IMAGE_FILE_ID, MENTOR_MENU_IMAGE_PATH,
    TRAINEE_MENU_IMAGE_FILE_ID, TRAINEE_MENU_IMAGE_PATH,
)
from keyboards.keyboards import get_keyboard_by_role, get_mentor_inline_menu, get_trainee_inline_menu
from utils.logger import logger


async def send_role_welcome(message: Message, user, primary_role: str):
    """Отправляет приветствие с меню по роли пользователя."""
    if primary_role in ("Наставник", "Стажер"):
        await message.answer(
            f"Добро пожаловать, {user.full_name}! Ты вошел как {primary_role}.",
            reply_markup=ReplyKeyboardRemove()
        )
        if primary_role == "Наставник":
            await send_mentor_menu(message)
        if primary_role == "Стажер":
            await send_trainee_menu(message)
    else:
        await message.answer(
            f"Добро пожаловать, {user.full_name}! Ты вошел как {primary_role}.",
            reply_markup=get_keyboard_by_role(primary_role)
        )


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
