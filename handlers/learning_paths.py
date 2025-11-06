import asyncio
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from database.db import (
    get_all_learning_paths, get_learning_path_by_id, save_trajectory_to_database,
    save_trajectory_with_attestation_and_group, delete_learning_path,
    create_attestation, add_attestation_question, get_all_attestations,
    get_attestation_by_id, check_attestation_in_use, delete_attestation, 
    get_all_active_tests, create_test, add_question_to_test,
    get_all_groups, check_user_permission, get_user_by_tg_id, get_user_roles,
    get_trajectories_using_attestation, get_trajectory_usage_info
)
from handlers.auth import check_auth
from states.states import LearningPathStates, AttestationStates
from keyboards.keyboards import (
    get_learning_paths_main_keyboard, get_trajectory_creation_start_keyboard,
    get_test_selection_keyboard, get_test_creation_cancel_keyboard,
    get_test_materials_choice_keyboard, get_test_materials_skip_keyboard,
    get_test_description_skip_keyboard, get_question_type_keyboard,
    get_more_questions_keyboard, get_session_management_keyboard,
    get_attestation_selection_keyboard, get_trajectory_save_confirmation_keyboard,
    get_trajectory_attestation_confirmation_keyboard, get_trajectory_final_confirmation_keyboard, 
    get_attestations_main_keyboard, get_attestation_creation_start_keyboard, 
    get_attestation_questions_keyboard, get_group_selection_keyboard, 
    get_main_menu_keyboard, get_keyboard_by_role, get_trajectory_selection_keyboard,
    get_trajectory_deletion_confirmation_keyboard
)
from utils.logger import log_user_action, log_user_error
from utils.validators import validate_name

router = Router()


@router.message(F.text.in_(["Траектории", "Траектория 📖"]))
async def cmd_learning_paths(message: Message, state: FSMContext, session: AsyncSession):
    """Обработчик команды 'Траектории'"""
    try:
        # КРИТИЧНО: Очищаем состояние и данные FSM при входе
        await state.clear()
        
        # Проверка авторизации
        is_auth = await check_auth(message, state, session)
        if not is_auth:
            return
        
        # Получение пользователя
        user = await get_user_by_tg_id(session, message.from_user.id)
        if not user:
            await message.answer("Ты не зарегистрирован в системе.")
            return
        
        # Проверка прав доступа
        has_permission = await check_user_permission(session, user.id, "manage_groups")
        if not has_permission:
            await message.answer(
                "❌ <b>Недостаточно прав</b>\n\n"
                "У тебя нет прав для управления траекториями.\n"
                "Обратись к администратору.",
                parse_mode="HTML"
            )
            log_user_error(user.tg_id, "learning_paths_access_denied", "Попытка доступа без прав")
            return
        
        # Показываем главное меню траекторий
        text = ("🗺️<b>РЕДАКТОР ТРАЕКТОРИЙ</b>🗺️\n\n"
                "В данном меню ты можешь:\n\n"
                "1 ➕Создать траекторию обучения\n"
                "2 ✏️Изменить траекторию обучения\n"
                "3 🗑️Удалить траекторию обучения")
        
        await message.answer(
            text,
            reply_markup=get_learning_paths_main_keyboard(),
            parse_mode="HTML"
        )
        
        await state.set_state(LearningPathStates.main_menu)
        log_user_action(user.tg_id, "opened_learning_paths", "Открыт редактор траекторий")
        
    except Exception as e:
        await message.answer("Произошла ошибка. Попробуй позже.")
        log_user_error(message.from_user.id, "learning_paths_error", str(e))


