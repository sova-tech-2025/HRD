from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from states.filters import (
    ENTITY_NAME_FILTER,
    GENERIC_FALLBACK_FILTER,
    GROUP_NAME_FILTER,
    LP_TEST_TEXT_FILTER,
    NUMERIC_INPUT_FILTER,
    OBJECT_NAME_FILTER,
    TEXT_RETRY_FILTER,
    USE_BUTTONS_FILTER,
)
from utils.messages.fallback import send_fallback_message, send_use_buttons_message

router = Router()


@router.message(USE_BUTTONS_FILTER)
async def handle_use_buttons_states(message: Message, state: FSMContext):
    """Обработка неожиданного ввода в состояниях, где нужно использовать кнопки"""
    await send_use_buttons_message(message)


@router.message(TEXT_RETRY_FILTER)
async def handle_text_retry_states(message: Message, state: FSMContext):
    """Обработка повторного ввода текста"""
    await message.answer(
        "🔄 <b>Повтори ввод</b>\n\nПожалуйста, введи текст ещё раз.\n\n"
        "Для отмены используй кнопку 'Отмена' в интерфейсе",
        parse_mode="HTML",
    )


@router.message(GROUP_NAME_FILTER)
async def handle_unexpected_group_name_input(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при создании/переименовании группы"""
    await message.answer(
        "❓ <b>Некорректное название группы</b>\n\n"
        "Пожалуйста, введи корректное название для группы.\n"
        "Название должно содержать только буквы, цифры, пробелы и знаки препинания.\n\n"
        "Для отмены используй кнопку 'Отмена' в интерфейсе",
        parse_mode="HTML",
    )


@router.message(OBJECT_NAME_FILTER)
async def handle_unexpected_object_name_input(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при создании/переименовании объекта"""
    await message.answer(
        "❓ <b>Некорректное название объекта</b>\n\n"
        "Пожалуйста, введи корректное название для объекта.\n"
        "Название должно содержать только буквы, цифры, пробелы и знаки препинания.\n\n"
        "Для отмены используй кнопку 'Отмена' в интерфейсе",
        parse_mode="HTML",
    )


@router.message(ENTITY_NAME_FILTER)
async def handle_unexpected_name_inputs(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при вводе названий (траектория/этап/сессия/аттестация)"""
    await message.answer(
        "❓ <b>Некорректное название</b>\n\n"
        "Пожалуйста, введи корректное название (минимум 3 символа).\n\n"
        "Для отмены используй кнопку 'Отмена' в интерфейсе",
        parse_mode="HTML",
    )


@router.message(NUMERIC_INPUT_FILTER)
async def handle_unexpected_numeric_inputs(message: Message, state: FSMContext):
    """Обработка неожиданного ввода числовых значений (баллы/пороги)"""
    await message.answer(
        "❓ <b>Некорректное число</b>\n\n"
        "Пожалуйста, введи положительное число.\n"
        "Можно использовать дробные числа (например: 1.5)\n\n"
        "Для отмены используй кнопку 'Отмена' в интерфейсе",
        parse_mode="HTML",
    )


@router.message(LP_TEST_TEXT_FILTER)
async def handle_unexpected_lp_test_text_inputs(message: Message, state: FSMContext):
    """Обработка неожиданного текстового ввода при создании теста в траектории"""
    await message.answer(
        "❓ <b>Некорректный ввод</b>\n\n"
        "Пожалуйста, введи корректный текст.\n\n"
        "Для отмены создания теста используй кнопку 'Отмена' в интерфейсе",
        parse_mode="HTML",
    )


@router.message(GENERIC_FALLBACK_FILTER)
async def handle_generic_fallback_states(message: Message, state: FSMContext):
    """Обработка неожиданного ввода — стандартный fallback для множества состояний"""
    await send_fallback_message(message, state)
