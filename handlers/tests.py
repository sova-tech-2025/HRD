from aiogram import Router, F
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession
import json

from database.db import (
    create_test, get_tests_by_creator, get_all_active_tests,
    add_question_to_test, get_test_questions, get_all_stages,
    update_test, delete_test, get_test_by_id, check_user_permission,
    get_user_by_tg_id, get_test_results_summary, get_user_by_id, get_user_roles,
    get_mentor_trainees, grant_test_access, update_question, delete_question,
    get_question_analytics, get_user_test_result, check_test_access
)
from database.models import InternshipStage, TestQuestion
from sqlalchemy import select
from keyboards.keyboards import (
    get_simple_test_selection_keyboard, get_stage_selection_keyboard,
    get_yes_no_keyboard, get_question_selection_keyboard,
    get_test_description_keyboard, get_test_materials_keyboard,
    get_materials_choice_keyboard, get_test_created_success_keyboard,
    get_test_actions_keyboard, get_test_filter_keyboard,
    get_question_type_keyboard, get_test_edit_menu,
    get_question_management_keyboard, get_test_settings_keyboard,
    get_finish_options_keyboard, get_test_start_keyboard, get_tests_main_keyboard
)
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from states.states import TestCreationStates, TestTakingStates
from utils.logger import log_user_action, log_user_error, logger
from handlers.auth import check_auth

router = Router()


@router.message(F.text.in_(["Тесты 📄", "Тесты"]))
async def cmd_tests_main(message: Message, state: FSMContext, session: AsyncSession):
    """Обработчик кнопки 'Тесты 📄' в главном меню рекрутера"""
    try:
        # Проверка авторизации
        is_auth = await check_auth(message, state, session)
        if not is_auth:
            return
        
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
                "У тебя нет прав для управления тестами.\n"
                "Обратись к администратору.",
                parse_mode="HTML"
            )
            return
        
        # Показываем меню управления тестами
        await message.answer(
            "📄 <b>УПРАВЛЕНИЕ ТЕСТАМИ</b>\n\n"
            "Выбери действие:",
            parse_mode="HTML",
            reply_markup=get_tests_main_keyboard()
        )
        
        log_user_action(user.tg_id, "tests_main_menu", "Открыто меню управления тестами")
        
    except Exception as e:
        await message.answer("Произошла ошибка при открытии меню тестов")
        log_user_error(message.from_user.id, "tests_main_error", str(e))


# =================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# =================================

async def get_creator_name(session: AsyncSession, creator_id: int) -> str:
    """Получение имени создателя теста"""
    try:
        creator = await get_user_by_id(session, creator_id)
        return creator.full_name if creator else "Неизвестен"
    except Exception as e:
        logger.error(f"Ошибка получения имени создателя {creator_id}: {e}")
        return "Неизвестен"

# =================================
# СОЗДАНИЕ ТЕСТОВ
# =================================

@router.message(Command("create_test"))
async def cmd_create_test_command(message: Message, state: FSMContext, session: AsyncSession):
    """Обработчик команды /create_test"""
    await cmd_create_test(message, state, session)

@router.message(Command("manage_tests"))
async def cmd_manage_tests_command(message: Message, state: FSMContext, session: AsyncSession):
    """Обработчик команды /manage_tests"""
    await cmd_list_tests(message, state, session)

@router.message(F.text.in_(["Создать тест", "Создать новый", "Создать тест"]))
async def cmd_create_test(message: Message, state: FSMContext, session: AsyncSession):
    """Обработчик команды создания теста"""
    is_auth = await check_auth(message, state, session)
    if not is_auth:
        return
    
    user = await get_user_by_tg_id(session, message.from_user.id)
    if not user:
        await message.answer("Ты не зарегистрирован в системе.")
        return
    
    has_permission = await check_user_permission(session, user.id, "create_tests")
    if not has_permission:
        await message.answer("У тебя нет прав для создания тестов.")
        return
    
    await message.answer(
        "🔧 <b>Создание нового теста</b>\n\n"
        "📝 Начинаем пошаговое создание теста для твоей системы стажировки.\n\n"
        "1️⃣ <b>Шаг 1:</b> Введи название теста\n"
        "💡 <i>Название должно быть информативным и понятным для стажеров</i>\n\n"
        "📋 <b>Пример:</b> «Основы работы с клиентами» или «Техника безопасности»",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🚫 Отменить создание теста", callback_data="cancel")]
        ])
    )
    
    await state.set_state(TestCreationStates.waiting_for_test_name)
    await state.update_data(creator_id=user.id)
    
    log_user_action(message.from_user.id, message.from_user.username, "started test creation")

@router.message(F.text.in_(["Открыть список тестов", "Список тестов", "Тесты стажеров 📝", "Открыть список тестов"]))
async def cmd_list_tests(message: Message, state: FSMContext, session: AsyncSession):
    """Обработчик команды просмотра списка тестов"""
    is_auth = await check_auth(message, state, session)
    if not is_auth:
        return
    
    # Очищаем состояние при входе в управление тестами
    await state.clear()

    user = await get_user_by_tg_id(session, message.from_user.id)
    if not user:
        await message.answer("Ты не зарегистрирован в системе.")
        return

    # Рекрутеры/управляющие (с правом create_tests) получают выбор
    if await check_user_permission(session, user.id, "create_tests"):
        await message.answer(
            "🗂️ Выбери, какие тесты ты хочешь просмотреть:",
            reply_markup=get_test_filter_keyboard()
        )
        return

    # Наставники (без права create_tests) видят все тесты
    tests = await get_all_active_tests(session)
    if not tests:
        await message.answer(
            "📋 <b>Список доступных тестов</b>\n\n"
            "В системе пока нет созданных тестов.\nОбратись к рекрутеру для создания тестов.",
            parse_mode="HTML"
        )
        return

    tests_list = "\n\n".join([
        f"<b>{i+1}. {test.name}</b>\n"
        f"   🎯 Порог: {test.threshold_score:.1f}/{test.max_score:.1f} б.\n"
        f"   📅 Создан: {test.created_date.strftime('%d.%m.%Y')}\n"
        f"   👤 Создатель: {await get_creator_name(session, test.creator_id)}"
        for i, test in enumerate(tests)
    ])
    
    await message.answer(
        f"📋 <b>Список доступных тестов</b>\n\n{tests_list}\n\n"
        f"Выбери тест для просмотра и предоставления доступа:",
        parse_mode="HTML",
        reply_markup=get_simple_test_selection_keyboard(tests)
    )


# =================================
# ОБРАБОТЧИКИ ИНЛАЙН КНОПОК ДЛЯ РАКИРОВКИ
# =================================

