"""
Обработчики для массовой рассылки тестов по группам (Task 8).
Включает выбор теста, выбор групп и отправку уведомлений.
"""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto, InputMediaDocument
from aiogram.fsm.context import FSMContext
from aiogram.filters import StateFilter
from sqlalchemy.ext.asyncio import AsyncSession

from database.db import (
    get_user_by_tg_id, check_user_permission, get_all_active_tests,
    get_test_by_id, get_all_groups, get_group_by_id, broadcast_test_to_groups,
    get_employees_in_group, get_all_knowledge_folders, get_knowledge_folder_by_id,
    get_knowledge_material_by_id, ensure_company_id
)
from states.states import BroadcastStates
from keyboards.keyboards import (
    get_broadcast_test_selection_keyboard, get_broadcast_groups_selection_keyboard,
    get_broadcast_success_keyboard, get_main_menu_keyboard, get_keyboard_by_role,
    get_broadcast_photos_keyboard, get_broadcast_folders_keyboard,
    get_broadcast_materials_keyboard, get_broadcast_tests_keyboard,
    get_broadcast_notification_keyboard, get_broadcast_main_menu_keyboard,
    get_broadcast_roles_selection_keyboard
)
from utils.logger import logger, log_user_action, log_user_error

router = Router()


# ===============================
# Обработчики для Task 8: Массовая рассылка тестов
# ===============================

@router.message(F.text.in_(["Рассылка ✈️", "Рассылка"]))
async def cmd_broadcast(message: Message, state: FSMContext, session: AsyncSession):
    """Обработчик кнопки 'Рассылка ✈️' в главном меню рекрутера"""
    try:
        # Получаем пользователя и проверяем права
        user = await get_user_by_tg_id(session, message.from_user.id)
        if not user:
            await message.answer("❌ Ты не зарегистрирован в системе.")
            return
        
        # Проверяем права на создание тестов (только рекрутеры)
        has_permission = await check_user_permission(session, user.id, "create_tests")
        if not has_permission:
            await message.answer(
                "❌ <b>Недостаточно прав</b>\n\n"
                "У тебя нет прав для массовой рассылки.\n"
                "Обратись к администратору.",
                parse_mode="HTML"
            )
            return
        
        # Показываем меню рассылки
        await message.answer(
            "✉️ <b>РАССЫЛКА</b> ✉️\n\n"
            "Выбери действие:",
            parse_mode="HTML",
            reply_markup=get_broadcast_main_menu_keyboard()
        )
        
        log_user_action(user.tg_id, "broadcast_menu_opened", "Открыто меню рассылки")
        
    except Exception as e:
        await message.answer("Произошла ошибка при запуске рассылки")
        log_user_error(message.from_user.id, "broadcast_start_error", str(e))