@router.callback_query(F.data == "create_trajectory", LearningPathStates.main_menu)
async def callback_create_trajectory(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Начало создания траектории"""
    try:
        await callback.answer()
        
        instruction_text = (
            "🗺️<b>РЕДАКТОР ТРАЕКТОРИЙ</b>🗺️\n"
            "➕Создание траектории\n"
            "📈<b>ИНСТРУКЦИЯ</b>\n\n"
            "Траектория состоит из составляющих:\n"
            "- Этапов\n"
            "- Сессий\n"
            "- Тестов\n\n"
            "Составляющие заполняются по порядку:\n\n"
            "Сначала название для  траектории, этапы в этой траектории, потом сессии для этапа и в конце тесты для каждой сессии\n\n"
            "Последним этапом в траектории является Аттестация - она аналогична экзамену или контрольной в школе.\n\n"
            "Аттестация открывается стажёру в самом конце, при условии,что стажёр прошёл все этапы до аттестации.\n\n"
            "Когда ты предоставишь доступ наставнику к траектории, он может открывать этап для стажёра\n\n"
            "Стажёр может проходить сессии внутри этапа в произвольном порядке (по договоренности с наставником)\n\n"
            "После прохождения всех сессий, наставник может открыть стажёру следующий этап (либо сделать это раньше, если этого требует бизнес-процесс)"
        )
        
        await callback.message.edit_text(
            instruction_text,
            reply_markup=get_trajectory_creation_start_keyboard(),
            parse_mode="HTML"
        )
        
        # Инициализируем данные траектории в state
        await state.update_data(
            trajectory_data={
                'name': '',
                'stages': [],
                'created_by_id': None
            },
            current_stage_number=1,
            current_session_number=1,
            current_test_number=1
        )
        
    except Exception as e:
        await callback.answer("Произошла ошибка")
        log_user_error(callback.from_user.id, "trajectory_creation_start_error", str(e))


@router.callback_query(F.data == "start_trajectory_creation", LearningPathStates.main_menu)
async def callback_start_trajectory_creation(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Начало ввода названия траектории"""
    try:
        await callback.answer()
        
        # Получаем пользователя для creator_id
        user = await get_user_by_tg_id(session, callback.from_user.id)
        if not user:
            await callback.message.edit_text("Ошибка: пользователь не найден")
            return
            
        # Обновляем creator_id в данных
        data = await state.get_data()
        trajectory_data = data.get('trajectory_data', {})
        trajectory_data['created_by_id'] = user.id
        await state.update_data(trajectory_data=trajectory_data)
        
        text = (
            "🗺️<b>РЕДАКТОР ТРАЕКТОРИЙ</b>🗺️\n"
            "➕Создание траектории\n"
            "🟡<b>Название траектории:</b> отправь название\n\n"
            "Введи название для траектории"
        )
        
        await callback.message.edit_text(text, parse_mode="HTML")
        await state.set_state(LearningPathStates.waiting_for_trajectory_name)
        
    except Exception as e:
        await callback.answer("Произошла ошибка")
        log_user_error(callback.from_user.id, "start_trajectory_creation_error", str(e))


@router.message(LearningPathStates.waiting_for_trajectory_name)
async def process_trajectory_name(message: Message, state: FSMContext, session: AsyncSession):
    """Обработка названия траектории"""
    try:
        name = message.text.strip()
        
        # Валидация названия
        if not validate_name(name):
            await message.answer("❌ Некорректное название траектории. Попробуй еще раз:")
            return
        
        # Сохраняем название траектории
        data = await state.get_data()
        trajectory_data = data.get('trajectory_data', {})
        trajectory_data['name'] = name
        await state.update_data(trajectory_data=trajectory_data)
        
        text = (
            "🗺️<b>РЕДАКТОР ТРАЕКТОРИЙ</b>🗺️\n"
            "➕Создание траектории\n"
            f"🟢<b>Название траектории:</b> {name}\n"
            "🟡<b>Этап 1:</b> отправь название\n\n"
            "Введи название для Этапа 1"
        )
        
        await message.answer(text, parse_mode="HTML")
        await state.set_state(LearningPathStates.waiting_for_stage_name)
        
    except Exception as e:
        await message.answer("Произошла ошибка при обработке названия")
        log_user_error(message.from_user.id, "trajectory_name_error", str(e))


@router.message(LearningPathStates.waiting_for_stage_name)
async def process_stage_name(message: Message, state: FSMContext, session: AsyncSession):
    """Обработка названия этапа"""
    try:
        stage_name = message.text.strip()
        
        # Валидация названия этапа
        if not validate_name(stage_name):
            await message.answer("❌ Некорректное название этапа. Попробуй еще раз:")
            return
        
        # Получаем данные траектории
        data = await state.get_data()
        trajectory_data = data.get('trajectory_data', {})
        current_stage_number = data.get('current_stage_number', 1)
        
        # Создаем новый этап
        new_stage = {
            'name': stage_name,
            'order': current_stage_number,
            'sessions': []
        }
        
        # Добавляем этап к траектории
        if 'stages' not in trajectory_data:
            trajectory_data['stages'] = []
        trajectory_data['stages'].append(new_stage)
        
        # Обновляем state данные
        await state.update_data(
            trajectory_data=trajectory_data,
            current_session_number=1  # Сбрасываем счетчик сессий
        )
        
        # Показываем прогресс и просим название первой сессии
        trajectory_progress = generate_trajectory_progress(trajectory_data)
        
        text = (
            f"🗺️<b>РЕДАКТОР ТРАЕКТОРИЙ</b>🗺️\n"
            "➕Создание траектории\n"
            f"{trajectory_progress}"
            "🟡<b>Сессия 1:</b> отправь название\n\n"
            "Введи название для сессии 1"
        )
        
        await message.answer(text, parse_mode="HTML")
        await state.set_state(LearningPathStates.waiting_for_session_name)
        
    except Exception as e:
        await message.answer("Произошла ошибка при обработке названия этапа")
        log_user_error(message.from_user.id, "stage_name_error", str(e))


@router.message(LearningPathStates.waiting_for_session_name)
async def process_session_name(message: Message, state: FSMContext, session: AsyncSession):
    """Обработка названия сессии"""
    try:
        session_name = message.text.strip()
        
        # Валидация названия сессии
        if not validate_name(session_name):
            await message.answer("❌ Некорректное название сессии. Попробуй еще раз:")
            return
        
        # Получаем данные
        data = await state.get_data()
        trajectory_data = data.get('trajectory_data', {})
        current_session_number = data.get('current_session_number', 1)
        
        # Создаем новую сессию
        new_session = {
            'name': session_name,
            'order': current_session_number,
            'tests': []
        }
        
        # Добавляем сессию к последнему этапу
        if trajectory_data.get('stages'):
            last_stage = trajectory_data['stages'][-1]
            last_stage['sessions'].append(new_session)
        
        await state.update_data(trajectory_data=trajectory_data)
        
        # Получаем все доступные тесты
        tests = await get_all_active_tests(session)
        
        # Показываем выбор тестов
        trajectory_progress = generate_trajectory_progress(trajectory_data)
        
        text = (
            f"🗺️<b>РЕДАКТОР ТРАЕКТОРИЙ</b>🗺️\n"
            "➕Создание траектории\n"
            f"{trajectory_progress}"
            f"🟡<b>Тест 1:</b> Выбери тест для сессии {current_session_number}"
        )
        
        await message.answer(
            text,
            reply_markup=get_test_selection_keyboard(tests, []),
            parse_mode="HTML"
        )
        await state.set_state(LearningPathStates.waiting_for_test_selection)
        
    except Exception as e:
        await message.answer("Произошла ошибка при обработке названия сессии")
        log_user_error(message.from_user.id, "session_name_error", str(e))


def generate_trajectory_progress(trajectory_data: dict) -> str:
    """Генерация текста прогресса создания траектории"""
    progress = ""
    
    if trajectory_data.get('name'):
        progress += f"🟢<b>Название траектории:</b> {trajectory_data['name']}\n"
    
    # Отображаем этапы
    for stage in trajectory_data.get('stages', []):
        progress += f"🟢<b>Этап {stage['order']}:</b> {stage['name']}\n"
        
        # Отображаем сессии этапа
        for session in stage.get('sessions', []):
            progress += f"🟢<b>Сессия {session['order']}:</b> {session['name']}\n"
            
            # Отображаем тесты сессии
            for i, test in enumerate(session.get('tests', []), 1):
                test_name = test.get('name', f'Тест {test.get("id", "?")}')
                progress += f"🟢<b>Тест {i}:</b> {test_name}\n"
    
    return progress


@router.callback_query(F.data == "create_new_test", LearningPathStates.waiting_for_test_selection)
async def callback_create_new_test(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Начало создания нового теста в процессе создания траектории"""
    try:
        await callback.answer()
        
        # Получаем прогресс траектории
        data = await state.get_data()
        trajectory_data = data.get('trajectory_data', {})
        trajectory_progress = generate_trajectory_progress(trajectory_data)
        
        text = (
            f"🗺️<b>РЕДАКТОР ТРАЕКТОРИЙ</b>🗺️\n"
            "➕Создание траектории\n"
            f"{trajectory_progress}"
            "🟡<b>Создание теста</b>\n\n"
            "🔧 Создание нового теста\n"
            "📝 Начинаем пошаговое создание теста для твоей системы стажировки.\n"
            "1️⃣ Шаг 1: Введи название теста\n"
            "💡 Название должно быть информативным и понятным для стажеров\n"
            "📋 Пример: «Основы работы с клиентами» или «Техника безопасности»"
        )
        
        await callback.message.edit_text(
            text,
            reply_markup=get_test_creation_cancel_keyboard(),
            parse_mode="HTML"
        )
        
        await state.set_state(LearningPathStates.creating_test_name)
        
    except Exception as e:
        await callback.answer("Произошла ошибка")
        log_user_error(callback.from_user.id, "create_new_test_error", str(e))


@router.message(LearningPathStates.creating_test_name)
async def process_new_test_name(message: Message, state: FSMContext, session: AsyncSession):
    """Обработка названия нового теста"""
    try:
        test_name = message.text.strip()
        
        # Валидация названия
        if not validate_name(test_name):
            await message.answer("❌ Некорректное название теста. Попробуй еще раз:")
            return
        
        # Сохраняем название теста
        await state.update_data(new_test_name=test_name)
        
        # Получаем прогресс траектории
        data = await state.get_data()
        trajectory_data = data.get('trajectory_data', {})
        trajectory_progress = generate_trajectory_progress(trajectory_data)
        
        text = (
            f"🗺️<b>РЕДАКТОР ТРАЕКТОРИЙ</b>🗺️\n"
            "➕Создание траектории\n"
            f"{trajectory_progress}"
            "🟡<b>Создание теста</b>\n\n"
            f"✅ Название принято: {test_name}\n"
            "2️⃣ Шаг 2: Материалы для изучения\n"
            "📚 Есть ли у тебя материалы, которые стажеры должны изучить перед прохождением теста?\n"
            "💡 Материалы могут быть:\n"
            "• Ссылки на обучающие видео\n"
            "• Документы и инструкции\n"
            "• Презентации или курсы\n"
            "• Любые другие учебные ресурсы\n"
            "❓ Хотите добавить материалы к тесту?"
        )
        
        await message.answer(
            text,
            reply_markup=get_test_materials_choice_keyboard(),
            parse_mode="HTML"
        )
        
        await state.set_state(LearningPathStates.creating_test_materials_choice)
        
    except Exception as e:
        await message.answer("Произошла ошибка при обработке названия теста")
        log_user_error(message.from_user.id, "new_test_name_error", str(e))


@router.callback_query(F.data == "add_materials", LearningPathStates.creating_test_materials_choice)
async def callback_add_materials(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Запрос материалов для теста"""
    try:
        await callback.answer()
        
        # Получаем прогресс траектории
        data = await state.get_data()
        trajectory_data = data.get('trajectory_data', {})
        trajectory_progress = generate_trajectory_progress(trajectory_data)
        
        text = (
            f"🗺️<b>РЕДАКТОР ТРАЕКТОРИЙ</b>🗺️\n"
            "➕Создание траектории\n"
            f"{trajectory_progress}"
            "🟡<b>Создание теста</b>\n\n"
            "📎 Отправь ссылку на материалы для изучения, документ, изображение или нажми 'Пропустить':"
        )
        
        await callback.message.edit_text(
            text,
            reply_markup=get_test_materials_skip_keyboard(),
            parse_mode="HTML"
        )
        
        await state.set_state(LearningPathStates.creating_test_materials)
        
    except Exception as e:
        await callback.answer("Произошла ошибка")
        log_user_error(callback.from_user.id, "add_materials_error", str(e))


@router.callback_query(F.data == "skip_materials", LearningPathStates.creating_test_materials_choice)
@router.callback_query(F.data == "skip_materials", LearningPathStates.creating_test_materials)
async def callback_skip_materials(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Пропуск материалов и переход к описанию"""
    try:
        await callback.answer()
        await state.update_data(new_test_materials="")
        await show_test_description_step(callback.message, state)
        
    except Exception as e:
        await callback.answer("Произошла ошибка")
        log_user_error(callback.from_user.id, "skip_materials_error", str(e))


@router.message(LearningPathStates.creating_test_materials)
async def process_test_materials(message: Message, state: FSMContext, session: AsyncSession):
    """Обработка материалов теста"""
    try:
        materials = message.text.strip()
        await state.update_data(new_test_materials=materials)
        await show_test_description_step(message, state)
        
    except Exception as e:
        await message.answer("Произошла ошибка при обработке материалов")
        log_user_error(message.from_user.id, "test_materials_error", str(e))


async def show_test_description_step(message, state: FSMContext):
    """Показать шаг описания теста"""
    try:
        # Получаем прогресс траектории
        data = await state.get_data()
        trajectory_data = data.get('trajectory_data', {})
        trajectory_progress = generate_trajectory_progress(trajectory_data)
        
        text = (
            f"🗺️<b>РЕДАКТОР ТРАЕКТОРИЙ</b>🗺️\n"
            "➕Создание траектории\n"
            f"{trajectory_progress}"
            "🟡<b>Создание теста</b>\n\n"
            "3️⃣ Шаг 3: Описание теста\n"
            "📝 Введи краткое описание теста, которое поможет стажерам понять:\n"
            "• О чем этот тест\n"
            "• Какие знания проверяются\n"
            "• Что ожидается от стажера\n"
            "💡 Пример: «Тест проверяет знание основных принципов обслуживания клиентов и умение решать конфликтные ситуации»\n"
            "✍️ Введи описание или нажми кнопку 'Пропустить':"
        )
        
        # Всегда отправляем новое сообщение, так как это может быть message от пользователя
        await message.answer(
            text,
            reply_markup=get_test_description_skip_keyboard(),
            parse_mode="HTML"
        )
        
        await state.set_state(LearningPathStates.creating_test_description)
        
    except Exception as e:
        log_user_error(message.from_user.id if hasattr(message, 'from_user') else 0, "show_description_error", str(e))


@router.callback_query(F.data == "skip_description", LearningPathStates.creating_test_description)
async def callback_skip_description(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Пропуск описания теста"""
    try:
        await callback.answer()
        await state.update_data(new_test_description="")
        await show_question_type_step(callback.message, state)
        
    except Exception as e:
        await callback.answer("Произошла ошибка")
        log_user_error(callback.from_user.id, "skip_description_error", str(e))


@router.message(LearningPathStates.creating_test_description)
async def process_test_description(message: Message, state: FSMContext, session: AsyncSession):
    """Обработка описания теста"""
    try:
        description = message.text.strip()
        await state.update_data(new_test_description=description)
        await show_question_type_step(message, state)
        
    except Exception as e:
        await message.answer("Произошла ошибка при обработке описания")
        log_user_error(message.from_user.id, "test_description_error", str(e))


async def show_question_type_step(message, state: FSMContext):
    """Показать шаг выбора типа вопроса"""
    try:
        # Получаем прогресс траектории
        data = await state.get_data()
        trajectory_data = data.get('trajectory_data', {})
        trajectory_progress = generate_trajectory_progress(trajectory_data)
        
        text = (
            f"🗺️<b>РЕДАКТОР ТРАЕКТОРИЙ</b>🗺️\n"
            "➕Создание траектории\n"
            f"{trajectory_progress}"
            "🟡<b>Создание теста</b>\n\n"
            "📝 Отлично! Теперь давай добавим вопросы к тесту.\n"
            "Выбери тип первого вопроса:"
        )
        
        # Всегда отправляем новое сообщение, так как это может быть message от пользователя
        await message.answer(
            text,
            reply_markup=get_question_type_keyboard(),
            parse_mode="HTML"
        )
        
        await state.set_state(LearningPathStates.creating_test_question_type)
        
    except Exception as e:
        log_user_error(message.from_user.id if hasattr(message, 'from_user') else 0, "show_question_type_error", str(e))


@router.callback_query(F.data.startswith("q_type:"), LearningPathStates.creating_test_question_type)
async def callback_question_type(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Обработка выбора типа вопроса"""
    try:
        await callback.answer()
        
        question_type = callback.data.split(":")[1]
        await state.update_data(new_test_question_type=question_type)
        
        # Получаем прогресс траектории
        data = await state.get_data()
        trajectory_data = data.get('trajectory_data', {})
        trajectory_progress = generate_trajectory_progress(trajectory_data)
        
        text = (
            f"🗺️<b>РЕДАКТОР ТРАЕКТОРИЙ</b>🗺️\n"
            "➕Создание траектории\n"
            f"{trajectory_progress}"
            "🟡<b>Создание теста</b>\n\n"
            "Введи текст вопроса:"
        )
        
        await callback.message.edit_text(text, parse_mode="HTML")
        await state.set_state(LearningPathStates.creating_test_question_text)
        
    except Exception as e:
        await callback.answer("Произошла ошибка")
        log_user_error(callback.from_user.id, "question_type_error", str(e))


@router.message(LearningPathStates.creating_test_question_text)
async def process_question_text(message: Message, state: FSMContext, session: AsyncSession):
    """Обработка текста вопроса"""
    try:
        question_text = message.text.strip()
        
        if not question_text:
            await message.answer("❌ Текст вопроса не может быть пустым. Попробуй еще раз:")
            return
        
        await state.update_data(new_test_question_text=question_text)
        
        # Получаем прогресс траектории и тип вопроса
        data = await state.get_data()
        trajectory_data = data.get('trajectory_data', {})
        trajectory_progress = generate_trajectory_progress(trajectory_data)
        q_type = data.get('new_test_question_type')
        
        if q_type == 'text':
            text = (
                f"🗺️<b>РЕДАКТОР ТРАЕКТОРИЙ</b>🗺️\n"
                "➕Создание траектории\n"
                f"{trajectory_progress}"
                "🟡<b>Создание теста</b>\n\n"
                "✅ Текст вопроса принят. Теперь введи единственный правильный ответ (точную фразу):"
            )
            await message.answer(text, parse_mode="HTML")
            await state.set_state(LearningPathStates.creating_test_question_answer)
        elif q_type in ['single_choice', 'multiple_choice']:
            text = (
                f"🗺️<b>РЕДАКТОР ТРАЕКТОРИЙ</b>🗺️\n"
                "➕Создание траектории\n"
                f"{trajectory_progress}"
                "🟡<b>Создание теста</b>\n\n"
                "✅ Текст вопроса принят. Теперь давай добавим варианты ответа.\n\n"
                "Введи **первый вариант** ответа:"
            )
            await message.answer(text, parse_mode="HTML")
            await state.update_data(new_test_current_options=[])
            await state.set_state(LearningPathStates.creating_test_question_options)
        elif q_type == 'yes_no':
            text = (
                f"🗺️<b>РЕДАКТОР ТРАЕКТОРИЙ</b>🗺️\n"
                "➕Создание траектории\n"
                f"{trajectory_progress}"
                "🟡<b>Создание теста</b>\n\n"
                "✅ Текст вопроса принят. Теперь выбери, какой ответ является правильным:"
            )
            await message.answer(
                text, 
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="👍 Да", callback_data="answer_bool:Да")],
                    [InlineKeyboardButton(text="👎 Нет", callback_data="answer_bool:Нет")]
                ])
            )
            await state.set_state(LearningPathStates.creating_test_question_answer)
        elif q_type == 'number':
            text = (
                f"🗺️<b>РЕДАКТОР ТРАЕКТОРИЙ</b>🗺️\n"
                "➕Создание траектории\n"
                f"{trajectory_progress}"
                "🟡<b>Создание теста</b>\n\n"
                "✅ Текст вопроса принят. Теперь введи правильный ответ (число):"
            )
            await message.answer(text, parse_mode="HTML")
            await state.set_state(LearningPathStates.creating_test_question_answer)
        
    except Exception as e:
        await message.answer("Произошла ошибка при обработке текста вопроса")
        log_user_error(message.from_user.id, "question_text_error", str(e))


@router.message(LearningPathStates.creating_test_question_options)
async def process_question_option(message: Message, state: FSMContext, session: AsyncSession):
    """Обработка одного варианта ответа и запрос следующего"""
    try:
        data = await state.get_data()
        options = data.get('new_test_current_options') or []
        
        # Проверка на дубликаты вариантов
        if message.text.strip() in options:
            await message.answer("❌ Такой вариант уже есть. Введи другой.")
            return

        options.append(message.text.strip())
        await state.update_data(new_test_current_options=options)
        
        trajectory_data = data.get('trajectory_data', {})
        trajectory_progress = generate_trajectory_progress(trajectory_data)
        current_options_text = "\n".join([f"  <b>{i+1}.</b> {opt}" for i, opt in enumerate(options)])
        
        if len(options) < 2:
            text = (
                f"🗺️<b>РЕДАКТОР ТРАЕКТОРИЙ</b>🗺️\n"
                "➕Создание траектории\n"
                f"{trajectory_progress}"
                "🟡<b>Создание теста</b>\n\n"
                f"✅ Вариант добавлен.\n\n<b>Текущие варианты:</b>\n{current_options_text}\n\n"
                "Введи **следующий вариант** ответа:"
            )
            await message.answer(text, parse_mode="HTML")
        else:
            text = (
                f"🗺️<b>РЕДАКТОР ТРАЕКТОРИЙ</b>🗺️\n"
                "➕Создание траектории\n"
                f"{trajectory_progress}"
                "🟡<b>Создание теста</b>\n\n"
                f"✅ Вариант добавлен.\n\n<b>Текущие варианты:</b>\n{current_options_text}\n\n"
                "Введи **следующий** или нажми 'Завершить'."
            )
            await message.answer(
                text, 
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="✅ Завершить добавление вариантов", callback_data="finish_trajectory_options")]
                ])
            )
        
    except Exception as e:
        await message.answer("Произошла ошибка при обработке варианта")
        log_user_error(message.from_user.id, "question_option_error", str(e))


@router.callback_query(LearningPathStates.creating_test_question_answer, F.data.startswith("answer_bool:"))
async def process_trajectory_bool_answer(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Обработка выбора правильного ответа для Да/Нет в траектории"""
    try:
        answer = callback.data.split(':')[1]
        await state.update_data(new_test_question_answer=answer)
        
        data = await state.get_data()
        trajectory_data = data.get('trajectory_data', {})
        trajectory_progress = generate_trajectory_progress(trajectory_data)
        
        text = (
            f"🗺️<b>РЕДАКТОР ТРАЕКТОРИЙ</b>🗺️\n"
            "➕Создание траектории\n"
            f"{trajectory_progress}"
            "🟡<b>Создание теста</b>\n\n"
            "🔢 Теперь укажите, сколько баллов можно получить за правильный ответ на этот вопрос.\n"
            "Ты можешь использовать дробные числа, например, 0.5 или 1.5."
        )
        
        await callback.message.edit_text(text, parse_mode="HTML")
        await state.set_state(LearningPathStates.creating_test_question_points)
        await callback.answer()
        
    except Exception as e:
        await callback.answer("Произошла ошибка")
        log_user_error(callback.from_user.id, "trajectory_bool_answer_error", str(e))


@router.callback_query(LearningPathStates.creating_test_question_options, F.data == "finish_trajectory_options")
async def finish_adding_trajectory_options(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Завершение добавления вариантов и переход к выбору правильного"""
    try:
        data = await state.get_data()
        options = data.get('new_test_current_options') or []
        q_type = data.get('new_test_question_type')
        trajectory_data = data.get('trajectory_data', {})
        trajectory_progress = generate_trajectory_progress(trajectory_data)
        
        if q_type == 'single_choice':
            # Для одного правильного ответа
            options_text = "\n".join([f"{i+1}. {opt}" for i, opt in enumerate(options)])
            text = (
                f"🗺️<b>РЕДАКТОР ТРАЕКТОРИЙ</b>🗺️\n"
                "➕Создание траектории\n"
                f"{trajectory_progress}"
                "🟡<b>Создание теста</b>\n\n"
                f"✅ Варианты приняты. Вот они:\n\n{options_text}\n\n"
                "Теперь введи **номер** правильного ответа (например: 2):"
            )
            await callback.message.edit_text(text, parse_mode="HTML")
            await state.set_state(LearningPathStates.creating_test_question_answer)
        elif q_type == 'multiple_choice':
            # Для нескольких правильных ответов
            options_text = "\n".join([f"{i+1}. {opt}" for i, opt in enumerate(options)])
            text = (
                f"🗺️<b>РЕДАКТОР ТРАЕКТОРИЙ</b>🗺️\n"
                "➕Создание траектории\n"
                f"{trajectory_progress}"
                "🟡<b>Создание теста</b>\n\n"
                f"✅ Варианты приняты. Вот они:\n\n{options_text}\n\n"
                "Теперь введи **номера** правильных ответов через запятую (например: 1, 3):"
            )
            await callback.message.edit_text(text, parse_mode="HTML")
            await state.set_state(LearningPathStates.creating_test_question_answer)
        
        await callback.answer()
        
    except Exception as e:
        await callback.answer("Произошла ошибка")
        log_user_error(callback.from_user.id, "finish_trajectory_options_error", str(e))


@router.message(LearningPathStates.creating_test_question_answer)
async def process_question_answer(message: Message, state: FSMContext, session: AsyncSession):
    """Обработка ответа на вопрос"""
    try:
        data = await state.get_data()
        q_type = data.get('new_test_question_type')
        answer = message.text.strip()
        
        if not answer:
            await message.answer("❌ Ответ не может быть пустым. Попробуй еще раз:")
            return
        
        # Обрабатываем ответ в зависимости от типа вопроса
        if q_type == 'single_choice':
            try:
                index = int(answer) - 1
                options = data.get('new_test_current_options') or []
                if not (0 <= index < len(options)):
                    raise ValueError
                answer = options[index]
            except (ValueError, IndexError):
                await message.answer("❌ Некорректный номер. Введи номер правильного ответа (например: 2):")
                return
        elif q_type == 'multiple_choice':
            try:
                indices = [int(i.strip()) - 1 for i in answer.split(',')]
                options = data.get('new_test_current_options') or []
                correct_answers = [options[i] for i in indices if 0 <= i < len(options)]
                if not correct_answers:
                    raise ValueError
                answer = correct_answers
            except (ValueError, IndexError):
                await message.answer("❌ Некорректный формат. Введи номера через запятую (например: 1, 3):")
                return
        
        await state.update_data(new_test_question_answer=answer)
        
        # Получаем прогресс траектории
        trajectory_data = data.get('trajectory_data', {})
        trajectory_progress = generate_trajectory_progress(trajectory_data)
        
        text = (
            f"🗺️<b>РЕДАКТОР ТРАЕКТОРИЙ</b>🗺️\n"
            "➕Создание траектории\n"
            f"{trajectory_progress}"
            "🟡<b>Создание теста</b>\n\n"
            "🔢 Теперь укажите, сколько баллов можно получить за правильный ответ на этот вопрос.\n"
            "Ты можешь использовать дробные числа, например, 0.5 или 1.5."
        )
        
        await message.answer(text, parse_mode="HTML")
        await state.set_state(LearningPathStates.creating_test_question_points)
        
    except Exception as e:
        await message.answer("Произошла ошибка при обработке ответа")
        log_user_error(message.from_user.id, "question_answer_error", str(e))


@router.message(LearningPathStates.creating_test_question_points)
async def process_question_points(message: Message, state: FSMContext, session: AsyncSession):
    """Обработка баллов за вопрос"""
    try:
        try:
            points = float(message.text.strip())
            if points <= 0:
                raise ValueError("Баллы должны быть положительным числом")
        except ValueError:
            await message.answer("❌ Введи корректное число баллов (например: 1 или 1.5)")
            return
        
        # Сохраняем вопрос
        data = await state.get_data()
        existing_questions = data.get('new_test_questions') or []

        # Создаем новый вопрос
        new_question = {
            'question_number': len(existing_questions) + 1,
            'question_type': data.get('new_test_question_type'),
            'question_text': data.get('new_test_question_text'),
            'correct_answer': data.get('new_test_question_answer'),
            'points': points,
            'options': data.get('new_test_current_options', [])
        }

        # Добавляем к существующим вопросам
        existing_questions.append(new_question)

        # Пересчитываем общий балл
        total_score = sum(q['points'] for q in existing_questions)

        await state.update_data(
            new_test_question_points=points,
            new_test_questions=existing_questions,
            new_test_total_score=total_score
        )
        
        # Получаем прогресс траектории
        trajectory_data = data.get('trajectory_data', {})
        trajectory_progress = generate_trajectory_progress(trajectory_data)
        
        text = (
            f"🗺️<b>РЕДАКТОР ТРАЕКТОРИЙ</b>🗺️\n"
            "➕Создание траектории\n"
            f"{trajectory_progress}"
            "🟡<b>Создание теста</b>\n\n"
            f"✅ Вопрос №{len(existing_questions)} добавлен!\n"
            "Текущая статистика теста:\n"
            f" • Количество вопросов: {len(existing_questions)}\n"
            f" • Максимальный балл: {total_score:.1f}\n"
            "❓ Хотите добавить еще один вопрос?"
        )
        
        await message.answer(
            text,
            reply_markup=get_more_questions_keyboard(),
            parse_mode="HTML"
        )
        
        await state.set_state(LearningPathStates.creating_test_more_questions)
        
    except Exception as e:
        await message.answer("Произошла ошибка при обработке баллов")
        log_user_error(message.from_user.id, "question_points_error", str(e))


@router.callback_query(F.data == "add_more_questions", LearningPathStates.creating_test_more_questions)
async def callback_add_more_questions(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Добавление еще одного вопроса к тесту в траектории"""
    try:
        await callback.answer()

        # Очищаем временные данные предыдущего вопроса
        data = await state.get_data()
        await state.update_data(
            new_test_question_type=None,
            new_test_question_text=None,
            new_test_question_answer=None,
            new_test_current_options=[],
            new_test_question_points=None
        )

        # Показываем выбор типа вопроса для следующего вопроса
        await show_question_type_step(callback.message, state)

        log_user_action(callback.from_user.id, "trajectory_test_add_more_questions", "Добавление еще одного вопроса к тесту в траектории")

    except Exception as e:
        await callback.message.edit_text("❌ Произошла ошибка при добавлении вопроса")
        log_user_error(callback.from_user.id, "trajectory_add_more_questions_error", str(e))


@router.callback_query(F.data == "finish_questions", LearningPathStates.creating_test_more_questions)
async def callback_finish_questions(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Завершение добавления вопросов и переход к проходному баллу"""
    try:
        await callback.answer()
        
        data = await state.get_data()
        total_score = data.get('new_test_total_score', 0)
        
        # Получаем прогресс траектории
        trajectory_data = data.get('trajectory_data', {})
        trajectory_progress = generate_trajectory_progress(trajectory_data)
        
        text = (
            f"🗺️<b>РЕДАКТОР ТРАЕКТОРИЙ</b>🗺️\n"
            "➕Создание траектории\n"
            f"{trajectory_progress}"
            "🟡<b>Создание теста</b>\n\n"
            "✅ Добавление вопросов завершено.\n"
            f"Максимальный балл за тест: {total_score:.1f}\n"
            f"Теперь введи проходной балл для этого теста (число от 0.5 до {total_score:.1f}):"
        )
        
        await callback.message.edit_text(text, parse_mode="HTML")
        await state.set_state(LearningPathStates.creating_test_threshold)
        
    except Exception as e:
        await callback.answer("Произошла ошибка")
        log_user_error(callback.from_user.id, "finish_questions_error", str(e))


@router.message(LearningPathStates.creating_test_threshold)
async def process_test_threshold(message: Message, state: FSMContext, session: AsyncSession):
    """Обработка проходного балла и создание теста"""
    try:
        try:
            threshold = float(message.text.strip())
            data = await state.get_data()
            total_score = data.get('new_test_total_score', 0)
            
            if threshold < 0.5 or threshold > total_score:
                raise ValueError(f"Проходной балл должен быть от 0.5 до {total_score:.1f}")
        except ValueError as e:
            await message.answer(f"❌ {str(e)}")
            return
        
        # Создаем тест в базе данных
        test_data = {
            'name': data.get('new_test_name'),
            'description': data.get('new_test_description', ''),
            'threshold_score': threshold,
            'max_score': data.get('new_test_total_score'),
            'material_link': data.get('new_test_materials', ''),
            'creator_id': data.get('trajectory_data', {}).get('created_by_id'),
            'stage_id': None
        }
        
        test = await create_test(session, test_data)
        if not test:
            await message.answer("❌ Ошибка создания теста")
            return
        
        # Добавляем вопросы к тесту
        questions = data.get('new_test_questions') or []
        for question_data in questions:
            question_data['test_id'] = test.id
            await add_question_to_test(session, question_data)
        
        # Добавляем тест к текущей сессии
        trajectory_data = data.get('trajectory_data', {})
        if trajectory_data.get('stages'):
            last_stage = trajectory_data['stages'][-1]
            if last_stage.get('sessions'):
                last_session = last_stage['sessions'][-1]
                last_session['tests'].append({
                    'id': test.id,
                    'name': test.name,
                    'order': len(last_session['tests']) + 1
                })
        
        await state.update_data(trajectory_data=trajectory_data)
        
        # Показываем успешное создание и выбор следующих действий
        trajectory_progress = generate_trajectory_progress(trajectory_data)
        percentage = (threshold / data.get('new_test_total_score', 1)) * 100
        
        text = (
            f"🗺️<b>РЕДАКТОР ТРАЕКТОРИЙ</b>🗺️\n"
            "➕Создание траектории\n"
            f"{trajectory_progress}"
            "🟡<b>Добавить тест к Сессии?</b>\n\n"
            f"✅ Тест «{test.name}» успешно создан и добавлен к Сессии!\n"
            f"📝 Вопросов добавлено: {len(questions)}\n"
            f"📊 Максимальный балл: {data.get('new_test_total_score'):.1f}\n"
            f"🎯 Проходной балл: {threshold:.1f} ({percentage:.1f}%)"
        )
        
        # Получаем обновленный список тестов
        tests = await get_all_active_tests(session)
        current_session_tests = []
        if trajectory_data.get('stages'):
            last_stage = trajectory_data['stages'][-1]
            if last_stage.get('sessions'):
                last_session = last_stage['sessions'][-1]
                current_session_tests = last_session.get('tests', [])
        
        await message.answer(
            text,
            reply_markup=get_test_selection_keyboard(tests, current_session_tests),
            parse_mode="HTML"
        )
        
        await state.set_state(LearningPathStates.waiting_for_test_selection)
        
        # Очищаем временные данные теста
        await state.update_data(
            new_test_name=None,
            new_test_description=None,
            new_test_materials=None,
            new_test_question_type=None,
            new_test_question_text=None,
            new_test_question_answer=None,
            new_test_question_points=None,
            new_test_questions=[],
            new_test_total_score=None
        )
        
    except Exception as e:
        await message.answer("Произошла ошибка при создании теста")
        log_user_error(message.from_user.id, "test_threshold_error", str(e))


@router.callback_query(F.data.startswith("select_test:"), LearningPathStates.waiting_for_test_selection)
async def callback_select_existing_test(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Выбор существующего теста для сессии"""
    try:
        await callback.answer()
        
        test_id = int(callback.data.split(":")[1])
        
        # Получаем информацию о тесте
        tests = await get_all_active_tests(session)
        selected_test = next((t for t in tests if t.id == test_id), None)
        
        if not selected_test:
            await callback.answer("Тест не найден", show_alert=True)
            return
        
        # Добавляем тест к текущей сессии
        data = await state.get_data()
        trajectory_data = data.get('trajectory_data', {})
        
        if trajectory_data.get('stages'):
            last_stage = trajectory_data['stages'][-1]
            if last_stage.get('sessions'):
                last_session = last_stage['sessions'][-1]
                last_session['tests'].append({
                    'id': test_id,
                    'name': selected_test.name,
                    'order': len(last_session['tests']) + 1
                })
        
        await state.update_data(trajectory_data=trajectory_data)
        
        # Показываем обновленную информацию
        trajectory_progress = generate_trajectory_progress(trajectory_data)
        
        text = (
            f"🗺️<b>РЕДАКТОР ТРАЕКТОРИЙ</b>🗺️\n"
            "➕Создание траектории\n"
            f"{trajectory_progress}"
            "🟡<b>Добавить тест к Сессии?</b>"
        )
        
        # Получаем текущие тесты в сессии
        current_session_tests = []
        if trajectory_data.get('stages'):
            last_stage = trajectory_data['stages'][-1]
            if last_stage.get('sessions'):
                last_session = last_stage['sessions'][-1]
                current_session_tests = last_session.get('tests', [])
        
        await callback.message.edit_text(
            text,
            reply_markup=get_test_selection_keyboard(tests, current_session_tests),
            parse_mode="HTML"
        )
        
    except Exception as e:
        await callback.answer("Произошла ошибка")
        log_user_error(callback.from_user.id, "select_test_error", str(e))


@router.callback_query(F.data == "save_session", LearningPathStates.waiting_for_test_selection)
async def callback_save_session(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Сохранение сессии и переход к управлению этапами"""
    try:
        await callback.answer()
        
        # Получаем данные траектории
        data = await state.get_data()
        trajectory_data = data.get('trajectory_data', {})
        current_stage_number = data.get('current_stage_number', 1)
        current_session_number = data.get('current_session_number', 1)
        
        # Подсчитываем количество созданных сессий
        sessions_count = 0
        if trajectory_data.get('stages'):
            last_stage = trajectory_data['stages'][-1]
            sessions_count = len(last_stage.get('sessions', []))
        
        trajectory_progress = generate_trajectory_progress(trajectory_data)
        
        text = (
            f"🗺️<b>РЕДАКТОР ТРАЕКТОРИЙ</b>🗺️\n"
            "➕Создание траектории\n"
            f"{trajectory_progress}\n"
            f"✅Ты Создал {sessions_count} Сессию для {current_stage_number} Этапа!\n\n"
            "🟡Хотите добавить ещё сессию?"
        )
        
        await callback.message.edit_text(
            text,
            reply_markup=get_session_management_keyboard(),
            parse_mode="HTML"
        )
        
        await state.set_state(LearningPathStates.adding_session_to_stage)
        
    except Exception as e:
        await callback.answer("Произошла ошибка")
        log_user_error(callback.from_user.id, "save_session_error", str(e))


@router.callback_query(F.data == "add_session", LearningPathStates.adding_session_to_stage)
async def callback_add_session(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Добавление новой сессии к текущему этапу"""
    try:
        await callback.answer()
        
        # Увеличиваем номер сессии
        data = await state.get_data()
        current_session_number = data.get('current_session_number', 1) + 1
        await state.update_data(current_session_number=current_session_number)
        
        # Получаем прогресс траектории
        trajectory_data = data.get('trajectory_data', {})
        trajectory_progress = generate_trajectory_progress(trajectory_data)
        
        text = (
            f"🗺️<b>РЕДАКТОР ТРАЕКТОРИЙ</b>🗺️\n"
            "➕Создание траектории\n"
            f"{trajectory_progress}"
            f"🟡<b>Сессия {current_session_number}:</b> отправь название\n\n"
            f"Введи название для сессии {current_session_number}"
        )
        
        await callback.message.edit_text(text, parse_mode="HTML")
        await state.set_state(LearningPathStates.waiting_for_session_name)
        
    except Exception as e:
        await callback.answer("Произошла ошибка")
        log_user_error(callback.from_user.id, "add_session_error", str(e))


@router.callback_query(F.data == "add_stage", LearningPathStates.adding_session_to_stage)
async def callback_add_stage(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Добавление нового этапа к траектории"""
    try:
        await callback.answer()
        
        # Увеличиваем номер этапа
        data = await state.get_data()
        current_stage_number = data.get('current_stage_number', 1) + 1
        await state.update_data(
            current_stage_number=current_stage_number,
            current_session_number=1  # Сбрасываем счетчик сессий
        )
        
        # Получаем прогресс траектории
        trajectory_data = data.get('trajectory_data', {})
        trajectory_progress = generate_trajectory_progress(trajectory_data)
        
        text = (
            f"🗺️<b>РЕДАКТОР ТРАЕКТОРИЙ</b>🗺️\n"
            "➕Создание траектории\n"
            f"{trajectory_progress}"
            f"🟡<b>Этап {current_stage_number}:</b> отправь название\n\n"
            f"Введи название для Этапа {current_stage_number}"
        )
        
        await callback.message.edit_text(text, parse_mode="HTML")
        await state.set_state(LearningPathStates.waiting_for_stage_name)
        
    except Exception as e:
        await callback.answer("Произошла ошибка")
        log_user_error(callback.from_user.id, "add_stage_error", str(e))


@router.callback_query(F.data == "save_trajectory", LearningPathStates.adding_session_to_stage)
async def callback_save_trajectory(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Сохранение траектории и переход к выбору аттестации"""
    try:
        await callback.answer()
        
        # Получаем данные траектории
        data = await state.get_data()
        trajectory_data = data.get('trajectory_data', {})
        trajectory_progress = generate_trajectory_progress(trajectory_data)
        
        text = (
            f"🗺️<b>РЕДАКТОР ТРАЕКТОРИЙ</b>🗺️\n"
            "➕Создание траектории\n"
            f"{trajectory_progress}\n"
            "Сохранить созданную траекторию?"
        )
        
        await callback.message.edit_text(
            text,
            reply_markup=get_trajectory_save_confirmation_keyboard(),
            parse_mode="HTML"
        )
        
        await state.set_state(LearningPathStates.waiting_for_trajectory_save_confirmation)
        
    except Exception as e:
        await callback.answer("Произошла ошибка")
        log_user_error(callback.from_user.id, "save_trajectory_error", str(e))


@router.callback_query(F.data == "confirm_trajectory_save", LearningPathStates.waiting_for_trajectory_save_confirmation)
async def callback_confirm_trajectory_save(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Подтверждение сохранения траектории и переход к выбору аттестации"""
    try:
        await callback.answer()
        
        # Получаем аттестации
        attestations = await get_all_attestations(session)
        
        if not attestations:
            await callback.message.edit_text(
                "❌ <b>Нет доступных аттестаций</b>\n\n"
                "Сначала создай хотя бы одну аттестацию.",
                parse_mode="HTML",
                reply_markup=get_main_menu_keyboard()
            )
            return
        
        # Получаем прогресс траектории
        data = await state.get_data()
        trajectory_data = data.get('trajectory_data', {})
        trajectory_progress = generate_trajectory_progress(trajectory_data)
        
        text = (
            f"🗺️<b>РЕДАКТОР ТРАЕКТОРИЙ</b>🗺️\n"
            "➕Создание траектории\n"
            f"{trajectory_progress}"
            "🔍🟡<b>Аттестация:</b> выбери тест для аттестации\n\n"
            "Подсказка: Аттестация - последний обязательный этап траектории (как экзамен или контрольная в школе), выбери один из вариантов аттестации, которые подготовили ранее, чтобы добавить его к текущей траектории"
        )
        
        await callback.message.edit_text(
            text,
            reply_markup=get_attestation_selection_keyboard(attestations),
            parse_mode="HTML"
        )
        
        await state.set_state(LearningPathStates.waiting_for_attestation_selection)
        
    except Exception as e:
        await callback.answer("Произошла ошибка")
        log_user_error(callback.from_user.id, "confirm_trajectory_save_error", str(e))


@router.callback_query(F.data.startswith("select_attestation:"), LearningPathStates.waiting_for_attestation_selection)
async def callback_select_attestation(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Выбор аттестации для траектории"""
    try:
        await callback.answer()
        
        attestation_id = int(callback.data.split(":")[1])
        
        # Получаем аттестацию
        attestation = await get_attestation_by_id(session, attestation_id)
        if not attestation:
            await callback.answer("Аттестация не найдена", show_alert=True)
            return
        
        await state.update_data(selected_attestation_id=attestation_id)
        
        # Получаем прогресс траектории
        data = await state.get_data()
        trajectory_data = data.get('trajectory_data', {})
        trajectory_progress = generate_trajectory_progress(trajectory_data)
        
        text = (
            f"🗺️<b>РЕДАКТОР ТРАЕКТОРИЙ</b>🗺️\n"
            "➕Создание траектории\n"
            f"{trajectory_progress}"
            f"🔍🟢<b>Аттестация:</b> {attestation.name}\n\n"
            "🟡Сохранить траекторию с Аттестацией?"
        )
        
        await callback.message.edit_text(
            text,
            reply_markup=get_trajectory_attestation_confirmation_keyboard(),
            parse_mode="HTML"
        )
        
        await state.set_state(LearningPathStates.waiting_for_attestation_confirmation)
        
    except Exception as e:
        await callback.answer("Произошла ошибка")
        log_user_error(callback.from_user.id, "select_attestation_error", str(e))


@router.callback_query(F.data == "confirm_attestation_and_proceed", LearningPathStates.waiting_for_attestation_confirmation)
async def callback_confirm_attestation_and_proceed(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """ПУНКТ 50 ТЗ: Подтверждение аттестации кнопкой 'Да' и переход к выбору группы"""
    try:
        await callback.answer()
        
        # Получаем группы
        groups = await get_all_groups(session)
        if not groups:
            await callback.answer("Нет доступных групп. Создай группу сначала.", show_alert=True)
            return
        
        # ПУНКТ 52 ТЗ: Точное сообщение
        text = "Выбери группу наставников, которым будет доступна траектория"
        
        await callback.message.edit_text(
            text,
            reply_markup=get_group_selection_keyboard(groups, page=0),
            parse_mode="HTML"
        )
        
        # Сохраняем что мы в процессе финального сохранения
        await state.update_data(finalizing_trajectory=True)
        
    except Exception as e:
        await callback.answer("Произошла ошибка")
        log_user_error(callback.from_user.id, "confirm_attestation_and_proceed_error", str(e))


@router.callback_query(F.data.startswith("select_group:"))
async def callback_select_group_for_trajectory(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Выбор группы для траектории (только если мы в процессе финализации)"""
    try:
        # Проверяем что мы в процессе финализации траектории
        data = await state.get_data()
        if not data.get('finalizing_trajectory'):
            return  # Игнорируем, если это не наш callback
        
        await callback.answer()
        
        group_id = int(callback.data.split(":")[1])
        attestation_id = data.get('selected_attestation_id')
        trajectory_data = data.get('trajectory_data', {})
        
        # Получаем название группы и аттестации
        groups = await get_all_groups(session)
        selected_group = next((g for g in groups if g.id == group_id), None)
        group_name = selected_group.name if selected_group else "Неизвестная группа"
        
        attestations = await get_all_attestations(session)
        selected_attestation = next((a for a in attestations if a.id == attestation_id), None)
        attestation_name = selected_attestation.name if selected_attestation else "Неизвестная аттестация"
        
        # Сохраняем данные группы и аттестации
        await state.update_data(
            selected_group_id=group_id,
            selected_group_name=group_name,
            selected_attestation_name=attestation_name
        )
        
        # ПО ТЗ ПУНКТ 54: Показываем ВСЮ информацию с группой + подтверждение
        trajectory_progress = generate_trajectory_progress(trajectory_data)
        
        text = (
            f"🗺️<b>РЕДАКТОР ТРАЕКТОРИЙ</b>🗺️\n"
            "➕Создание траектории\n"
            f"{trajectory_progress}"
            f"🔍🟢<b>Аттестация:</b> {attestation_name}\n"
            f"🗂️<b>Группа:</b> {group_name}\n\n"
            "🟡Сохранить траекторию?"
        )
        
        await callback.message.edit_text(
            text,
            reply_markup=get_trajectory_final_confirmation_keyboard(),
            parse_mode="HTML"
        )
        
        await state.set_state(LearningPathStates.waiting_for_final_save_confirmation)
        
    except Exception as e:
        await callback.answer("Произошла ошибка")
        log_user_error(callback.from_user.id, "select_group_trajectory_error", str(e))


@router.callback_query(F.data == "final_confirm_save", LearningPathStates.waiting_for_final_save_confirmation)
async def callback_final_confirm_save(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """ПУНКТ 55 ТЗ: Финальное сохранение траектории"""
    try:
        await callback.answer()
        
        # Получаем все данные
        data = await state.get_data()
        trajectory_data = data.get('trajectory_data', {})
        attestation_id = data.get('selected_attestation_id')
        group_id = data.get('selected_group_id')
        
        # Финально сохраняем траекторию
        success = await save_trajectory_with_attestation_and_group(
            session, trajectory_data, attestation_id, group_id
        )
        
        if not success:
            await callback.answer("Ошибка сохранения траектории", show_alert=True)
            return
        
        # ПУНКТ 56 ТЗ: Точное сообщение согласно ТЗ
        text = (
            "✅Ты успешно создал новую траекторию обучения\n"
            f"🟢<b>Название траектории:</b> {trajectory_data['name']}\n\n"
            "\nТеперь ты можешь передать её наставникам"
        )
        
        await callback.message.edit_text(text, parse_mode="HTML")
        
        # Очищаем состояние
        await state.clear()
        
        log_user_action(callback.from_user.id, "trajectory_created_final", f"Финально создана траектория: {trajectory_data['name']}")
        
    except Exception as e:
        await callback.answer("Произошла ошибка")
        log_user_error(callback.from_user.id, "final_confirm_save_error", str(e))


@router.callback_query(F.data == "cancel_final_confirmation", LearningPathStates.waiting_for_final_save_confirmation)
async def callback_cancel_final_confirmation(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Отмена финального подтверждения (пункт 54 ТЗ)"""
    try:
        await callback.answer()
        
        # Возвращаемся к выбору группы
        groups = await get_all_groups(session)
        if not groups:
            await callback.answer("Нет доступных групп", show_alert=True)
            return
        
        text = "Выбери группу наставников, которым будет доступна траектория"
        
        await callback.message.edit_text(
            text,
            reply_markup=get_group_selection_keyboard(groups, page=0),
            parse_mode="HTML"
        )
        
        await state.set_state(LearningPathStates.waiting_for_group_selection)
        
    except Exception as e:
        await callback.answer("Произошла ошибка")
        log_user_error(callback.from_user.id, "cancel_final_confirmation_error", str(e))


@router.callback_query(F.data == "cancel_trajectory_save", LearningPathStates.waiting_for_trajectory_save_confirmation)
async def callback_cancel_trajectory_save(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Отмена сохранения траектории"""
    try:
        await callback.answer()
        
        # Возвращаемся к управлению сессиями
        data = await state.get_data()
        trajectory_data = data.get('trajectory_data', {})
        current_stage_number = data.get('current_stage_number', 1)
        
        # Подсчитываем количество созданных сессий
        sessions_count = 0
        if trajectory_data.get('stages'):
            last_stage = trajectory_data['stages'][-1]
            sessions_count = len(last_stage.get('sessions', []))
        
        trajectory_progress = generate_trajectory_progress(trajectory_data)
        
        text = (
            f"🗺️<b>РЕДАКТОР ТРАЕКТОРИЙ</b>🗺️\n"
            "➕Создание траектории\n"
            f"{trajectory_progress}\n"
            f"✅Ты Создал {sessions_count} Сессию для {current_stage_number} Этапа!\n\n"
            "🟡Хотите добавить ещё сессию?"
        )
        
        await callback.message.edit_text(
            text,
            reply_markup=get_session_management_keyboard(),
            parse_mode="HTML"
        )
        
        await state.set_state(LearningPathStates.adding_session_to_stage)
        
    except Exception as e:
        await callback.answer("Произошла ошибка")
        log_user_error(callback.from_user.id, "cancel_trajectory_save_error", str(e))


@router.callback_query(F.data == "cancel_attestation_selection", LearningPathStates.waiting_for_attestation_selection)
async def callback_cancel_attestation_selection(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Отмена выбора аттестации"""
    try:
        await callback.answer()
        
        # Возвращаемся к подтверждению сохранения траектории
        data = await state.get_data()
        trajectory_data = data.get('trajectory_data', {})
        trajectory_progress = generate_trajectory_progress(trajectory_data)
        
        text = (
            f"🗺️<b>РЕДАКТОР ТРАЕКТОРИЙ</b>🗺️\n"
            "➕Создание траектории\n"
            f"{trajectory_progress}\n"
            "Сохранить созданную траекторию?"
        )
        
        await callback.message.edit_text(
            text,
            reply_markup=get_trajectory_save_confirmation_keyboard(),
            parse_mode="HTML"
        )
        
        await state.set_state(LearningPathStates.waiting_for_trajectory_save_confirmation)
        
    except Exception as e:
        await callback.answer("Произошла ошибка")
        log_user_error(callback.from_user.id, "cancel_attestation_selection_error", str(e))


@router.callback_query(F.data == "cancel_attestation_confirmation", LearningPathStates.waiting_for_attestation_confirmation)
async def callback_cancel_attestation_confirmation(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """ПУНКТ 49 ТЗ: Отмена подтверждения аттестации"""
    try:
        await callback.answer()
        
        # Возвращаемся к выбору аттестации  
        attestations = await get_all_attestations(session)
        
        # У нас теперь всегда есть mock аттестации
        
        data = await state.get_data()
        trajectory_data = data.get('trajectory_data', {})
        trajectory_progress = generate_trajectory_progress(trajectory_data)
        
        text = (
            f"🗺️<b>РЕДАКТОР ТРАЕКТОРИЙ</b>🗺️\n"
            "➕Создание траектории\n"
            f"{trajectory_progress}"
            "🔍🟡<b>Аттестация:</b> выбери тест для аттестации\n\n"
            "Подсказка: Аттестация - последний обязательный этап траектории (как экзамен или контрольная в школе), выбери один из вариантов аттестации, которые подготовили ранее, чтобы добавить его к текущей траектории"
        )
        
        await callback.message.edit_text(
            text,
            reply_markup=get_attestation_selection_keyboard(attestations),
            parse_mode="HTML"
        )
        
        await state.set_state(LearningPathStates.waiting_for_attestation_selection)
        
    except Exception as e:
        await callback.answer("Произошла ошибка")
        log_user_error(callback.from_user.id, "cancel_attestation_confirmation_error", str(e))


@router.callback_query(F.data == "edit_trajectory", LearningPathStates.main_menu)
async def callback_edit_trajectory(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Просмотр существующих траекторий"""
    try:
        await callback.answer()
        
        # Получаем все траектории
        learning_paths = await get_all_learning_paths(session)
        
        if not learning_paths:
            await callback.answer("Нет созданных траекторий для просмотра", show_alert=True)
            return
        
        text = (
            "🗺️<b>РЕДАКТОР ТРАЕКТОРИЙ</b>🗺️\n"
            "👁️Просмотр траекторий\n\n"
            "Выбери траекторию для просмотра:"
        )
        
        # Создаем клавиатуру с пагинацией (5 траекторий на страницу)
        from keyboards.keyboards import get_trajectory_selection_for_editor_keyboard
        keyboard = get_trajectory_selection_for_editor_keyboard(learning_paths, page=0, per_page=5)
        
        await callback.message.edit_text(
            text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        
        await state.set_state(LearningPathStates.waiting_for_trajectory_selection)
        await state.update_data(all_trajectories=learning_paths, trajectory_page=0)
        
    except Exception as e:
        await callback.answer("Произошла ошибка")
        log_user_error(callback.from_user.id, "edit_trajectory_error", str(e))


# Дублирующий обработчик для кнопки "Назад к траекториям" из состояния просмотра траектории
@router.callback_query(F.data == "edit_trajectory", LearningPathStates.editing_trajectory)
async def callback_back_to_trajectories(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Возврат к списку траекторий из просмотра конкретной траектории"""
    # Переиспользуем логику основного обработчика
    await callback_edit_trajectory(callback, state, session)


@router.callback_query(F.data.startswith("trajectories_page_prev:") | F.data.startswith("trajectories_page_next:"), LearningPathStates.waiting_for_trajectory_selection)
async def callback_trajectories_page(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Навигация по страницам списка траекторий"""
    try:
        await callback.answer()
        
        parts = callback.data.split(":")
        page = int(parts[1])
        
        # Пытаемся получить траектории из кэша state
        data = await state.get_data()
        learning_paths = data.get('all_trajectories')
        
        # Если нет в кэше - получаем из БД
        if not learning_paths:
            learning_paths = await get_all_learning_paths(session)
            if not learning_paths:
                await callback.answer("Нет созданных траекторий для просмотра", show_alert=True)
                return
            await state.update_data(all_trajectories=learning_paths)
        
        text = (
            "🗺️<b>РЕДАКТОР ТРАЕКТОРИЙ</b>🗺️\n"
            "👁️Просмотр траекторий\n\n"
            "Выбери траекторию для просмотра:"
        )
        
        # Создаем клавиатуру с пагинацией (5 траекторий на страницу)
        from keyboards.keyboards import get_trajectory_selection_for_editor_keyboard
        keyboard = get_trajectory_selection_for_editor_keyboard(learning_paths, page=page, per_page=5)
        
        await callback.message.edit_text(
            text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        
        await state.update_data(trajectory_page=page)
        
    except (ValueError, IndexError) as e:
        await callback.answer("Ошибка при обработке данных", show_alert=True)
        log_user_error(callback.from_user.id, "trajectories_page_error", f"Invalid data: {callback.data}, {str(e)}")
    except Exception as e:
        await callback.answer("Произошла ошибка")
        log_user_error(callback.from_user.id, "trajectories_page_error", str(e))


@router.callback_query(F.data.startswith("edit_path:"), LearningPathStates.waiting_for_trajectory_selection)
async def callback_edit_specific_trajectory(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Открытие редактора траектории"""
    try:
        await callback.answer()
        
        path_id = int(callback.data.split(":")[1])
        
        # Перенаправляем в редактор траекторий
        from handlers.trajectory_editor import _show_editor_main_menu
        
        await _show_editor_main_menu(callback.message, state, session, path_id, callback.from_user.id)
        
    except (ValueError, IndexError) as e:
        await callback.answer("Ошибка при обработке данных", show_alert=True)
        log_user_error(callback.from_user.id, "edit_specific_trajectory_error", f"Invalid data: {callback.data}, {str(e)}")
    except Exception as e:
        await callback.answer("Произошла ошибка")
        log_user_error(callback.from_user.id, "edit_specific_trajectory_error", str(e))


# ================== АТТЕСТАЦИИ ==================

@router.callback_query(F.data == "manage_attestations", LearningPathStates.main_menu)
async def callback_manage_attestations(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Управление аттестациями"""
    try:
        await callback.answer()
        
        # Получаем все аттестации
        attestations = await get_all_attestations(session)
        
        text = (
            "🔍<b>РЕДАКТОР АТТЕСТАЦИЙ</b>🔍\n"
            "Выбери нужную тебе аттестацию или создай новую"
        )
        
        await callback.message.edit_text(
            text,
            reply_markup=get_attestations_main_keyboard(attestations),
            parse_mode="HTML"
        )
        
        await state.set_state(AttestationStates.main_menu)
        
    except Exception as e:
        await callback.answer("Произошла ошибка")
        log_user_error(callback.from_user.id, "manage_attestations_error", str(e))


@router.callback_query(F.data == "create_attestation", AttestationStates.main_menu)
async def callback_create_attestation(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """ПУНКТ 5-6 ТЗ: Создание аттестации"""
    try:
        await callback.answer()
        
        # ПУНКТ 6 ТЗ: Точное сообщение с инструкциями
        text = (
            "🔍<b>РЕДАКТОР АТТЕСТАЦИЙ</b>🔍\n"
            "➕Создание аттестации\n"
            "📈<b>ИНСТРУКЦИЯ</b>\n\n"
            "Подсказка: Аттестация - последний обязательный этап траектории (как экзамен или контрольная в школе)\n\n"
            "Аттестацию проводит будущий руководитель лично со стажером\n\n"
            "Связывает будущего руководителя и стажёра - наставник\n\n"
            "Именно наставник после прохождения стажёром всех этапов на проходной балл связывает в Аттестации будущего руководителя и стажёра\n\n"
            "Аттестация проходит в формате опросного теста, который заполняет руководитель\n"
            "Опросный тест - это тест, в котором руководитель читает вопрос у себя на телефоне, затем слушает вживую ответ стажёра и далее вводит балл, на который ответил стажер. После идёт переход к следующему вопросу\n\n"
            "Стажёру в его ЛК приходит только результат аттестации"
        )
        
        await callback.message.edit_text(
            text,
            reply_markup=get_attestation_creation_start_keyboard(),
            parse_mode="HTML"
        )
        
        await state.set_state(AttestationStates.waiting_for_attestation_creation_start)
        
    except Exception as e:
        await callback.answer("Произошла ошибка")
        log_user_error(callback.from_user.id, "create_attestation_error", str(e))


# ================== СОЗДАНИЕ АТТЕСТАЦИЙ ПО ТЗ ==================

@router.callback_query(F.data == "start_attestation_creation", AttestationStates.waiting_for_attestation_creation_start)
async def callback_start_attestation_creation(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """ПУНКТ 7 ТЗ: Кнопка 'Далее⏩'"""
    try:
        await callback.answer()
        
        # ПУНКТ 8 ТЗ: Запрос названия
        text = (
            "🔍<b>РЕДАКТОР АТТЕСТАЦИЙ</b>🔍\n"
            "➕Создание аттестации\n"
            "🟡<b>Название:</b> отправь название"
        )
        
        await callback.message.edit_text(
            text,
            parse_mode="HTML"
        )
        
        await state.set_state(AttestationStates.waiting_for_attestation_name)
        
    except Exception as e:
        await callback.answer("Произошла ошибка")
        log_user_error(callback.from_user.id, "start_attestation_creation_error", str(e))


@router.message(AttestationStates.waiting_for_attestation_name)
async def process_attestation_name(message: Message, state: FSMContext, session: AsyncSession):
    """ПУНКТ 9 ТЗ: Обработка названия аттестации"""
    try:
        name = message.text.strip()
        
        # Валидация названия
        if not validate_name(name):
            await message.answer("❌ Некорректное название. Попробуй еще раз:")
            return
        
        # Сохраняем название
        await state.update_data(attestation_name=name, questions=[])
        
        # ПУНКТ 10 ТЗ: Запрос первого вопроса с примером
        text = (
            "🔍<b>РЕДАКТОР АТТЕСТАЦИЙ</b>🔍\n"
            "➕Создание аттестации\n"
            f"🟢<b>Название:</b> {name}\n"
            "🟡<b>Вопрос 1:</b> введи текст вопроса и описание возможных критериев ответа, например:\n\n"
            "Первый вопрос 👇\n\n"
            "\"Что ты должен проверять в зале на предмет чистоты?\"\n\n"
            "Правильный ответ: Стажер должен в свободной форме перечислить основные точки контроля в течение дня:, столы, подстолья, урны (мусор везде выкинут), десертный холодильник, чистота помещения, чистота зоны самообслуживания.\n\n"
            "Назвал все критерии - 10\n"
            "Назвал половину - 5\n"
            "Ничего/плохо назвал - 0\n\n"
            "💡 <b>Введи ВЕСЬ БЛОК</b> (вопрос + правильный ответ + критерии оценки) как показано в примере"
        )
        
        await message.answer(text, parse_mode="HTML")
        await state.set_state(AttestationStates.waiting_for_attestation_question)
        
        log_user_action(message.from_user.id, "attestation_name_set", f"Название аттестации: {name}")
        
    except Exception as e:
        await message.answer("Произошла ошибка при обработке названия")
        log_user_error(message.from_user.id, "process_attestation_name_error", str(e))


@router.message(AttestationStates.waiting_for_attestation_question)
async def process_attestation_question(message: Message, state: FSMContext, session: AsyncSession):
    """ПУНКТ 11-12-14 ТЗ: Обработка вопросов аттестации"""
    try:
        question_text = message.text.strip()
        
        # Получаем текущие данные
        data = await state.get_data()
        questions = data.get('questions') or []
        attestation_name = data.get('attestation_name', 'Неизвестно')
        
        # Добавляем новый вопрос
        question_number = len(questions) + 1
        questions.append({
            'number': question_number,
            'text': question_text,
            'max_points': 10  # По умолчанию
        })
        
        await state.update_data(questions=questions)
        
        # ПУНКТ 12/14 ТЗ: Показываем прогресс и запрашиваем следующий вопрос
        # Показываем только последние 3 вопроса полностью (чтобы не превысить лимит Telegram)
        questions_text = ""
        recent_questions = questions[-3:] if len(questions) > 3 else questions
        
        for q in recent_questions:
            questions_text += f"✅ <b>Вопрос {q['number']}:</b>\n{q['text']}\n\n"
        
        # Если вопросов больше 3, показываем сколько еще есть
        if len(questions) > 3:
            questions_text = f"📝 <i>Добавлено вопросов: {len(questions) - 3} + показаны последние 3:</i>\n\n" + questions_text
        
        text = (
            "🔍<b>РЕДАКТОР АТТЕСТАЦИЙ</b>🔍\n"
            "➕Создание аттестации\n"
            f"🟢<b>Название:</b> {attestation_name}\n"
            f"📊 <b>Всего вопросов:</b> {question_number}\n\n"
            f"{questions_text}"
            f"🟡<b>Вопрос {question_number + 1}:</b> введи текст вопроса для руководителя\n\n"
            "Для продолжения отправь текст вопроса или сохрани текущие вопросы"
        )
        
        await message.answer(
            text,
            reply_markup=get_attestation_questions_keyboard(),
            parse_mode="HTML"
        )
        
        log_user_action(message.from_user.id, "attestation_question_added", f"Вопрос {question_number}")
        
    except Exception as e:
        await message.answer("Произошла ошибка при обработке вопроса")
        log_user_error(message.from_user.id, "process_attestation_question_error", str(e))


@router.callback_query(F.data == "save_attestation_questions", AttestationStates.waiting_for_attestation_question)
async def callback_save_attestation_questions(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """ПУНКТ 15 ТЗ: Сохранение вопросов аттестации"""
    try:
        await callback.answer()
        
        # Получаем данные
        data = await state.get_data()
        attestation_name = data.get('attestation_name', 'Неизвестно')
        questions = data.get('questions') or []
        
        if not questions:
            await callback.answer("Нет вопросов для сохранения", show_alert=True)
            return
        
        # ПУНКТ 16 ТЗ: Запрос проходного балла  
        text = (
            "🔍<b>РЕДАКТОР АТТЕСТАЦИЙ</b>🔍\n"
            "➕Создание аттестации\n"
            f"🟢<b>Название:</b> {attestation_name}\n\n"
            "✅ Добавление вопросов завершено.\n"
            "Теперь введи проходной балл для аттестации"
        )
        
        await callback.message.edit_text(text, parse_mode="HTML")
        await state.set_state(AttestationStates.waiting_for_passing_score)
        
    except Exception as e:
        await callback.answer("Произошла ошибка")
        log_user_error(callback.from_user.id, "save_attestation_questions_error", str(e))


@router.message(AttestationStates.waiting_for_passing_score)
async def process_attestation_passing_score(message: Message, state: FSMContext, session: AsyncSession):
    """ПУНКТ 17-18 ТЗ: Обработка проходного балла и финализация"""
    try:
        passing_score_text = message.text.strip()
        
        # Валидация числа (ПО ТЗ: может быть любое число, например 10)
        try:
            passing_score = float(passing_score_text)
            if passing_score <= 0:
                await message.answer("❌ Проходной балл должен быть положительным числом")
                return
        except ValueError:
            await message.answer("❌ Введи корректное число (например: 10 или 15)")
            return
        
        # Получаем данные
        data = await state.get_data()
        attestation_name = data.get('attestation_name')
        questions = data.get('questions') or []
        user = await get_user_by_tg_id(session, message.from_user.id)
        
        # Сохраняем вопросы перед созданием аттестации
        if not hasattr(create_attestation, '_pending_questions'):
            create_attestation._pending_questions = {}
        create_attestation._pending_questions['current'] = questions
        
        # Создаем аттестацию в БД
        attestation = await create_attestation(
            session=session,
            name=attestation_name,
            passing_score=passing_score,
            creator_id=user.id
        )
        
        # Добавляем вопросы
        if attestation:
            for question in questions:
                await add_attestation_question(
                    session=session,
                    attestation_id=attestation.id if hasattr(attestation, 'id') else 1,
                    question_text=question['text'],
                    max_points=question['max_points'],
                    question_number=question['number']
                )
        
        # ПУНКТ 18 ТЗ: Точное сообщение об успехе
        text = (
            "🔍<b>РЕДАКТОР АТТЕСТАЦИЙ</b>🔍\n"
            "➕Создание аттестации\n"
            f"🟢<b>Название:</b> {attestation_name}\n\n"
            f"✅ Аттестация «{attestation_name}» успешно создана!\n"
            f"📝 Вопросов добавлено: {len(questions)}\n"
            f"🎯 Проходной балл: {passing_score:.1f}\n\n"
            "Теперь ты можешь добавить данную аттестацию к любой траектории"
        )
        
        await message.answer(text, parse_mode="HTML")
        
        # КРИТИЧНО: После создания показываем обновленный список аттестаций
        updated_attestations = await get_all_attestations(session)
        
        menu_text = (
            "🔍<b>РЕДАКТОР АТТЕСТАЦИЙ</b>🔍\n"
            "Выбери нужную тебе аттестацию или создай новую\n\n"
            f"✅ <b>Аттестация «{attestation_name}» добавлена в список!</b>"
        )
        
        await message.answer(
            menu_text,
            reply_markup=get_attestations_main_keyboard(updated_attestations),
            parse_mode="HTML"
        )
        
        # Переходим в главное меню аттестаций
        await state.set_state(AttestationStates.main_menu)
        
        log_user_action(message.from_user.id, "attestation_created", f"Аттестация: {attestation_name}")
        
    except Exception as e:
        await message.answer("Произошла ошибка при создании аттестации")
        log_user_error(message.from_user.id, "process_attestation_passing_score_error", str(e))


@router.callback_query(F.data.startswith("view_attestation:"), AttestationStates.main_menu)
async def callback_view_attestation(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Просмотр существующей аттестации"""
    try:
        await callback.answer()
        
        attestation_id = int(callback.data.split(":")[1])
        
        # Получаем аттестацию
        attestation = await get_attestation_by_id(session, attestation_id)
        if not attestation:
            await callback.answer("Аттестация не найдена", show_alert=True)
            return
        
        # Сбрасываем страницу при первом открытии
        await state.update_data(current_attestation_id=attestation_id, attestation_page=0)
        
        # Используем универсальную функцию рендеринга
        text, keyboard = await render_attestation_page(session, attestation_id, 0)
        
        await callback.message.edit_text(
            text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        
    except Exception as e:
        await callback.answer("Произошла ошибка")
        log_user_error(callback.from_user.id, "view_attestation_error", str(e))


async def render_attestation_page(session: AsyncSession, attestation_id: int, page: int) -> tuple[str, InlineKeyboardMarkup]:
    """Универсальная функция рендеринга страницы аттестации"""
    attestation = await get_attestation_by_id(session, attestation_id)
    if not attestation:
        raise ValueError("Аттестация не найдена")
    
    questions_per_page = 3
    total_questions = len(attestation.questions)
    total_pages = (total_questions + questions_per_page - 1) // questions_per_page
    
    # Ограничиваем page в пределах допустимого
    page = max(0, min(page, total_pages - 1))
    
    # Генерируем текст
    questions_text = ""
    if attestation.questions:
        start_idx = page * questions_per_page
        end_idx = start_idx + questions_per_page
        page_questions = attestation.questions[start_idx:end_idx]
        
        for question in page_questions:
            questions_text += f"🟢<b>Вопрос {question.question_number}:</b>\n{question.question_text}\n\n"
        
        if total_questions > questions_per_page:
            questions_text += f"📄 <i>Страница {page + 1} из {total_pages}</i>\n\n"
    
    # Информация о траекториях
    using_trajectories = await get_trajectories_using_attestation(session, attestation_id)
    if using_trajectories:
        if len(using_trajectories) == 1:
            trajectories_info = f"🗺️ <b>Используется в траектории:</b> {using_trajectories[0]}\n\n"
        else:
            trajectories_list = "\n".join([f"• {name}" for name in using_trajectories])
            trajectories_info = f"🗺️ <b>Используется в траекториях:</b>\n{trajectories_list}\n\n"
    else:
        trajectories_info = "🗺️ <b>Траектории:</b> Не привязана к траекториям\n\n"
    
    text = (
        "🔍<b>РЕДАКТОР АТТЕСТАЦИЙ</b>🔍\n"
        f"📋 <b>Аттестация:</b> {attestation.name}\n"
        f"📝 <b>Всего вопросов:</b> {total_questions}\n\n"
        f"{questions_text}"
        f"🎯 <b>Проходной балл:</b> {attestation.passing_score:.1f}\n"
        f"📊 <b>Максимальный балл:</b> {getattr(attestation, 'max_score', 20):.1f}\n\n"
        f"{trajectories_info}"
    )
    
    # Создаем клавиатуру
    keyboard_buttons = []
    if total_questions > 3:
        nav_row = []
        if page > 0:
            nav_row.append(InlineKeyboardButton(text="⬅️ Назад", callback_data=f"attestation_page_prev:{attestation_id}"))
        if page < total_pages - 1:
            nav_row.append(InlineKeyboardButton(text="Вперёд ➡️", callback_data=f"attestation_page_next:{attestation_id}"))
        if nav_row:
            keyboard_buttons.append(nav_row)
    
    keyboard_buttons.extend([
        [InlineKeyboardButton(text="🗑️ Удалить", callback_data=f"delete_attestation:{attestation_id}")],
        [InlineKeyboardButton(text="↩️ Назад к аттестациям", callback_data="back_to_attestations_list")],
        [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
    ])
    
    return text, InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)


@router.callback_query(F.data.startswith("attestation_page_prev:"))
async def callback_attestation_page_prev(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Переход на предыдущую страницу вопросов аттестации"""
    try:
        await callback.answer()
        
        attestation_id = int(callback.data.split(":")[1])
        data = await state.get_data()
        current_page = data.get('attestation_page', 0)
        
        new_page = max(0, current_page - 1)
        await state.update_data(attestation_page=new_page)
        
        text, keyboard = await render_attestation_page(session, attestation_id, new_page)
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
        
    except Exception as e:
        await callback.answer("Произошла ошибка")
        log_user_error(callback.from_user.id, "attestation_page_prev_error", str(e))


@router.callback_query(F.data.startswith("attestation_page_next:"))
async def callback_attestation_page_next(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Переход на следующую страницу вопросов аттестации"""
    try:
        await callback.answer()
        
        attestation_id = int(callback.data.split(":")[1])
        data = await state.get_data()
        current_page = data.get('attestation_page', 0)
        
        attestation = await get_attestation_by_id(session, attestation_id)
        if not attestation:
            await callback.answer("Аттестация не найдена", show_alert=True)
            return
        
        total_pages = (len(attestation.questions) + 2) // 3  # 3 вопроса на страницу
        new_page = min(current_page + 1, total_pages - 1)
        await state.update_data(attestation_page=new_page)
        
        text, keyboard = await render_attestation_page(session, attestation_id, new_page)
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
        
    except Exception as e:
        await callback.answer("Произошла ошибка")
        log_user_error(callback.from_user.id, "attestation_page_next_error", str(e))


@router.callback_query(F.data == "back_to_attestations_list")  
async def callback_back_to_attestations_list(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Возврат к списку аттестаций"""
    try:
        await callback.answer()
        
        # Получаем все аттестации
        attestations = await get_all_attestations(session)
        
        text = (
            "🔍<b>РЕДАКТОР АТТЕСТАЦИЙ</b>🔍\n"
            "Выбери нужную тебе аттестацию или создай новую"
        )
        
        await callback.message.edit_text(
            text,
            reply_markup=get_attestations_main_keyboard(attestations),
            parse_mode="HTML"
        )
        
        await state.set_state(AttestationStates.main_menu)
        
    except Exception as e:
        await callback.answer("Произошла ошибка")
        log_user_error(callback.from_user.id, "back_to_attestations_error", str(e))


@router.callback_query(F.data.startswith("delete_attestation:"), AttestationStates.main_menu)
async def callback_delete_attestation_confirm(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Подтверждение удаления аттестации"""
    try:
        await callback.answer()
        
        attestation_id = int(callback.data.split(":")[1])
        
        # Получаем информацию об аттестации
        attestation = await get_attestation_by_id(session, attestation_id)
        if not attestation:
            await callback.answer("Аттестация не найдена", show_alert=True)
            return
        
        # Проверяем, используется ли аттестация в траекториях
        is_in_use = await check_attestation_in_use(session, attestation_id)
        
        if is_in_use:
            # Получаем названия траекторий, использующих эту аттестацию
            trajectory_names = await get_trajectories_using_attestation(session, attestation_id)
            
            # Формируем список траекторий для отображения
            if len(trajectory_names) == 1:
                trajectories_text = f"траектории «{trajectory_names[0]}»"
            else:
                trajectories_list = "\n".join([f"• {name}" for name in trajectory_names])
                trajectories_text = f"следующим траекториям:\n{trajectories_list}"
            
            # Аттестация используется - показываем предупреждение с названиями траекторий
            text = (
                "⚠️ <b>УДАЛЕНИЕ НЕВОЗМОЖНО</b> ⚠️\n\n"
                f"📋 <b>Аттестация:</b> {attestation.name}\n\n"
                f"❌ <b>Данную аттестацию нельзя удалить, поскольку она привязана к {trajectories_text}</b>\n\n"
                "💡 <i>Сначала удали все траектории, использующие эту аттестацию, а затем попробуй снова.</i>"
            )
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="↩️ Назад к аттестации", callback_data=f"view_attestation:{attestation_id}")],
                [InlineKeyboardButton(text="🔍 К списку аттестаций", callback_data="back_to_attestations_list")]
            ])
            
        else:
            # Аттестацию можно удалить - показываем подтверждение
            questions_count = len(attestation.questions) if hasattr(attestation, 'questions') and attestation.questions else 0
            
            text = (
                "⚠️ <b>ПОДТВЕРЖДЕНИЕ УДАЛЕНИЯ</b> ⚠️\n\n"
                f"📋 <b>Аттестация:</b> {attestation.name}\n"
                f"📝 <b>Количество вопросов:</b> {questions_count}\n"
                f"🎯 <b>Проходной балл:</b> {attestation.passing_score:.1f}\n\n"
                "❗ <b>Ты уверен, что хочешь удалить эту аттестацию?</b>\n\n"
                "⚠️ <i>Это действие нельзя будет отменить!</i>"
            )
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🗑️ Да, удалить", callback_data=f"confirm_delete_attestation:{attestation_id}")],
                [InlineKeyboardButton(text="❌ Отменить", callback_data=f"view_attestation:{attestation_id}")]
            ])
        
        await callback.message.edit_text(
            text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        
        if not is_in_use:
            await state.set_state(AttestationStates.waiting_for_delete_confirmation)
            await state.update_data(attestation_id=attestation_id, attestation_name=attestation.name)
        
        log_user_action(callback.from_user.id, "delete_attestation_requested", 
                       f"ID: {attestation_id}, В использовании: {is_in_use}")
        
    except Exception as e:
        await callback.answer("Произошла ошибка")
        log_user_error(callback.from_user.id, "delete_attestation_confirm_error", str(e))


@router.callback_query(F.data.startswith("view_attestation:"), AttestationStates.waiting_for_delete_confirmation)
async def callback_cancel_delete_attestation(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Отмена удаления аттестации - возврат к просмотру"""
    try:
        await callback.answer()
        
        # Возвращаемся в основное состояние
        await state.set_state(AttestationStates.main_menu)
        
        # Перенаправляем к обычному просмотру аттестации
        await callback_view_attestation(callback, state, session)
        
    except Exception as e:
        await callback.answer("Произошла ошибка")
        log_user_error(callback.from_user.id, "cancel_delete_attestation_error", str(e))


@router.callback_query(F.data.startswith("confirm_delete_attestation:"), AttestationStates.waiting_for_delete_confirmation)
async def callback_confirm_delete_attestation(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Окончательное удаление аттестации"""
    try:
        await callback.answer()
        
        attestation_id = int(callback.data.split(":")[1])
        data = await state.get_data()
        attestation_name = data.get('attestation_name', 'Неизвестная аттестация')
        
        # Выполняем удаление
        success = await delete_attestation(session, attestation_id)
        
        if success:
            # Удаление успешно
            text = (
                "✅ <b>АТТЕСТАЦИЯ УДАЛЕНА</b> ✅\n\n"
                f"📋 <b>Аттестация «{attestation_name}» успешно удалена!</b>\n\n"
                "💡 <i>Все вопросы и данные аттестации были удалены из системы.</i>"
            )
            
            await callback.message.edit_text(text, parse_mode="HTML")
            
            # Показываем обновленный список аттестаций
            await asyncio.sleep(2)  # Небольшая пауза для чтения сообщения
            
            attestations = await get_all_attestations(session)
            
            menu_text = (
                "🔍<b>РЕДАКТОР АТТЕСТАЦИЙ</b>🔍\n"
                "Выбери нужную тебе аттестацию или создай новую\n\n"
                f"🗑️ <b>Аттестация «{attestation_name}» удалена из списка</b>"
            )
            
            await callback.message.answer(
                menu_text,
                reply_markup=get_attestations_main_keyboard(attestations),
                parse_mode="HTML"
            )
            
            await state.set_state(AttestationStates.main_menu)
            
            log_user_action(callback.from_user.id, "attestation_deleted", f"'{attestation_name}' (ID: {attestation_id})")
            
        else:
            # Ошибка при удалении
            text = (
                "❌ <b>ОШИБКА УДАЛЕНИЯ</b> ❌\n\n"
                f"📋 <b>Не удалось удалить аттестацию «{attestation_name}»</b>\n\n"
                "Возможные причины:\n"
                "• Аттестация используется в траекториях\n"
                "• Ошибка базы данных\n\n"
                "💡 <i>Попробуй еще раз или обратись к администратору</i>"
            )
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="↩️ Назад к списку", callback_data="back_to_attestations_list")]
            ])
            
            await callback.message.edit_text(
                text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )
            
            log_user_error(callback.from_user.id, "attestation_deletion_failed", f"'{attestation_name}' (ID: {attestation_id})")
        
    except Exception as e:
        await callback.answer("Произошла ошибка")
        log_user_error(callback.from_user.id, "confirm_delete_attestation_error", str(e))


@router.callback_query(F.data == "back_to_trajectories_main", AttestationStates.main_menu)
async def callback_back_to_trajectories_main_from_attestations(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Возврат к главному меню траекторий из аттестаций"""
    try:
        await callback.answer()
        
        # Показываем главное меню траекторий
        text = ("🗺️<b>РЕДАКТОР ТРАЕКТОРИЙ</b>🗺️\n\n"
                "В данном меню ты можешь:\n\n"
                "1 ➕Создать траекторию обучения\n"
                "2 ✏️Изменить траекторию обучения\n"
                "3 🗑️Удалить траекторию обучения")
        
        await callback.message.edit_text(
            text,
            reply_markup=get_learning_paths_main_keyboard(),
            parse_mode="HTML"
        )
        
        await state.set_state(LearningPathStates.main_menu)
        
    except Exception as e:
        await callback.answer("Произошла ошибка")
        log_user_error(callback.from_user.id, "back_to_trajectories_main_from_attestations_error", str(e))


# ================== УДАЛЕНИЕ ТРАЕКТОРИЙ ==================

@router.callback_query(F.data == "delete_trajectory", LearningPathStates.main_menu)
async def callback_delete_trajectory(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Обработчик кнопки удаления траектории"""
    try:
        await callback.answer()
        
        # Получаем все траектории
        trajectories = await get_all_learning_paths(session)
        
        if not trajectories:
            await callback.message.edit_text(
                "🗑️ <b>Удаление траекторий</b>\n\n"
                "В системе нет траекторий для удаления.",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_trajectories_main")]
                ])
            )
            return
        
        # Показываем список траекторий для выбора
        text = "🗑️ <b>Удаление траекторий</b>\n\n"
        text += "Выбери траекторию для удаления:\n\n"
        
        for i, trajectory in enumerate(trajectories, 1):
            text += f"{i}. {trajectory.name}\n"
        
        await callback.message.edit_text(
            text,
            parse_mode="HTML",
            reply_markup=get_trajectory_selection_keyboard(trajectories)
        )
        
        await state.set_state(LearningPathStates.trajectory_deletion)
        log_user_action(callback.from_user.id, "opened_trajectory_deletion", "Открыто меню удаления траекторий")
        
    except Exception as e:
        await callback.answer("Произошла ошибка")
        log_user_error(callback.from_user.id, "delete_trajectory_error", str(e))


@router.callback_query(F.data.startswith("select_trajectory_to_delete:"), LearningPathStates.trajectory_deletion)
async def callback_select_trajectory_to_delete(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Обработчик выбора траектории для удаления"""
    try:
        await callback.answer()
        
        trajectory_id = int(callback.data.split(":")[1])
        trajectory = await get_learning_path_by_id(session, trajectory_id)
        
        if not trajectory:
            await callback.message.edit_text(
                "❌ <b>Ошибка</b>\n\n"
                "Траектория не найдена.",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_trajectory_selection")]
                ])
            )
            return
        
        # Собираем информацию об использовании траектории
        usage_info = await get_trajectory_usage_info(session, trajectory_id)
        
        # Формируем предупреждающее сообщение
        warning_text = f"⚠️ <b>ПРЕДУПРЕЖДЕНИЕ</b> ⚠️\n\n"
        warning_text += f"<b>Траектория:</b> {trajectory.name}\n\n"
        
        if usage_info['total_users'] > 0:
            warning_text += f"⚠️ <b>ВНИМАНИЕ! Эта траектория активно используется:</b>\n\n"
            warning_text += f"👥 <b>Стажеры:</b> {usage_info['trainees_count']} чел.\n"
            warning_text += f"📊 <b>Всего пользователей:</b> {usage_info['total_users']} чел.\n\n"
            
            if usage_info['trainees']:
                warning_text += "<b>Список затронутых стажеров:</b>\n"
                for trainee in usage_info['trainees'][:10]:  # Показываем только первых 10
                    warning_text += f"• {trainee.full_name}\n"
                if len(usage_info['trainees']) > 10:
                    warning_text += f"... и еще {len(usage_info['trainees']) - 10} стажеров\n"
                warning_text += "\n"
        
        warning_text += "⚠️ <b>ПОСЛЕДСТВИЯ УДАЛЕНИЯ:</b>\n\n"
        warning_text += "📚 <b>Для стажеров:</b>\n"
        warning_text += "• ❌ РЕЗУЛЬТАТЫ ТЕСТОВ ТРАЕКТОРИИ БУДУТ ПОТЕРЯНЫ\n"
        warning_text += "• ❌ НЕ СМОГУТ ПРОЙТИ АТТЕСТАЦИЮ ПО ЭТОЙ ТРАЕКТОРИИ\n"
        warning_text += "• ❌ ПОТЕРЯЮТ ДОСТУП К МАТЕРИАЛАМ ЭТОЙ ТРАЕКТОРИИ\n"
        warning_text += "• ❌ ПРОГРЕСС ПО ЭТОЙ ТРАЕКТОРИИ БУДЕТ СБРОШЕН\n"
        warning_text += "• ✅ ТЕСТЫ ОСТАНУТСЯ В СИСТЕМЕ (можно использовать в других траекториях)\n\n"
        
        warning_text += "👨‍🏫 <b>Для наставников:</b>\n"
        warning_text += "• ❌ НЕ СМОГУТ УПРАВЛЯТЬ ПРОГРЕССОМ ПО ЭТОЙ ТРАЕКТОРИИ\n"
        warning_text += "• ❌ ПОТЕРЯЮТ ДОСТУП К МАТЕРИАЛАМ ЭТОЙ ТРАЕКТОРИИ\n"
        warning_text += "• ❌ НЕ СМОГУТ ОТСЛЕЖИВАТЬ ОБУЧЕНИЕ ПО ЭТОЙ ТРАЕКТОРИИ\n\n"
        
        warning_text += "🗂️ <b>Системные изменения:</b>\n"
        warning_text += "• ❌ ЭТАПЫ И СЕССИИ ТРАЕКТОРИИ БУДУТ УДАЛЕНЫ\n"
        warning_text += "• ❌ СВЯЗИ ТЕСТОВ С ТРАЕКТОРИЕЙ БУДУТ УДАЛЕНЫ\n"
        warning_text += "• ❌ РЕЗУЛЬТАТЫ И СТАТИСТИКА ПО ТРАЕКТОРИИ БУДУТ ПОТЕРЯНЫ\n"
        warning_text += "• ❌ СВЯЗИ АТТЕСТАЦИИ С ТРАЕКТОРИЕЙ БУДУТ УДАЛЕНЫ\n"
        warning_text += "• ✅ ТЕСТЫ И ВОПРОСЫ ОСТАНУТСЯ В СИСТЕМЕ\n"
        warning_text += "• ✅ АТТЕСТАЦИИ ОСТАНУТСЯ В СИСТЕМЕ\n\n"
        
        warning_text += "ℹ️ <b>ВАЖНО:</b>\n"
        warning_text += "• ✅ Пользователи останутся в системе\n"
        warning_text += "• ✅ Роли пользователей не изменятся\n"
        warning_text += "• ✅ Наставничество сохранится\n"
        warning_text += "• ✅ Другие траектории не пострадают\n\n"
        
        warning_text += "⚠️ <b>ЭТО ДЕЙСТВИЕ НЕОБРАТИМО!</b>\n"
        warning_text += "После удаления восстановить траекторию и данные будет невозможно.\n\n"
        warning_text += "❓ <b>Ты ДЕЙСТВИТЕЛЬНО хочешь удалить эту траекторию?</b>"
        
        await callback.message.edit_text(
            warning_text,
            parse_mode="HTML",
            reply_markup=get_trajectory_deletion_confirmation_keyboard(trajectory_id)
        )
        
        log_user_action(callback.from_user.id, "selected_trajectory_for_deletion", f"trajectory_id: {trajectory_id}")
        
    except Exception as e:
        await callback.answer("Произошла ошибка")
        log_user_error(callback.from_user.id, "select_trajectory_to_delete_error", str(e))


@router.callback_query(F.data.startswith("confirm_trajectory_deletion:"), LearningPathStates.trajectory_deletion)
async def callback_confirm_trajectory_deletion(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Обработчик подтверждения удаления траектории"""
    try:
        await callback.answer()
        
        trajectory_id = int(callback.data.split(":")[1])
        trajectory = await get_learning_path_by_id(session, trajectory_id)
        
        if not trajectory:
            await callback.message.edit_text(
                "❌ <b>Ошибка</b>\n\n"
                "Траектория не найдена.",
                parse_mode="HTML"
            )
            return
        
        # Удаляем траекторию
        success = await delete_learning_path(session, trajectory_id)
        
        if success:
            await callback.message.edit_text(
                f"✅ <b>Траектория удалена</b>\n\n"
                f"Траектория '{trajectory.name}' успешно удалена из системы.",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="⬅️ К списку траекторий", callback_data="back_to_trajectories_main")]
                ])
            )
            log_user_action(callback.from_user.id, "deleted_trajectory", f"trajectory_id: {trajectory_id}, name: {trajectory.name}")
        else:
            await callback.message.edit_text(
                f"❌ <b>Ошибка удаления</b>\n\n"
                f"Не удалось удалить траекторию '{trajectory.name}'.\n"
                f"Попробуй позже или обратись к администратору.",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_trajectory_selection")]
                ])
            )
            log_user_error(callback.from_user.id, "trajectory_deletion_failed", f"trajectory_id: {trajectory_id}")
        
    except Exception as e:
        await callback.answer("Произошла ошибка")
        log_user_error(callback.from_user.id, "confirm_trajectory_deletion_error", str(e))


@router.callback_query(F.data == "back_to_trajectory_selection", LearningPathStates.trajectory_deletion)
async def callback_back_to_trajectory_selection(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Возврат к выбору траектории для удаления"""
    try:
        await callback.answer()
        
        # Получаем все траектории
        trajectories = await get_all_learning_paths(session)
        
        if not trajectories:
            await callback.message.edit_text(
                "🗑️ <b>Удаление траекторий</b>\n\n"
                "В системе нет траекторий для удаления.",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_trajectories_main")]
                ])
            )
            return
        
        # Показываем список траекторий для выбора
        text = "🗑️ <b>Удаление траекторий</b>\n\n"
        text += "Выбери траекторию для удаления:\n\n"
        
        for i, trajectory in enumerate(trajectories, 1):
            text += f"{i}. {trajectory.name}\n"
        
        await callback.message.edit_text(
            text,
            parse_mode="HTML",
            reply_markup=get_trajectory_selection_keyboard(trajectories)
        )
        
    except Exception as e:
        await callback.answer("Произошла ошибка")
        log_user_error(callback.from_user.id, "back_to_trajectory_selection_error", str(e))


@router.callback_query(F.data == "back_to_trajectories_main")
async def callback_back_to_trajectories_main_universal(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Универсальный возврат к главному меню траекторий"""
    try:
        await callback.answer()
        
        # Показываем главное меню траекторий
        text = ("🗺️<b>РЕДАКТОР ТРАЕКТОРИЙ</b>🗺️\n\n"
                "В данном меню ты можешь:\n\n"
                "1 ➕Создать траекторию обучения\n"
                "2 ✏️Изменить траекторию обучения\n"
                "3 🗑️Удалить траекторию обучения")
        
        await callback.message.edit_text(
            text,
            reply_markup=get_learning_paths_main_keyboard(),
            parse_mode="HTML"
        )
        
        await state.set_state(LearningPathStates.main_menu)
        
    except Exception as e:
        await callback.answer("Произошла ошибка")
        log_user_error(callback.from_user.id, "back_to_trajectories_main_universal_error", str(e))


# ================== ОБЩИЕ CALLBACKS ==================

@router.callback_query(F.data == "cancel_test_creation")
async def callback_cancel_test_creation(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Отмена создания теста и возврат к выбору тестов"""
    try:
        await callback.answer()
        
        # Получаем все доступные тесты
        tests = await get_all_active_tests(session)
        
        # Получаем текущие тесты в сессии
        data = await state.get_data()
        trajectory_data = data.get('trajectory_data', {})
        current_session_tests = []
        
        if trajectory_data.get('stages'):
            last_stage = trajectory_data['stages'][-1]
            if last_stage.get('sessions'):
                last_session = last_stage['sessions'][-1]
                current_session_tests = last_session.get('tests', [])
        
        trajectory_progress = generate_trajectory_progress(trajectory_data)
        current_session_number = data.get('current_session_number', 1)
        
        text = (
            f"🗺️<b>РЕДАКТОР ТРАЕКТОРИЙ</b>🗺️\n"
            "➕Создание траектории\n"
            f"{trajectory_progress}"
            f"🟡<b>Тест {len(current_session_tests) + 1}:</b> Выбери тест для сессии {current_session_number}"
        )
        
        await callback.message.edit_text(
            text,
            reply_markup=get_test_selection_keyboard(tests, current_session_tests),
            parse_mode="HTML"
        )
        
        await state.set_state(LearningPathStates.waiting_for_test_selection)
        
        # Очищаем временные данные теста
        await state.update_data(
            new_test_name=None,
            new_test_description=None,
            new_test_materials=None,
            new_test_question_type=None,
            new_test_question_text=None,
            new_test_question_answer=None,
            new_test_question_points=None,
            new_test_questions=[],
            new_test_total_score=None
        )
        
    except Exception as e:
        await callback.answer("Произошла ошибка")
        log_user_error(callback.from_user.id, "cancel_test_creation_error", str(e))