@router.callback_query(F.data == "create_test")
async def callback_create_test(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Обработчик инлайн кнопки 'Создать новый'"""
    try:
        await callback.answer()
        
        # Получаем пользователя и проверяем права
        user = await get_user_by_tg_id(session, callback.from_user.id)
        if not user:
            await callback.message.edit_text("❌ Ты не зарегистрирован в системе.")
            return
        
        has_permission = await check_user_permission(session, user.id, "create_tests")
        if not has_permission:
            await callback.message.edit_text(
                "❌ <b>Недостаточно прав</b>\n\n"
                "У тебя нет прав для создания тестов.\n"
                "Обратись к администратору.",
                parse_mode="HTML"
            )
            return
        
        await callback.message.edit_text(
            "🔧 <b>Создание нового теста</b>\n\n"
            "📝 Начинаем пошаговое создание теста для твоей системы стажировки.\n\n"
            "1️⃣ <b>Шаг 1:</b> Введи название теста\n"
            "💡 <i>Название должно быть информативным и понятным для стажеров</i>\n\n"
            "📋 <b>Пример:</b> «Основы работы с клиентами» или «Техника безопасности»",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_tests_menu")],
                [InlineKeyboardButton(text="🚫 Отменить создание теста", callback_data="cancel")]
            ])
        )
        
        await state.set_state(TestCreationStates.waiting_for_test_name)
        await state.update_data(creator_id=user.id)
        
        log_user_action(user.tg_id, "started test creation", "Начато создание теста через инлайн кнопку")
        
    except Exception as e:
        await callback.message.edit_text("Произошла ошибка при создании теста")
        log_user_error(callback.from_user.id, "callback_create_test_error", str(e))


@router.callback_query(F.data == "list_tests")
async def callback_list_tests(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Обработчик инлайн кнопки 'Список тестов'"""
    try:
        await callback.answer()
        
        # Очищаем состояние при входе в управление тестами
        await state.clear()
        
        # Получаем пользователя и проверяем права
        user = await get_user_by_tg_id(session, callback.from_user.id)
        if not user:
            await callback.message.edit_text("❌ Ты не зарегистрирован в системе.")
            return
        
        # Рекрутеры/управляющие (с правом create_tests) получают выбор
        if await check_user_permission(session, user.id, "create_tests"):
            await callback.message.edit_text(
                "🗂️ Выбери, какие тесты ты хочешь просмотреть:",
                reply_markup=get_test_filter_keyboard()
            )
            return
        
        # Наставники (без права create_tests) видят все тесты
        tests = await get_all_active_tests(session)
        if not tests:
            await callback.message.edit_text(
                "📋 <b>Список доступных тестов</b>\n\n"
                "В системе пока нет созданных тестов.\nОбратись к рекрутеру для создания тестов.",
                parse_mode="HTML"
            )
            return
        
        tests_list = "\n\n".join([
            f"<b>{i+1}. {test.name}</b>\n"
            f"   🎯 Порог: {test.threshold_score:.1f}/{test.max_score:.1f} б.\n"
            f"   📅 Создан: {test.created_date.strftime('%d.%m.%Y')}\n"
            f"   👤 Создатель: {await get_creator_name(session, test.creator_id)}"
            for i, test in enumerate(tests)
        ])
        
        await callback.message.edit_text(
            f"📋 <b>Список доступных тестов</b>\n\n{tests_list}\n\n"
            f"Выбери тест для просмотра и предоставления доступа:",
            parse_mode="HTML",
            reply_markup=get_simple_test_selection_keyboard(tests)
        )
        
        log_user_action(user.tg_id, "list_tests", "Открыт список тестов через инлайн кнопку")
        
    except Exception as e:
        await callback.message.edit_text("Произошла ошибка при открытии списка тестов")
        log_user_error(callback.from_user.id, "callback_list_tests_error", str(e))


@router.callback_query(F.data == "back_to_tests_menu")
async def callback_back_to_tests_menu(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Обработчик кнопки 'Назад' - возврат к меню (для рекрутеров) или главному меню (для наставников)"""
    try:
        await callback.answer()
        
        # Получаем пользователя
        user = await get_user_by_tg_id(session, callback.from_user.id)
        if not user:
            await callback.message.edit_text("❌ Ты не зарегистрирован в системе.")
            return
        
        # Проверяем права на создание тестов
        has_create_permission = await check_user_permission(session, user.id, "create_tests")
        
        if has_create_permission:
            # Рекрутер - возврат к меню управления тестами
            await callback.message.edit_text(
                "📄 <b>УПРАВЛЕНИЕ ТЕСТАМИ</b>\n\n"
                "Выбери действие:",
                parse_mode="HTML",
                reply_markup=get_tests_main_keyboard()
            )
            log_user_action(user.tg_id, "back_to_tests_menu", "Возврат к меню управления тестами")
        else:
            # Наставник - удаляем сообщение (возврат к главному меню через reply клавиатуру)
            await callback.message.delete()
            log_user_action(user.tg_id, "back_to_tests_menu", "Возврат к главному меню (наставник)")
        
        # Очищаем состояние FSM
        await state.clear()
        
    except Exception as e:
        await callback.message.answer("Произошла ошибка при возврате к меню")
        log_user_error(callback.from_user.id, "callback_back_to_tests_menu_error", str(e))


@router.callback_query(F.data == "test_back")
async def callback_test_back(callback: CallbackQuery, state: FSMContext):
    """Обработчик кнопки 'Назад' в процессе создания теста"""
    try:
        await callback.answer()
        
        current_state = await state.get_state()
        data = await state.get_data()
        
        if current_state == TestCreationStates.waiting_for_materials:
            # Возврат к Шагу 1 - вводу названия теста
            test_name = data.get('test_name', '')
            await callback.message.edit_text(
                "🔧 <b>Создание нового теста</b>\n\n"
                "📝 Начинаем пошаговое создание теста для твоей системы стажировки.\n\n"
                "1️⃣ <b>Шаг 1:</b> Введи название теста\n"
                "💡 <i>Название должно быть информативным и понятным для стажеров</i>\n\n"
                "📋 <b>Пример:</b> «Основы работы с клиентами» или «Техника безопасности»",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_tests_menu")],
                    [InlineKeyboardButton(text="🚫 Отменить создание теста", callback_data="cancel")]
                ])
            )
            await state.set_state(TestCreationStates.waiting_for_test_name)
            
        elif current_state == TestCreationStates.waiting_for_description:
            # Возврат к Шаг 2 - выбору материалов
            test_name = data.get('test_name', '')
            await callback.message.edit_text(
                f"✅ <b>Название принято:</b> {test_name}\n\n"
                "2️⃣ <b>Шаг 2:</b> Материалы для изучения\n\n"
                "📚 Есть ли у тебя материалы, которые стажеры должны изучить перед прохождением теста?\n\n"
                "💡 <b>Материалы могут быть:</b>\n"
                "• Ссылки на обучающие видео\n"
                "• Документы и инструкции\n"
                "• Презентации или курсы\n"
                "• Любые другие учебные ресурсы\n\n"
                "❓ Хотите добавить материалы к тесту?",
                parse_mode="HTML",
                reply_markup=get_materials_choice_keyboard()
            )
            await state.set_state(TestCreationStates.waiting_for_materials)
            
        else:
            # Для других состояний - просто возврат к предыдущему шагу
            await callback.message.edit_text("❌ Не удалось вернуться к предыдущему шагу.")
            
    except Exception as e:
        await callback.message.edit_text("❌ Произошла ошибка при возврате к предыдущему шагу.")
        log_user_error(callback.from_user.id, "test_back_error", str(e))


@router.message(TestCreationStates.waiting_for_test_name)
async def process_test_name(message: Message, state: FSMContext, session: AsyncSession):
    """Обработка названия теста"""
    if not message.text:
        await message.answer(
            "❌ Пожалуйста, отправь название теста текстом, а не файлом или медиа.\n\n"
            "Введи название теста текстом:"
        )
        return
    
    test_name = message.text.strip()
    
    if len(test_name) < 3:
        await message.answer("❌ Название теста должно содержать не менее 3 символов. Попробуй еще раз:")
        return
    
    await state.update_data(test_name=test_name)
    
    await message.answer(
        f"✅ <b>Название принято:</b> {test_name}\n\n"
        "2️⃣ <b>Шаг 2:</b> Материалы для изучения\n\n"
        "📚 Есть ли у тебя материалы, которые стажеры должны изучить перед прохождением теста?\n\n"
        "💡 <b>Материалы могут быть:</b>\n"
        "• Ссылки на обучающие видео\n"
        "• Документы и инструкции\n"
        "• Презентации или курсы\n"
        "• Любые другие учебные ресурсы\n\n"
        "❓ Хочешь добавить материалы к тесту?",
        parse_mode="HTML",
        reply_markup=get_materials_choice_keyboard()
    )
    
    await state.set_state(TestCreationStates.waiting_for_materials)

@router.callback_query(TestCreationStates.waiting_for_materials, F.data.startswith("materials:"))
async def process_materials_choice(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора материалов"""
    choice = callback.data.split(':')[1]
    
    if choice == "yes":
        await callback.message.edit_text(
            "📎 Отправь ссылку на материалы для изучения, документ, изображение или нажми кнопку 'Пропустить'",
            reply_markup=get_test_materials_keyboard()
        )
    elif choice == "skip":
        await state.update_data(material_link=None)
        await ask_for_description(callback.message, state)
    else:
        await state.update_data(material_link=None)
        await ask_for_description(callback.message, state)
    
    await callback.answer()

@router.message(TestCreationStates.waiting_for_materials)
async def process_materials_input(message: Message, state: FSMContext):
    """Обработка ввода материалов"""
    if message.document:
        # Проверяем поддерживаемые типы
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
        
        if message.document.mime_type not in allowed_mimes:
            await message.answer(
                "❌ Неподдерживаемый формат файла.",
                reply_markup=get_test_materials_keyboard()
            )
            return
        
        # Пользователь отправил документ
        file_info = f"Файл: {message.document.file_name}"
        await state.update_data(material_link=file_info, material_file_id=message.document.file_id, material_type="document")
        await message.answer(f"✅ Документ '{message.document.file_name}' добавлен к тесту.")
    elif message.photo:
        # Пользователь отправил фото
        photo_file_id = message.photo[-1].file_id
        await state.update_data(material_link="Изображение", material_file_id=photo_file_id, material_type="photo")
        await message.answer("✅ Изображение добавлено к тесту.")
    elif message.video:
        # Пользователь отправил видео напрямую
        video_file_id = message.video.file_id
        await state.update_data(material_link="Видео", material_file_id=video_file_id, material_type="video")
        await message.answer("✅ Видео добавлено к тесту.")
    elif message.text:
        # Пользователь отправил текст
        if message.text.lower() == 'пропустить':
            await state.update_data(material_link=None)
        else:
            await state.update_data(material_link=message.text.strip())
    else:
        # Неподдерживаемый тип сообщения
        await message.answer(
            "❌ Пожалуйста, отправь ссылку на материалы, документ, изображение или нажми кнопку 'Пропустить'.",
            reply_markup=get_test_materials_keyboard()
        )
        return
    
    await ask_for_description(message, state)

async def ask_for_description(message: Message, state: FSMContext, show_cancel_button: bool = True):
    """Запрос описания теста"""
    keyboard = get_test_description_keyboard() if show_cancel_button else None
    
    await message.answer(
        "3️⃣ <b>Шаг 3:</b> Описание теста\n\n"
        "📝 Введи краткое описание теста, которое поможет стажерам понять:\n"
        "• О чем этот тест\n"
        "• Какие знания проверяются\n"
        "• Что ожидается от стажера\n\n"
        "💡 <b>Пример:</b> «Тест проверяет знание основных принципов обслуживания клиентов и умение решать конфликтные ситуации»\n\n"
        "✍️ Введи описание или нажми кнопку 'Пропустить':",
        parse_mode="HTML",
        reply_markup=keyboard
    )
    await state.set_state(TestCreationStates.waiting_for_description)

@router.callback_query(TestCreationStates.waiting_for_description, F.data == "description:skip")
async def process_skip_description(callback: CallbackQuery, state: FSMContext):
    """Обработка пропуска описания"""
    await state.update_data(description=None, questions=[], current_question_number=1)
    
    await callback.message.edit_text(
        "📝 <b>Отлично! Теперь давай добавим вопросы к тесту.</b>\n\n"
        "Выбери тип <b>первого вопроса</b>:",
        parse_mode="HTML",
        reply_markup=get_question_type_keyboard(is_creating_test=True)
    )
    await state.set_state(TestCreationStates.waiting_for_question_type)
    await callback.answer()

@router.message(TestCreationStates.waiting_for_description)
async def process_description(message: Message, state: FSMContext):
    """Обработка описания и начало добавления вопросов"""
    description = None if message.text.lower() == 'пропустить' else message.text.strip()
    await state.update_data(description=description, questions=[], current_question_number=1)
    
    await message.answer(
        "📝 <b>Отлично! Теперь давай добавим вопросы к тесту.</b>\n\n"
        "Выбери тип <b>первого вопроса</b>:",
        parse_mode="HTML",
        reply_markup=get_question_type_keyboard(is_creating_test=True)
    )
    await state.set_state(TestCreationStates.waiting_for_question_type)

@router.callback_query(TestCreationStates.waiting_for_question_type, F.data.startswith("q_type:"))
async def process_question_type(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора типа вопроса"""
    question_type = callback.data.split(':')[1]
    await state.update_data(current_question_type=question_type)
    
    await callback.message.edit_text("Введи <b>текст вопроса</b>:")
    await state.set_state(TestCreationStates.waiting_for_question_text)
    await callback.answer()

@router.message(TestCreationStates.waiting_for_question_text)
async def process_question_text(message: Message, state: FSMContext):
    """Обработка текста вопроса"""
    await state.update_data(current_question_text=message.text.strip())
    data = await state.get_data()
    q_type = data.get('current_question_type')

    if q_type == 'text':
        await message.answer(
            "✅ Текст вопроса принят. Теперь введи **единственный правильный ответ** (точную фразу):",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="❌ Отменить создание вопроса", callback_data="cancel_current_question")]
            ])
        )
        await state.set_state(TestCreationStates.waiting_for_answer)
    elif q_type in ['single_choice', 'multiple_choice']:
        await message.answer(
            "✅ Текст вопроса принят. Теперь давай добавим варианты ответа.\n\n"
            "Введи **первый вариант** ответа:",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="❌ Отменить создание вопроса", callback_data="cancel_current_question")]
            ])
        )
        await state.update_data(current_options=[])
        await state.set_state(TestCreationStates.waiting_for_option)
    elif q_type == 'yes_no':
        await message.answer(
            "✅ Текст вопроса принят. Теперь выбери, какой ответ является правильным:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="👍 Да", callback_data="answer_bool:Да")],
                [InlineKeyboardButton(text="👎 Нет", callback_data="answer_bool:Нет")],
                [InlineKeyboardButton(text="❌ Отменить создание вопроса", callback_data="cancel_current_question")]
            ])
        )
        await state.set_state(TestCreationStates.waiting_for_answer)

@router.message(TestCreationStates.waiting_for_option)
async def process_option(message: Message, state: FSMContext):
    """Обработка одного варианта ответа и запрос следующего"""
    data = await state.get_data()
    options = data.get('current_options', [])
    
    # Проверка на дубликаты вариантов
    if message.text.strip() in options:
        await message.answer("❌ Такой вариант уже есть. Введи другой.")
        return

    options.append(message.text.strip())
    await state.update_data(current_options=options)
    
    current_options_text = "\n".join([f"  <b>{i+1}.</b> {opt}" for i, opt in enumerate(options)])
    
    if len(options) < 2:
        await message.answer(
            f"✅ Вариант добавлен.\n\n<b>Текущие варианты:</b>\n{current_options_text}\n\nВведи **следующий вариант** ответа:",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="❌ Отменить создание вопроса", callback_data="cancel_current_question")]
            ])
        )
    else:
        await message.answer(
            f"✅ Вариант добавлен.\n\n<b>Текущие варианты:</b>\n{current_options_text}\n\nВведи **следующий** или нажми 'Завершить'.",
            parse_mode="HTML",
            reply_markup=get_finish_options_keyboard()
        )

@router.callback_query(TestCreationStates.waiting_for_option, F.data == "finish_options")
async def finish_adding_options(callback: CallbackQuery, state: FSMContext):
    """Завершение добавления вариантов и переход к выбору правильного"""
    data = await state.get_data()
    options = data.get('current_options', [])
    q_type = data.get('current_question_type')
    
    if q_type == 'single_choice':
        # Для одного правильного ответа, показываем варианты для выбора
        options_text = "\n".join([f"{i+1}. {opt}" for i, opt in enumerate(options)])
        await callback.message.edit_text(
            f"✅ Варианты приняты. Вот они:\n\n{options_text}\n\n"
            "Теперь введи **номер** правильного ответа (например: 2):",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="❌ Отменить создание вопроса", callback_data="cancel_current_question")]
            ])
        )
        await state.set_state(TestCreationStates.waiting_for_answer)

    elif q_type == 'multiple_choice':
        # Для нескольких вариантов, запрашиваем номера
        options_text = "\n".join([f"{i+1}. {opt}" for i, opt in enumerate(options)])
        await callback.message.edit_text(
            f"✅ Варианты приняты. Вот они:\n\n{options_text}\n\n"
            "Теперь введи **номера** правильных ответов через запятую (например: 1, 3):",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="❌ Отменить создание вопроса", callback_data="cancel_current_question")]
            ])
        )
        await state.set_state(TestCreationStates.waiting_for_answer)
    
    await callback.answer()

@router.message(TestCreationStates.waiting_for_answer)
async def process_answer(message: Message, state: FSMContext):
    """Обработка ответа на вопрос"""
    data = await state.get_data()
    q_type = data.get('current_question_type')
    
    answer = message.text.strip()
    
    if q_type == 'single_choice':
        try:
            index = int(answer) - 1
            options = data['current_options']
            if not (0 <= index < len(options)):
                raise ValueError
            answer = options[index]
        except (ValueError, IndexError):
            await message.answer("❌ Некорректный номер. Введи номер правильного ответа (например: 2):")
            return
    elif q_type == 'multiple_choice':
        try:
            indices = [int(i.strip()) - 1 for i in answer.split(',')]
            options = data['current_options']
            correct_answers = [options[i] for i in indices if 0 <= i < len(options)]
            if not correct_answers:
                raise ValueError
            answer = correct_answers
        except (ValueError, IndexError):
            await message.answer("❌ Некорректный формат. Введи номера через запятую (например: 1, 3):")
            return

    await state.update_data(current_answer=answer)
    await message.answer(
        "🔢 Теперь укажите, сколько баллов можно получить за правильный ответ на этот вопрос.\n"
        "Ты можешь использовать <b>дробные числа</b>, например, <code>0.5</code> или <code>1.5</code>.",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отменить создание вопроса", callback_data="cancel_current_question")]
        ])
    )
    await state.set_state(TestCreationStates.waiting_for_points)

@router.message(TestCreationStates.waiting_for_points)
async def process_points(message: Message, state: FSMContext):
    """Обработка баллов за вопрос и запрос на следующий"""
    try:
        points = float(message.text.replace(',', '.').strip())
        if points <= 0:
            await message.answer("❌ Количество баллов должно быть больше нуля. Попробуй еще раз:")
            return
    except ValueError:
        await message.answer("❌ Пожалуйста, введи число (можно дробное):")
        return

    data = await state.get_data()
    questions = data.get('questions', [])
    questions.append({
        "type": data.get('current_question_type'),
        "text": data['current_question_text'],
        "options": data.get('current_options'),
        "answer": data['current_answer'],
        "points": points
    })
    
    await state.update_data(questions=questions, current_question_number=data['current_question_number'] + 1)
    
    total_questions = len(questions)
    total_score = sum(q['points'] for q in questions)
    
    await message.answer(
        f"✅ <b>Вопрос №{total_questions} добавлен!</b>\n\n"
        f"Текущая статистика теста:\n"
        f" • Количество вопросов: {total_questions}\n"
        f" • Максимальный балл: {total_score:.1f}\n\n"
        "❓ Хочешь добавить еще один вопрос?",
        parse_mode="HTML",
        reply_markup=get_yes_no_keyboard("more_questions")
    )
    await state.set_state(TestCreationStates.waiting_for_more_questions)

@router.callback_query(TestCreationStates.waiting_for_more_questions, F.data.startswith("more_questions:"))
async def process_more_questions_choice(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Обработка выбора: добавить еще вопрос или завершить"""
    data = await state.get_data()
    test_id = data.get('test_id_to_edit')  # Проверяем, добавляем ли вопрос к существующему тесту
    
    if callback.data.endswith(":yes"):
        # Продолжаем добавлять вопросы
        is_creating_test = test_id is None
        await callback.message.edit_text(
            f"Выбери тип <b>следующего вопроса</b>:",
            parse_mode="HTML",
            reply_markup=get_question_type_keyboard(is_creating_test=is_creating_test)
        )
        await state.set_state(TestCreationStates.waiting_for_question_type)
    else:
        # Завершаем добавление вопросов
        if test_id:
            # Добавляем вопросы к существующему тесту
            questions_to_add = data.get('questions', [])
            initial_count = data.get('initial_questions_count', 0)
            
            # Получаем текущие вопросы из БД для определения правильного question_number
            existing_questions = await get_test_questions(session, test_id)
            current_max_number = len(existing_questions)
            
            # Добавляем только новые вопросы (не те, что были в тесте изначально)
            new_questions = questions_to_add[initial_count:]
            
            if new_questions:
                # Добавляем новые вопросы в БД
                for i, q_data in enumerate(new_questions, start=current_max_number + 1):
                    question_db_data = {
                        'test_id': test_id,
                        'question_number': i,
                        'question_type': q_data['type'],
                        'question_text': q_data['text'],
                        'options': q_data.get('options'),
                        'correct_answer': q_data['answer'],
                        'points': q_data['points']
                    }
                    await add_question_to_test(session, question_db_data)
                
                # Обновляем max_score теста
                test = await get_test_by_id(session, test_id)
                if test:
                    all_questions = await get_test_questions(session, test_id)
                    new_max_score = sum(q.points for q in all_questions)
                    await update_test(session, test_id, {"max_score": new_max_score})
            
            # Сохраняем session_id перед очисткой
            session_id = data.get('editor_session_id')
            await state.clear()
            if session_id:
                await state.update_data(editor_session_id=session_id)
            
            # Возвращаемся к списку вопросов
            await _show_questions_list(callback.message, state, session, test_id)
        else:
            # Создаем новый тест - переходим к настройке проходного балла
            total_score = sum(q['points'] for q in data.get('questions', []))
            
            await callback.message.edit_text(
                f"✅ <b>Добавление вопросов завершено.</b>\n\n"
                f"Максимальный балл за тест: <b>{total_score:.1f}</b>\n\n"
                f"Теперь введи <b>проходной балл</b> для этого теста (число от 0.5 до {total_score:.1f}):",
                parse_mode="HTML"
            )
            await state.set_state(TestCreationStates.waiting_for_threshold)
    await callback.answer()

@router.message(TestCreationStates.waiting_for_threshold)
async def process_threshold_and_create_test(message: Message, state: FSMContext, session: AsyncSession):
    """Обработка проходного балла и финальное создание теста"""
    data = await state.get_data()
    questions = data.get('questions', [])
    max_score = sum(q['points'] for q in questions)
    
    try:
        threshold_score = float(message.text.replace(',', '.').strip())
        if threshold_score <= 0 or threshold_score > max_score:
            await message.answer(f"❌ Проходной балл должен быть от 0.5 до {max_score:.1f}. Попробуй еще раз:")
            return
    except ValueError:
        await message.answer(f"❌ Пожалуйста, введи число от 0.5 до {max_score:.1f}:")
        return
    
    # 1. Создаем объект теста в БД
    test_data = {
        'name': data['test_name'],
        'description': data.get('description'),
        'threshold_score': threshold_score,
        'max_score': max_score,
        'material_link': data.get('material_link'),
        'material_file_path': data.get('material_file_id'),
        'material_type': data.get('material_type'),
        'creator_id': data['creator_id']
    }
    test = await create_test(session, test_data)
    
    if not test:
        await message.answer("❌ Произошла критическая ошибка при создании теста. Попробуй еще раз.")
        await state.clear()
        return
        
    # 2. Добавляем вопросы в БД, связанные с этим тестом
    for i, q_data in enumerate(questions):
        question_db_data = {
            'test_id': test.id,
            'question_number': i + 1,
            'question_type': q_data['type'],
            'question_text': q_data['text'],
            'options': q_data.get('options'),
            'correct_answer': q_data['answer'],
            'points': q_data['points']
        }
        await add_question_to_test(session, question_db_data)
        
    # 3. Финальное сообщение
    success_rate = (threshold_score / max_score) * 100
    
    await message.answer(
        f"✅ <b>Тест «{test.name}» успешно создан и готов к работе!</b>\n\n"
        f"📝 <b>Вопросов добавлено:</b> {len(questions)}\n"
        f"📊 <b>Максимальный балл:</b> {test.max_score:.1f}\n"
        f"🎯 <b>Проходной балл:</b> {test.threshold_score:.1f} ({success_rate:.1f}%)\n\n"
        "🎉 Теперь наставники могут предоставлять доступ к этому тесту.",
        parse_mode="HTML",
        reply_markup=get_test_created_success_keyboard()
    )
    
    log_user_action(
        message.from_user.id, 
        message.from_user.username, 
        "created test with questions", 
        {"test_id": test.id, "questions_count": len(questions)}
    )
    
    await state.clear()

@router.callback_query(
    F.data.startswith("test:"),
    ~StateFilter(TestTakingStates.waiting_for_test_selection)
)
async def process_test_selection(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Обработчик выбора теста для управления (не для прохождения)"""
    test_id = int(callback.data.split(':')[1])
    
    # Удаляем медиа-файл с материалами, если он был отправлен
    data = await state.get_data()
    if 'material_message_id' in data:
        try:
            await callback.bot.delete_message(
                chat_id=callback.message.chat.id,
                message_id=data['material_message_id']
            )
        except Exception:
            pass  # Сообщение уже удалено или недоступно
    
    # Очищаем сохраненные message_id
    await state.update_data(material_message_id=None, material_text_message_id=None)
    
    test = await get_test_by_id(session, test_id)
    
    if not test:
        await callback.message.answer("❌ Тест не найден.")
        await callback.answer()
        return
    
    questions = await get_test_questions(session, test_id)
    questions_count = len(questions)
    
    stage_info = ""
    if test.stage_id:
        stage = await session.execute(select(InternshipStage).where(InternshipStage.id == test.stage_id))
        stage_obj = stage.scalar_one_or_none()
        if stage_obj:
            stage_info = f"🎯 <b>Этап:</b> {stage_obj.name}\n"
    
    test_info = f"""📋 <b>Детальная информация о тесте</b>

📌 <b>Название:</b> {test.name}
📝 <b>Описание:</b> {test.description or 'Не указано'}
❓ <b>Количество вопросов:</b> {questions_count}
🎲 <b>Максимальный балл:</b> {test.max_score:.1f}
🎯 <b>Порог:</b> {test.threshold_score:.1f} б.
{stage_info}📅 <b>Дата создания:</b> {test.created_date.strftime('%d.%m.%Y %H:%M')}
🔗 <b>Материалы:</b> {test.material_link if test.material_link else 'Отсутствуют'}
"""
    
    # Определяем роль пользователя для показа подходящих кнопок
    user = await get_user_by_tg_id(session, callback.from_user.id)
    user_roles = await get_user_roles(session, user.id)
    role_names = [role.name for role in user_roles]
    
    # КРИТИЧЕСКАЯ ПРОВЕРКА: Определяем контекст - откуда пришел пользователь
    # Получаем данные состояния для определения контекста
    state_data = await state.get_data()
    context = state_data.get('test_context', 'management')  # По умолчанию - управление
    
    # Если у пользователя есть доступ (через рассылку или индивидуально), показываем интерфейс прохождения
    # Но ТОЛЬКО если контекст = 'taking' (из "Мои тесты")
    has_access = await check_test_access(session, user.id, test_id)
    is_mentor = "Наставник" in role_names
    is_recruiter = "Рекрутер" in role_names
    is_trainee = "Стажер" in role_names
    is_employee = "Сотрудник" in role_names
    
    # Проверяем роль пользователя для определения интерфейса
    # ПРИОРИТЕТ 1: Если пользователь из "Мои тесты 📋" (context == 'taking') и имеет доступ,
    # показываем интерфейс ПРОХОЖДЕНИЯ для ВСЕХ ролей (стажер, сотрудник, наставник, рекрутер, руководитель)
    if context == 'taking' and has_access:
        # УНИВЕРСАЛЬНО: Любая роль из "Мои тесты 📋" с доступом к тесту
        existing_result = await get_user_test_result(session, user.id, test_id)
        
        test_info_for_user = f"""📌 <b>{test.name}</b>

<b>Порог:</b> {test.threshold_score:.1f}/{test.max_score:.1f} б.

{test.description or 'Описание отсутствует'}

Если есть сомнения по теме, сначала прочти прикреплённые обучающие материалы, а потом переходи к тесту"""
        
        await callback.message.edit_text(
            test_info_for_user,
            parse_mode="HTML",
            reply_markup=get_test_start_keyboard(test_id, bool(existing_result))
        )
        
        # Устанавливаем состояние для корректной работы кнопки "Начать тест"
        await state.update_data(selected_test_id=test_id)
        await state.set_state(TestTakingStates.waiting_for_test_start)
    elif is_mentor and context != 'taking':
        # ПРИОРИТЕТ 2: Наставник из меню "Тесты стажеров" - показываем интерфейс УПРАВЛЕНИЯ
        can_edit = await check_user_permission(session, user.id, "edit_tests")
        user_role = "creator" if can_edit else "mentor"
        
        await callback.message.edit_text(
            test_info,
            parse_mode="HTML",
            reply_markup=get_test_actions_keyboard(test_id, user_role)
        )
        await callback.answer()
    elif is_recruiter:
        # ПРИОРИТЕТ 3: Рекрутер из меню "Тесты 📄" - показываем интерфейс УПРАВЛЕНИЯ
        can_edit = await check_user_permission(session, user.id, "edit_tests")
        user_role = "creator" if can_edit else "mentor"
        
        await callback.message.edit_text(
            test_info,
            parse_mode="HTML",
            reply_markup=get_test_actions_keyboard(test_id, user_role)
        )
        await callback.answer()
    else:
        # ПРИОРИТЕТ 4: Остальные случаи - показываем меню УПРАВЛЕНИЯ
        can_edit = await check_user_permission(session, user.id, "edit_tests")
        user_role = "creator" if can_edit else "mentor"
        
        await callback.message.edit_text(
            test_info,
            parse_mode="HTML",
            reply_markup=get_test_actions_keyboard(test_id, user_role)
        )
        await callback.answer()
    
    log_user_action(
        callback.from_user.id, 
        callback.from_user.username, 
        "viewed test details", 
        {"test_id": test_id}
    )

@router.callback_query(F.data.startswith("grant_access_to_test:"))
async def process_grant_access_to_test(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Обработчик предоставления доступа к тесту стажерам"""
    test_id = int(callback.data.split(':')[1])
    
    user = await get_user_by_tg_id(session, callback.from_user.id)
    if not user:
        await callback.message.answer("❌ Пользователь не найден.")
        await callback.answer()
        return
    
    # КРИТИЧЕСКАЯ ПРОВЕРКА ПРАВ!
    has_permission = await check_user_permission(session, user.id, "grant_test_access")
    if not has_permission:
        await callback.message.edit_text(
            "❌ <b>Недостаточно прав</b>\n\n"
            "У тебя нет прав для предоставления доступа к тестам.\n"
            "Обратитесь к администратору.",
            parse_mode="HTML"
        )
        await callback.answer()
        return
    
    # Проверяем, является ли пользователь наставником
    trainees = await get_mentor_trainees(session, user.id)
    
    if not trainees:
        await callback.message.edit_text(
            "❌ <b>Нет стажеров</b>\n\n"
            "У тебя нет назначенных стажеров.\n"
            "Обратись к рекрутеру для назначения стажеров.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ Назад к тесту", callback_data=f"test:{test_id}")],
                [InlineKeyboardButton(text="📋 К списку тестов", callback_data="back_to_tests")]
            ])
        )
        await callback.answer()
        return
    
    test = await get_test_by_id(session, test_id)
    if not test:
        await callback.message.answer("❌ Тест не найден.")
        await callback.answer()
        return
    
    # Создаем кнопки для выбора стажеров
    keyboard = []
    for trainee in trainees:
        keyboard.append([InlineKeyboardButton(
            text=f"👤 {trainee.full_name}",
            callback_data=f"grant_to_trainee:{test_id}:{trainee.id}"
        )])
    
    keyboard.append([InlineKeyboardButton(text="⬅️ Назад к тесту", callback_data=f"test:{test_id}")])
    
    await callback.message.edit_text(
        f"🔐 <b>Предоставление доступа к тесту</b>\n\n"
        f"👤 <b>Тест:</b> {test.name}\n"
        f"👥 <b>Твои стажеры:</b> {len(trainees)}\n\n"
        "Выбери стажера, которому хочешь предоставить доступ к этому тесту:",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
    )
    
    await callback.answer()

