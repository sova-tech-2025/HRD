from aiogram import Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from bot.states.states import AttestationStates, LearningPathStates, ManagerAttestationStates

router = Router()


@router.message(StateFilter(ManagerAttestationStates.waiting_for_date))
async def handle_unexpected_date_input(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при вводе даты аттестации"""
    await message.answer(
        "❓ <b>Неправильный формат даты</b>\n\n"
        "Пожалуйста, введи дату в формате: <code>ДД.ММ.ГГГГ</code>\n\n"
        "📅 <b>Примеры корректного ввода:</b>\n"
        "• 28.08.2025\n"
        "• 01.12.2025\n"
        "• 15.09.2025\n\n"
        "Для отмены используй кнопку 'Отмена' в интерфейсе",
        parse_mode="HTML",
    )


@router.message(StateFilter(ManagerAttestationStates.waiting_for_time))
async def handle_unexpected_time_input(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при вводе времени аттестации"""
    await message.answer(
        "❓ <b>Неправильный формат времени</b>\n\n"
        "Пожалуйста, введи время в формате: <code>ЧЧ:ММ</code>\n\n"
        "⏰ <b>Примеры корректного ввода:</b>\n"
        "• 12:00\n"
        "• 09:30\n"
        "• 16:45\n\n"
        "Для отмены используй кнопку 'Отмена' в интерфейсе",
        parse_mode="HTML",
    )


@router.message(StateFilter(ManagerAttestationStates.waiting_for_score))
async def handle_unexpected_score_input(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при оценке вопроса аттестации"""
    await message.answer(
        "❓ <b>Неправильный формат балла</b>\n\n"
        "Пожалуйста, введи балл числом от 0 до максимального балла за вопрос.\n\n"
        "📊 <b>Примеры корректного ввода:</b>\n"
        "• 10 - отличный ответ\n"
        "• 5 - удовлетворительный ответ\n"
        "• 0 - неправильный/отсутствующий ответ\n\n"
        "⚠️ Балл не может быть больше максимального или отрицательным.\n\n"
        "Для отмены используй кнопку 'Отмена' в интерфейсе",
        parse_mode="HTML",
    )


@router.message(StateFilter(LearningPathStates.waiting_for_attestation_confirmation))
async def handle_unexpected_attestation_confirmation_input(message: Message, state: FSMContext):
    """Fallback для состояния подтверждения аттестации"""
    await message.answer(
        "⚠️ <b>Пожалуйста, используй кнопки!</b>\n\n"
        "📋 Доступные действия:\n"
        "• ✅Да - подтвердить добавление аттестации\n"
        "• 🚫Отменить - вернуться к выбору аттестации\n\n"
        "❓ Нажмите на соответствующую кнопку ниже.",
        parse_mode="HTML",
    )


@router.message(StateFilter(AttestationStates.waiting_for_attestation_question))
async def handle_unexpected_attestation_question_input(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при добавлении вопроса аттестации"""
    await message.answer(
        "❓ <b>Некорректный вопрос аттестации</b>\n\n"
        "Пожалуйста, введи полный текст вопроса с критериями оценки.\n\n"
        "Формат вопроса должен включать:\n"
        "• Сам вопрос\n"
        "• Правильный ответ или критерии\n"
        "• Систему оценки (например: все назвал - 10, половину - 5, ничего - 0)\n\n"
        "Для отмены используй кнопку 'Отмена' в интерфейсе",
        parse_mode="HTML",
    )


@router.message(StateFilter(LearningPathStates.creating_test_materials))
async def handle_unexpected_test_materials_input(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при добавлении материалов"""
    await message.answer(
        "❓ <b>Некорректные материалы</b>\n\n"
        "Пожалуйста, отправь:\n"
        "• Ссылку на материалы\n"
        "• Документы: PDF, DOC, DOCX, XLS, XLSX, PPT, PPTX\n"
        "• Изображения: JPG, PNG, GIF, WEBP\n"
        "• Или нажми кнопку 'Пропустить'\n\n"
        "Для отмены создания теста используй кнопку 'Отменить' в интерфейсе",
        parse_mode="HTML",
    )