@router.callback_query(F.data == "create_broadcast")
async def callback_create_broadcast(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Обработчик кнопки 'Создать рассылку'"""
    try:
        await callback.answer()
        
        # Запрашиваем текст рассылки
        await callback.message.edit_text(
            "✉️<b>РЕДАКТОР РАССЫЛКИ</b>✉️\n\n"
            "📝 <b>Шаг 1 из 6: Текст рассылки</b>\n\n"
            "🟡 Введи текст, который увидят получатели рассылки.\n\n"
            "💡 <i>Это может быть информация о новом тесте, материалах или любое другое сообщение.</i>\n\n"
            "📏 Минимум 10 символов, максимум 4000 символов.",
            parse_mode="HTML"
        )
        
        await state.set_state(BroadcastStates.waiting_for_script)
        await state.update_data(broadcast_photos=[], broadcast_docs=[], broadcast_material_id=None, selected_test_id=None)
        log_user_action(callback.from_user.id, "broadcast_creation_started", "Начато создание рассылки")
        
    except Exception as e:
        await callback.message.edit_text("Произошла ошибка при создании рассылки")
        log_user_error(callback.from_user.id, "create_broadcast_error", str(e))


@router.message(StateFilter(BroadcastStates.waiting_for_script))
async def process_broadcast_script(message: Message, state: FSMContext, session: AsyncSession):
    """Обработка текста рассылки"""
    try:
        script_text = message.text.strip() if message.text else ""
        
        # Валидация текста
        if len(script_text) < 10:
            await message.answer(
                "❌ Текст слишком короткий!\n\n"
                "Минимальная длина: 10 символов.\n"
                "Попробуй ещё раз."
            )
            return
        
        if len(script_text) > 4000:
            await message.answer(
                "❌ Текст слишком длинный!\n\n"
                "Максимальная длина: 4000 символов.\n"
                f"Твой текст: {len(script_text)} символов.\n\n"
                "Сократи текст и попробуй ещё раз."
            )
            return
        
        # Сохраняем текст
        await state.update_data(broadcast_script=script_text)
        
        # Переходим к загрузке фото
        await message.answer(
            "✉️<b>РЕДАКТОР РАССЫЛКИ</b>✉️\n\n"
            "📝 <b>Шаг 2 из 6: Фотографии</b>\n\n"
            "🟡 Отправь фотографии для рассылки (по одной или несколько сразу).\n\n"
            "💡 <i>Фотографии помогут сделать рассылку более наглядной и привлекательной.</i>\n\n"
            "Ты можешь:\n"
            "• Отправить одну или несколько фотографий\n"
            "• Нажать 'Завершить загрузку' когда закончишь\n"
            "• Пропустить этот шаг",
            parse_mode="HTML",
            reply_markup=get_broadcast_photos_keyboard(has_photos=False)
        )
        
        await state.set_state(BroadcastStates.waiting_for_photos)
        # Инициализируем списки для фото и документов-изображений
        await state.update_data(broadcast_photos=[], broadcast_docs=[])
        log_user_action(message.from_user.id, "broadcast_script_set", f"Текст рассылки установлен ({len(script_text)} символов)")
        
    except Exception as e:
        await message.answer("Произошла ошибка при обработке текста")
        log_user_error(message.from_user.id, "process_broadcast_script_error", str(e))


@router.message(F.photo, StateFilter(BroadcastStates.waiting_for_photos))
async def process_broadcast_photos(message: Message, state: FSMContext, session: AsyncSession):
    """Обработка фотографий для рассылки"""
    try:
        # Получаем текущие фото
        data = await state.get_data()
        photos = data.get("broadcast_photos", [])
        docs = data.get("broadcast_docs", [])
        
        # Проверяем лимит
        if len(photos) + len(docs) >= 10:
            await message.answer(
                "❌ Достигнут лимит!\n\n"
                "Telegram позволяет отправить максимум 10 изображений.\n"
                "Нажми 'Завершить загрузку' для продолжения.",
                reply_markup=get_broadcast_photos_keyboard(has_photos=True)
            )
            return
        
        # Добавляем новое фото (берем самое большое разрешение)
        photo_file_id = message.photo[-1].file_id
        photos.append(photo_file_id)
        
        await state.update_data(broadcast_photos=photos)
        
        # Показываем обновленную клавиатуру с кнопкой "Завершить"
        await message.answer(
            f"✅ Фото добавлено! Всего фото: {len(photos)}\n\n"
            "Можешь отправить ещё фото или завершить загрузку.",
            reply_markup=get_broadcast_photos_keyboard(has_photos=True)
        )
        
        log_user_action(message.from_user.id, "broadcast_photo_added", f"Добавлено фото ({len(photos)} всего)")
        
    except Exception as e:
        await message.answer("Произошла ошибка при загрузке фото")
        log_user_error(message.from_user.id, "process_broadcast_photos_error", str(e))


@router.message(F.document, StateFilter(BroadcastStates.waiting_for_photos))
async def process_broadcast_image_docs(message: Message, state: FSMContext, session: AsyncSession):
    """Принимаем изображения, отправленные как документы (без сжатия) для рассылки"""
    try:
        if not message.document or not message.document.mime_type or not message.document.mime_type.startswith("image/"):
            await message.answer("❌ Пришли изображение-документ (jpg/png) или используй обычные фото")
            return

        data = await state.get_data()
        docs = data.get("broadcast_docs", []) or []
        docs.append(message.document.file_id)

        await state.update_data(broadcast_docs=docs)

        total_photos = len(data.get("broadcast_photos", []))
        await message.answer(
            f"✅ Изображение-документ добавлен! Всего: фото {total_photos}, документов {len(docs)}\n\n"
            "Можешь отправить ещё или завершить загрузку.",
            reply_markup=get_broadcast_photos_keyboard(has_photos=True)
        )

        log_user_action(message.from_user.id, "broadcast_image_doc_added", f"Добавлено доков: {len(docs)}")

    except Exception as e:
        await message.answer("Произошла ошибка при загрузке документа-изображения")
        log_user_error(message.from_user.id, "process_broadcast_image_docs_error", str(e))


@router.message(StateFilter(BroadcastStates.waiting_for_photos))
async def process_broadcast_wrong_content(message: Message, state: FSMContext, session: AsyncSession):
    """Обработка неправильного типа контента"""
    await message.answer(
        "❌ Неподдерживаемый тип!\n\n"
        "Отправь фотографию или изображение-документ.",
        reply_markup=get_broadcast_photos_keyboard(has_photos=False)
    )


@router.callback_query(F.data == "broadcast_skip_photos", StateFilter(BroadcastStates.waiting_for_photos))
async def callback_skip_photos(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Пропуск загрузки фото"""
    try:
        await callback.answer()
        
        # Получаем company_id с помощью общего helper
        company_id = await ensure_company_id(session, state, callback.from_user.id)
        if company_id is None:
            await callback.message.edit_text(
                "❌ Не удалось определить компанию. Попробуй снова или обратись к администратору."
            )
            await state.clear()
            log_user_error(callback.from_user.id, "broadcast_company_missing", "company_id not resolved")
            return

        # Показываем выбор материалов
        folders = await get_all_knowledge_folders(session, company_id)
        
        if not folders:
            await callback.message.edit_text(
                "✉️<b>РЕДАКТОР РАССЫЛКИ</b>✉️\n\n"
                "📝 <b>Шаг 3 из 6: Материалы</b>\n\n"
                "📚 В базе знаний пока нет материалов.\n"
                "Сначала создай папки и материалы в разделе 'База знаний'.\n\n"
                "Переходим к выбору теста...",
                parse_mode="HTML"
            )
            # Переходим сразу к выбору теста
            await show_test_selection(callback, state, session, company_id)
            return
        
        await callback.message.edit_text(
            "✉️<b>РЕДАКТОР РАССЫЛКИ</b>✉️\n\n"
            "📝 <b>Шаг 3 из 6: Материалы</b>\n\n"
            "🟡 Выбери папку с материалом для рассылки.\n\n"
            "💡 <i>Материал будет отправлен получателям по кнопке 'Материалы'.</i>",
            parse_mode="HTML",
            reply_markup=get_broadcast_folders_keyboard(folders)
        )
        
        await state.set_state(BroadcastStates.selecting_material)
        log_user_action(callback.from_user.id, "broadcast_photos_skipped", "Фото пропущены")
        
    except Exception as e:
        await callback.message.edit_text("Произошла ошибка")
        log_user_error(callback.from_user.id, "skip_photos_error", str(e))


@router.callback_query(F.data == "broadcast_finish_photos", StateFilter(BroadcastStates.waiting_for_photos))
async def callback_finish_photos(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Завершение загрузки фото"""
    try:
        await callback.answer()
        
        data = await state.get_data()
        photos = data.get("broadcast_photos", [])
        docs = data.get("broadcast_docs", [])
        total = len(photos) + len(docs)
        
        if total == 0:
            await callback.answer("Сначала загрузи хотя бы одно изображение!", show_alert=True)
            return
        
        # Получаем company_id с помощью helper
        company_id = await ensure_company_id(session, state, callback.from_user.id)
        if company_id is None:
            await callback.message.edit_text(
                "❌ Не удалось определить компанию. Попробуй снова или обратись к администратору."
            )
            await state.clear()
            log_user_error(callback.from_user.id, "broadcast_finish_photos_company_missing", "company_id not resolved")
            return
        
        # Показываем выбор материалов
        folders = await get_all_knowledge_folders(session, company_id)
        
        if not folders:
            await callback.message.edit_text(
                "✉️<b>РЕДАКТОР РАССЫЛКИ</b>✉️\n\n"
                "📝 <b>Шаг 3 из 6: Материалы</b>\n\n"
                "📚 В базе знаний пока нет материалов.\n"
                "Сначала создай папки и материалы в разделе 'База знаний'.\n\n"
                "Переходим к выбору теста...",
                parse_mode="HTML"
            )
            # Переходим сразу к выбору теста
            await show_test_selection(callback, state, session, company_id)
            return
        
        await callback.message.edit_text(
            "✉️<b>РЕДАКТОР РАССЫЛКИ</b>✉️\n\n"
            "📝 <b>Шаг 3 из 6: Материалы</b>\n\n"
            f"✅ Загружено: фото {len(photos)}, документов {len(docs)}\n\n"
            "🟡 Выбери папку с материалом для рассылки.\n\n"
            "💡 <i>Материал будет отправлен получателям по кнопке 'Материалы'.</i>",
            parse_mode="HTML",
            reply_markup=get_broadcast_folders_keyboard(folders)
        )
        
        await state.set_state(BroadcastStates.selecting_material)
        log_user_action(callback.from_user.id, "broadcast_photos_finished", f"Загружено {len(photos)} фото")
        
    except Exception as e:
        await callback.message.edit_text("Произошла ошибка")
        log_user_error(callback.from_user.id, "finish_photos_error", str(e))


async def show_test_selection(callback: CallbackQuery, state: FSMContext, session: AsyncSession, company_id: int = None):
    """Вспомогательная функция показа выбора теста"""
    if company_id is None:
        company_id = await ensure_company_id(session, state, callback.from_user.id)
    if company_id is None:
        await callback.answer("Не удалось определить компанию. Повтори попытку позже.", show_alert=True)
        await state.clear()
        log_user_error(callback.from_user.id, "broadcast_show_tests_company_missing", "company_id not resolved")
        return

    tests = await get_all_active_tests(session, company_id)
    
    if not tests:
        await callback.message.edit_text(
            "✉️<b>РЕДАКТОР РАССЫЛКИ</b>✉️\n\n"
            "📝 <b>Шаг 4 из 6: Тест</b>\n\n"
            "❌ В системе пока нет созданных тестов.\n\n"
            "Переходим к выбору ролей...",
            parse_mode="HTML"
        )
        # Переходим сразу к выбору ролей
        await show_roles_selection(callback, state, session)
        return
    
    await callback.message.edit_text(
        "✉️<b>РЕДАКТОР РАССЫЛКИ</b>✉️\n\n"
        "📝 <b>Шаг 4 из 6: Тест</b>\n\n"
        "🟡 Выбери тест для рассылки (опционально).\n\n"
        "💡 <i>Если выберешь тест, получатели смогут перейти к нему по кнопке.</i>",
        parse_mode="HTML",
        reply_markup=get_broadcast_tests_keyboard(tests)
    )
    
    await state.set_state(BroadcastStates.selecting_test)


async def show_roles_selection(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Вспомогательная функция показа выбора ролей"""
    await callback.message.edit_text(
        "✉️<b>РЕДАКТОР РАССЫЛКИ</b>✉️\n\n"
        "📝 <b>Шаг 5 из 6: Выбор ролей</b>\n\n"
        "🟡 Выбери роли, которым отправить рассылку:\n\n"
        "💡 <i>Можно выбрать несколько ролей или отправить всем</i>",
        parse_mode="HTML",
        reply_markup=get_broadcast_roles_selection_keyboard([])
    )
    await state.update_data(selected_roles=[])
    await state.set_state(BroadcastStates.selecting_roles)


async def show_groups_selection(callback: CallbackQuery, state: FSMContext, session: AsyncSession, company_id: int = None):
    """Вспомогательная функция показа выбора групп"""
    data = await state.get_data()
    selected_test_id = data.get("selected_test_id")
    broadcast_material_id = data.get("broadcast_material_id")
    selected_roles = data.get("selected_roles", [])
    
    if company_id is None:
        company_id = await ensure_company_id(session, state, callback.from_user.id)
    if company_id is None:
        await callback.answer("Не удалось определить компанию. Повтори попытку позже.", show_alert=True)
        await state.clear()
        log_user_error(callback.from_user.id, "broadcast_show_groups_company_missing", "company_id not resolved")
        return
    # Получаем все группы
    groups = await get_all_groups(session, company_id)
    
    if not groups:
        await callback.message.edit_text(
            "✉️<b>РЕДАКТОР РАССЫЛКИ</b>✉️\n\n"
            "❌ <b>Нет доступных групп</b>\n\n"
            "В системе пока нет созданных групп.\n"
            "Сначала создай группы пользователей.",
            parse_mode="HTML",
            reply_markup=get_main_menu_keyboard()
        )
        return
    
    # Формируем информацию о рассылке
    info_lines = ["✉️<b>РЕДАКТОР РАССЫЛКИ</b>✉️\n\n", "📝 <b>Шаг 6 из 6: Выбор групп</b>\n\n"]
    
    # Добавляем информацию о тесте (если есть)
    if selected_test_id:
        test = await get_test_by_id(session, selected_test_id, company_id=company_id)
        if test:
            info_lines.append(f"🟢 <b>Тест:</b> {test.name}\n")
    
    # Добавляем информацию о материале (если есть)
    if broadcast_material_id:
        material = await get_knowledge_material_by_id(session, broadcast_material_id)
        if material:
            info_lines.append(f"🟢 <b>Материал:</b> {material.name}\n")
    
    # Добавляем информацию о ролях
    if selected_roles:
        role_names = {
            "trainee": "Стажер",
            "employee": "Сотрудник",
            "mentor": "Наставник",
            "recruiter": "Рекрутер",
            "manager": "Руководитель"
        }
        selected_display = [role_names.get(r, r) for r in selected_roles]
        info_lines.append(f"🟢 <b>Роли:</b> {', '.join(selected_display)}\n")
    
    info_lines.append("\n🟡 <b>Выбери группы для рассылки👇</b>")
    
    await callback.message.edit_text(
        "".join(info_lines),
        parse_mode="HTML",
        reply_markup=get_broadcast_groups_selection_keyboard(groups, [])
    )
    
    await state.update_data(selected_groups=[])
    await state.set_state(BroadcastStates.selecting_groups)


@router.callback_query(F.data.startswith("broadcast_folder:"), StateFilter(BroadcastStates.selecting_material))
async def callback_show_folder_materials(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Показ материалов из выбранной папки"""
    try:
        await callback.answer()
        
        # Получаем company_id для изоляции
        data = await state.get_data()
        company_id = data.get('company_id')
        
        folder_id = int(callback.data.split(":")[1])
        folder = await get_knowledge_folder_by_id(session, folder_id, company_id=company_id)
        
        if not folder:
            await callback.answer("Папка не найдена", show_alert=True)
            return
        
        # Фильтруем только активные материалы
        active_materials = [m for m in folder.materials if m.is_active]
        
        if not active_materials:
            await callback.answer(
                "В этой папке нет материалов. Выбери другую папку или пропусти этот шаг.",
                show_alert=True
            )
            return
        
        await callback.message.edit_text(
            "✉️<b>РЕДАКТОР РАССЫЛКИ</b>✉️\n\n"
            "📝 <b>Шаг 3 из 5: Материалы</b>\n\n"
            f"📁 <b>Папка:</b> {folder.name}\n\n"
            "🟡 Выбери материал для рассылки:",
            parse_mode="HTML",
            reply_markup=get_broadcast_materials_keyboard(folder.name, active_materials)
        )
        
        log_user_action(callback.from_user.id, "broadcast_folder_selected", f"Выбрана папка: {folder.name}")
        
    except Exception as e:
        await callback.message.edit_text("Произошла ошибка")
        log_user_error(callback.from_user.id, "show_folder_materials_error", str(e))


@router.callback_query(F.data == "broadcast_back_to_folders", StateFilter(BroadcastStates.selecting_material))
async def callback_back_to_folders(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Возврат к выбору папок"""
    try:
        await callback.answer()
        
        # Получение company_id из контекста (добавлен CompanyMiddleware)
        data = await state.get_data()
        company_id = data.get('company_id')
        
        folders = await get_all_knowledge_folders(session, company_id)
        
        await callback.message.edit_text(
            "✉️<b>РЕДАКТОР РАССЫЛКИ</b>✉️\n\n"
            "📝 <b>Шаг 3 из 5: Материалы</b>\n\n"
            "🟡 Выбери папку с материалом для рассылки:",
            parse_mode="HTML",
            reply_markup=get_broadcast_folders_keyboard(folders)
        )
        
    except Exception as e:
        await callback.message.edit_text("Произошла ошибка")
        log_user_error(callback.from_user.id, "back_to_folders_error", str(e))


@router.callback_query(F.data.startswith("broadcast_select_material:"), StateFilter(BroadcastStates.selecting_material))
async def callback_broadcast_material_selected(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Выбор материала для рассылки"""
    try:
        await callback.answer()
        
        material_id = int(callback.data.split(":")[1])
        material = await get_knowledge_material_by_id(session, material_id)
        
        if not material or not material.is_active:
            await callback.answer("Материал не найден или неактивен", show_alert=True)
            return
        
        # Сохраняем выбранный материал
        await state.update_data(broadcast_material_id=material_id)
        
        # Переходим к выбору теста
        await show_test_selection(callback, state, session)
        
        log_user_action(callback.from_user.id, "broadcast_material_selected", f"Выбран материал: {material.name}")
        
    except Exception as e:
        await callback.message.edit_text("Произошла ошибка")
        log_user_error(callback.from_user.id, "material_selected_error", str(e))


@router.callback_query(F.data == "broadcast_skip_material", StateFilter(BroadcastStates.selecting_material))
async def callback_skip_material(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Пропуск выбора материала"""
    try:
        await callback.answer()
        
        # Переходим к выбору теста
        data = await state.get_data()
        company_id = data.get('company_id')
        await show_test_selection(callback, state, session, company_id)
        
        log_user_action(callback.from_user.id, "broadcast_material_skipped", "Материал пропущен")
        
    except Exception as e:
        await callback.message.edit_text("Произошла ошибка")
        log_user_error(callback.from_user.id, "skip_material_error", str(e))


@router.callback_query(F.data == "test_filter:broadcast")
async def callback_start_broadcast(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Шаг 3 ТЗ: Начало процесса рассылки"""
    try:
        await callback.answer()
        
        # Получаем пользователя и проверяем права
        user = await get_user_by_tg_id(session, callback.from_user.id)
        if not user:
            await callback.message.edit_text("❌ Ты не зарегистрирован в системе.")
            return
        
        # Проверяем права на создание тестов (только рекрутеры)
        has_permission = await check_user_permission(session, user.id, "create_tests")
        if not has_permission:
            await callback.message.edit_text(
                "❌ <b>Недостаточно прав</b>\n\n"
                "У тебя нет прав для массовой рассылки тестов.\n"
                "Обратись к администратору.",
                parse_mode="HTML"
            )
            return
        
        # Получение company_id из контекста (добавлен CompanyMiddleware)
        company_id = await ensure_company_id(session, state, callback.from_user.id)
        # Получаем все активные тесты
        tests = await get_all_active_tests(session, company_id)
        
        if not tests:
            await callback.message.edit_text(
                "✉️<b>РЕДАКТОР РАССЫЛКИ</b>✉️\n\n"
                "❌ <b>Нет доступных тестов</b>\n\n"
                "В системе пока нет созданных тестов для рассылки.\n"
                "Сначала создай тесты.",
                parse_mode="HTML",
                reply_markup=get_main_menu_keyboard()
            )
            return
        
        # Шаг 4 ТЗ: Показываем список тестов для выбора
        await callback.message.edit_text(
            "✉️<b>РЕДАКТОР РАССЫЛКИ</b>✉️\n\n"
            "🟡<b>Какой тест ты хочешь отправить пользователям?</b>\n\n"
            "📝 <b>Рассылка будет отправлена сотрудникам, стажерам и наставникам</b>\n\n"
            "Выбери тест из списка👇",
            parse_mode="HTML",
            reply_markup=get_broadcast_test_selection_keyboard(tests)
        )
        
        await state.set_state(BroadcastStates.selecting_test)
        log_user_action(user.tg_id, "broadcast_started", "Начата массовая рассылка тестов")
        
    except Exception as e:
        await callback.message.edit_text("Произошла ошибка при запуске рассылки")
        log_user_error(callback.from_user.id, "broadcast_start_error", str(e))


@router.callback_query(F.data.startswith("broadcast_test:"), BroadcastStates.selecting_test)
async def callback_select_broadcast_test(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Выбор теста для рассылки"""
    try:
        await callback.answer()
        
        # Получаем company_id для изоляции
        data = await state.get_data()
        company_id = data.get('company_id')
        
        test_id = int(callback.data.split(":")[1])
        
        # Получаем информацию о тесте с изоляцией
        test = await get_test_by_id(session, test_id, company_id=company_id)
        if not test:
            await callback.answer("Тест не найден", show_alert=True)
            return
        
        # Сохраняем выбранный тест
        await state.update_data(selected_test_id=test_id)
        
        # Переходим к выбору ролей
        await show_roles_selection(callback, state, session)
        
        log_user_action(callback.from_user.id, "broadcast_test_selected", f"Выбран тест для рассылки: {test.name}")
        
    except Exception as e:
        await callback.message.edit_text("Произошла ошибка при выборе теста")
        log_user_error(callback.from_user.id, "broadcast_test_select_error", str(e))


@router.callback_query(F.data == "broadcast_skip_test", StateFilter(BroadcastStates.selecting_test))
async def callback_skip_test(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Пропуск выбора теста"""
    try:
        await callback.answer()
        
        # Переходим к выбору ролей
        await show_roles_selection(callback, state, session)
        
        log_user_action(callback.from_user.id, "broadcast_test_skipped", "Тест пропущен")
        
    except Exception as e:
        await callback.message.edit_text("Произошла ошибка")
        log_user_error(callback.from_user.id, "skip_test_error", str(e))


@router.callback_query(F.data.startswith("broadcast_role:"), BroadcastStates.selecting_roles)
async def callback_toggle_broadcast_role(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Выбор/отмена роли для рассылки"""
    try:
        await callback.answer()
        
        role_key = callback.data.split(":")[1]
        
        # Получаем текущие выбранные роли
        data = await state.get_data()
        selected_roles = data.get("selected_roles", [])
        
        # Переключаем роль
        if role_key in selected_roles:
            selected_roles.remove(role_key)
        else:
            selected_roles.append(role_key)
        
        await state.update_data(selected_roles=selected_roles)
        
        # Обновляем клавиатуру
        role_names = {
            "trainee": "Стажер",
            "employee": "Сотрудник", 
            "mentor": "Наставник",
            "recruiter": "Рекрутер",
            "manager": "Руководитель"
        }
        selected_display = [role_names[r] for r in selected_roles]
        
        info_text = (
            "✉️<b>РЕДАКТОР РАССЫЛКИ</b>✉️\n\n"
            "📝 <b>Шаг 5 из 6: Выбор ролей</b>\n\n"
            "🟡 Выбери роли, которым отправить рассылку:\n\n"
        )
        
        if selected_roles:
            info_text += f"✅ Выбрано: {', '.join(selected_display)}\n\n"
        else:
            info_text += "⚠️ Не выбрано ни одной роли\n\n"
        
        info_text += "💡 <i>Можно выбрать несколько ролей или отправить всем</i>"
        
        await callback.message.edit_text(
            info_text,
            parse_mode="HTML",
            reply_markup=get_broadcast_roles_selection_keyboard(selected_roles)
        )
        
    except Exception as e:
        await callback.message.edit_text("Произошла ошибка при выборе роли")
        log_user_error(callback.from_user.id, "broadcast_role_toggle_error", str(e))


@router.callback_query(F.data == "broadcast_roles_all", BroadcastStates.selecting_roles)
async def callback_select_all_roles(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Переключить все роли (выбрать все / снять все)"""
    try:
        data = await state.get_data()
        current_roles = data.get("selected_roles", [])
        all_roles = ["trainee", "employee", "mentor", "recruiter", "manager"]
        
        # TOGGLE: Если все выбраны → снять все, иначе → выбрать все
        if set(current_roles) == set(all_roles):
            # Снять все
            await callback.answer("Сняты все роли")
            await state.update_data(selected_roles=[])
            
            info_text = (
                "✉️<b>РЕДАКТОР РАССЫЛКИ</b>✉️\n\n"
                "📝 <b>Шаг 5 из 6: Выбор ролей</b>\n\n"
                "🟡 Выбери роли, которым отправить рассылку:\n\n"
                "⚠️ Не выбрано ни одной роли\n\n"
                "💡 <i>Можно выбрать несколько ролей или отправить всем</i>"
            )
            
            await callback.message.edit_text(
                info_text,
                parse_mode="HTML",
                reply_markup=get_broadcast_roles_selection_keyboard([])
            )
        else:
            # Выбрать все
            await callback.answer("Выбраны все роли")
            await state.update_data(selected_roles=all_roles)
            
            info_text = (
                "✉️<b>РЕДАКТОР РАССЫЛКИ</b>✉️\n\n"
                "📝 <b>Шаг 5 из 6: Выбор ролей</b>\n\n"
                "✅ Выбраны все роли: Стажер, Сотрудник, Наставник, Рекрутер, Руководитель\n\n"
                "💡 <i>Рассылка будет отправлена всем пользователям выбранных групп</i>"
            )
            
            await callback.message.edit_text(
                info_text,
                parse_mode="HTML",
                reply_markup=get_broadcast_roles_selection_keyboard(all_roles)
            )
        
    except Exception as e:
        await callback.message.edit_text("Произошла ошибка")
        log_user_error(callback.from_user.id, "broadcast_roles_all_error", str(e))


@router.callback_query(F.data == "broadcast_roles_next", BroadcastStates.selecting_roles)
async def callback_proceed_to_groups(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Переход к выбору групп после выбора ролей"""
    try:
        data = await state.get_data()
        selected_roles = data.get("selected_roles", [])
        
        if not selected_roles:
            await callback.answer("⚠️ Выбери хотя бы одну роль", show_alert=True)
            return
        
        await callback.answer()
        
        # Переходим к выбору групп
        data = await state.get_data()
        company_id = data.get('company_id')
        await show_groups_selection(callback, state, session, company_id)
        
        log_user_action(callback.from_user.id, "broadcast_roles_selected", f"Выбраны роли: {', '.join(selected_roles)}")
        
    except Exception as e:
        await callback.message.edit_text("Произошла ошибка")
        log_user_error(callback.from_user.id, "broadcast_proceed_groups_error", str(e))


@router.callback_query(F.data.startswith("broadcast_group:"), BroadcastStates.selecting_groups)
async def callback_toggle_broadcast_group(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Шаг 7-10 ТЗ: Выбор/отмена групп для рассылки"""
    try:
        await callback.answer()
        
        group_id = int(callback.data.split(":")[1])
        
        # Получаем текущие данные
        data = await state.get_data()
        selected_test_id = data.get("selected_test_id")
        selected_groups = data.get("selected_groups", [])
        broadcast_docs = data.get("broadcast_docs", [])
        broadcast_material_id = data.get("broadcast_material_id")
        company_id = data.get('company_id')
        
        # Получаем информацию о тесте (опционально) и группе
        test = None
        if selected_test_id:
            test = await get_test_by_id(session, selected_test_id, company_id=company_id)
        
        group = await get_group_by_id(session, group_id, company_id=company_id)
        
        if not group:
            await callback.answer("Группа не найдена", show_alert=True)
            return
        
        # Переключаем выбор группы
        if group_id in selected_groups:
            selected_groups.remove(group_id)
        else:
            selected_groups.append(group_id)
        
        await state.update_data(selected_groups=selected_groups)
        
        # Получаем названия выбранных групп
        selected_group_names = []
        for gid in selected_groups:
            g = await get_group_by_id(session, gid, company_id=company_id)
            if g:
                selected_group_names.append(g.name)
        
        # Формируем сообщение согласно ТЗ
        groups_text = "; ".join(selected_group_names) if selected_group_names else ""
        
        # Получение company_id из контекста (добавлен CompanyMiddleware)
        company_id = await ensure_company_id(session, state, callback.from_user.id)
        # Получаем все группы для отображения
        all_groups = await get_all_groups(session, company_id)
        
        # Формируем информацию о рассылке
        info_lines = ["✉️<b>РЕДАКТОР РАССЫЛКИ</b>✉️\n\n"]
        
        # Добавляем информацию о тесте (если есть)
        if test:
            info_lines.append(f"🟢 <b>Тест:</b> {test.name}\n")
        
        # Добавляем информацию о материале (если есть)
        if broadcast_material_id:
            material = await get_knowledge_material_by_id(session, broadcast_material_id)
            if material:
                info_lines.append(f"🟢 <b>Материал:</b> {material.name}\n")
        
        # Добавляем информацию о группах
        if selected_group_names:
            info_lines.append(f"🟢 <b>Группы:</b> {groups_text}\n\n")
            info_lines.append("🟡 <b>Добавить ещё группу?</b>\n")
            info_lines.append("Выбери группу на клавиатуре👇")
        else:
            info_lines.append("🟡 <b>Выбери группы для рассылки👇</b>")
        
        message_text = "".join(info_lines)
        
        await callback.message.edit_text(
            message_text,
            parse_mode="HTML",
            reply_markup=get_broadcast_groups_selection_keyboard(all_groups, selected_groups)
        )
        
        log_user_action(callback.from_user.id, "broadcast_group_toggled", 
                       f"Группа {group.name} {'добавлена' if group_id in selected_groups else 'убрана'}")
        
    except Exception as e:
        await callback.message.edit_text("Произошла ошибка при выборе группы")
        log_user_error(callback.from_user.id, "broadcast_group_toggle_error", str(e))


@router.callback_query(F.data == "broadcast_send", BroadcastStates.selecting_groups)
async def callback_send_broadcast(callback: CallbackQuery, state: FSMContext, session: AsyncSession, bot):
    """Отправка рассылки с новыми параметрами"""
    try:
        await callback.answer()
        
        # Получаем данные рассылки
        data = await state.get_data()
        broadcast_script = data.get("broadcast_script")
        broadcast_photos = data.get("broadcast_photos", [])
        broadcast_material_id = data.get("broadcast_material_id")
        selected_test_id = data.get("selected_test_id")
        selected_groups = data.get("selected_groups", [])
        selected_roles = data.get("selected_roles", [])
        broadcast_docs = data.get("broadcast_docs", [])
        company_id = data.get('company_id')
        
        # Проверяем обязательные поля
        if not broadcast_script or not selected_groups:
            await callback.answer("Не указан текст рассылки или группы", show_alert=True)
            return
        
        # Получаем пользователя
        user = await get_user_by_tg_id(session, callback.from_user.id)
        if not user:
            await callback.message.edit_text("❌ Пользователь не найден")
            return
        
        # Проверяем права на рассылку
        has_permission = await check_user_permission(session, user.id, "create_tests")
        if not has_permission:
            await callback.message.edit_text("❌ У тебя нет прав для массовой рассылки.")
            return
        
        # Преобразуем ключи ролей в названия для БД
        target_role_names = None
        if selected_roles:
            role_mapping = {
                "trainee": "Стажер",
                "employee": "Сотрудник",
                "mentor": "Наставник",
                "recruiter": "Рекрутер",
                "manager": "Руководитель"
            }
            target_role_names = [role_mapping[r] for r in selected_roles]
        
        # Получаем company_id для изоляции
        data = await state.get_data()
        company_id = data.get('company_id')
        
        # Выполняем массовую рассылку с новыми параметрами
        result = await broadcast_test_to_groups(
            session=session,
            test_id=selected_test_id,
            group_ids=selected_groups,
            sent_by_id=user.id,
            bot=bot,
            broadcast_script=broadcast_script,
            company_id=company_id,
            broadcast_photos=broadcast_photos,
            broadcast_material_id=broadcast_material_id,
            broadcast_docs=broadcast_docs,
            target_roles=target_role_names
        )
        
        if not result["success"]:
            await callback.message.edit_text(
                "❌ <b>Ошибка рассылки</b>\n\n"
                f"Произошла ошибка: {result.get('error', 'Неизвестная ошибка')}",
                parse_mode="HTML",
                reply_markup=get_main_menu_keyboard()
            )
            return
        
        # Формируем сообщение об успехе
        groups_text = "; ".join(result["group_names"])
        
        success_parts = ["✉️<b>РЕДАКТОР РАССЫЛКИ</b>✉️\n\n"]
        
        if selected_test_id:
            test = await get_test_by_id(session, selected_test_id, company_id=company_id)
            if test:
                success_parts.append(f"🟢 <b>Тест:</b> {test.name}\n")
        
        if broadcast_material_id:
            material = await get_knowledge_material_by_id(session, broadcast_material_id)
            if material:
                success_parts.append(f"🟢 <b>Материал:</b> {material.name}\n")
        
        if broadcast_photos:
            success_parts.append(f"🟢 <b>Фото:</b> {len(broadcast_photos)} шт.\n")
        if broadcast_docs:
            success_parts.append(f"🟢 <b>Документы-изображения:</b> {len(broadcast_docs)} шт.\n")
        
        success_parts.append(f"🟢 <b>Группы:</b> {groups_text}\n\n")
        success_parts.append("✅ <b>Ты успешно отправил рассылку!</b>\n\n")
        success_parts.append(
            f"📊 <b>Статистика:</b>\n"
            f"• Получателей в группах: {result['total_users']}\n"
            f"• Уведомлений отправлено: {result['total_sent']}\n"
            f"• Ошибок отправки: {result['failed_sends']}"
        )
        
        await callback.message.edit_text(
            "".join(success_parts),
            parse_mode="HTML",
            reply_markup=get_broadcast_success_keyboard()
        )
        
        # Очищаем состояние
        await state.clear()
        
        log_user_action(callback.from_user.id, "broadcast_completed", 
                       f"Рассылка завершена: группы {groups_text}, отправлено {result['total_sent']}")
        
    except Exception as e:
        await callback.message.edit_text("Произошла ошибка при отправке рассылки")
        log_user_error(callback.from_user.id, "broadcast_send_error", str(e))


@router.callback_query(F.data.startswith("broadcast_material:"))
async def callback_broadcast_material(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Отправка материала получателю рассылки"""
    try:
        await callback.answer()
        
        material_id = int(callback.data.split(":")[1])
        material = await get_knowledge_material_by_id(session, material_id)
        
        if not material or not material.is_active:
            await callback.answer("Материал недоступен", show_alert=True)
            return
        
        # Готовим текст для превью/сообщения
        is_link = material.material_type == "link"
        if is_link:
            message_text = f"📚 <b>{material.name}</b>\n\n"
            if material.description:
                message_text += f"{material.description}\n\n"
            message_text += f"🔗 {material.content}"
        else:
            caption = f"📄 {material.name}"
            if material.description:
                caption += f"\n\n{material.description}"

        # Превью: сначала отправляем фото/документы-превью, если есть
        if material.photos and len(material.photos) > 0:
            # Разделяем фото и документы-изображения
            photo_ids = []
            doc_ids = []
            for item in material.photos:
                if isinstance(item, dict):
                    (doc_ids if item.get("kind") == "document" else photo_ids).append(item.get("id"))
                else:
                    photo_ids.append(item)

            # Фото — одной медиагруппой, caption у первого (если ссылка — используем message_text как caption)
            if photo_ids:
                if len(photo_ids) == 1:
                    # Одно фото — отправляем через send_photo
                    await callback.bot.send_photo(
                        chat_id=callback.message.chat.id,
                        photo=photo_ids[0],
                        caption=(message_text if is_link else None),
                        parse_mode="HTML" if is_link else None
                    )
                else:
                    # Несколько фото — используем media_group
                    media_group = []
                    for i, file_id in enumerate(photo_ids, 1):
                        if i == 1:
                            media_group.append(InputMediaPhoto(media=file_id, caption=(message_text if is_link else None), parse_mode="HTML" if is_link else None))
                        else:
                            media_group.append(InputMediaPhoto(media=file_id))
                    await callback.bot.send_media_group(chat_id=callback.message.chat.id, media=media_group)
            else:
                # Нет фото — отправим текст отдельно перед группой документов, если ссылка
                if is_link:
                    await callback.message.answer(message_text, parse_mode="HTML")

            # Документы-изображения — отдельной медиагруппой документов без caption (текст уже отправлен/прикреплён)
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

        else:
            # Превью нет
            if is_link:
                await callback.message.answer(message_text, parse_mode="HTML")

        # Затем основной материал
        if not is_link:
            if material.material_type == "video":
                await callback.bot.send_video(
                    chat_id=callback.message.chat.id,
                    video=material.content,
                    caption=caption[:1024] if len(caption) > 1024 else caption
                )
            elif material.material_type == "photo":
                try:
                    await callback.bot.send_photo(
                        chat_id=callback.message.chat.id,
                        photo=material.content,
                        caption=caption[:1024] if len(caption) > 1024 else caption
                    )
                except Exception as inner_error:
                    logger.error(f"Ошибка отправки фото в рассылке: {inner_error}")
                    await callback.bot.send_document(
                        chat_id=callback.message.chat.id,
                        document=material.content,
                        caption=caption[:1024] if len(caption) > 1024 else caption
                    )
            else:
                # Документы (pdf, doc, excel, презентации и т.д.)
                await callback.bot.send_document(
                    chat_id=callback.message.chat.id,
                    document=material.content,
                    caption=caption[:1024] if len(caption) > 1024 else caption
                )
        
        log_user_action(callback.from_user.id, "broadcast_material_viewed", f"Просмотрен материал: {material.name}")
        
    except Exception as e:
        await callback.answer("Произошла ошибка при загрузке материала", show_alert=True)
        log_user_error(callback.from_user.id, "broadcast_material_error", str(e))