@router.callback_query(F.data.startswith("grant_to_trainee:"))
async def process_grant_to_trainee(callback: CallbackQuery, state: FSMContext, session: AsyncSession, bot):
    """Обработчик предоставления доступа конкретному стажеру"""
    parts = callback.data.split(':')
    test_id = int(parts[1])
    trainee_id = int(parts[2])
    
    user = await get_user_by_tg_id(session, callback.from_user.id)
    test = await get_test_by_id(session, test_id)
    trainee = await get_user_by_id(session, trainee_id)
    
    if not all([user, test, trainee]):
        await callback.message.answer("❌ Данные не найдены.")
        await callback.answer()
        return
    
    # Предоставляем доступ с отправкой уведомления
    success = await grant_test_access(session, trainee_id, test_id, user.id, bot)
    
    if success:
        await callback.message.edit_text(
            f"✅ <b>Доступ предоставлен!</b>\n\n"
            f"👤 <b>Стажер:</b> {trainee.full_name}\n"
            f"📋 <b>Тест:</b> {test.name}\n"
            f"🎯 <b>Проходной балл:</b> {test.threshold_score:.1f}/{test.max_score:.1f}\n\n"
            f"📬 <b>Уведомление отправлено!</b>\n"
            f"Стажер {trainee.full_name} получил уведомление о новом тесте в личном кабинете.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔐 Предоставить доступ другому стажеру", callback_data=f"grant_access_to_test:{test_id}")],
                [InlineKeyboardButton(text="⬅️ Назад к тесту", callback_data=f"test:{test_id}")],
                [InlineKeyboardButton(text="📋 К списку тестов", callback_data="back_to_tests")]
            ])
        )
        
        log_user_action(
            callback.from_user.id, 
            callback.from_user.username, 
            "granted test access", 
            {"test_id": test_id, "trainee_id": trainee_id}
        )
    else:
        await callback.message.edit_text(
            f"ℹ️ <b>Доступ уже был предоставлен</b>\n\n"
            f"👤 <b>Стажер:</b> {trainee.full_name}\n"
            f"📋 <b>Тест:</b> {test.name}\n\n"
            f"Этот стажер уже имеет доступ к данному тесту.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔐 Предоставить доступ другому стажеру", callback_data=f"grant_access_to_test:{test_id}")],
                [InlineKeyboardButton(text="⬅️ Назад к тесту", callback_data=f"test:{test_id}")]
            ])
        )
    
    await callback.answer()

