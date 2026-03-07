from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from keyboards.keyboards import get_fallback_keyboard


async def send_fallback_message(message: Message, state: FSMContext):
    """Универсальная функция для отправки fallback сообщения с неожиданным вводом"""
    await message.answer(
        "👀 <b>Команда не распознана</b>\n\n"
        "Бот не знает такую команду. Похоже, ты ввел что-то случайно…\n\n"
        "Вот что можно сделать дальше:",
        parse_mode="HTML",
        reply_markup=get_fallback_keyboard(),
    )


async def send_use_buttons_message(message: Message):
    """Сообщение для состояний, где нужно использовать кнопки"""
    await message.answer(
        "❌ <b>Некорректный выбор</b>\n\n"
        "Пожалуйста, используй кнопки для выбора действия.\n\n"
        "Для отмены используй кнопку 'Отмена' в интерфейсе",
        parse_mode="HTML",
    )
