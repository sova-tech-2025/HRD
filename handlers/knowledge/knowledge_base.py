"""
Обработчики для системы базы знаний (Task 9).
Включает создание, управление и просмотр папок и материалов базы знаний.
"""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto, InputMediaDocument
from aiogram.fsm.context import FSMContext
from aiogram.filters import StateFilter
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List
import os

from database.db import (
    get_user_by_tg_id, check_user_permission,
    create_knowledge_folder, get_all_knowledge_folders, get_knowledge_folder_by_id,
    update_knowledge_folder_name, delete_knowledge_folder,
    create_knowledge_material, get_knowledge_material_by_id, delete_knowledge_material,
    set_folder_access_groups, get_folder_access_info, get_all_groups,
    check_folder_access, get_accessible_knowledge_folders_for_user, ensure_company_id
)
from states.states import KnowledgeBaseStates
from utils.auth.auth import check_auth
from utils.handlers.user import get_current_user
from utils.handlers.callback import ensure_callback_auth
from keyboards.keyboards import (
    get_knowledge_base_main_keyboard, get_knowledge_folders_keyboard,
    get_folder_created_keyboard, get_material_description_keyboard,
    get_material_save_keyboard, get_material_saved_keyboard,
    get_folder_view_keyboard, get_material_view_keyboard,
    get_material_delete_confirmation_keyboard, get_group_access_selection_keyboard,
    get_folder_rename_confirmation_keyboard, get_folder_delete_confirmation_keyboard,
    get_folder_deleted_keyboard, get_employee_knowledge_folders_keyboard,
    get_employee_folder_materials_keyboard, get_employee_material_view_keyboard
)
from utils.logger import log_user_action, log_user_error, logger
from utils.validators import validate_name

router = Router()


# ===============================
# Вспомогательные функции
# ===============================

# ===============================
# Обработчики для рекрутера и сотрудника (база знаний)
# ===============================

async def start_material_addition(callback: CallbackQuery, state: FSMContext, session: AsyncSession, folder_id: int) -> bool:
    """
    Общая логика начала добавления материала в папку.
    
    Args:
        callback: Callback query от пользователя
        state: FSM контекст
        session: Сессия БД
        folder_id: ID папки для добавления материала
        
    Returns:
        bool: True если успешно, False если ошибка
    """
    try:
        # Получаем company_id для изоляции
        company_id = await ensure_company_id(session, state, callback.from_user.id)
        if company_id is None:
            await callback.message.edit_text(
                "❌ Не удалось определить компанию. Обнови сессию командой /start."
            )
            await state.clear()
            log_user_error(callback.from_user.id, "knowledge_base_company_missing", "company_id not resolved")
            return False
        
        # Получаем информацию о папке
        folder = await get_knowledge_folder_by_id(session, folder_id, company_id=company_id)
        if not folder:
            await callback.message.edit_text("❌ Папка не найдена")
            await state.clear()
            return False
            
        # Сохраняем folder_id и сбрасываем поля текущего материала в состоянии
        await state.update_data(
            current_folder_id=folder_id,
            material_name=None,
            material_content=None,
            material_type=None,
            material_description="",
            material_photos=[],
            material_number=None,
        )
        
        # ТЗ 9-1 шаг 8: Запрашиваем название материала
        await callback.message.edit_text(
            "📚РЕДАКТОР БАЗЫ ЗНАНИЙ📚\n\n"
            f"📁Папка: {folder.name}\n\n"
            "🟡Введи название материала:",
            parse_mode="HTML"
        )
        
        await state.set_state(KnowledgeBaseStates.waiting_for_material_name)
        log_user_action(callback.from_user.id, "material_creation_started", f"Начато создание материала в папке {folder.name}")
        return True
        
    except Exception as e:
        logger.error(f"Ошибка начала добавления материала: {e}")
        return False


@router.message(F.text.in_(["База знаний", "База знаний 📁️", "База знаний 📒"]))
async def cmd_knowledge_base_universal(message: Message, state: FSMContext, session: AsyncSession):
    """Универсальный обработчик кнопки 'База знаний' для рекрутера, сотрудника и стажера (ТЗ 9-1 шаг 1)"""
    try:
        # Проверка авторизации
        is_auth = await check_auth(message, state, session)
        if not is_auth:
            return

        # Получение пользователя
        user = await get_current_user(message, state, session)
        if not user:
            await message.answer("❌ Ты не зарегистрирован в системе.")
            return

        # Определяем роль пользователя
        user_roles = [role.name for role in user.roles]
        
        # РЕКРУТЕР - управление базой знаний (ТЗ 9-1 шаг 1)
        if "Рекрутер" in user_roles:
            has_permission = await check_user_permission(session, user.id, "manage_groups")
            if not has_permission:
                await message.answer("❌ У тебя нет прав для управления базой знаний.")
                return

            # Получаем company_id
            company_id = await ensure_company_id(session, state, message.from_user.id)
            if company_id is None:
                await message.answer("❌ Не удалось определить компанию. Обнови сессию командой /start.")
                await state.clear()
                log_user_error(message.from_user.id, "kb_recruiter_company_missing", "company_id not resolved")
                return
            # Получаем все папки
            folders = await get_all_knowledge_folders(session, company_id)
            
            if not folders:
                # ТЗ 9-1 шаг 2: Нет папок
                await message.answer(
                    "📚РЕДАКТОР БАЗЫ ЗНАНИЙ📚\n\n"
                    "Ты не создал ни одной папки",
                    reply_markup=get_knowledge_base_main_keyboard(has_folders=False),
                    parse_mode="HTML"
                )
            else:
                # ТЗ 9-2 шаг 2: Есть папки
                await message.answer(
                    "📚РЕДАКТОР БАЗЫ ЗНАНИЙ📚\n\n"
                    "Ниже на клавиатуре ты видишь список всех созданных папок в системе👇\n"
                    "🟡Выбери действие или папку, чтобы продолжить",
                    reply_markup=get_knowledge_folders_keyboard(folders),
                    parse_mode="HTML"
                )

            await state.set_state(KnowledgeBaseStates.main_menu)
            log_user_action(message.from_user.id, "knowledge_base_opened", "Открыта база знаний (рекрутер)")
            
        # ПРОСМОТР БАЗЫ ЗНАНИЙ - для Стажеров, Сотрудников, Наставников и Руководителей
        elif "Стажер" in user_roles or "Сотрудник" in user_roles or "Наставник" in user_roles or "Руководитель" in user_roles:
            has_permission = await check_user_permission(session, user.id, "view_knowledge_base")
            if not has_permission:
                await message.answer("❌ У тебя нет прав для просмотра базы знаний.")
                return

            # Получаем company_id
            company_id = await ensure_company_id(session, state, message.from_user.id)
            if company_id is None:
                await message.answer("❌ Не удалось определить компанию. Обнови сессию командой /start.")
                await state.clear()
                log_user_error(message.from_user.id, "kb_employee_company_missing", "company_id not resolved")
                return
            # Получаем папки, доступные пользователю
            accessible_folders = await get_accessible_knowledge_folders_for_user(session, user.id, company_id)

            if not accessible_folders:
                await message.answer(
                    "📚 <b>База знаний</b>\n\n"
                    "В данный момент для тебя нет доступных материалов.\n"
                    "Обратись к рекрутеру для получения доступа к необходимым разделам.",
                    parse_mode="HTML",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="☰ Главное меню", callback_data="main_menu")]
                    ])
                )
            else:
                await message.answer(
                    "📚 <b>База знаний</b>\n\n"
                    "Выбери раздел для изучения материалов:",
                    reply_markup=get_employee_knowledge_folders_keyboard(accessible_folders),
                    parse_mode="HTML"
                )

            await state.set_state(KnowledgeBaseStates.employee_browsing)

            # Определяем роль для логирования
            role_name = "стажер"
            if "Сотрудник" in user_roles:
                role_name = "сотрудник"
            elif "Наставник" in user_roles:
                role_name = "наставник"
            elif "Руководитель" in user_roles:
                role_name = "руководитель"

            log_user_action(message.from_user.id, f"{role_name}_knowledge_base_opened", f"Открыта база знаний ({role_name})")

        else:
            await message.answer("❌ База знаний доступна только для авторизованных пользователей.")

    except Exception as e:
        await message.answer("Произошла ошибка при открытии базы знаний")
        log_user_error(message.from_user.id, "knowledge_base_universal_error", str(e))