@router.callback_query(F.data.startswith("edit_test:"))
async def process_edit_test_menu(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Показывает меню редактирования теста"""
    parts = callback.data.split(':')
    test_id = int(parts[1])
    
    # Проверяем, есть ли session_id в callback_data (открытие из редактора траекторий)
    session_id = None
    if len(parts) > 2:
        try:
            session_id = int(parts[2])
            # Сохраняем session_id в state для возврата назад
            await state.update_data(editor_session_id=session_id)
        except (ValueError, IndexError):
            pass
    
    test = await get_test_by_id(session, test_id)
    if not test:
        await callback.answer("❌ Тест не найден.", show_alert=True)
        return
    
    # КРИТИЧЕСКАЯ ПРОВЕРКА ПРАВ!
    user = await get_user_by_tg_id(session, callback.from_user.id)
    if not user:
        await callback.answer("❌ Пользователь не найден.", show_alert=True)
        return
        
    has_permission = await check_user_permission(session, user.id, "edit_tests")
    if not has_permission:
        await callback.message.edit_text(
            "❌ <b>Недостаточно прав</b>\n\n"
            "У тебя нет прав для редактирования тестов.\n"
            "Обратитесь к администратору.",
            parse_mode="HTML"
        )
        await callback.answer()
        return

    await callback.message.edit_text(
        f"✏️ <b>Редактирование теста: «{test.name}»</b>\n\n"
        "Выбери, что ты хочешь изменить:",
        parse_mode="HTML",
        reply_markup=get_test_edit_menu(test_id, session_id=session_id)
    )
    await callback.answer()

def _get_edit_test_callback(test_id: int, session_id: int = None) -> str:
    """Вспомогательная функция для создания callback возврата к редактированию теста"""
    if session_id:
        return f"edit_test:{test_id}:{session_id}"
    return f"edit_test:{test_id}"

@router.callback_query(F.data.startswith("edit_test_meta:"))
async def process_edit_test_meta(callback: CallbackQuery, state: FSMContext):
    """Запрашивает новое название теста"""
    test_id = int(callback.data.split(':')[1])
    await state.update_data(test_id_to_edit=test_id)
    
    # Получаем session_id из state, если тест открыт из редактора траекторий
    data = await state.get_data()
    session_id = data.get('editor_session_id')
    
    await callback.message.edit_text(
        "Введи новое <b>название</b> теста:",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Назад", callback_data=_get_edit_test_callback(test_id, session_id))]
        ])
    )
    await state.set_state(TestCreationStates.waiting_for_new_test_name)
    await callback.answer()

@router.message(TestCreationStates.waiting_for_new_test_name)
async def process_new_test_name(message: Message, state: FSMContext):
    """Обрабатывает новое название и запрашивает описание"""
    await state.update_data(new_test_name=message.text.strip())
    await message.answer(
        "✅ Название обновлено. Теперь введи новое <b>описание</b> или нажми кнопку 'Пропустить':",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⏭️ Пропустить", callback_data="edit_description:skip")]
        ])
    )
    await state.set_state(TestCreationStates.waiting_for_new_test_description)

@router.callback_query(TestCreationStates.waiting_for_new_test_description, F.data == "edit_description:skip")
async def process_skip_edit_description(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Обработка пропуска описания при редактировании"""
    data = await state.get_data()
    test_id = data['test_id_to_edit']
    
    update_data = {
        "name": data['new_test_name'],
        "description": None
    }
    
    await update_test(session, test_id, update_data)
    
    test = await get_test_by_id(session, test_id)
    # Получаем session_id из state перед очисткой
    data = await state.get_data()
    session_id = data.get('editor_session_id')
    await state.clear()
    # Восстанавливаем session_id после очистки, если был
    if session_id:
        await state.update_data(editor_session_id=session_id)
    
    await callback.message.edit_text(
        f"✅ Название теста <b>«{test.name}»</b> успешно обновлено. Описание удалено.",
        parse_mode="HTML",
        reply_markup=get_test_edit_menu(test_id, session_id=session_id)
    )
    await callback.answer()

@router.message(TestCreationStates.waiting_for_new_test_description)
async def process_new_test_description(message: Message, state: FSMContext, session: AsyncSession):
    """Обновляет метаданные теста"""
    data = await state.get_data()
    test_id = data['test_id_to_edit']
    description = None if message.text.lower() == 'пропустить' else message.text.strip()
    
    update_data = {
        "name": data['new_test_name'],
        "description": description
    }
    
    await update_test(session, test_id, update_data)
    
    test = await get_test_by_id(session, test_id)
    # Получаем session_id из state перед очисткой
    data = await state.get_data()
    session_id = data.get('editor_session_id')
    await state.clear()
    # Восстанавливаем session_id после очистки, если был
    if session_id:
        await state.update_data(editor_session_id=session_id)
    
    await message.answer(
        f"✅ Название и описание теста <b>«{test.name}»</b> успешно обновлены.",
        parse_mode="HTML",
        reply_markup=get_test_edit_menu(test_id, session_id=session_id)
    )


@router.callback_query(F.data.startswith("edit_test_threshold:"))
async def process_edit_threshold(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Запрашивает новый проходной балл"""
    test_id = int(callback.data.split(':')[1])
    test = await get_test_by_id(session, test_id)
    if not test:
        await callback.answer("❌ Тест не найден.", show_alert=True)
        return
        
    await state.update_data(test_id_to_edit=test_id)
    
    # Получаем session_id из state, если тест открыт из редактора траекторий
    data = await state.get_data()
    session_id = data.get('editor_session_id')
    
    await callback.message.edit_text(
        f"Текущий проходной балл: <b>{test.threshold_score:.1f}</b> из <b>{test.max_score:.1f}</b>.\n\n"
        f"Введи новый проходной балл (от 0.5 до {test.max_score:.1f}):",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Назад", callback_data=_get_edit_test_callback(test_id, session_id))]
        ])
    )
    await state.set_state(TestCreationStates.waiting_for_new_threshold)
    await callback.answer()

@router.message(TestCreationStates.waiting_for_new_threshold)
async def process_new_threshold(message: Message, state: FSMContext, session: AsyncSession):
    """Обновляет проходной балл"""
    data = await state.get_data()
    test_id = data['test_id_to_edit']
    test = await get_test_by_id(session, test_id)
    
    try:
        new_threshold = float(message.text.replace(',', '.').strip())
        if not (0 < new_threshold <= test.max_score):
            await message.answer(f"❌ Балл должен быть между 0 и {test.max_score:.1f}. Попробуй снова.")
            return
    except ValueError:
        await message.answer("❌ Пожалуйста, введи число.")
        return
        
    await update_test(session, test_id, {"threshold_score": new_threshold})
    
    # Получаем session_id из state перед очисткой
    data = await state.get_data()
    session_id = data.get('editor_session_id')
    await state.clear()
    # Восстанавливаем session_id после очистки, если был
    if session_id:
        await state.update_data(editor_session_id=session_id)
    
    await message.answer(
        f"✅ Проходной балл для теста <b>«{test.name}»</b> обновлен на <b>{new_threshold:.1f}</b>.",
        parse_mode="HTML",
        reply_markup=get_test_edit_menu(test_id, session_id=session_id)
    )


async def _show_questions_list(message, state: FSMContext, session: AsyncSession, test_id: int):
    """Внутренняя функция для отображения списка вопросов"""
    # Получаем session_id из state, если тест открыт из редактора траекторий
    data = await state.get_data()
    session_id = data.get('editor_session_id')
    
    questions = await get_test_questions(session, test_id)
    
    if not questions:
        text = "В этом тесте пока нет вопросов. Ты можешь добавить их."
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="➕ Добавить вопрос", callback_data=f"add_q_to_test:{test_id}")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data=_get_edit_test_callback(test_id, session_id))]
        ])
        
        # Пытаемся отредактировать сообщение, если не получается - отправляем новое
        try:
            await message.edit_text(text, reply_markup=keyboard)
        except Exception:
            await message.answer(text, reply_markup=keyboard)
        return
    
    text = "Выбери вопрос для редактирования или удаления:\n\n"
    buttons = []
    for q in questions:
        text += f"<b>{q.question_number}.</b> {q.question_text[:50]}... ({q.points:.1f} б.)\n"
        buttons.append([InlineKeyboardButton(
            text=f"Вопрос {q.question_number}",
            callback_data=f"select_question_for_edit:{q.id}"
        )])
        
    buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data=_get_edit_test_callback(test_id, session_id))])

    # Пытаемся отредактировать сообщение, если не получается - отправляем новое
    try:
        await message.edit_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
    except Exception:
        await message.answer(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))


@router.callback_query(F.data.startswith("edit_test_questions:"))
async def process_manage_questions(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Показывает список вопросов для управления"""
    test_id = int(callback.data.split(':')[1])
    await _show_questions_list(callback.message, state, session, test_id)
    await callback.answer()


async def _show_question_edit_menu(message, state: FSMContext, session: AsyncSession, question_id: int):
    """Внутренняя функция для отображения меню редактирования вопроса"""
    question = await session.get(TestQuestion, question_id)
    if not question:
        # Пытаемся отправить сообщение об ошибке
        try:
            await message.answer("❌ Вопрос не найден.")
        except Exception:
            pass
        return False
        
    await state.update_data(question_id_to_edit=question_id, test_id_to_edit=question.test_id)
    
    # Определяем, первый ли и последний ли это вопрос
    questions = await get_test_questions(session, question.test_id)
    is_first = question.question_number == 1
    is_last = question.question_number == len(questions)

    options_text = ""
    if question.options:
        options_text = "\n".join([f"  - {opt}" for opt in question.options])
        options_text = f"\n<b>Варианты:</b>\n{options_text}"

    text = (
        f"<b>Вопрос {question.question_number}:</b> {question.question_text}\n"
        f"<b>Тип:</b> {question.question_type}\n"
        f"{options_text}\n"
        f"<b>Ответ:</b> {question.correct_answer}\n"
        f"<b>Баллы:</b> {question.points:.1f}\n\n"
        "Выбери действие:"
    )

    try:
        await message.edit_text(
            text,
            parse_mode="HTML",
            reply_markup=get_question_management_keyboard(question_id, is_first, is_last)
        )
    except Exception:
        await message.answer(
            text,
            parse_mode="HTML",
            reply_markup=get_question_management_keyboard(question_id, is_first, is_last)
        )
    
    await state.set_state(TestCreationStates.waiting_for_question_action)
    return True


@router.callback_query(F.data.startswith("select_question_for_edit:"))
async def select_question_for_edit(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Показывает меню действий для выбранного вопроса"""
    question_id = int(callback.data.split(':')[1])
    await _show_question_edit_menu(callback.message, state, session, question_id)
    await callback.answer()


@router.callback_query(F.data.startswith("move_q_"))
async def move_question(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Перемещает вопрос вверх или вниз"""
    direction = callback.data.split(':')[0].split('_')[2]
    question_id = int(callback.data.split(':')[1])
    
    question = await session.get(TestQuestion, question_id)
    if not question:
        await callback.answer("❌ Вопрос не найден.", show_alert=True)
        return
        
    test_id = question.test_id
    questions = await get_test_questions(session, test_id)
    
    # Находим индекс вопроса
    current_index = -1
    for i, q in enumerate(questions):
        if q.id == question_id:
            current_index = i
            break
            
    if direction == "up" and current_index > 0:
        questions[current_index], questions[current_index - 1] = questions[current_index - 1], questions[current_index]
    elif direction == "down" and current_index < len(questions) - 1:
        questions[current_index], questions[current_index + 1] = questions[current_index + 1], questions[current_index]
        
    # Обновляем нумерацию
    for i, q in enumerate(questions):
        q.question_number = i + 1
        
    # Обновляем список вопросов
    await _show_questions_list(callback.message, state, session, test_id)
    await callback.answer("Порядок вопросов изменен")


@router.callback_query(F.data.startswith("q_stats:"))
async def question_statistics(callback: CallbackQuery, session: AsyncSession):
    """Показывает статистику по вопросу"""
    question_id = int(callback.data.split(':')[1])
    question = await session.get(TestQuestion, question_id)
    if not question:
        await callback.answer("❌ Вопрос не найден.", show_alert=True)
        return

    stats = await get_question_analytics(session, question_id)
    
    total = stats.get("total_answers", 0)
    correct = stats.get("correct_answers", 0)
    success_rate = (correct / total * 100) if total > 0 else 0
    
    # Получаем информацию о тесте для контекста
    test = await get_test_by_id(session, question.test_id)
    test_name = test.name if test else "Неизвестный тест"
    
    if total == 0:
        # Если нет данных - показываем это явно
        stats_text = f"""📊 <b>Статистика по вопросу №{question.question_number}</b>

🧪 <b>Тест:</b> {test_name}
📝 <b>Текст вопроса:</b> {question.question_text[:100]}{'...' if len(question.question_text) > 100 else ''}

📈 <b>Текущие показатели:</b>
 📊 Всего ответов: <b>0</b>
 ✅ Правильных ответов: <b>0</b>
 📈 Процент успеха: <b>0%</b>
 ⏱️ Среднее время: <b>нет данных</b>

💡 <b>Статус:</b> Данные отсутствуют
ℹ️ <i>Статистика появится после того, как стажеры начнут проходить этот тест и отвечать на данный вопрос.</i>"""
    else:
        # Если есть данные - показываем полную статистику
        stats_text = f"""📊 <b>Статистика по вопросу №{question.question_number}</b>

🧪 <b>Тест:</b> {test_name}
📝 <b>Текст вопроса:</b> {question.question_text[:100]}{'...' if len(question.question_text) > 100 else ''}

📈 <b>Показатели эффективности:</b>
 📊 Всего ответов: <b>{total}</b>
 ✅ Правильных ответов: <b>{correct}</b> ({success_rate:.1f}%)
 ❌ Неправильных ответов: <b>{total - correct}</b>
 ⏱️ Среднее время на ответ: <b>{stats.get("avg_time_seconds", 0):.1f}</b> сек.

💡 <b>Анализ сложности:</b>
{'🟢 Легкий вопрос' if success_rate >= 80 else '🟡 Средний вопрос' if success_rate >= 60 else '🔴 Сложный вопрос'}"""

    await callback.message.edit_text(
        stats_text,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Назад к вопросу", callback_data=f"select_question_for_edit:{question_id}")]
        ])
    )
    await callback.answer()


@router.callback_query(F.data.startswith("edit_q_text:"))
async def process_edit_question_text(callback: CallbackQuery, state: FSMContext):
    """Запрашивает новый текст вопроса"""
    question_id = int(callback.data.split(':')[1])
    await callback.message.edit_text(
        "Введи новый текст вопроса:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Назад", callback_data=f"select_question_for_edit:{question_id}")]
        ])
    )
    await state.set_state(TestCreationStates.waiting_for_question_edit)
    await callback.answer()

