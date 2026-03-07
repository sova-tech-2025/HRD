from aiogram import Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from keyboards.keyboards import get_role_selection_keyboard
from states.states import RegistrationStates
from utils.messages.fallback import send_fallback_message

router = Router()


@router.message(StateFilter(RegistrationStates.waiting_for_full_name))
async def handle_unexpected_name_input(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при запросе имени"""
    if not message.text or len(message.text.strip()) < 2:
        await message.answer(
            "❌ <b>Некорректное имя</b>\n\n"
            "Пожалуйста, введи своё полное имя (минимум 2 символа).\n"
            "Например: <code>Иван Петров</code>\n\n"
            "Для отмены регистрации используй кнопку 'Отмена' в интерфейсе",
            parse_mode="HTML",
        )
    else:
        await send_fallback_message(message, state)


@router.message(StateFilter(RegistrationStates.waiting_for_phone))
async def handle_unexpected_phone_input(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при запросе телефона"""
    await message.answer(
        "❌ <b>Некорректный формат телефона</b>\n\n"
        "Пожалуйста, отправь свой номер телефона, используя кнопку 'Поделиться контактом' или введи в формате:\n"
        "• <code>+7 (999) 123-45-67</code>\n"
        "• <code>89991234567</code>\n\n"
        "Для отмены регистрации используй кнопку 'Отмена' в интерфейсе",
        parse_mode="HTML",
    )


@router.message(StateFilter(RegistrationStates.waiting_for_role))
async def handle_unexpected_role_input(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при выборе роли"""
    await message.answer(
        "❌ <b>Некорректный выбор роли</b>\n\nПожалуйста, выбери роль, используя кнопки ниже:",
        parse_mode="HTML",
        reply_markup=get_role_selection_keyboard(),
    )