@router.callback_query(F.data == "trainee_knowledge_base")
async def callback_trainee_knowledge_base(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Обработчик инлайн-кнопки 'База знаний 📒' из меню стажера"""
    if not await ensure_callback_auth(callback, state, session):
        return
    try:
        await callback.message.delete()
    except Exception as e:
        logger.warning(f"Не удалось удалить сообщение: {e}")

    await cmd_knowledge_base_universal(callback.message, state, session)
    await callback.answer()


@router.callback_query(F.data == "kb_create_folder", StateFilter(KnowledgeBaseStates.main_menu))
async def callback_create_folder(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Начало создания папки (ТЗ 9-1 шаг 3)"""
    try:
        await callback.answer()
        
        # Проверяем права
        user = await get_user_by_tg_id(session, callback.from_user.id)
        if not user:
            await callback.message.edit_text("❌ Пользователь не найден")
            return
            
        has_permission = await check_user_permission(session, user.id, "manage_groups")
        if not has_permission:
            await callback.message.edit_text("❌ У тебя нет прав для этой операции.")
            return
        
        # ТЗ 9-1 шаг 4
        await callback.message.edit_text(
            "📚РЕДАКТОР БАЗЫ ЗНАНИЙ📚\n\n"
            "Введи название для новой папки:",
            parse_mode="HTML"
        )
        
        await state.set_state(KnowledgeBaseStates.waiting_for_folder_name)
        log_user_action(callback.from_user.id, "folder_creation_started", "Начато создание папки")
        
    except Exception as e:
        await callback.message.edit_text("Произошла ошибка при создании папки")
        log_user_error(callback.from_user.id, "create_folder_error", str(e))


@router.message(StateFilter(KnowledgeBaseStates.waiting_for_folder_name))
async def process_folder_name(message: Message, state: FSMContext, session: AsyncSession):
    """Обработка названия новой папки (ТЗ 9-1 шаг 5)"""
    try:
        folder_name = message.text.strip()
        
        # Валидация названия
        if not validate_name(folder_name):
            await message.answer("❌ Некорректное название папки. Название должно содержать от 2 до 100 символов и состоять из букв, цифр и основных знаков препинания.")
            return
            
        # Получаем пользователя
        user = await get_user_by_tg_id(session, message.from_user.id)
        if not user:
            await message.answer("❌ Ошибка получения данных пользователя")
            await state.clear()
            return
        
        # Получаем company_id
        company_id = await ensure_company_id(session, state, message.from_user.id)
        if company_id is None:
            await message.answer("❌ Не удалось определить компанию. Обнови сессию командой /start.")
            await state.clear()
            log_user_error(message.from_user.id, "kb_folder_create_company_missing", "company_id not resolved")
            return
            
        # Создаем папку
        folder = await create_knowledge_folder(session, folder_name, user.id, None, company_id)
        if not folder:
            await message.answer("❌ Не удалось создать папку. Возможно, папка с таким названием уже существует.")
            return
        
        # Сохраняем изменения в базу данных
        await session.commit()
        
        # ТЗ 9-1 шаг 6: Папка создана успешно
        await message.answer(
            "📚РЕДАКТОР БАЗЫ ЗНАНИЙ📚\n\n"
            "✅Ты успешно добавил новую папку в базу знаний!\n"
            f"Название папки: {folder_name}\n"
            "Добавить материалы в папку?",
            reply_markup=get_folder_created_keyboard(),
            parse_mode="HTML"
        )
        
        # Сохраняем ID созданной папки в состояние
        await state.update_data(current_folder_id=folder.id)
        await state.set_state(KnowledgeBaseStates.folder_created_add_material)
        
        log_user_action(message.from_user.id, "folder_created", f"Создана папка: {folder_name}")
        
    except Exception as e:
        await message.answer("Произошла ошибка при создании папки")
        log_user_error(message.from_user.id, "process_folder_name_error", str(e))


@router.callback_query(F.data == "kb_add_material", StateFilter(KnowledgeBaseStates.folder_created_add_material))
async def callback_add_material(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Начало добавления материала в папку (ТЗ 9-1 шаг 7)"""
    try:
        await callback.answer()
        
        # Проверяем права
        user = await get_user_by_tg_id(session, callback.from_user.id)
        if not user:
            await callback.message.edit_text("❌ Пользователь не найден")
            return
            
        has_permission = await check_user_permission(session, user.id, "manage_groups")
        if not has_permission:
            await callback.message.edit_text("❌ У тебя нет прав для этой операции.")
            return
        
        data = await state.get_data()
        folder_id = data.get("current_folder_id")
        
        if not folder_id:
            await callback.message.edit_text("❌ Ошибка: папка не найдена")
            await state.clear()
            return
        
        # Используем общую функцию для начала добавления материала
        success = await start_material_addition(callback, state, session, folder_id)
        if not success:
            await callback.message.edit_text("Произошла ошибка при добавлении материала")
        
    except Exception as e:
        await callback.message.edit_text("Произошла ошибка при добавлении материала")
        log_user_error(callback.from_user.id, "add_material_error", str(e))


@router.callback_query(F.data.startswith("kb_add_material_to_folder:"), StateFilter(KnowledgeBaseStates.main_menu, KnowledgeBaseStates.viewing_folder))
async def callback_add_material_to_existing_folder(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Начало добавления материала в существующую папку"""
    try:
        await callback.answer()
        
        # Проверяем права
        user = await get_user_by_tg_id(session, callback.from_user.id)
        if not user:
            await callback.message.edit_text("❌ Пользователь не найден")
            return
            
        has_permission = await check_user_permission(session, user.id, "manage_groups")
        if not has_permission:
            await callback.message.edit_text("❌ У тебя нет прав для этой операции.")
            return
        
        # Извлекаем folder_id из callback_data
        folder_id = int(callback.data.split(":")[1])
        
        # Используем общую функцию для начала добавления материала
        success = await start_material_addition(callback, state, session, folder_id)
        if not success:
            await callback.message.edit_text("Произошла ошибка при добавлении материала")
        
    except Exception as e:
        await callback.message.edit_text("Произошла ошибка при добавлении материала")
        log_user_error(callback.from_user.id, "add_material_to_existing_folder_error", str(e))


@router.message(StateFilter(KnowledgeBaseStates.waiting_for_material_name))
async def process_material_name(message: Message, state: FSMContext, session: AsyncSession):
    """Обработка названия материала (ТЗ 9-1 шаг 9)"""
    try:
        material_name = message.text.strip()
        
        # Валидация названия
        if not validate_name(material_name):
            await message.answer("❌ Некорректное название материала. Название должно содержать от 2 до 100 символов и состоять из букв, цифр и основных знаков препинания.")
            return
            
        data = await state.get_data()
        folder_id = data.get("current_folder_id")
        company_id = await ensure_company_id(session, state, message.from_user.id)
        if company_id is None:
            await message.answer("❌ Не удалось определить компанию. Обнови сессию командой /start.")
            await state.clear()
            log_user_error(message.from_user.id, "material_name_company_missing", "company_id not resolved")
            return
        
        if not folder_id:
            await message.answer("❌ Ошибка: папка не найдена")
            await state.clear()
            return
            
        # Получаем папку
        folder = await get_knowledge_folder_by_id(session, folder_id, company_id=company_id)
        if not folder:
            await message.answer("❌ Папка не найдена")
            await state.clear()
            return
            
        # Обновляем состояние
        await state.update_data(material_name=material_name)
        
        # Получаем количество существующих материалов для правильной нумерации
        material_number = len(folder.materials) + 1
        
        # ТЗ 9-1 шаг 10
        await message.answer(
            "📚РЕДАКТОР БАЗЫ ЗНАНИЙ📚\n\n"
            f"📁Папка: {folder.name}\n\n"
            f"🔗Материал {material_number}: {material_name}\n"
            "🟡Отправь документ или ссылку с материалом",
            parse_mode="HTML"
        )
        
        await state.set_state(KnowledgeBaseStates.waiting_for_material_content)
        log_user_action(message.from_user.id, "material_name_set", f"Название материала: {material_name}")
        
    except Exception as e:
        await message.answer("Произошла ошибка при обработке названия материала")
        log_user_error(message.from_user.id, "process_material_name_error", str(e))


@router.message(StateFilter(KnowledgeBaseStates.waiting_for_material_content))
async def process_material_content(message: Message, state: FSMContext, session: AsyncSession):
    """Обработка содержимого материала (ТЗ 9-1 шаг 11)"""
    try:
        data = await state.get_data()
        folder_id = data.get("current_folder_id")
        material_name = data.get("material_name")
        company_id = await ensure_company_id(session, state, message.from_user.id)
        if company_id is None:
            await message.answer("❌ Не удалось определить компанию. Обнови сессию командой /start.")
            await state.clear()
            log_user_error(message.from_user.id, "material_content_company_missing", "company_id not resolved")
            return

        if not folder_id or not material_name:
            await message.answer("❌ Ошибка данных состояния")
            await state.clear()
            return

        # Получаем папку
        folder = await get_knowledge_folder_by_id(session, folder_id, company_id=company_id)
        if not folder:
            await message.answer("❌ Папка не найдена")
            await state.clear()
            return

        material_content = ""
        material_type = "link"

        # Обрабатываем документ или текст
        if message.document:
            # Проверяем тип файла и размер
            allowed_mimes = {
                'application/pdf',
                'application/msword',  # .doc
                'application/vnd.openxmlformats-officedocument.wordprocessingml.document',  # .docx
                'application/vnd.ms-excel',  # .xls
                'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',  # .xlsx
                'application/vnd.ms-powerpoint',  # .ppt
                'application/vnd.openxmlformats-officedocument.presentationml.presentation',  # .pptx
                'image/jpeg', 'image/png', 'image/gif', 'image/webp',
                'text/plain',  # .txt
                'application/rtf',  # .rtf
                'application/vnd.oasis.opendocument.text',  # .odt
                'video/mp4',  # .mp4
                'video/quicktime'  # .mov
            }
            
            if message.document.mime_type in allowed_mimes:
                # Проверяем размер файла (50MB лимит)
                max_size = 50 * 1024 * 1024  # 50MB
                if message.document.file_size > max_size:
                    await message.answer(f"❌ Файл слишком большой. Максимальный размер: {max_size // (1024*1024)}MB")
                    return

                # Сохраняем file_id документа (в т.ч. изображений без сжатия)
                material_content = message.document.file_id
                # Определяем тип материала по расширению;
                # изображения, присланные как документ, считаем документом (без сжатия)
                ext = os.path.splitext(message.document.file_name)[1].lower()
                if ext in {'.mp4', '.mov'}:
                    material_type = "video"
                elif ext in {'.xls', '.xlsx'}:
                    material_type = "excel"
                elif ext in {'.ppt', '.pptx'}:
                    material_type = "presentation"
                elif ext in {'.doc', '.docx'}:
                    material_type = "document"
                elif ext in {'.jpg', '.jpeg', '.png', '.gif', '.webp'}:
                    # Фото прислано как файл — отправляем как документ (без сжатия)
                    material_type = "document"
                else:
                    material_type = "pdf"
                await message.answer("✅ Документ успешно добавлен!")
            else:
                await message.answer(
                    "❌ Неподдерживаемый формат файла."
                )
                return
        elif message.photo:
            # Пользователь отправил фото напрямую
            photo_file_id = message.photo[-1].file_id
            material_content = photo_file_id
            material_type = "photo"
            await message.answer("✅ Изображение добавлено!")
        elif message.video:
            # Пользователь отправил видео напрямую
            video_file_id = message.video.file_id
            material_content = video_file_id
            material_type = "video"
            await message.answer("✅ Видео добавлено!")
        elif message.text:
            # Ссылка
            material_content = message.text.strip()
            material_type = "link"
        else:
            await message.answer(
                "❌ Отправь документ, изображение или ссылку"
            )
            return

        # Обновляем состояние
        await state.update_data(
            material_content=material_content,
            material_type=material_type
        )

        # Получаем количество существующих материалов для правильной нумерации
        material_number = len(folder.materials) + 1
        
        # Обновляем состояние с номером материала
        await state.update_data(material_number=material_number)
        
        # ТЗ 9-1 шаг 12
        content_display = material_content if material_type == "link" else "Документ"
        await message.answer(
            "📚РЕДАКТОР БАЗЫ ЗНАНИЙ📚\n\n"
            f"📁Папка: {folder.name}\n\n"
            f"🔗Материал {material_number}: {material_name}\n"
            f"🟢Вложение: {content_display}\n"
            "🟡Описание: введи описание для материала, чтобы сотрудники лучше понимали для чего им этот документ / ссылка, либо нажми \"⏩Пропустить\"",
            reply_markup=get_material_description_keyboard(),
            parse_mode="HTML"
        )
        
        await state.set_state(KnowledgeBaseStates.waiting_for_material_description)
        log_user_action(message.from_user.id, "material_content_set", f"Содержимое материала: {material_type}")
        
    except Exception as e:
        await message.answer("Произошла ошибка при обработке содержимого материала")
        log_user_error(message.from_user.id, "process_material_content_error", str(e))


@router.callback_query(F.data == "kb_skip_description", KnowledgeBaseStates.waiting_for_material_description)
async def callback_skip_description(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Пропуск описания материала"""
    try:
        await callback.answer()
        await state.update_data(material_description="")
        await show_photo_upload_option(callback, state, session)

    except Exception as e:
        await callback.message.edit_text("Произошла ошибка при пропуске описания")
        log_user_error(callback.from_user.id, "skip_description_error", str(e))


@router.callback_query(F.data == "kb_skip_photos", KnowledgeBaseStates.waiting_for_material_photos)
async def callback_skip_photos(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Пропуск добавления фотографий к материалу"""
    try:
        await callback.answer()
        await state.update_data(material_photos=[])  # Пустой список фотографий
        await show_material_confirmation(callback, state, session)

    except Exception as e:
        await callback.message.edit_text("Произошла ошибка при пропуске фотографий")
        log_user_error(callback.from_user.id, "skip_photos_error", str(e))


@router.message(F.photo, StateFilter(KnowledgeBaseStates.waiting_for_material_photos))
async def process_material_photos(message: Message, state: FSMContext, session: AsyncSession):
    """Обработка фотографий для материала"""
    try:
        photos = []  # будет списком элементов вида {"id": file_id, "kind": "photo"|"document"}

        # Обрабатываем фотографии
        if message.photo:
            # Одна фотография
            photos = [{"id": message.photo[-1].file_id, "kind": "photo"}]  # Берем фото с максимальным разрешением
        elif message.document and message.document.mime_type and message.document.mime_type.startswith("image/"):
            # Изображение отправлено как документ (без сжатия)
            photos = [{"id": message.document.file_id, "kind": "document"}]
        elif message.media_group_id:
            # Несколько фотографий (альбом)
            await message.answer(
                "⚠️ При отправке альбома фото обрабатываются по отдельности.\n"
                "Рекомендуется отправлять по одному."
            )
            if message.photo:
                photos = [{"id": message.photo[-1].file_id, "kind": "photo"}]
        else:
            await message.answer("❌ Пожалуйста, отправь фотографию или нажми '⏩Пропустить'")
            return

        # Получаем текущие фотографии из состояния
        data = await state.get_data()
        # Безопасная инициализация (исключить перенос None/старых значений)
        current_photos = data.get('material_photos') or []
        # Нормализуем: если в состоянии лежат строки (наследие) — приводим к объектам
        normalized = []
        for item in current_photos:
            if isinstance(item, dict):
                normalized.append(item)
            else:
                normalized.append({"id": item, "kind": "photo"})
        normalized.extend(photos)
        
        # Проверяем лимит
        if len(normalized) >= 10:
            await message.answer(
                "❌ Достигнут лимит!\n\n"
                "Можно добавить максимум 10 фотографий к материалу.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="✅Продолжить", callback_data="kb_finish_photos")]
                ])
            )
            return

        # Обновляем состояние
        await state.update_data(material_photos=normalized)

        # Показываем сколько фотографий добавлено и предлагаем добавить еще или продолжить
        photos_count = len(normalized)
        response_text = f"🖼️ Добавлено фотографий: {photos_count}\n\n"
        response_text += "Отправь еще фотографии или нажми кнопку для продолжения."

        keyboard_buttons = [
            [InlineKeyboardButton(text="✅Продолжить", callback_data="kb_finish_photos")],
            [InlineKeyboardButton(text="≡ Главное меню", callback_data="main_menu")]
        ]
        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)

        await message.answer(response_text, reply_markup=keyboard)
        log_user_action(message.from_user.id, "material_photos_added", f"Добавлено {len(photos)} фото к материалу, всего: {photos_count}")

    except Exception as e:
        await message.answer("Произошла ошибка при обработке фотографий")
        log_user_error(message.from_user.id, "process_material_photos_error", str(e))