@router.message(TestCreationStates.waiting_for_question_edit)
async def save_new_question_text(message: Message, state: FSMContext, session: AsyncSession):
    """Сохраняет новый текст вопроса"""
    data = await state.get_data()
    question_id = data['question_id_to_edit']
    await update_question(session, question_id, {"question_text": message.text.strip()})
    
    await message.answer("✅ Текст вопроса обновлен.")
    # Возвращаемся к меню редактирования вопроса
    await _show_question_edit_menu(message, state, session, question_id)


@router.callback_query(F.data.startswith("edit_q_answer:"))
async def process_edit_question_answer(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Запрашивает новый ответ в зависимости от типа вопроса"""
    question_id = int(callback.data.split(':')[1])
    await state.update_data(question_id_to_edit=question_id)
    question = await session.get(TestQuestion, question_id)

    if not question:
        await callback.answer("❌ Вопрос не найден.", show_alert=True)
        return

    back_button = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Назад", callback_data=f"select_question_for_edit:{question_id}")]
    ])

    if question.question_type in ['text', 'number']:
        await callback.message.edit_text(
            "Введи новый <b>правильный ответ</b>:",
            parse_mode="HTML",
            reply_markup=back_button
        )
        await state.set_state(TestCreationStates.waiting_for_answer_edit)
    elif question.question_type in ['single_choice', 'multiple_choice', 'yes_no']:
        options_text = "\n".join([f"{i+1}. {opt}" for i, opt in enumerate(question.options)])
        prompt = "Введи **номер** нового правильного ответа:"
        if question.question_type == 'multiple_choice':
            prompt = "Введи **номера** новых правильных ответов через запятую (напр: 1, 3):"
        
        await callback.message.edit_text(
            f"Текущие варианты:\n{options_text}\n\n{prompt}",
            parse_mode="HTML",
            reply_markup=back_button
        )
        await state.set_state(TestCreationStates.waiting_for_answer_edit)

    await callback.answer()


@router.message(TestCreationStates.waiting_for_answer_edit)
async def save_new_question_answer(message: Message, state: FSMContext, session: AsyncSession):
    """Сохраняет новый ответ на вопрос"""
    data = await state.get_data()
    question_id = data['question_id_to_edit']
    question = await session.get(TestQuestion, question_id)
    new_answer = message.text.strip()

    if question.question_type == 'multiple_choice':
        try:
            indices = [int(i.strip()) - 1 for i in new_answer.split(',')]
            options = question.options
            correct_answers = [options[i] for i in indices if 0 <= i < len(options)]
            if not correct_answers: raise ValueError
            new_answer = json.dumps(correct_answers)
        except (ValueError, IndexError):
            await message.answer("❌ Некорректный формат. Введи номера через запятую (например: 1, 3):")
            return
    elif question.question_type == 'single_choice':
        try:
            index = int(new_answer) - 1
            if not (0 <= index < len(question.options)): raise ValueError
            new_answer = question.options[index]
        except (ValueError, IndexError):
            await message.answer(f"❌ Введи номер от 1 до {len(question.options)}.")
            return

    await update_question(session, question_id, {"correct_answer": new_answer})
    
    await message.answer("✅ Ответ на вопрос обновлен.")
    await _show_question_edit_menu(message, state, session, question_id)


@router.callback_query(F.data.startswith("edit_q_points:"))
async def process_edit_question_points(callback: CallbackQuery, state: FSMContext):
    """Запрашивает новое количество баллов за вопрос"""
    question_id = int(callback.data.split(':')[1])
    await callback.message.edit_text(
        "Введи новое количество <b>баллов</b> за правильный ответ (можно дробное).\n\n"
        "Для установки штрафа, введи отрицательное число, например: <code>-0.5</code>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Назад", callback_data=f"select_question_for_edit:{question_id}")]
        ])
    )
    await state.set_state(TestCreationStates.waiting_for_points_edit)
    await callback.answer()

@router.message(TestCreationStates.waiting_for_points_edit)
async def save_new_question_points(message: Message, state: FSMContext, session: AsyncSession):
    """Сохраняет новое количество баллов"""
    data = await state.get_data()
    question_id = data['question_id_to_edit']
    
    try:
        points = float(message.text.replace(',', '.').strip())
        if points == 0:
            await message.answer("❌ Количество баллов не может быть равно нулю. Попробуй еще раз:")
            return
            
        penalty = 0
        if points < 0:
            penalty = abs(points)
            points = 0
            
    except ValueError:
        await message.answer("❌ Пожалуйста, введи число.")
        return

    await update_question(session, question_id, {"points": points, "penalty_points": penalty})
    
    await message.answer("✅ Количество баллов обновлено. Максимальный балл за тест был автоматически пересчитан.")
    await _show_question_edit_menu(message, state, session, question_id)


@router.callback_query(F.data.startswith("delete_q:"))
async def process_delete_question(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Удаляет вопрос"""
    question_id = int(callback.data.split(':')[1])
    
    question = await session.get(TestQuestion, question_id)
    if not question:
        await callback.answer("❌ Вопрос не найден.", show_alert=True)
        return

    test_id = question.test_id
    await delete_question(session, question_id)
    
    await callback.message.edit_text(
        f"✅ Вопрос №{question.question_number} был успешно удален.\n"
        "Максимальный балл за тест был автоматически пересчитан.",
        parse_mode="HTML"
    )
    
    # Возвращаемся к списку вопросов
    await _show_questions_list(callback.message, state, session, test_id)
    await callback.answer()


@router.callback_query(F.data == "back_to_q_list")
async def back_to_question_list(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Возврат к списку вопросов"""
    data = await state.get_data()
    test_id = data['test_id_to_edit']
    await _show_questions_list(callback.message, state, session, test_id)
    await callback.answer()


@router.callback_query(F.data.startswith("test_results:"))
async def process_test_results(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Обработчик просмотра результатов теста"""
    test_id = int(callback.data.split(':')[1])
    
    test = await get_test_by_id(session, test_id)
    
    if not test:
        await callback.message.answer("❌ Тест не найден.")
        await callback.answer()
        return
    
    results = await get_test_results_summary(session, test_id)
    
    if not results:
        await callback.message.edit_text(
            f"📊 <b>Результаты теста:</b> {test.name}\n\n"
            "📋 Пока никто не проходил этот тест.\n"
            "Результаты появятся после того, как стажеры начнут проходить тест.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ Назад к тесту", callback_data=f"test:{test_id}")],
                [InlineKeyboardButton(text="📋 К списку тестов", callback_data="back_to_tests")]
            ])
        )
    else:
        # Формируем статистику
        total_attempts = len(results)
        passed_count = sum(1 for r in results if r.is_passed)
        average_score = sum(r.score for r in results) / total_attempts
        
        results_text = f"""📊 <b>Результаты теста:</b> {test.name}

📈 <b>Общая статистика:</b>
• Всего попыток: {total_attempts}
• Успешно прошли: {passed_count} ({passed_count/total_attempts*100:.1f}%)
• Средний балл: {average_score:.1f}

📋 <b>Последние результаты:</b>"""
        
        # Показываем последние 5 результатов
        for i, result in enumerate(results[:5]):
            user = await get_user_by_id(session, result.user_id)
            status = "✅" if result.is_passed else "❌"
            results_text += f"\n{status} {user.full_name if user else 'Неизвестен'}: {result.score:.1f}/{result.max_possible_score:.1f} б."
        
        if total_attempts > 5:
            results_text += f"\n... и еще {total_attempts - 5} результатов"
        
        await callback.message.edit_text(
            results_text,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ Назад к тесту", callback_data=f"test:{test_id}")],
                [InlineKeyboardButton(text="📋 К списку тестов", callback_data="back_to_tests")]
            ])
        )
    
    await callback.answer()

