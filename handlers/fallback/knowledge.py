from aiogram import Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from states.states import KnowledgeBaseStates

router = Router()


@router.message(StateFilter(KnowledgeBaseStates.waiting_for_folder_name))
async def handle_unexpected_folder_name_input(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при создании папки"""
    if not message.text:
        await message.answer(
            "❓ <b>Неправильный формат</b>\n\n"
            "Название папки должно быть текстом.\n\n"
            "📝 <b>Требования:</b>\n"
            "• Только текст (без файлов, изображений)\n"
            "• От 3 до 50 символов\n"
            "• Уникальное название\n\n"
            "Попробуй ещё раз или используй кнопку 'Отмена' в интерфейсе",
            parse_mode="HTML",
        )


@router.message(StateFilter(KnowledgeBaseStates.waiting_for_material_name))
async def handle_unexpected_material_name_input(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при создании материала"""
    if not message.text:
        await message.answer(
            "❓ <b>Неправильный формат</b>\n\n"
            "Название материала должно быть текстом.\n\n"
            "📝 <b>Требования:</b>\n"
            "• Только текст (без файлов, изображений)\n"
            "• От 3 до 100 символов\n"
            "• Понятное название для сотрудников\n\n"
            "Попробуй ещё раз или используй кнопку 'Отмена' в интерфейсе",
            parse_mode="HTML",
        )


@router.message(StateFilter(KnowledgeBaseStates.waiting_for_material_content))
async def handle_unexpected_material_content_input(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при добавлении содержимого материала"""
    if not message.text and not message.document:
        await message.answer(
            "❓ <b>Неправильный формат</b>\n\n"
            "Содержимое материала должно быть ссылкой или документом.\n\n"
            "📎 <b>Поддерживаемые форматы:</b>\n"
            "• Ссылка (URL) - отправь текстом\n"
            "• Документы: PDF, DOC, DOCX, TXT, RTF, ODT\n"
            "• Таблицы: XLS, XLSX\n"
            "• Презентации: PPT, PPTX\n"
            "• Изображения: JPG, PNG, GIF, WEBP\n\n"
            "Попробуй ещё раз или используй кнопку 'Отмена' в интерфейсе",
            parse_mode="HTML",
        )


@router.message(StateFilter(KnowledgeBaseStates.waiting_for_material_description))
async def handle_unexpected_material_description_input(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при добавлении описания материала"""
    if not message.text:
        await message.answer(
            "❓ <b>Неправильный формат</b>\n\n"
            "Описание материала должно быть текстом.\n\n"
            "📝 <b>Как правильно:</b>\n"
            "• Введи описание текстом\n"
            '• Или нажми "⏩Пропустить" для продолжения без описания\n\n'
            "Попробуй ещё раз или используй кнопку 'Отмена' в интерфейсе",
            parse_mode="HTML",
        )


@router.message(StateFilter(KnowledgeBaseStates.waiting_for_material_photos))
async def handle_unexpected_material_photos_input(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при добавлении фотографий к материалу"""
    if not message.photo and not message.media_group_id:
        await message.answer(
            "❓ <b>Неправильный формат</b>\n\n"
            "Ожидаются фотографии для материала.\n\n"
            "🖼️ <b>Как правильно:</b>\n"
            "• Отправь фотографию или несколько фотографий\n"
            '• Или нажми "⏩Пропустить" для продолжения без фото\n\n'
            "Попробуй ещё раз или используй кнопку 'Отмена' в интерфейсе",
            parse_mode="HTML",
        )
