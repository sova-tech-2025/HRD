"""Общие хелперы для callback-хэндлеров."""
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, FSInputFile
from sqlalchemy.ext.asyncio import AsyncSession

from config import MENTOR_MENU_IMAGE_FILE_ID, MENTOR_MENU_IMAGE_PATH, TRAINEE_MENU_IMAGE_FILE_ID, TRAINEE_MENU_IMAGE_PATH
from database.db import get_user_by_tg_id, get_user_by_id, get_user_roles
from keyboards.keyboards import get_mentor_inline_menu, get_trainee_inline_menu
from utils.logger import logger


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


async def cleanup_callback(callback: CallbackQuery, state: FSMContext):
    """Удаляет старое inline-сообщение и очищает состояние."""
    try:
        await callback.message.delete()
    except Exception:
        pass
    await state.clear()
    await callback.answer()


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