@router.callback_query(F.data.startswith("delete_test:"))
async def process_delete_test(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Обработчик удаления теста"""
    test_id = int(callback.data.split(':')[1])
    
    test = await get_test_by_id(session, test_id)
    
    if not test:
        await callback.message.answer("❌ Тест не найден.")
        await callback.answer()
        return
    
    # КРИТИЧЕСКАЯ ПРОВЕРКА ПРАВ!
    user = await get_user_by_tg_id(session, callback.from_user.id)
    if not user:
        await callback.answer("❌ Пользователь не найден.", show_alert=True)
        return
        
    has_permission = await check_user_permission(session, user.id, "edit_tests")
    if not has_permission:
        await callback.message.edit_text(
            "❌ <b>Недостаточно прав</b>\n\n"
            "У тебя нет прав для удаления тестов.\n"
            "Обратитесь к администратору.",
            parse_mode="HTML"
        )
        await callback.answer()
        return
    
    await callback.message.edit_text(
        f"🗑️ <b>Удаление теста</b>\n\n"
        f"Ты действительно хочешь удалить тест <b>«{test.name}»</b>?\n\n"
        "⚠️ <b>Внимание:</b> Это действие нельзя отменить!",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Да, удалить", callback_data=f"confirm_delete_test:{test_id}")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data=f"test:{test_id}")]
        ])
    )
    
    await callback.answer()

@router.callback_query(F.data.startswith("confirm_delete_test:"))
async def process_confirm_delete_test(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Подтверждение удаления теста"""
    test_id = int(callback.data.split(':')[1])
    
    test = await get_test_by_id(session, test_id)
    
    if not test:
        await callback.message.answer("❌ Тест не найден.")
        await callback.answer()
        return
    
    # КРИТИЧЕСКАЯ ПРОВЕРКА ПРАВ!
    user = await get_user_by_tg_id(session, callback.from_user.id)
    if not user:
        await callback.answer("❌ Пользователь не найден.", show_alert=True)
        return
        
    has_permission = await check_user_permission(session, user.id, "edit_tests")
    if not has_permission:
        await callback.message.edit_text(
            "❌ <b>Недостаточно прав</b>\n\n"
            "У тебя нет прав для удаления тестов.\n"
            "Обратитесь к администратору.",
            parse_mode="HTML"
        )
        await callback.answer()
        return
    
    success = await delete_test(session, test_id)
    
    if success:
        await callback.message.edit_text(
            f"✅ <b>Тест удален</b>\n\n"
            f"Тест <b>«{test.name}»</b> успешно удален из системы.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📋 К списку тестов", callback_data="back_to_tests")]
            ])
        )
        
        log_user_action(
            callback.from_user.id, 
            callback.from_user.username, 
            "deleted test", 
            {"test_id": test_id, "test_name": test.name}
        )
    else:
        await callback.message.edit_text(
            "❌ <b>Ошибка удаления</b>\n\n"
            "Произошла ошибка при удалении теста. Попробуй еще раз позже.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ Назад к тесту", callback_data=f"test:{test_id}")]
            ])
        )
    
    await callback.answer()

@router.callback_query(F.data.startswith("test_filter:"))
async def process_test_filter(callback: CallbackQuery, session: AsyncSession):
    """Обработчик выбора фильтра тестов"""
    filter_type = callback.data.split(':')[1]
    
    # Пропускаем broadcast - он обрабатывается в broadcast.py
    if filter_type == "broadcast":
        return
    
    user = await get_user_by_tg_id(session, callback.from_user.id)
    if not user:
        await callback.answer("❌ Пользователь не найден.", show_alert=True)
        return

    if filter_type == "my":
        tests = await get_tests_by_creator(session, user.id)
        list_title = "📋 <b>Список твоих тестов</b>"
        empty_message = "У тебя пока нет созданных тестов."
    else:  # all
        tests = await get_all_active_tests(session)
        list_title = "📋 <b>Список всех тестов в системе</b>"
        empty_message = "В системе пока нет созданных тестов."

    if not tests:
        await callback.message.edit_text(
            f"{list_title}\n\n{empty_message}",
            parse_mode="HTML",
            reply_markup=get_test_filter_keyboard()
        )
    else:
        tests_list = "\n\n".join([
            f"<b>{i+1}. {test.name}</b>\n"
            f"   🎯 Порог: {test.threshold_score:.1f}/{test.max_score:.1f} б.\n"
            f"   📅 Создан: {test.created_date.strftime('%d.%m.%Y')}\n"
            f"   👤 Создатель: {await get_creator_name(session, test.creator_id)}"
            for i, test in enumerate(tests)
        ])
        
        await callback.message.edit_text(
            f"{list_title}\n\n{tests_list}\n\n"
            f"Выбери тест для редактирования и управления:",
            parse_mode="HTML",
            reply_markup=get_simple_test_selection_keyboard(tests)
        )
    await callback.answer()