@router.message(F.document, StateFilter(KnowledgeBaseStates.waiting_for_material_photos))
async def process_material_image_docs(message: Message, state: FSMContext, session: AsyncSession):
    """Обработка изображений-документов (фото без сжатия) для материала"""
    try:
        # Проверяем, что это изображение
        if not message.document or not message.document.mime_type or not message.document.mime_type.startswith("image/"):
            await message.answer("❌ Пришли изображение или используй обычные фото")
            return
        
        # Создаём объект фото с пометкой "document"
        photos = [{"id": message.document.file_id, "kind": "document"}]
        
        # Получаем текущие фотографии из состояния
        data = await state.get_data()
        current_photos = data.get('material_photos') or []
        
        # Нормализуем существующие
        normalized = []
        for item in current_photos:
            if isinstance(item, dict):
                normalized.append(item)
            else:
                normalized.append({"id": item, "kind": "photo"})
        normalized.extend(photos)
        
        # Проверяем лимит
        if len(normalized) >= 10:
            await message.answer(
                "❌ Достигнут лимит!\n\n"
                "Можно добавить максимум 10 фотографий к материалу.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="✅Продолжить", callback_data="kb_finish_photos")]
                ])
            )
            return
        
        # Обновляем состояние
        await state.update_data(material_photos=normalized)
        
        # Показываем результат
        photos_count = len(normalized)
        response_text = f"🖼️ Добавлено фотографий: {photos_count}\n\n"
        response_text += "Отправь еще фотографии или нажми кнопку для продолжения."
        
        keyboard_buttons = [
            [InlineKeyboardButton(text="✅Продолжить", callback_data="kb_finish_photos")],
            [InlineKeyboardButton(text="≡ Главное меню", callback_data="main_menu")]
        ]
        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
        
        await message.answer(response_text, reply_markup=keyboard)
        log_user_action(message.from_user.id, "material_image_doc_added", f"Добавлен image-document к материалу, всего: {photos_count}")
        
    except Exception as e:
        await message.answer("Произошла ошибка при загрузке изображения-документа")
        log_user_error(message.from_user.id, "process_material_image_docs_error", str(e))


@router.message(StateFilter(KnowledgeBaseStates.waiting_for_material_photos))
async def process_material_wrong_content(message: Message, state: FSMContext, session: AsyncSession):
    """Обработка неправильного типа контента"""
    await message.answer(
        "❌ Неподдерживаемый тип!\n\n"
        "Отправь фотографию или изображение-документ.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅Продолжить", callback_data="kb_finish_photos")],
            [InlineKeyboardButton(text="≡ Главное меню", callback_data="main_menu")]
        ])
    )