@router.callback_query(F.data == "back_to_tests")
async def process_back_to_tests(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Возврат к списку тестов (или к выбору фильтра)"""
    user = await get_user_by_tg_id(session, callback.from_user.id)
    if not user:
        await callback.answer("❌ Пользователь не найден.", show_alert=True)
        return

    # Рекрутеры/управляющие (с правом create_tests) возвращаются к выбору фильтра
    if await check_user_permission(session, user.id, "create_tests"):
        await callback.message.edit_text(
            "🗂️ Выбери, какие тесты ты хочешь просмотреть:",
            reply_markup=get_test_filter_keyboard()
        )
    # Наставники (без права create_tests) возвращаются к списку всех тестов
    else:
        tests = await get_all_active_tests(session)
        if not tests:
            await callback.message.edit_text(
                "📋 <b>Список доступных тестов</b>\n\n"
                "В системе пока нет созданных тестов.\nОбратись к рекрутеру для создания тестов.",
                parse_mode="HTML"
            )
        else:
            tests_list = "\n\n".join([
                f"<b>{i+1}. {test.name}</b>\n"
                f"   🎯 Порог: {test.threshold_score:.1f}/{test.max_score:.1f} б.\n"
                f"   📅 Создан: {test.created_date.strftime('%d.%m.%Y')}\n"
                f"   👤 Создатель: {await get_creator_name(session, test.creator_id)}"
                for i, test in enumerate(tests)
            ])
            await callback.message.edit_text(
                f"📋 <b>Список доступных тестов</b>\n\n{tests_list}\n\n"
                f"Выбери тест для просмотра и предоставления доступа:",
                parse_mode="HTML",
                reply_markup=get_simple_test_selection_keyboard(tests)
            )
    await callback.answer()

# Обработка отмены операций
@router.callback_query(F.data.startswith("materials:no"))
async def process_no_materials(callback: CallbackQuery, state: FSMContext):
    """Обработка отказа от материалов"""
    await state.update_data(material_link=None)
    await ask_for_description(callback.message, state)
    await callback.answer()

@router.callback_query(F.data == "cancel")
async def process_cancel_test_creation(callback: CallbackQuery, state: FSMContext):
    """Отмена создания теста"""
    await callback.message.edit_text("❌ Создание теста отменено.")
    await state.clear()
    await callback.answer()

@router.callback_query(F.data.startswith("edit_test_stage:"))
async def process_edit_test_stage(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Показывает список этапов для выбора"""
    test_id = int(callback.data.split(':')[1])
    stages = await get_all_stages(session)
    if not stages:
        await callback.answer("❌ В системе не созданы этапы стажировки.", show_alert=True)
        return

    await state.update_data(test_id_to_edit=test_id)
    await callback.message.edit_text(
        "Выбери новый этап для этого теста:",
        reply_markup=get_stage_selection_keyboard(stages)
    )
    await state.set_state(TestCreationStates.waiting_for_new_stage)
    await callback.answer()

@router.callback_query(TestCreationStates.waiting_for_new_stage, F.data.startswith("stage:"))
async def save_new_test_stage(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Сохраняет новый этап для теста"""
    stage_id_str = callback.data.split(':')[1]
    stage_id = int(stage_id_str) if stage_id_str != 'none' else None
    
    data = await state.get_data()
    test_id = data['test_id_to_edit']
    session_id = data.get('editor_session_id')  # Получаем session_id из state
    
    await update_test(session, test_id, {"stage_id": stage_id})
    
    test = await get_test_by_id(session, test_id)
    stage_name = (await session.get(InternshipStage, stage_id)).name if stage_id else "не назначен"

    await callback.message.edit_text(
        f"✅ Этап для теста <b>«{test.name}»</b> обновлен на <b>«{stage_name}»</b>.",
        parse_mode="HTML",
        reply_markup=get_test_edit_menu(test_id, session_id=session_id)
    )
    # Восстанавливаем session_id после очистки, если был
    await state.clear()
    if session_id:
        await state.update_data(editor_session_id=session_id)
    await callback.answer()

@router.callback_query(F.data.startswith("preview_test:"))
async def preview_test(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Предпросмотр теста"""
    test_id = int(callback.data.split(':')[1])
    
    # Получаем session_id из state, если тест открыт из редактора траекторий
    data = await state.get_data()
    session_id = data.get('editor_session_id')
    
    test = await get_test_by_id(session, test_id)
    questions = await get_test_questions(session, test_id)

    if not test:
        await callback.answer("❌ Тест не найден.", show_alert=True)
        return
    
    if not questions:
        await callback.message.edit_text(
            f"👁️ <b>Предпросмотр теста: «{test.name}»</b>\n\n"
            "📝 <b>Описание:</b> " + (test.description or "Не указано") + "\n"
            f"🎯 <b>Проходной балл:</b> {test.threshold_score:.1f} из {test.max_score:.1f} б.\n"
            f"🔗 <b>Материалы:</b> {'Есть' if test.material_link else 'Отсутствуют'}\n\n"
            "❓ <b>Вопросы:</b> Пока не добавлено ни одного вопроса.\n\n"
            "💡 Добавь вопросы через раздел «Управление вопросами», чтобы тест стал полноценным.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="➕ Добавить вопрос", callback_data=f"add_q_to_test:{test_id}")],
                [InlineKeyboardButton(text="⬅️ Назад к редактированию", callback_data=_get_edit_test_callback(test_id, session_id))]
            ])
        )
        await callback.answer()
        return

    preview_text = f"👁️ <b>Предпросмотр теста: «{test.name}»</b>\n\n"
    for q in questions:
        preview_text += f"<b>Вопрос {q.question_number} ({q.points:.1f} б. / штраф: {q.penalty_points:.1f} б.):</b> {q.question_text}\n"
        if q.options:
            for i, opt in enumerate(q.options):
                prefix = "✔️" if opt == q.correct_answer else "➖"
                preview_text += f"  {prefix} {opt}\n"
        else:
            preview_text += f"  <i>(Правильный ответ: {q.correct_answer})</i>\n"
        preview_text += "\n"

    await callback.message.edit_text(
        preview_text,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Назад к редактированию", callback_data=_get_edit_test_callback(test_id, session_id))]
        ])
    )
    await callback.answer()

@router.callback_query(F.data.startswith("edit_test_materials:"))
async def process_edit_test_materials(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Запрашивает новую ссылку на материалы"""
    test_id = int(callback.data.split(':')[1])
    
    # Получаем session_id из state, если тест открыт из редактора траекторий
    data = await state.get_data()
    session_id = data.get('editor_session_id')
    
    test = await get_test_by_id(session, test_id)
    if not test:
        await callback.answer("❌ Тест не найден.", show_alert=True)
        return
        
    await state.update_data(test_id_to_edit=test_id)
    
    await callback.message.edit_text(
        f"Текущие материалы: {test.material_link or 'не указаны'}\n\n"
        "📎 Отправь новую ссылку, документ, изображение или нажми кнопку 'Удалить'",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🗑️ Удалить материалы", callback_data="edit_materials:delete")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data=_get_edit_test_callback(test_id, session_id))]
        ])
    )
    await state.set_state(TestCreationStates.waiting_for_new_materials)
    await callback.answer()

@router.callback_query(TestCreationStates.waiting_for_new_materials, F.data == "edit_materials:delete")
async def process_delete_materials(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Обработка удаления материалов"""
    data = await state.get_data()
    test_id = data['test_id_to_edit']
    
    update_data = {
        "material_link": None,
        "material_file_path": None
    }
    
    await update_test(session, test_id, update_data)
    
    test = await get_test_by_id(session, test_id)
    # Получаем session_id из state перед очисткой
    data = await state.get_data()
    session_id = data.get('editor_session_id')
    await state.clear()
    # Восстанавливаем session_id после очистки, если был
    if session_id:
        await state.update_data(editor_session_id=session_id)
    
    await callback.message.edit_text(
        f"✅ Материалы для теста <b>«{test.name}»</b> удалены.",
        parse_mode="HTML",
        reply_markup=get_test_edit_menu(test_id, session_id=session_id)
    )
    await callback.answer()

@router.message(TestCreationStates.waiting_for_new_materials)
async def save_new_materials(message: Message, state: FSMContext, session: AsyncSession):
    """Сохраняет новую ссылку на материалы или документ"""
    data = await state.get_data()
    test_id = data['test_id_to_edit']
    
    update_data = {}
    
    if message.document:
        # Проверяем поддерживаемые типы
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
        
        if message.document.mime_type not in allowed_mimes:
            await message.answer(
                "❌ Неподдерживаемый формат файла."
            )
            return
        
        # Пользователь отправил документ
        file_info = f"Файл: {message.document.file_name}"
        update_data = {
            "material_link": file_info,
            "material_file_path": message.document.file_id,
            "material_type": "document"
        }
        await message.answer(f"✅ Документ '{message.document.file_name}' добавлен к тесту.")
    elif message.photo:
        # Пользователь отправил фото
        photo_file_id = message.photo[-1].file_id
        update_data = {
            "material_link": "Изображение",
            "material_file_path": photo_file_id,
            "material_type": "photo"
        }
        await message.answer("✅ Изображение добавлено к тесту.")
    elif message.video:
        # Пользователь отправил видео напрямую
        video_file_id = message.video.file_id
        update_data = {
            "material_link": "Видео",
            "material_file_path": video_file_id,
            "material_type": "video"
        }
        await message.answer("✅ Видео добавлено к тесту.")
    elif message.text:
        # Пользователь отправил текст
        if message.text.lower() == 'удалить':
            update_data = {
                "material_link": None,
                "material_file_path": None,
                "material_type": None
            }
        else:
            update_data = {
                "material_link": message.text.strip(),
                "material_file_path": None,
                "material_type": None
            }
    else:
        # Неподдерживаемый тип сообщения
        await message.answer(
            "❌ Пожалуйста, отправь ссылку на материалы, документ, изображение или напиши 'удалить'."
        )
        return
    
    await update_test(session, test_id, update_data)
    
    test = await get_test_by_id(session, test_id)
    # Получаем session_id из state перед очисткой
    data = await state.get_data()
    session_id = data.get('editor_session_id')
    await state.clear()
    # Восстанавливаем session_id после очистки, если был
    if session_id:
        await state.update_data(editor_session_id=session_id)
    
    await message.answer(
        f"✅ Материалы для теста <b>«{test.name}»</b> обновлены.",
        parse_mode="HTML",
        reply_markup=get_test_edit_menu(test_id, session_id=session_id)
    )

@router.callback_query(F.data.startswith("edit_test_settings:"))
async def process_test_settings(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Показывает меню настроек теста"""
    test_id = int(callback.data.split(':')[1])
    
    # Получаем session_id из state, если тест открыт из редактора траекторий
    data = await state.get_data()
    session_id = data.get('editor_session_id')
    
    test = await get_test_by_id(session, test_id)
    if not test:
        await callback.answer("❌ Тест не найден.", show_alert=True)
        return
        
    await callback.message.edit_text(
        "⚙️ <b>Настройки теста</b>\n\n"
        "Здесь ты можешь изменить параметры прохождения теста.",
        parse_mode="HTML",
        reply_markup=get_test_settings_keyboard(test.id, test.shuffle_questions, test.max_attempts, session_id=session_id)
    )
    await callback.answer()

@router.callback_query(F.data.startswith("toggle_shuffle:"))
async def toggle_shuffle_questions(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Переключает перемешивание вопросов"""
    test_id = int(callback.data.split(':')[1])
    
    # Получаем session_id из state, если тест открыт из редактора траекторий
    data = await state.get_data()
    session_id = data.get('editor_session_id')
    
    test = await get_test_by_id(session, test_id)
    if not test:
        await callback.answer("❌ Тест не найден.", show_alert=True)
        return

    new_shuffle_state = not test.shuffle_questions
    await update_test(session, test_id, {"shuffle_questions": new_shuffle_state})
    
    # Обновляем клавиатуру и текст
    test.shuffle_questions = new_shuffle_state # Обновляем локальный объект
    
    shuffle_status = "✅ <b>Включено:</b> Вопросы будут показываться в случайном порядке." if test.shuffle_questions else "☑️ <b>Выключено:</b> Вопросы будут показываться по порядку."
    
    await callback.message.edit_text(
        f"⚙️ <b>Настройки теста</b>\n\n"
        f"<b>Перемешивание вопросов:</b>\n{shuffle_status}\n\n"
        "Здесь ты можешь изменить параметры прохождения теста.",
        parse_mode="HTML",
        reply_markup=get_test_settings_keyboard(test.id, test.shuffle_questions, test.max_attempts, session_id=session_id)
    )
    await callback.answer()

@router.callback_query(F.data.startswith("answer_bool:"), TestCreationStates.waiting_for_answer)
async def process_bool_answer(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора правильного ответа для Да/Нет (ТОЛЬКО для обычного создания теста)"""
    answer = callback.data.split(':')[1]
    await state.update_data(current_answer=answer)
    await callback.message.edit_text(
        "🔢 Теперь укажите, сколько баллов можно получить за правильный ответ?",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отменить создание вопроса", callback_data="cancel_current_question")]
        ])
    )
    await state.set_state(TestCreationStates.waiting_for_points)
    await callback.answer()

@router.callback_query(F.data.startswith("edit_attempts:"))
async def process_edit_attempts(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Запрашивает новое количество попыток"""
    test_id = int(callback.data.split(':')[1])
    test = await get_test_by_id(session, test_id)
    if not test:
        await callback.answer("❌ Тест не найден.", show_alert=True)
        return
        
    await state.update_data(test_id_to_edit=test_id)
    
    await callback.message.edit_text(
        f"Текущее количество попыток: <b>{'бесконечно' if test.max_attempts == 0 else test.max_attempts}</b>.\n\n"
        "Введи новое количество попыток (от 1 до 10). "
        "Введи 0 для бесконечного количества попыток.",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Назад", callback_data=f"edit_test_settings:{test_id}")]
        ])
    )
    await state.set_state(TestCreationStates.waiting_for_new_attempts)
    await callback.answer()

@router.message(TestCreationStates.waiting_for_new_attempts)
async def save_new_attempts(message: Message, state: FSMContext, session: AsyncSession):
    """Сохраняет новое количество попыток"""
    data = await state.get_data()
    test_id = data['test_id_to_edit']
    
    try:
        attempts = int(message.text.strip())
        if not (0 <= attempts <= 10):
            await message.answer("❌ Введи число от 0 до 10.")
            return
    except ValueError:
        await message.answer("❌ Пожалуйста, введи число.")
        return
        
    await update_test(session, test_id, {"max_attempts": attempts})
    
    test = await get_test_by_id(session, test_id)
    # Получаем session_id из state перед очисткой
    data = await state.get_data()
    session_id = data.get('editor_session_id')
    await state.clear()
    # Восстанавливаем session_id после очистки, если был
    if session_id:
        await state.update_data(editor_session_id=session_id)
    
    await message.answer(
        f"✅ Количество попыток для теста <b>«{test.name}»</b> обновлено.",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⚙️ К настройкам", callback_data=f"edit_test_settings:{test_id}")],
            [InlineKeyboardButton(text="✏️ К редактированию", callback_data=_get_edit_test_callback(test_id, session_id))]
        ])
    )