@router.callback_query(F.data == "kb_finish_photos", KnowledgeBaseStates.waiting_for_material_photos)
async def callback_finish_photos(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Завершение добавления фотографий и переход к подтверждению"""
    try:
        await callback.answer()
        await show_material_confirmation(callback, state, session)

    except Exception as e:
        await callback.message.edit_text("Произошла ошибка при завершении добавления фотографий")
        log_user_error(callback.from_user.id, "finish_photos_error", str(e))


@router.message(StateFilter(KnowledgeBaseStates.waiting_for_material_description))
async def process_material_description(message: Message, state: FSMContext, session: AsyncSession):
    """Обработка описания материала (ТЗ 9-1 шаг 13)"""
    try:
        description = message.text.strip() if message.text else ""
        await state.update_data(material_description=description)
        await show_photo_upload_option(message, state, session)

    except Exception as e:
        await message.answer("Произошла ошибка при обработке описания")
        log_user_error(message.from_user.id, "process_material_description_error", str(e))


async def show_photo_upload_option(message_or_callback, state: FSMContext, session: AsyncSession):
    """Предложение добавить фотографии к материалу (необязательный шаг)"""
    try:
        data = await state.get_data()
        folder_id = data.get("current_folder_id")
        material_name = data.get("material_name")
        material_content = data.get("material_content")
        material_type = data.get("material_type")
        material_description = data.get("material_description", "")

        if hasattr(message_or_callback, "from_user") and message_or_callback.from_user:
            user_id = message_or_callback.from_user.id
        elif hasattr(message_or_callback, "message") and message_or_callback.message and message_or_callback.message.from_user:
            user_id = message_or_callback.message.from_user.id
        else:
            user_id = None

        company_id = await ensure_company_id(session, state, user_id) if user_id else None
        if company_id is None:
            if hasattr(message_or_callback, 'text') or hasattr(message_or_callback, 'photo'):
                await message_or_callback.answer("❌ Не удалось определить компанию. Обнови сессию командой /start.")
            else:
                await message_or_callback.message.edit_text("❌ Не удалось определить компанию. Обнови сессию командой /start.")
            await state.clear()
            if user_id:
                log_user_error(user_id, "material_photo_option_company_missing", "company_id not resolved")
            return

        # Получаем папку
        folder = await get_knowledge_folder_by_id(session, folder_id, company_id=company_id)
        if not folder:
            if hasattr(message_or_callback, 'text') or hasattr(message_or_callback, 'photo'):
                await message_or_callback.answer("❌ Папка не найдена")
            else:
                await message_or_callback.message.edit_text("❌ Папка не найдена")
            await state.clear()
            return

        # Формируем сообщение с информацией о материале
        content_display = material_content if material_type == "link" else "Документ"
        description_display = material_description if material_description else "Без описания"

        message_text = (
            "📚РЕДАКТОР БАЗЫ ЗНАНИЙ📚\n\n"
            f"📁Папка: {folder.name}\n\n"
            f"🔗Материал: {material_name}\n"
            f"🟢Вложение: {content_display}\n"
            f"🟢Описание: {description_display}\n\n"
            "🖼️Хотите добавить фотографии к этому материалу?\n"
            "Фотографии помогут лучше иллюстрировать содержание материала.\n\n"
            "Отправь фотографии по одной или сразу несколько, либо пропусти этот шаг."
        )

        keyboard_buttons = [
            [InlineKeyboardButton(text="⏩Пропустить", callback_data="kb_skip_photos")],
            [InlineKeyboardButton(text="≡ Главное меню", callback_data="main_menu")]
        ]
        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)

        if hasattr(message_or_callback, 'text') or hasattr(message_or_callback, 'photo'):
            # Message
            await message_or_callback.answer(message_text, reply_markup=keyboard, parse_mode="HTML")
        else:
            # CallbackQuery
            await message_or_callback.message.edit_text(message_text, reply_markup=keyboard, parse_mode="HTML")

        await state.set_state(KnowledgeBaseStates.waiting_for_material_photos)
        log_user_action(message_or_callback.from_user.id if hasattr(message_or_callback, 'from_user') else message_or_callback.from_user.id,
                       "material_photo_upload_offered", f"Предложено добавить фото к материалу: {material_name}")

    except Exception as e:
        error_msg = "Произошла ошибка при предложении добавить фотографии"
        if hasattr(message_or_callback, 'text') or hasattr(message_or_callback, 'photo'):
            await message_or_callback.answer(error_msg)
        else:
            await message_or_callback.message.edit_text(error_msg)
        log_user_error(message_or_callback.from_user.id if hasattr(message_or_callback, 'from_user') else message_or_callback.from_user.id,
                      "show_photo_upload_option_error", str(e))


async def show_material_confirmation(message_or_callback, state: FSMContext, session: AsyncSession):
    """Показ подтверждения сохранения материала (ТЗ 9-1 шаг 14)"""
    try:
        data = await state.get_data()
        folder_id = data.get("current_folder_id")
        material_name = data.get("material_name")
        material_content = data.get("material_content")
        material_type = data.get("material_type")
        material_description = data.get("material_description", "")
        material_photos = data.get("material_photos", [])
        material_number = data.get("material_number", 1)

        if hasattr(message_or_callback, "from_user") and message_or_callback.from_user:
            user_id = message_or_callback.from_user.id
        elif hasattr(message_or_callback, "message") and message_or_callback.message and message_or_callback.message.from_user:
            user_id = message_or_callback.message.from_user.id
        else:
            user_id = None

        company_id = await ensure_company_id(session, state, user_id) if user_id else None
        if company_id is None:
            if hasattr(message_or_callback, 'text') or hasattr(message_or_callback, 'photo'):
                await message_or_callback.answer("❌ Не удалось определить компанию. Обнови сессию командой /start.")
            else:
                await message_or_callback.message.edit_text("❌ Не удалось определить компанию. Обнови сессию командой /start.")
            await state.clear()
            if user_id:
                log_user_error(user_id, "material_confirmation_company_missing", "company_id not resolved")
            return

        # Получаем папку
        folder = await get_knowledge_folder_by_id(session, folder_id, company_id=company_id)
        if not folder:
            if hasattr(message_or_callback, 'text') or hasattr(message_or_callback, 'photo'):
                await message_or_callback.answer("❌ Папка не найдена")
            else:
                await message_or_callback.message.edit_text("❌ Папка не найдена")
            await state.clear()
            return

        # Формируем сообщение подтверждения
        content_display = material_content if material_type == "link" else "Документ"
        description_display = material_description if material_description else "Без описания"
        photos_count = 0
        if material_photos:
            if isinstance(material_photos[0], dict):
                photos_count = len(material_photos)
            else:
                photos_count = len(material_photos)
        photos_display = f"{photos_count} фото" if photos_count > 0 else "Без фотографий"

        confirmation_text = (
            "📚РЕДАКТОР БАЗЫ ЗНАНИЙ📚\n\n"
            f"📁Папка: {folder.name}\n\n"
            f"🔗Материал {material_number}: {material_name}\n"
            f"🟢Вложение: {content_display}\n"
            f"🟢Описание: {description_display}\n"
            f"🖼️Фотографии: {photos_display}\n\n"
            "🟡Сохранить материал в папке?"
        )
        
        if hasattr(message_or_callback, 'text') or hasattr(message_or_callback, 'photo'):
            # Message
            await message_or_callback.answer(
                confirmation_text,
                reply_markup=get_material_save_keyboard(),
                parse_mode="HTML"
            )
        else:
            # CallbackQuery
            await message_or_callback.message.edit_text(
                confirmation_text,
                reply_markup=get_material_save_keyboard(),
                parse_mode="HTML"
            )
        
        await state.set_state(KnowledgeBaseStates.confirming_material_save)
        
    except Exception as e:
        error_text = "Произошла ошибка при подтверждении материала"
        if hasattr(message_or_callback, 'text') or hasattr(message_or_callback, 'photo'):
            await message_or_callback.answer(error_text)
        else:
            await message_or_callback.message.edit_text(error_text)
        log_user_error(message_or_callback.from_user.id, "show_material_confirmation_error", str(e))


@router.callback_query(F.data == "kb_save_material", KnowledgeBaseStates.confirming_material_save)
async def callback_save_material(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Сохранение материала (ТЗ 9-1 шаг 15)"""
    try:
        await callback.answer()
        
        # Проверяем права
        user = await get_user_by_tg_id(session, callback.from_user.id)
        if not user:
            await callback.message.edit_text("❌ Пользователь не найден")
            return
            
        has_permission = await check_user_permission(session, user.id, "manage_groups")
        if not has_permission:
            await callback.message.edit_text("❌ У тебя нет прав для этой операции.")
            return
        
        data = await state.get_data()
        folder_id = data.get("current_folder_id")
        material_name = data.get("material_name")
        material_content = data.get("material_content")
        material_type = data.get("material_type")
        material_description = data.get("material_description", "")
        material_photos = data.get("material_photos", [])

        # Получаем пользователя
        user = await get_user_by_tg_id(session, callback.from_user.id)
        if not user:
            await callback.message.edit_text("❌ Ошибка получения данных пользователя")
            await state.clear()
            return

        # Создаем материал
        material = await create_knowledge_material(
            session, folder_id, material_name, material_type,
            material_content, user.id, material_description, material_photos
        )
        
        if not material:
            await callback.message.edit_text("❌ Не удалось создать материал")
            return
        
        # Сохраняем изменения в базу данных
        await session.commit()
        
        # Получаем папку для отображения
        folder = await get_knowledge_folder_by_id(session, folder_id, company_id=user.company_id)
        
        # ТЗ 9-1 шаг 16: Материал сохранен - показываем только активные материалы в папке
        materials_display = []
        active_materials = [mat for mat in folder.materials if mat.is_active]
        for i, mat in enumerate(active_materials, 1):
            mat_content = mat.content if mat.material_type == "link" else "Документ"
            mat_description = mat.description if mat.description else "Без описания"
            photos_info = ""
            if mat.photos and len(mat.photos) > 0:
                photos_info = f"\n🖼️Фотографий: {len(mat.photos)}"

            materials_display.append(
                f"🔗Материал {i}: {mat.name}\n"
                f"🟢Вложение: {mat_content}\n"
                f"🟢 Описание: {mat_description}{photos_info}"
            )
        
        materials_text = "\n\n".join(materials_display)
        
        # Формируем финальное сообщение
        final_message = (
            "📚РЕДАКТОР БАЗЫ ЗНАНИЙ📚\n\n"
            f"📁Папка: {folder.name}\n\n"
            f"{materials_text}\n\n"
            "✅Ты успешно сохранил материал!\n"
            "Теперь ты можешь его найти в базе знаний"
        )
        
        # Проверяем длину текста
        if len(final_message) > 4096:
            final_message = (
                "📚РЕДАКТОР БАЗЫ ЗНАНИЙ📚\n\n"
                f"📁Папка: {folder.name}\n\n"
                "✅Ты успешно сохранил материал!\n\n"
                f"В папке теперь {len(active_materials)} материалов."
            )
        
        await callback.message.edit_text(
            final_message,
            reply_markup=get_material_saved_keyboard(folder_id),
            parse_mode="HTML"
        )
        # Очищаем пер-материальные поля, оставляя текущую папку для быстрого добавления следующего материала
        await state.update_data(
            material_name=None,
            material_content=None,
            material_type=None,
            material_description="",
            material_photos=[],
            material_number=None,
        )

        await state.set_state(KnowledgeBaseStates.folder_created_add_material)
        log_user_action(callback.from_user.id, "material_created", f"Создан материал: {material_name}")
        
    except Exception as e:
        await callback.message.edit_text("Произошла ошибка при сохранении материала")
        log_user_error(callback.from_user.id, "save_material_error", str(e))


@router.callback_query(F.data == "kb_cancel_material")
async def callback_cancel_material(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Отмена создания материала"""
    try:
        await callback.answer()
        
        # Возвращаемся к главному меню
        company_id = await ensure_company_id(session, state, callback.from_user.id)
        if company_id is None:
            await callback.message.edit_text("❌ Не удалось определить компанию. Обнови сессию командой /start.")
            await state.clear()
            log_user_error(callback.from_user.id, "cancel_material_company_missing", "company_id not resolved")
            return
        folders = await get_all_knowledge_folders(session, company_id)
        
        if not folders:
            await callback.message.edit_text(
                "📚РЕДАКТОР БАЗЫ ЗНАНИЙ📚\n\n"
                "Ты не создал ни одной папки",
                reply_markup=get_knowledge_base_main_keyboard(has_folders=False),
                parse_mode="HTML"
            )
        else:
            await callback.message.edit_text(
                "📚РЕДАКТОР БАЗЫ ЗНАНИЙ📚\n\n"
                "Ниже на клавиатуре ты видишь список всех созданных папок в системе👇\n"
                "🟡Выбери действие или папку, чтобы продолжить",
                reply_markup=get_knowledge_folders_keyboard(folders),
                parse_mode="HTML"
            )
        
        await state.set_state(KnowledgeBaseStates.main_menu)
        log_user_action(callback.from_user.id, "material_creation_cancelled", "Отменено создание материала")
        
    except Exception as e:
        await callback.message.edit_text("Произошла ошибка при отмене")
        log_user_error(callback.from_user.id, "cancel_material_error", str(e))


@router.callback_query(F.data.startswith("kb_folder:"), StateFilter(KnowledgeBaseStates.main_menu, KnowledgeBaseStates.folder_created_add_material, KnowledgeBaseStates.viewing_folder))
async def callback_view_folder(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Просмотр содержимого папки (ТЗ 9-2 шаг 3)"""
    try:
        await callback.answer()
        
        # Получаем company_id для изоляции
        company_id = await ensure_company_id(session, state, callback.from_user.id)
        if company_id is None:
            await callback.message.edit_text("❌ Не удалось определить компанию. Обнови сессию командой /start.")
            await state.clear()
            log_user_error(callback.from_user.id, "view_folder_company_missing", "company_id not resolved")
            return
        
        folder_id = int(callback.data.split(":")[1])
        
        # Получаем папку с материалами
        folder = await get_knowledge_folder_by_id(session, folder_id, company_id=company_id)
        if not folder:
            await callback.message.edit_text("❌ Папка не найдена")
            return
            
        # Получаем информацию о доступе
        access_info = await get_folder_access_info(session, folder_id, company_id=company_id)
        access_text = access_info.get("description", "все группы") if access_info.get("success") else "все группы"
        
        # ТЗ 9-2 шаг 4
        await callback.message.edit_text(
            "📚РЕДАКТОР БАЗЫ ЗНАНИЙ📚\n"
            f"📁Папка: {folder.name}\n"
            f"🔒Доступ: {access_text}\n\n"
            "🟡Выбери материал, который хочешь посмотреть или действие",
            reply_markup=get_folder_view_keyboard(folder_id, folder.materials),
            parse_mode="HTML"
        )
        
        await state.update_data(current_folder_id=folder_id)
        await state.set_state(KnowledgeBaseStates.viewing_folder)
        
        log_user_action(callback.from_user.id, "folder_viewed", f"Просмотр папки: {folder.name}")
        
    except Exception as e:
        await callback.message.edit_text("Произошла ошибка при просмотре папки")
        log_user_error(callback.from_user.id, "view_folder_error", str(e))


@router.callback_query(F.data.startswith("kb_material:"), StateFilter(KnowledgeBaseStates.viewing_folder))
async def callback_view_material(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Просмотр материала (ТЗ 9-2 шаг 5)"""
    try:
        await callback.answer()
        
        material_id = int(callback.data.split(":")[1])
        
        # Получаем материал
        material = await get_knowledge_material_by_id(session, material_id)
        if not material:
            await callback.message.edit_text("❌ Материал не найден")
            return
            
        # Формируем отображение содержимого
        content_display = material.content if material.material_type == "link" else "Файл"
        description_display = material.description if material.description else "Описание не указано"
        photos_display = ""
        if material.photos and len(material.photos) > 0:
            photos_display = f"\n🖼️Фотографий: {len(material.photos)}"

        # Получаем номер материала в папке для правильного отображения
        material_number = material.order_number

        # ТЗ 9-2 шаг 6
        message_text = (
            "📚РЕДАКТОР БАЗЫ ЗНАНИЙ📚\n"
            f"📁Папка: {material.folder.name}\n"
            f"🔗Материал {material_number}: {material.name}\n"
            f"🟢Вложение: {content_display}\n"
            f"🟢 Описание: {description_display}{photos_display}"
        )

        # Сначала отправляем фото/документы БЕЗ кнопок, соблюдая ограничения Telegram
        if material.photos and len(material.photos) > 0:
            try:
                photo_ids = []
                doc_ids = []
                for item in material.photos:
                    if isinstance(item, dict):
                        (doc_ids if item.get("kind") == "document" else photo_ids).append(item.get("id"))
                    else:
                        photo_ids.append(item)

                # 1) Если есть фото — отправляем их одним media group, caption на первом
                if photo_ids:
                    if len(photo_ids) == 1:
                        # Одно фото — отправляем через send_photo
                        await callback.bot.send_photo(
                            chat_id=callback.message.chat.id,
                            photo=photo_ids[0],
                            caption=message_text,
                            parse_mode="HTML"
                        )
                    else:
                        # Несколько фото — используем media_group
                        media_group = []
                        for i, file_id in enumerate(photo_ids, 1):
                            if i == 1:
                                media_group.append(InputMediaPhoto(media=file_id, caption=message_text, parse_mode="HTML"))
                            else:
                                media_group.append(InputMediaPhoto(media=file_id))
                        await callback.bot.send_media_group(chat_id=callback.message.chat.id, media=media_group)
                else:
                    # Если фото нет — отправим текст отдельным сообщением
                    await callback.message.edit_text(message_text, parse_mode="HTML")

                # 2) Документы (изображения без сжатия) нельзя смешивать с фото — отправляем группой документов
                if doc_ids:
                    if len(doc_ids) == 1:
                        # Один документ — отправляем через send_document
                        await callback.bot.send_document(
                            chat_id=callback.message.chat.id,
                            document=doc_ids[0]
                        )
                    else:
                        # Несколько документов — используем media_group
                        docs_group = [InputMediaDocument(media=fid) for fid in doc_ids]
                        # Текст уже отправлен: как caption первого фото или отдельным сообщением
                        await callback.bot.send_media_group(chat_id=callback.message.chat.id, media=docs_group)

            except Exception as media_error:
                logger.error(f"Ошибка отправки media для материала {material.name}: {media_error}")
                # Fallback: отправляем обычное сообщение БЕЗ кнопок
                await callback.message.edit_text(message_text, parse_mode="HTML")
        else:
            # Если нет фото/документов-превью, отправляем только текст БЕЗ кнопок
            await callback.message.edit_text(message_text, parse_mode="HTML")

        # Затем отправляем файл
        if material.material_type != "link":
            try:
                # Отправляем файл по file_id в зависимости от типа
                if material.material_type == "video":
                    await callback.bot.send_video(
                        chat_id=callback.message.chat.id,
                        video=material.content  # file_id
                    )
                elif material.material_type == "photo":
                    try:
                        await callback.bot.send_photo(
                            chat_id=callback.message.chat.id,
                            photo=material.content  # file_id
                        )
                    except Exception as inner_error:
                        # Fallback: если это документ, ошибочно помеченный как фото — отправляем документом
                        logger.error(f"Ошибка отправки фото как photo для {material.name}: {inner_error}. Пробуем как document")
                        await callback.bot.send_document(
                            chat_id=callback.message.chat.id,
                            document=material.content
                        )
                else:
                    # Документы (pdf, doc, excel, изображения без сжатия и т.п.)
                    await callback.bot.send_document(
                        chat_id=callback.message.chat.id,
                        document=material.content  # file_id
                    )
            except Exception as file_error:
                logger.error(f"Ошибка отправки файла {material.name}: {file_error}")
                await callback.bot.send_message(
                    chat_id=callback.message.chat.id,
                    text=f"⚠️ Ошибка при отправке файла {material.name}."
                )

        # Отправляем кнопки управления отдельно
        await callback.bot.send_message(
            chat_id=callback.message.chat.id,
            text=f"⚙️ Управление материалом: {material.name}",
            reply_markup=get_material_view_keyboard(material_id),
            parse_mode="HTML"
        )

        await state.update_data(current_material_id=material_id)
        await state.set_state(KnowledgeBaseStates.viewing_material)

        log_user_action(callback.from_user.id, "material_viewed", f"Просмотр материала: {material.name}")
        
    except Exception as e:
        await callback.message.edit_text("Произошла ошибка при просмотре материала")
        log_user_error(callback.from_user.id, "view_material_error", str(e))


@router.callback_query(F.data.startswith("kb_delete_material:"))
async def callback_delete_material(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Подтверждение удаления материала (ТЗ 9-2 шаг 7-1)"""
    try:
        await callback.answer()

        material_id = int(callback.data.split(":")[1])

        # Получаем материал
        material = await get_knowledge_material_by_id(session, material_id)
        if not material:
            await callback.message.edit_text("❌ Материал не найден")
            return

        # Формируем отображение содержимого
        if material.material_type == "link":
            content_display = material.content  # Показываем сам URL для ссылок
        else:
            # Для файлов показываем тип файла
            content_display = f"📎 {material.material_type.title()}"

        description_display = material.description if material.description else "Описание не указано"

        # Добавляем информацию о фотографиях
        photos_display = ""
        if material.photos and len(material.photos) > 0:
            photos_display = f"\n🖼️Фотографий: {len(material.photos)}"

        # Получаем номер материала в папке для правильного отображения
        material_number = material.order_number

        # Создаем текст для media group или обычного сообщения
        message_text = (
            "📚РЕДАКТОР БАЗЫ ЗНАНИЙ📚\n"
            f"📁Папка: {material.folder.name}\n"
            f"🔗Материал {material_number}: {material.name}\n"
            f"🟢Вложение: {content_display}\n"
            f"🟢 Описание: {description_display}{photos_display}"
        )

        # Сначала отправляем фото/документы БЕЗ кнопок, соблюдая ограничения Telegram
        if material.photos and len(material.photos) > 0:
            try:
                photo_ids = []
                doc_ids = []
                for item in material.photos:
                    if isinstance(item, dict):
                        (doc_ids if item.get("kind") == "document" else photo_ids).append(item.get("id"))
                    else:
                        photo_ids.append(item)

                # 1) Если есть фото — отправляем их одним media group, caption на первом
                if photo_ids:
                    if len(photo_ids) == 1:
                        # Одно фото — отправляем через send_photo
                        await callback.bot.send_photo(
                            chat_id=callback.message.chat.id,
                            photo=photo_ids[0],
                            caption=message_text,
                            parse_mode="HTML"
                        )
                    else:
                        # Несколько фото — используем media_group
                        media_group = []
                        for i, file_id in enumerate(photo_ids, 1):
                            if i == 1:
                                media_group.append(InputMediaPhoto(media=file_id, caption=message_text, parse_mode="HTML"))
                            else:
                                media_group.append(InputMediaPhoto(media=file_id))
                        await callback.bot.send_media_group(chat_id=callback.message.chat.id, media=media_group)
                else:
                    # Если фото нет — отправим текст отдельным сообщением
                    await callback.message.edit_text(message_text, parse_mode="HTML")

                # 2) Документы (изображения без сжатия) — отдельная медиагруппа из документов
                if doc_ids:
                    if len(doc_ids) == 1:
                        # Один документ — отправляем через send_document
                        await callback.bot.send_document(
                            chat_id=callback.message.chat.id,
                            document=doc_ids[0]
                        )
                    else:
                        # Несколько документов — используем media_group
                        docs_group = [InputMediaDocument(media=fid) for fid in doc_ids]
                        await callback.bot.send_media_group(chat_id=callback.message.chat.id, media=docs_group)

            except Exception as media_error:
                logger.error(f"Ошибка отправки media для материала {material.name}: {media_error}")
                # Fallback: отправляем обычное сообщение
                await callback.message.edit_text(message_text, parse_mode="HTML")
        else:
            # Если нет фото/документов, отправляем только текст
            await callback.message.edit_text(message_text, parse_mode="HTML")

        # Затем отправляем файл (если это не ссылка)
        if material.material_type != "link":
            try:
                # Отправляем файл по file_id в зависимости от типа
                if material.material_type == "video":
                    await callback.bot.send_video(
                        chat_id=callback.message.chat.id,
                        video=material.content  # file_id
                    )
                elif material.material_type == "photo":
                    await callback.bot.send_photo(
                        chat_id=callback.message.chat.id,
                        photo=material.content  # file_id
                    )
                else:
                    # Документы (pdf, doc, excel, etc.)
                    await callback.bot.send_document(
                        chat_id=callback.message.chat.id,
                        document=material.content  # file_id
                    )
            except Exception as file_error:
                logger.error(f"Ошибка отправки файла {material.name}: {file_error}")
                await callback.bot.send_message(
                    chat_id=callback.message.chat.id,
                    text=f"⚠️ Ошибка при отправке файла {material.name}."
                )

        # Наконец, отправляем сообщение с подтверждением удаления
        await callback.bot.send_message(
            chat_id=callback.message.chat.id,
            text="🟡Ты уверен, что хочешь удалить материал?\n"
                 "❗️Доступ к нему будет утрачен навсегда",
            reply_markup=get_material_delete_confirmation_keyboard(material_id),
            parse_mode="HTML"
        )

        await state.set_state(KnowledgeBaseStates.confirming_material_deletion)

    except Exception as e:
        await callback.message.edit_text("Произошла ошибка при удалении материала")
        log_user_error(callback.from_user.id, "delete_material_error", str(e))


@router.callback_query(F.data.startswith("kb_confirm_delete_material:"), StateFilter(KnowledgeBaseStates.confirming_material_deletion))
async def callback_confirm_delete_material(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Подтверждение удаления материала (ТЗ 9-2 шаг 7-3)"""
    try:
        await callback.answer()
        
        # Проверяем права
        user = await get_user_by_tg_id(session, callback.from_user.id)
        if not user:
            await callback.message.edit_text("❌ Пользователь не найден")
            return
            
        has_permission = await check_user_permission(session, user.id, "manage_groups")
        if not has_permission:
            await callback.message.edit_text("❌ У тебя нет прав для этой операции.")
            return
        
        material_id = int(callback.data.split(":")[1])
        
        # Получаем материал
        material = await get_knowledge_material_by_id(session, material_id)
        if not material:
            await callback.message.edit_text("❌ Материал не найден")
            return
            
        # Получаем пользователя
        user = await get_user_by_tg_id(session, callback.from_user.id)
        if not user:
            await callback.message.edit_text("❌ Ошибка получения данных пользователя")
            return
            
        # Сохраняем данные для отображения
        folder_name = material.folder.name
        material_name = material.name
        material_number = material.order_number
        content_display = material.content if material.material_type == "link" else "Файл"
        description_display = material.description if material.description else "Описание не указано"
        
        # Удаляем материал
        success = await delete_knowledge_material(session, material_id, user.id)
        if not success:
            await callback.message.edit_text("❌ Не удалось удалить материал")
            return
        
        # Сохраняем изменения в базу данных
        await session.commit()
        
        # ТЗ 9-2 шаг 7-4
        await callback.message.edit_text(
            "📚РЕДАКТОР БАЗЫ ЗНАНИЙ📚\n"
            f"📁Папка: {folder_name}\n\n"
            "❗️ВЫ УСПЕШНО УДАЛИЛИ МАТЕРИАЛ👇\n\n"
            f"🔗Материал {material_number}: {material_name}\n"
            f"🟢Вложение: {content_display}\n"
            f"🟢 Описание: {description_display}",
            parse_mode="HTML"
        )
        
        # Немедленно возвращаемся к просмотру папки с обновленной клавиатурой
        await callback_view_folder_by_id(callback, state, session, material.folder_id)
        
        log_user_action(callback.from_user.id, "material_deleted", f"Удален материал: {material_name}")
        
    except Exception as e:
        await callback.message.edit_text("Произошла ошибка при удалении материала")
        log_user_error(callback.from_user.id, "confirm_delete_material_error", str(e))


@router.callback_query(F.data == "kb_back")
async def callback_back(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Возврат назад (ТЗ 9-2 шаг 9)"""
    try:
        await callback.answer()
        
        current_state = await state.get_state()
        data = await state.get_data()
        
        if current_state == KnowledgeBaseStates.viewing_material:
            # Возврат к просмотру папки
            folder_id = data.get("current_folder_id")
            if folder_id:
                await callback_view_folder_by_id(callback, state, session, folder_id)
            else:
                await show_main_folders_list(callback, state, session)
        else:
            # Возврат к главному списку папок
            await show_main_folders_list(callback, state, session)
            
    except Exception as e:
        await callback.message.edit_text("Произошла ошибка при возврате")
        log_user_error(callback.from_user.id, "back_error", str(e))


async def callback_view_folder_by_id(callback: CallbackQuery, state: FSMContext, session: AsyncSession, folder_id: int):
    """Вспомогательная функция для просмотра папки по ID"""
    try:
        # Получаем company_id для изоляции
        company_id = await ensure_company_id(session, state, callback.from_user.id)
        if company_id is None:
            await callback.message.edit_text("❌ Не удалось определить компанию. Обнови сессию командой /start.")
            await state.clear()
            log_user_error(callback.from_user.id, "view_folder_by_id_company_missing", "company_id not resolved")
            return
        
        # Получаем папку с материалами
        folder = await get_knowledge_folder_by_id(session, folder_id, company_id=company_id)
        if not folder:
            await callback.message.edit_text("❌ Папка не найдена")
            return
            
        # Получаем информацию о доступе
        access_info = await get_folder_access_info(session, folder_id, company_id=company_id)
        access_text = access_info.get("description", "все группы") if access_info.get("success") else "все группы"
        
        await callback.message.edit_text(
            "📚РЕДАКТОР БАЗЫ ЗНАНИЙ📚\n"
            f"📁Папка: {folder.name}\n"
            f"🔒Доступ: {access_text}\n\n"
            "🟡Выбери материал, который хочешь посмотреть или действие",
            reply_markup=get_folder_view_keyboard(folder_id, folder.materials),
            parse_mode="HTML"
        )
        
        await state.update_data(current_folder_id=folder_id)
        await state.set_state(KnowledgeBaseStates.viewing_folder)
        
    except Exception as e:
        await callback.message.edit_text("Произошла ошибка при просмотре папки")
        log_user_error(callback.from_user.id, "view_folder_by_id_error", str(e))


async def show_main_folders_list(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Показ основного списка папок (ТЗ 9-2 шаг 10)"""
    try:
        company_id = await ensure_company_id(session, state, callback.from_user.id)
        if company_id is None:
            await callback.message.edit_text("❌ Не удалось определить компанию. Обнови сессию командой /start.")
            await state.clear()
            log_user_error(callback.from_user.id, "show_main_folders_company_missing", "company_id not resolved")
            return
        folders = await get_all_knowledge_folders(session, company_id)
        
        if not folders:
            await callback.message.edit_text(
                "📚РЕДАКТОР БАЗЫ ЗНАНИЙ📚\n\n"
                "Ты не создал ни одной папки",
                reply_markup=get_knowledge_base_main_keyboard(has_folders=False),
                parse_mode="HTML"
            )
        else:
            await callback.message.edit_text(
                "📚РЕДАКТОР БАЗЫ ЗНАНИЙ📚\n\n"
                "Ниже на клавиатуре ты видишь список всех созданных папок в системе👇\n"
                "🟡Выбери действие или папку, чтобы продолжить",
                reply_markup=get_knowledge_folders_keyboard(folders),
                parse_mode="HTML"
            )
        
        await state.set_state(KnowledgeBaseStates.main_menu)
        
    except Exception as e:
        await callback.message.edit_text("Произошла ошибка при отображении папок")
        log_user_error(callback.from_user.id, "show_main_folders_error", str(e))


# ===============================
# Обработчики изменения доступа к папке (ТЗ 9-3)
# ===============================

@router.callback_query(F.data.startswith("kb_access:"), StateFilter(KnowledgeBaseStates.viewing_folder))
async def callback_folder_access(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Настройка доступа к папке (ТЗ 9-3 шаг 4)"""
    try:
        await callback.answer()
        
        # Проверяем права
        user = await get_user_by_tg_id(session, callback.from_user.id)
        if not user:
            await callback.message.edit_text("❌ Пользователь не найден")
            return
            
        has_permission = await check_user_permission(session, user.id, "manage_groups")
        if not has_permission:
            await callback.message.edit_text("❌ У тебя нет прав для этой операции.")
            return
        
        folder_id = int(callback.data.split(":")[1])
        
        # Получаем company_id
        company_id = await ensure_company_id(session, state, callback.from_user.id)
        if company_id is None:
            await callback.message.edit_text(
                "❌ Не удалось определить компанию. Обнови сессию командой /start."
            )
            await state.clear()
            log_user_error(callback.from_user.id, "folder_access_company_missing", "company_id not resolved")
            return
        
        # Получаем папку
        folder = await get_knowledge_folder_by_id(session, folder_id, company_id=company_id)
        if not folder:
            await callback.message.edit_text("❌ Папка не найдена")
            return

        # Получаем все группы
        groups = await get_all_groups(session, company_id)
        if not groups:
            await callback.message.edit_text("❌ В системе нет групп для настройки доступа")
            return
            
        # Получаем текущие группы с доступом
        current_group_ids = [group.id for group in folder.accessible_groups] if folder.accessible_groups else []
        
        # Получаем информацию о текущем доступе
        access_info = await get_folder_access_info(session, folder_id, company_id=company_id)
        access_text = access_info.get("description", "все группы") if access_info.get("success") else "все группы"
        
        # ТЗ 9-3 шаг 5
        await callback.message.edit_text(
            "📚РЕДАКТОР БАЗЫ ЗНАНИЙ📚\n\n"
            f"📁Папка: {folder.name}\n"
            f"🔒Доступ: {access_text}\n\n"
            "🟡Каким группам ты хочешь предоставить доступ к этой папке?\n"
            "Выбери группу на клавиатуре👇",
            reply_markup=get_group_access_selection_keyboard(groups, current_group_ids),
            parse_mode="HTML"
        )
        
        await state.update_data(
            current_folder_id=folder_id,
            selected_group_ids=current_group_ids.copy()
        )
        await state.set_state(KnowledgeBaseStates.selecting_access_groups)
        
        log_user_action(callback.from_user.id, "folder_access_setup", f"Настройка доступа к папке: {folder.name}")
        
    except Exception as e:
        await callback.message.edit_text("Произошла ошибка при настройке доступа")
        log_user_error(callback.from_user.id, "folder_access_error", str(e))


@router.callback_query(F.data.startswith("kb_toggle_group:"))
async def callback_toggle_group_access(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Переключение доступа для группы (ТЗ 9-3 шаги 6-9)"""
    try:
        await callback.answer()
        
        # Проверяем права
        user = await get_user_by_tg_id(session, callback.from_user.id)
        if not user:
            await callback.message.edit_text("❌ Пользователь не найден")
            return
            
        has_permission = await check_user_permission(session, user.id, "manage_groups")
        if not has_permission:
            await callback.message.edit_text("❌ У тебя нет прав для этой операции.")
            return
        
        group_id = int(callback.data.split(":")[1])
        data = await state.get_data()
        folder_id = data.get("current_folder_id")
        selected_group_ids = data.get("selected_group_ids", [])
        
        if not folder_id:
            await callback.message.edit_text("❌ Ошибка: папка не найдена")
            return
            
        # Переключаем выбор группы
        if group_id in selected_group_ids:
            selected_group_ids.remove(group_id)
        else:
            selected_group_ids.append(group_id)
            
        # Получаем company_id, папку и группы для обновления интерфейса
        company_id = await ensure_company_id(session, state, callback.from_user.id)
        folder = await get_knowledge_folder_by_id(session, folder_id, company_id=company_id)
        groups = await get_all_groups(session, company_id)
        
        if not folder or not groups:
            await callback.message.edit_text("❌ Ошибка получения данных")
            return
            
        # Формируем текст доступа
        if selected_group_ids:
            selected_groups = [g for g in groups if g.id in selected_group_ids]
            access_text = "; ".join([group.name for group in selected_groups]) + ";"
        else:
            access_text = "все группы"
            
        # Обновляем сообщение согласно ТЗ
        message_text = (
            "📚РЕДАКТОР БАЗЫ ЗНАНИЙ📚\n\n"
            f"📁Папка: {folder.name}\n"
            f"🔒Доступ: {access_text}\n\n"
        )
        
        if selected_group_ids:
            message_text += "🟡Добавить ещё группу к данной папке?\nВыбери группу на клавиатуре👇"
        else:
            message_text += "🟡Каким группам ты хочешь предоставить доступ к этой папке?\nВыбери группу на клавиатуре👇"
        
        await callback.message.edit_text(
            message_text,
            reply_markup=get_group_access_selection_keyboard(groups, selected_group_ids),
            parse_mode="HTML"
        )
        
        await state.update_data(selected_group_ids=selected_group_ids)
        
    except Exception as e:
        await callback.message.edit_text("Произошла ошибка при переключении доступа")
        log_user_error(callback.from_user.id, "toggle_group_access_error", str(e))


@router.callback_query(F.data == "kb_save_access", StateFilter(KnowledgeBaseStates.selecting_access_groups))
async def callback_save_access(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Сохранение настроек доступа (ТЗ 9-3 шаг 10)"""
    try:
        await callback.answer()
        
        # Проверяем права
        user = await get_user_by_tg_id(session, callback.from_user.id)
        if not user:
            await callback.message.edit_text("❌ Пользователь не найден")
            return
            
        has_permission = await check_user_permission(session, user.id, "manage_groups")
        if not has_permission:
            await callback.message.edit_text("❌ У тебя нет прав для этой операции.")
            return
        
        data = await state.get_data()
        folder_id = data.get("current_folder_id")
        selected_group_ids = data.get("selected_group_ids", [])
        
        if not folder_id:
            await callback.message.edit_text("❌ Ошибка: папка не найдена")
            return
            
        # Получаем пользователя
        user = await get_user_by_tg_id(session, callback.from_user.id)
        if not user:
            await callback.message.edit_text("❌ Ошибка получения данных пользователя")
            return
        
        # Получаем company_id для изоляции
        data = await state.get_data()
        company_id = data.get('company_id') or user.company_id
            
        # Сохраняем настройки доступа
        success = await set_folder_access_groups(session, folder_id, selected_group_ids, user.id, company_id=company_id)
        if not success:
            await callback.message.edit_text("❌ Не удалось сохранить настройки доступа")
            return
        
        # Сохраняем изменения в базу данных
        await session.commit()
        
        # Возвращаемся к просмотру папки
        await callback_view_folder_by_id(callback, state, session, folder_id)
        
        log_user_action(callback.from_user.id, "folder_access_saved", f"Сохранены настройки доступа для папки {folder_id}")
        
    except Exception as e:
        await callback.message.edit_text("Произошла ошибка при сохранении доступа")
        log_user_error(callback.from_user.id, "save_access_error", str(e))


# ===============================
# Обработчики изменения названия папки (ТЗ 9-4)
# ===============================

@router.callback_query(F.data.startswith("kb_rename_folder:"), StateFilter(KnowledgeBaseStates.viewing_folder))
async def callback_rename_folder(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Начало переименования папки (ТЗ 9-4 шаг 4)"""
    try:
        await callback.answer()
        
        # Проверяем права
        user = await get_user_by_tg_id(session, callback.from_user.id)
        if not user:
            await callback.message.edit_text("❌ Пользователь не найден")
            return
            
        has_permission = await check_user_permission(session, user.id, "manage_groups")
        if not has_permission:
            await callback.message.edit_text("❌ У тебя нет прав для этой операции.")
            return
        
        folder_id = int(callback.data.split(":")[1])
        
        # Получаем папку с изоляцией
        folder = await get_knowledge_folder_by_id(session, folder_id, company_id=user.company_id)
        if not folder:
            await callback.message.edit_text("❌ Папка не найдена")
            return
            
        # ТЗ 9-4 шаг 5
        await callback.message.edit_text(
            "📚РЕДАКТОР БАЗЫ ЗНАНИЙ📚\n\n"
            f"📁Папка: {folder.name}\n"
            "🟡Введи новое название для папки:",
            parse_mode="HTML"
        )
        
        await state.update_data(current_folder_id=folder_id, old_folder_name=folder.name)
        await state.set_state(KnowledgeBaseStates.waiting_for_new_folder_name)
        
        log_user_action(callback.from_user.id, "folder_rename_started", f"Начато переименование папки: {folder.name}")
        
    except Exception as e:
        await callback.message.edit_text("Произошла ошибка при переименовании папки")
        log_user_error(callback.from_user.id, "rename_folder_error", str(e))


@router.message(StateFilter(KnowledgeBaseStates.waiting_for_new_folder_name))
async def process_new_folder_name(message: Message, state: FSMContext, session: AsyncSession):
    """Обработка нового названия папки (ТЗ 9-4 шаг 6)"""
    try:
        new_name = message.text.strip()
        
        # Валидация названия
        if not validate_name(new_name):
            await message.answer("❌ Некорректное новое название папки. Название должно содержать от 2 до 100 символов и состоять из букв, цифр и основных знаков препинания.")
            return
            
        data = await state.get_data()
        folder_id = data.get("current_folder_id")
        old_name = data.get("old_folder_name")
        
        if not folder_id:
            await message.answer("❌ Ошибка: папка не найдена")
            await state.clear()
            return
            
        # ТЗ 9-4 шаг 7
        await message.answer(
            "📚РЕДАКТОР БАЗЫ ЗНАНИЙ📚\n\n"
            f"📁Папка: {old_name}\n"
            f"🟡Новое название для папки: {new_name}",
            reply_markup=get_folder_rename_confirmation_keyboard(),
            parse_mode="HTML"
        )
        
        await state.update_data(new_folder_name=new_name)
        await state.set_state(KnowledgeBaseStates.confirming_folder_rename)
        
        log_user_action(message.from_user.id, "new_folder_name_set", f"Новое название: {new_name}")
        
    except Exception as e:
        await message.answer("Произошла ошибка при обработке названия папки")
        log_user_error(message.from_user.id, "process_new_folder_name_error", str(e))


@router.callback_query(F.data == "kb_confirm_rename")
async def callback_confirm_rename(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Подтверждение переименования папки (ТЗ 9-4 шаг 8)"""
    try:
        await callback.answer()
        
        # Проверяем права
        user = await get_user_by_tg_id(session, callback.from_user.id)
        if not user:
            await callback.message.edit_text("❌ Пользователь не найден")
            return
            
        has_permission = await check_user_permission(session, user.id, "manage_groups")
        if not has_permission:
            await callback.message.edit_text("❌ У тебя нет прав для этой операции.")
            return
        
        data = await state.get_data()
        folder_id = data.get("current_folder_id")
        new_name = data.get("new_folder_name")
        
        if not folder_id or not new_name:
            await callback.message.edit_text("❌ Ошибка данных")
            return
            
        # Получаем пользователя
        user = await get_user_by_tg_id(session, callback.from_user.id)
        if not user:
            await callback.message.edit_text("❌ Ошибка получения данных пользователя")
            return
        
        # Получаем company_id для изоляции
        data = await state.get_data()
        company_id = data.get('company_id') or user.company_id
            
        # Переименовываем папку
        success = await update_knowledge_folder_name(session, folder_id, new_name, user.id, company_id=company_id)
        if not success:
            await callback.message.edit_text("❌ Не удалось переименовать папку. Возможно, папка с таким названием уже существует.")
            return
        
        # Сохраняем изменения в базу данных
        await session.commit()
        
        # ТЗ 9-4 шаг 9
        await callback.message.edit_text(
            "📚РЕДАКТОР БАЗЫ ЗНАНИЙ📚\n\n"
            "✅Ты успешно изменил название папки\n"
            f"🟡Новое название для папки: {new_name}",
            reply_markup=get_folder_deleted_keyboard(folder_id),  # Передаем folder_id для возврата к папке
            parse_mode="HTML"
        )
        
        log_user_action(callback.from_user.id, "folder_renamed", f"Папка переименована в: {new_name}")
        
    except Exception as e:
        await callback.message.edit_text("Произошла ошибка при подтверждении переименования")
        log_user_error(callback.from_user.id, "confirm_rename_error", str(e))


@router.callback_query(F.data == "kb_cancel_rename")
async def callback_cancel_rename(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Отмена переименования папки"""
    try:
        await callback.answer()
        
        data = await state.get_data()
        folder_id = data.get("current_folder_id")
        
        if folder_id:
            await callback_view_folder_by_id(callback, state, session, folder_id)
        else:
            await show_main_folders_list(callback, state, session)
            
        log_user_action(callback.from_user.id, "folder_rename_cancelled", "Отменено переименование папки")
        
    except Exception as e:
        await callback.message.edit_text("Произошла ошибка при отмене")
        log_user_error(callback.from_user.id, "cancel_rename_error", str(e))


# ===============================
# Обработчики удаления папки (ТЗ 9-5)
# ===============================

@router.callback_query(F.data.startswith("kb_delete_folder:"), StateFilter(KnowledgeBaseStates.viewing_folder))
async def callback_delete_folder(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Подтверждение удаления папки (ТЗ 9-5 шаг 4)"""
    try:
        await callback.answer()
        
        # Проверяем права
        user = await get_user_by_tg_id(session, callback.from_user.id)
        if not user:
            await callback.message.edit_text("❌ Пользователь не найден")
            return
            
        has_permission = await check_user_permission(session, user.id, "manage_groups")
        if not has_permission:
            await callback.message.edit_text("❌ У тебя нет прав для этой операции.")
            return
        
        folder_id = int(callback.data.split(":")[1])
        
        # Получаем папку с изоляцией
        folder = await get_knowledge_folder_by_id(session, folder_id, company_id=user.company_id)
        if not folder:
            await callback.message.edit_text("❌ Папка не найдена")
            return
            
        # Получаем информацию о доступе
        access_info = await get_folder_access_info(session, folder_id, company_id=user.company_id)
        access_text = access_info.get("description", "все группы") if access_info.get("success") else "все группы"
        
        # ТЗ 9-5 шаг 5
        await callback.message.edit_text(
            "📚РЕДАКТОР БАЗЫ ЗНАНИЙ📚\n\n"
            f"📁Папка: {folder.name}\n"
            f"🔒Доступ: {access_text}\n\n"
            "🟡Ты уверен, что хочешь удалить папку?\n"
            "❗️Доступ ко всем материалам внутри папки будет утрачен навсегда",
            reply_markup=get_folder_delete_confirmation_keyboard(folder_id),
            parse_mode="HTML"
        )
        
        await state.set_state(KnowledgeBaseStates.confirming_folder_deletion)
        
    except Exception as e:
        await callback.message.edit_text("Произошла ошибка при удалении папки")
        log_user_error(callback.from_user.id, "delete_folder_error", str(e))


@router.callback_query(F.data.startswith("kb_confirm_delete_folder:"), StateFilter(KnowledgeBaseStates.confirming_folder_deletion))
async def callback_confirm_delete_folder(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Подтверждение удаления папки (ТЗ 9-5 шаг 6)"""
    try:
        await callback.answer()
        
        # Проверяем права
        user = await get_user_by_tg_id(session, callback.from_user.id)
        if not user:
            await callback.message.edit_text("❌ Пользователь не найден")
            return
            
        has_permission = await check_user_permission(session, user.id, "manage_groups")
        if not has_permission:
            await callback.message.edit_text("❌ У тебя нет прав для этой операции.")
            return
        
        folder_id = int(callback.data.split(":")[1])
        
        # Получаем пользователя
        user = await get_user_by_tg_id(session, callback.from_user.id)
        if not user:
            await callback.message.edit_text("❌ Ошибка получения данных пользователя")
            return
        
        # Получаем папку с изоляцией
        folder = await get_knowledge_folder_by_id(session, folder_id, company_id=user.company_id)
        if not folder:
            await callback.message.edit_text("❌ Папка не найдена")
            return
            
        # Сохраняем название для отображения
        folder_name = folder.name
        
        # Удаляем папку с изоляцией
        success = await delete_knowledge_folder(session, folder_id, user.id, company_id=user.company_id)
        if not success:
            await callback.message.edit_text("❌ Не удалось удалить папку")
            return
        
        # Сохраняем изменения в базу данных
        await session.commit()
        
        # ТЗ 9-5 шаг 7
        await callback.message.edit_text(
            "📚РЕДАКТОР БАЗЫ ЗНАНИЙ📚\n\n"
            "✅ВЫ УСПЕШНО УДАЛИЛИ ПАПКУ\n"
            f"📁Папка: {folder_name}",
            reply_markup=get_folder_deleted_keyboard(),
            parse_mode="HTML"
        )
        
        log_user_action(callback.from_user.id, "folder_deleted", f"Удалена папка: {folder_name}")
        
    except Exception as e:
        await callback.message.edit_text("Произошла ошибка при удалении папки")
        log_user_error(callback.from_user.id, "confirm_delete_folder_error", str(e))


@router.callback_query(F.data == "kb_cancel_delete")
async def callback_cancel_delete(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Отмена удаления"""
    try:
        await callback.answer()
        
        data = await state.get_data()
        folder_id = data.get("current_folder_id")
        
        if folder_id:
            await callback_view_folder_by_id(callback, state, session, folder_id)
        else:
            await show_main_folders_list(callback, state, session)
            
        log_user_action(callback.from_user.id, "delete_cancelled", "Отменено удаление")
        
    except Exception as e:
        await callback.message.edit_text("Произошла ошибка при отмене")
        log_user_error(callback.from_user.id, "cancel_delete_error", str(e))


# ===============================
# Обработчики для сотрудников (просмотр базы знаний)
# ===============================

# Убрано: дублирующий обработчик - теперь используется универсальный выше


@router.callback_query(F.data == "knowledge_base")
async def callback_employee_knowledge_base(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Открытие базы знаний для сотрудника (заменяет заглушку)"""
    try:
        await callback.answer()
        
        # Получение пользователя
        user = await get_user_by_tg_id(session, callback.from_user.id)
        if not user:
            await callback.message.edit_text("❌ Ты не зарегистрирован в системе.")
            return

        # Проверка прав доступа к базе знаний
        has_permission = await check_user_permission(session, user.id, "view_knowledge_base")
        if not has_permission:
            await callback.message.edit_text("❌ У тебя нет прав для просмотра базы знаний.")
            return

        # Получаем папки, доступные пользователю
        data = await state.get_data()
        company_id = data.get('company_id')
        accessible_folders = await get_accessible_knowledge_folders_for_user(session, user.id, company_id)
        
        if not accessible_folders:
            await callback.message.edit_text(
                "📚 <b>База знаний</b>\n\n"
                "В данный момент для тебя нет доступных материалов.\n"
                "Обратитесь к рекрутеру для получения доступа к необходимым разделам.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="☰ Главное меню", callback_data="main_menu")]
                ]),
                parse_mode="HTML"
            )
        else:
            await callback.message.edit_text(
                "📚 <b>База знаний</b>\n\n"
                "Выбери раздел для изучения материалов:",
                reply_markup=get_employee_knowledge_folders_keyboard(accessible_folders),
                parse_mode="HTML"
            )

        await state.set_state(KnowledgeBaseStates.employee_browsing)
        log_user_action(callback.from_user.id, "employee_knowledge_base_opened", "Открыта база знаний (сотрудник)")

    except Exception as e:
        await callback.message.edit_text("Произошла ошибка при открытии базы знаний")
        log_user_error(callback.from_user.id, "employee_knowledge_base_error", str(e))


@router.callback_query(F.data.startswith("kb_emp_folder:"))
async def callback_employee_view_folder(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Просмотр папки сотрудником"""
    try:
        await callback.answer()
        
        folder_id = int(callback.data.split(":")[1])
        
        # Получение пользователя
        user = await get_user_by_tg_id(session, callback.from_user.id)
        if not user:
            await callback.message.edit_text("❌ Ты не зарегистрирован в системе.")
            return

        # Проверяем доступ к папке
        has_access = await check_folder_access(session, folder_id, user.id, company_id=user.company_id)
        if not has_access:
            await callback.message.edit_text("❌ У тебя нет доступа к этой папке.")
            return

        # Получаем папку с материалами с изоляцией
        folder = await get_knowledge_folder_by_id(session, folder_id, company_id=user.company_id)
        if not folder:
            await callback.message.edit_text("❌ Папка не найдена")
            return

        if not folder.materials:
            await callback.message.edit_text(
                f"📁 <b>{folder.name}</b>\n\n"
                "В данной папке пока нет материалов.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="⬅️ Назад к папкам", callback_data="kb_emp_back_to_folders")]
                ]),
                parse_mode="HTML"
            )
        else:
            await callback.message.edit_text(
                f"📁 <b>{folder.name}</b>\n\n"
                "Выбери материал для изучения:",
                reply_markup=get_employee_folder_materials_keyboard(folder_id, folder.materials),
                parse_mode="HTML"
            )

        await state.update_data(current_folder_id=folder_id)
        await state.set_state(KnowledgeBaseStates.employee_viewing_folder)
        
        log_user_action(callback.from_user.id, "employee_folder_viewed", f"Сотрудник просмотрел папку: {folder.name}")

    except Exception as e:
        await callback.message.edit_text("Произошла ошибка при просмотре папки")
        log_user_error(callback.from_user.id, "employee_view_folder_error", str(e))


@router.callback_query(F.data.startswith("kb_emp_material:"))
async def callback_employee_view_material(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Просмотр материала сотрудником"""
    try:
        await callback.answer()
        
        material_id = int(callback.data.split(":")[1])
        
        # Получение пользователя
        user = await get_user_by_tg_id(session, callback.from_user.id)
        if not user:
            await callback.message.edit_text("❌ Ты не зарегистрирован в системе.")
            return

        # Получаем материал
        material = await get_knowledge_material_by_id(session, material_id)
        if not material:
            await callback.message.edit_text("❌ Материал не найден")
            return

        # Получаем company_id для изоляции
        data = await state.get_data()
        company_id = data.get('company_id') or user.company_id

        # Проверяем доступ к папке материала
        has_access = await check_folder_access(session, material.folder_id, user.id, company_id=company_id)
        if not has_access:
            await callback.message.edit_text("❌ У тебя нет доступа к этому материалу.")
            return

        # Формируем отображение содержимого
        if material.material_type == "link":
            content_display = f"🔗 <a href='{material.content}'>Открыть ссылку</a>"
        else:
            # Для файлов отправляем файл и показываем информацию
            content_display = "📎 Файл прикреплен ниже"

        description_display = material.description if material.description else "Описание не указано"

        message_text = (
            f"📄 <b>{material.name}</b>\n\n"
            f"📁 Папка: {material.folder.name}\n\n"
            f"{content_display}\n\n"
            f"<b>Описание:</b>\n{description_display}"
        )

        # Сначала отправляем фото/документы БЕЗ кнопок, соблюдая ограничения Telegram
        if material.photos and len(material.photos) > 0:
            try:
                photo_ids = []
                doc_ids = []
                for item in material.photos:
                    if isinstance(item, dict):
                        (doc_ids if item.get("kind") == "document" else photo_ids).append(item.get("id"))
                    else:
                        photo_ids.append(item)

                # 1) Фото — одной медиагруппой с caption на первом
                if photo_ids:
                    if len(photo_ids) == 1:
                        # Одно фото — отправляем через send_photo
                        await callback.bot.send_photo(
                            chat_id=callback.message.chat.id,
                            photo=photo_ids[0],
                            caption=message_text,
                            parse_mode="HTML"
                        )
                    else:
                        # Несколько фото — используем media_group
                        media_group = []
                        for i, file_id in enumerate(photo_ids, 1):
                            if i == 1:
                                media_group.append(InputMediaPhoto(media=file_id, caption=message_text, parse_mode="HTML"))
                            else:
                                media_group.append(InputMediaPhoto(media=file_id))
                        await callback.bot.send_media_group(chat_id=callback.message.chat.id, media=media_group)
                else:
                    # Если фото нет — отправим текст отдельным сообщением
                    await callback.message.edit_text(message_text, parse_mode="HTML")

                # 2) Документы-изображения — отдельной медиагруппой документов
                if doc_ids:
                    if len(doc_ids) == 1:
                        # Один документ — отправляем через send_document
                        await callback.bot.send_document(
                            chat_id=callback.message.chat.id,
                            document=doc_ids[0]
                        )
                    else:
                        # Несколько документов — используем media_group
                        docs_group = [InputMediaDocument(media=fid) for fid in doc_ids]
                        await callback.bot.send_media_group(chat_id=callback.message.chat.id, media=docs_group)

            except Exception as media_error:
                logger.error(f"Ошибка отправки media group для материала {material.name}: {media_error}")
                # Fallback: отправляем обычное сообщение БЕЗ кнопок
                await callback.message.edit_text(
                    message_text,
                    parse_mode="HTML"
                )
        else:
            # Если нет фото/документов, отправляем только текст БЕЗ кнопок
            await callback.message.edit_text(
                message_text,
                parse_mode="HTML"
            )

        # Затем отправляем файл
        if material.material_type != "link":
            try:
                # Отправляем файл по file_id в зависимости от типа
                if material.material_type == "video":
                    await callback.bot.send_video(
                        chat_id=callback.message.chat.id,
                        video=material.content  # file_id
                    )
                elif material.material_type == "photo":
                    try:
                        await callback.bot.send_photo(
                            chat_id=callback.message.chat.id,
                            photo=material.content  # file_id
                        )
                    except Exception as inner_error:
                        logger.error(f"Ошибка отправки фото: {inner_error}")
                        await callback.bot.send_document(
                            chat_id=callback.message.chat.id,
                            document=material.content
                        )
                else:
                    # Документы (pdf, doc, excel, etc.)
                    await callback.bot.send_document(
                        chat_id=callback.message.chat.id,
                        document=material.content  # file_id
                    )
            except Exception as file_error:
                logger.error(f"Ошибка отправки файла {material.name}: {file_error}")
                await callback.bot.send_message(
                    chat_id=callback.message.chat.id,
                    text=f"⚠️ Ошибка при отправке файла {material.name}. Попробуй позже."
                )

        # Наконец, отправляем кнопки навигации отдельно
        await callback.bot.send_message(
            chat_id=callback.message.chat.id,
            text=f"📋 Навигация по материалам",
            reply_markup=get_employee_material_view_keyboard(material.folder_id),
            parse_mode="HTML"
        )

        await state.set_state(KnowledgeBaseStates.employee_viewing_material)

        log_user_action(callback.from_user.id, "employee_material_viewed", f"Сотрудник просмотрел материал: {material.name}")

    except Exception as e:
        await callback.message.edit_text("Произошла ошибка при просмотре материала")
        log_user_error(callback.from_user.id, "employee_view_material_error", str(e))


@router.callback_query(F.data == "kb_emp_back_to_folders")
async def callback_employee_back_to_folders(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Возврат к списку папок для сотрудника"""
    try:
        await callback.answer()
        
        # Получение пользователя
        user = await get_user_by_tg_id(session, callback.from_user.id)
        if not user:
            await callback.message.edit_text("❌ Ты не зарегистрирован в системе.")
            return

        # Получаем папки, доступные пользователю
        data = await state.get_data()
        company_id = data.get('company_id')
        accessible_folders = await get_accessible_knowledge_folders_for_user(session, user.id, company_id)
        
        if not accessible_folders:
            await callback.message.edit_text(
                "📚 <b>База знаний</b>\n\n"
                "В данный момент для тебя нет доступных материалов.\n"
                "Обратитесь к рекрутеру для получения доступа к необходимым разделам.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="☰ Главное меню", callback_data="main_menu")]
                ]),
                parse_mode="HTML"
            )
        else:
            await callback.message.edit_text(
                "📚 <b>База знаний</b>\n\n"
                "Выбери раздел для изучения материалов:",
                reply_markup=get_employee_knowledge_folders_keyboard(accessible_folders),
                parse_mode="HTML"
            )

        await state.set_state(KnowledgeBaseStates.employee_browsing)

    except Exception as e:
        await callback.message.edit_text("Произошла ошибка при возврате к папкам")
        log_user_error(callback.from_user.id, "employee_back_to_folders_error", str(e))


# ===============================
# Общие обработчики
# ===============================