@router.callback_query(F.data.startswith("add_q_to_test:"))
async def add_question_to_test_handler(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Начинает процесс добавления нового вопроса к существующему тесту"""
    test_id = int(callback.data.split(':')[1])
    test = await get_test_by_id(session, test_id)
    if not test:
        await callback.answer("❌ Тест не найден.", show_alert=True)
        return

    questions = await get_test_questions(session, test_id)
    
    # Преобразуем существующие вопросы в формат словарей для совместимости
    questions_dict = []
    for q in questions:
        questions_dict.append({
            "type": q.question_type,
            "text": q.question_text,
            "options": q.options,
            "answer": q.correct_answer,
            "points": q.points
        })
    
    await state.update_data(
        test_id_to_edit=test_id, 
        questions=questions_dict, 
        initial_questions_count=len(questions_dict),  # Сохраняем изначальное количество
        current_question_number=len(questions_dict) + 1
    )
    
    await callback.message.edit_text(
        "Начинаем добавление нового вопроса.\n\n"
        "Выбери тип вопроса:",
        reply_markup=get_question_type_keyboard(is_creating_test=False)
    )
    await state.set_state(TestCreationStates.waiting_for_question_type)
    await callback.answer()

# =================================
# ОБРАБОТЧИКИ КНОПОК "НАЗАД" ДЛЯ ФОРМ РЕДАКТИРОВАНИЯ
# =================================

@router.callback_query(F.data.startswith("edit_test:"), TestCreationStates.waiting_for_new_test_name)
async def cancel_test_name_edit(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Отмена редактирования названия теста"""
    parts = callback.data.split(':')
    test_id = int(parts[1])
    # Сохраняем session_id перед очисткой, если был
    data = await state.get_data()
    session_id = data.get('editor_session_id')
    await state.clear()
    # Восстанавливаем session_id, если был
    if session_id:
        await state.update_data(editor_session_id=session_id)
        # Обновляем callback_data чтобы передать session_id
        callback.data = f"edit_test:{test_id}:{session_id}"
    # Перенаправляем обратно к меню редактирования
    await process_edit_test_menu(callback, state, session)

@router.callback_query(F.data.startswith("edit_test:"), TestCreationStates.waiting_for_new_threshold)
async def cancel_threshold_edit(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Отмена редактирования порога"""
    parts = callback.data.split(':')
    test_id = int(parts[1])
    # Сохраняем session_id перед очисткой, если был
    data = await state.get_data()
    session_id = data.get('editor_session_id')
    await state.clear()
    # Восстанавливаем session_id, если был
    if session_id:
        await state.update_data(editor_session_id=session_id)
        # Обновляем callback_data чтобы передать session_id
        callback.data = f"edit_test:{test_id}:{session_id}"
    await process_edit_test_menu(callback, state, session)

@router.callback_query(F.data.startswith("edit_test:"), TestCreationStates.waiting_for_new_materials)
async def cancel_materials_edit(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Отмена редактирования материалов"""
    parts = callback.data.split(':')
    test_id = int(parts[1])
    # Сохраняем session_id перед очисткой, если был
    data = await state.get_data()
    session_id = data.get('editor_session_id')
    await state.clear()
    # Восстанавливаем session_id, если был
    if session_id:
        await state.update_data(editor_session_id=session_id)
        # Обновляем callback_data чтобы передать session_id
        callback.data = f"edit_test:{test_id}:{session_id}"
    await process_edit_test_menu(callback, state, session)

@router.callback_query(F.data.startswith("edit_test_settings:"), TestCreationStates.waiting_for_new_attempts)
async def cancel_attempts_edit(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Отмена редактирования количества попыток"""
    test_id = int(callback.data.split(':')[1])
    # Сохраняем session_id перед очисткой, если был
    data = await state.get_data()
    session_id = data.get('editor_session_id')
    await state.clear()
    # Восстанавливаем session_id, если был
    if session_id:
        await state.update_data(editor_session_id=session_id)
    await process_test_settings(callback, state, session)

@router.callback_query(F.data.startswith("select_question_for_edit:"), TestCreationStates.waiting_for_question_edit)
async def cancel_question_text_edit(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Отмена редактирования текста вопроса"""
    question_id = int(callback.data.split(':')[1])
    # Сохраняем session_id перед очисткой, если был
    data = await state.get_data()
    session_id = data.get('editor_session_id')
    await state.clear()
    # Восстанавливаем session_id после очистки, если был
    if session_id:
        await state.update_data(editor_session_id=session_id)
    await select_question_for_edit(callback, state, session)

@router.callback_query(F.data.startswith("select_question_for_edit:"), TestCreationStates.waiting_for_points_edit)
async def cancel_question_points_edit(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Отмена редактирования баллов за вопрос"""
    question_id = int(callback.data.split(':')[1])
    # Сохраняем session_id перед очисткой, если был
    data = await state.get_data()
    session_id = data.get('editor_session_id')
    await state.clear()
    # Восстанавливаем session_id после очистки, если был
    if session_id:
        await state.update_data(editor_session_id=session_id)
    await select_question_for_edit(callback, state, session)

@router.callback_query(F.data.startswith("select_question_for_edit:"), TestCreationStates.waiting_for_answer_edit)
async def cancel_question_answer_edit(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Отмена редактирования ответа на вопрос"""
    question_id = int(callback.data.split(':')[1])
    # Сохраняем session_id перед очисткой, если был
    data = await state.get_data()
    session_id = data.get('editor_session_id')
    await state.clear()
    # Восстанавливаем session_id после очистки, если был
    if session_id:
        await state.update_data(editor_session_id=session_id)
    await select_question_for_edit(callback, state, session)

@router.callback_query(F.data == "cancel_current_question")
async def cancel_current_question_creation(callback: CallbackQuery, state: FSMContext):
    """Отмена создания текущего вопроса и возврат к выбору типа вопроса"""
    data = await state.get_data()
    test_id = data.get('test_id_to_edit')
    questions = data.get('questions', [])
    
    # Очищаем данные текущего вопроса
    await state.update_data(
        current_question_type=None,
        current_question_text=None,
        current_options=None,
        current_answer=None
    )
    
    # Определяем контекст и показываем соответствующее сообщение
    if test_id:
        # Добавляем вопрос к существующему тесту
        context_text = "добавления нового вопроса к тесту"
        is_creating_test = False
    else:
        # Создаем новый тест
        context_text = "создания текущего вопроса"
        is_creating_test = True
    
    await callback.message.edit_text(
        f"❌ <b>Отмена {context_text}</b>\n\n"
        f"Выбери тип вопроса или заверши создание:",
        parse_mode="HTML",
        reply_markup=get_question_type_keyboard(is_creating_test=is_creating_test)
    )
    await state.set_state(TestCreationStates.waiting_for_question_type)
    await callback.answer()

@router.callback_query(F.data == "cancel_question")
async def cancel_question_creation(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Отмена добавления нового вопроса"""
    data = await state.get_data()
    test_id = data.get('test_id_to_edit')
    questions = data.get('questions', [])
    
    if test_id:
        # Если добавляли вопрос к существующему тесту - возвращаемся к списку вопросов
        # Сохраняем session_id перед очисткой
        data = await state.get_data()
        session_id = data.get('editor_session_id')
        await state.clear()
        # Восстанавливаем session_id после очистки, если был
        if session_id:
            await state.update_data(editor_session_id=session_id)
        await _show_questions_list(callback.message, state, session, test_id)
    elif questions:
        # Если создаем новый тест и уже есть добавленные вопросы - 
        # возвращаемся к выбору: добавить еще вопрос или завершить
        total_questions = len(questions)
        total_score = sum(q['points'] for q in questions)
        
        # Очищаем данные текущего вопроса
        await state.update_data(
            current_question_type=None,
            current_question_text=None,
            current_options=None,
            current_answer=None
        )
        
        await callback.message.edit_text(
            f"✅ <b>Добавление текущего вопроса отменено.</b>\n\n"
            f"📋 <b>Создание теста продолжается!</b>\n\n"
            f"📊 Текущая статистика теста:\n"
            f" • Количество вопросов: {total_questions}\n"
            f" • Максимальный балл: {total_score:.1f}\n\n"
            "❓ Хочешь добавить еще один вопрос или завершить создание теста?",
            parse_mode="HTML",
            reply_markup=get_yes_no_keyboard("more_questions")
        )
        await state.set_state(TestCreationStates.waiting_for_more_questions)
    else:
        # Если создавали новый тест и еще нет вопросов - отменяем создание
        await callback.message.edit_text(
            "❌ <b>Создание теста отменено.</b>\n\n"
            "Тест не может существовать без вопросов. "
            "Для создания теста необходимо добавить хотя бы один вопрос.",
            parse_mode="HTML"
        )
        await state.clear()
    
    await callback.answer()

@router.callback_query(
    F.data.startswith("view_materials:"),
    ~StateFilter(TestTakingStates.waiting_for_test_selection, TestTakingStates.waiting_for_test_start)
)
async def process_view_materials_admin(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Обработчик просмотра материалов для рекрутера/наставника (только в контексте управления)"""
    test_id = int(callback.data.split(':')[1])
    
    test = await get_test_by_id(session, test_id)
    if not test:
        await callback.answer("❌ Тест не найден.", show_alert=True)
        return
    
    if not test.material_link:
        await callback.message.edit_text(
            f"📚 <b>Материалы к тесту: «{test.name}»</b>\n\n"
            "К этому тесту не прикреплены материалы для изучения.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ Назад к тесту", callback_data=f"test:{test_id}")]
            ])
        )
        await callback.answer()
        return
    
    if test.material_file_path:
        # Если есть прикрепленный файл - отправляем его
        try:
            # Определяем тип и используем правильный метод
            if test.material_type == "photo":
                sent_media = await callback.bot.send_photo(
                    chat_id=callback.message.chat.id,
                    photo=test.material_file_path
                )
            elif test.material_type == "video":
                sent_media = await callback.bot.send_video(
                    chat_id=callback.message.chat.id,
                    video=test.material_file_path
                )
            else:
                sent_media = await callback.bot.send_document(
                    chat_id=callback.message.chat.id,
                    document=test.material_file_path
                )
            
            # Сохраняем message_id медиа-файла для последующего удаления
            await state.update_data(material_message_id=sent_media.message_id)
            
            sent_text = await callback.message.answer(
                "📎 Материал отправлен выше.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="⬅️ Назад к тесту", callback_data=f"test:{test_id}")]
                ])
            )
            # Сохраняем message_id текстового сообщения
            await state.update_data(material_text_message_id=sent_text.message_id)
        except Exception as e:
            await callback.message.edit_text(
                f"❌ <b>Ошибка загрузки файла</b>\n\n"
                f"Не удалось загрузить прикрепленный файл.\n"
                f"Возможно, файл был удален из Telegram.\n\n"
                f"📌 <b>Тест:</b> {test.name}",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="⬅️ Назад к тесту", callback_data=f"test:{test_id}")]
                ])
            )
    else:
        # Если это ссылка
        await callback.message.edit_text(
            f"📚 <b>Материалы к тесту: «{test.name}»</b>\n\n"
            f"🔗 <b>Ссылка на материалы:</b>\n{test.material_link}",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ Назад к тесту", callback_data=f"test:{test_id}")]
            ])
        )
    
    await callback.answer()