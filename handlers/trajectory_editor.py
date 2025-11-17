"""
Обработчики для редактора траекторий обучения.
Включает редактирование траекторий, этапов, сессий и управление тестами.
"""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from database.db import (
    get_learning_path_by_id,
    get_session_tests, get_all_active_tests, get_all_groups, get_all_attestations,
    update_learning_path_name, update_learning_stage_name, update_learning_session_name,
    update_learning_path_group, update_learning_path_attestation,
    delete_learning_stage, delete_learning_session, check_stage_has_trainees,
    check_session_has_trainees, add_test_to_session_from_editor, remove_test_from_session,
    get_attestation_by_id, get_all_learning_paths, get_user_by_tg_id, ensure_company_id
)
from database.models import LearningStage, LearningSession, LearningPath
from states.states import LearningPathStates
from keyboards.keyboards import (
    get_trajectory_editor_main_keyboard, get_stage_editor_keyboard,
    get_session_tests_keyboard, get_test_selection_for_session_keyboard,
    get_group_selection_for_trajectory_keyboard, get_attestation_selection_for_trajectory_keyboard,
    get_trajectory_attestation_management_keyboard, get_stage_deletion_confirmation_keyboard,
    get_session_deletion_confirmation_keyboard, get_back_to_editor_keyboard
)
from utils.trajectory_formatters import (
    format_trajectory_structure, format_stage_editor_view, format_session_tests_editor_view,
    format_trajectory_structure_with_new_stage
)
from utils.logger import log_user_action, log_user_error
from utils.validators import validate_name

router = Router()


# ===============================
# ВНУТРЕННИЕ ФУНКЦИИ БИЗНЕС-ЛОГИКИ
# ===============================

async def render_attestation_page_for_editor(session: AsyncSession, attestation_id: int, path_id: int, page: int, company_id: int) -> tuple[str, InlineKeyboardMarkup]:
    """Универсальная функция рендеринга страницы аттестации для редактора траекторий"""
    attestation = await get_attestation_by_id(session, attestation_id, company_id=company_id)
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
    
    text = (
        "🔍<b>РЕДАКТОР АТТЕСТАЦИЙ</b>🔍\n"
        f"📋 <b>Аттестация:</b> {attestation.name}\n"
        f"📝 <b>Всего вопросов:</b> {total_questions}\n\n"
        f"{questions_text}"
        f"🎯 <b>Проходной балл:</b> {attestation.passing_score:.1f}\n"
        f"📊 <b>Максимальный балл:</b> {getattr(attestation, 'max_score', 20):.1f}\n"
    )
    
    # Создаем клавиатуру
    keyboard_buttons = []
    if total_questions > 3:
        nav_row = []
        if page > 0:
            nav_row.append(InlineKeyboardButton(text="⬅️ Назад", callback_data=f"editor_attestation_page_prev:{path_id}:{attestation_id}:{page-1}"))
        if page < total_pages - 1:
            nav_row.append(InlineKeyboardButton(text="Вперёд ➡️", callback_data=f"editor_attestation_page_next:{path_id}:{attestation_id}:{page+1}"))
        if nav_row:
            keyboard_buttons.append(nav_row)
    
    keyboard_buttons.extend([
        [InlineKeyboardButton(text="⬅️ Назад", callback_data=f"edit_trajectory_attestation:{path_id}")],
        [InlineKeyboardButton(text="≡ Главное меню", callback_data="main_menu")]
    ])
    
    return text, InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)

async def _show_editor_main_menu(message: Message, state: FSMContext, session: AsyncSession, path_id: int, user_id: int):
    """Внутренняя функция для отображения главного экрана редактора"""
    user = await get_user_by_tg_id(session, user_id)
    if not user:
        await message.answer("❌ Пользователь не найден")
        return
    
    # Получаем траекторию с полными данными
    learning_path = await get_learning_path_by_id(session, path_id, company_id=user.company_id)
    if not learning_path:
        await message.answer("Траектория не найдена")
        return
    
    # Форматируем структуру траектории
    text = format_trajectory_structure(learning_path, show_header=True)
    
    # Получаем этапы для клавиатуры
    stages = sorted(learning_path.stages, key=lambda s: s.order_number) if learning_path.stages else []
    
    keyboard = get_trajectory_editor_main_keyboard(stages, path_id)
    
    # Пытаемся отредактировать сообщение, если не получается - отправляем новое
    try:
        await message.edit_text(
            text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )
    except Exception:
        await message.answer(
            text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )
    
    await state.set_state(LearningPathStates.editor_main_menu)
    await state.update_data(path_id=path_id)
    
    log_user_action(user_id, "opened_trajectory_editor", f"Path ID: {path_id}")


async def _show_stage_editor(message: Message, state: FSMContext, session: AsyncSession, stage_id: int, user_id: int):
    """Внутренняя функция для отображения экрана редактирования этапа"""
    user = await get_user_by_tg_id(session, user_id)
    if not user:
        await message.answer("❌ Пользователь не найден")
        return
    
    # Получаем этап с сессиями
    result = await session.execute(
        select(LearningStage).where(LearningStage.id == stage_id)
        .options(selectinload(LearningStage.sessions), selectinload(LearningStage.learning_path))
    )
    stage = result.scalar_one_or_none()
    
    if not stage:
        await message.answer("Этап не найден")
        return
    
    learning_path = stage.learning_path
    
    # Получаем всю траекторию с полными данными для отображения полной структуры
    learning_path = await get_learning_path_by_id(session, learning_path.id, company_id=user.company_id)
    if not learning_path:
        await message.answer("Траектория не найдена")
        return
    
    # Находим редактируемый этап в загруженной траектории
    stage = None
    for s in learning_path.stages:
        if s.id == stage_id:
            stage = s
            break
    
    if not stage:
        await message.answer("Этап не найден")
        return
    
    # Загружаем тесты для всех сессий всех этапов
    for s in learning_path.stages:
        if s.sessions:
            for session_item in s.sessions:
                # Получаем company_id для изоляции
                data = await state.get_data()
                company_id = data.get('company_id') or (user.company_id if 'user' in locals() else None)
                
                session_tests = await get_session_tests(session, session_item.id, company_id=company_id)
                session_item.tests = session_tests
    
    sessions = sorted(stage.sessions, key=lambda s: s.order_number) if stage.sessions else []
    
    # Форматируем вид для редактирования этапа
    text = format_stage_editor_view(learning_path, stage)
    
    keyboard = get_stage_editor_keyboard(stage, sessions, learning_path.id)
    
    # Пытаемся отредактировать сообщение, если не получается - отправляем новое
    try:
        await message.edit_text(
            text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )
    except Exception:
        await message.answer(
            text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )
    
    await state.update_data(path_id=learning_path.id, stage_id=stage_id)
    
    log_user_action(user_id, "opened_stage_editor", f"Stage ID: {stage_id}")


async def _show_session_editor(message: Message, state: FSMContext, session: AsyncSession, session_id: int, user_id: int):
    """Внутренняя функция для отображения экрана управления тестами сессии"""
    user = await get_user_by_tg_id(session, user_id)
    if not user:
        await message.answer("❌ Пользователь не найден")
        return
    
    # Получаем сессию с этапом и траекторией
    result = await session.execute(
        select(LearningSession).where(LearningSession.id == session_id)
        .options(
            selectinload(LearningSession.stage).selectinload(LearningStage.learning_path)
        )
    )
    learning_session = result.scalar_one_or_none()
    
    if not learning_session:
        await message.answer("Сессия не найдена")
        return
    
    stage = learning_session.stage
    learning_path_id = stage.learning_path.id if hasattr(stage.learning_path, 'id') else stage.learning_path_id
    
    # Получаем всю траекторию с полными данными для отображения полной структуры
    learning_path = await get_learning_path_by_id(session, learning_path_id, company_id=user.company_id)
    if not learning_path:
        await message.answer("Траектория не найдена")
        return
    
    # Находим редактируемую сессию и её этап в загруженной траектории
    stage = None
    learning_session = None
    for s in learning_path.stages:
        if s.sessions:
            for sess in s.sessions:
                if sess.id == session_id:
                    stage = s
                    learning_session = sess
                    break
        if stage:
            break
    
    if not stage or not learning_session:
        await message.answer("Сессия не найдена")
        return
    
    # Получаем company_id для изоляции
    data = await state.get_data()
    company_id = data.get('company_id')
    if not company_id:
        user = await get_user_by_tg_id(session, message.from_user.id)
        company_id = user.company_id if user else None
    
    # Загружаем тесты для всех сессий всех этапов
    for s in learning_path.stages:
        if s.sessions:
            for session_item in s.sessions:
                session_tests = await get_session_tests(session, session_item.id, company_id=company_id)
                session_item.tests = session_tests
    
    # Получаем тесты редактируемой сессии с правильной сортировкой
    tests = await get_session_tests(session, session_id, company_id=company_id)
    
    # Форматируем вид для управления тестами
    text = format_session_tests_editor_view(learning_path, stage, learning_session, tests)
    
    keyboard = get_session_tests_keyboard(tests, session_id, stage.id)
    
    # Пытаемся отредактировать сообщение, если не получается - отправляем новое
    try:
        await message.edit_text(
            text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )
    except Exception:
        await message.answer(
            text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )
    
    await state.update_data(session_id=session_id, stage_id=stage.id, path_id=learning_path.id)
    
    log_user_action(user_id, "opened_session_editor", f"Session ID: {session_id}")


# ===============================
# ГЛАВНЫЙ ЭКРАН РЕДАКТОРА
# ===============================

@router.callback_query(F.data.startswith("editor_main_menu:"))
async def callback_editor_main_menu(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Главный экран редактора траектории"""
    try:
        await callback.answer()
        
        path_id = int(callback.data.split(":")[1])
        
        await _show_editor_main_menu(callback.message, state, session, path_id, callback.from_user.id)
        
    except (ValueError, IndexError) as e:
        await callback.answer("Ошибка при обработке данных", show_alert=True)
        log_user_error(callback.from_user.id, "editor_main_menu_error", f"Invalid data: {callback.data}, {str(e)}")
    except Exception as e:
        await callback.answer("Произошла ошибка")
        log_user_error(callback.from_user.id, "editor_main_menu_error", str(e))


@router.callback_query(F.data == "edit_trajectory", LearningPathStates.editor_main_menu)
async def callback_back_to_trajectory_list_from_editor(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Возврат к списку траекторий из главного меню редактора"""
    try:
        await callback.answer()
        
        # Переиспользуем логику из handlers/learning_paths.py
        from handlers.learning_paths import callback_edit_trajectory
        await callback_edit_trajectory(callback, state, session)
        
        log_user_action(callback.from_user.id, "back_to_trajectory_list_from_editor", "Возврат к списку траекторий")
        
    except Exception as e:
        await callback.answer("Произошла ошибка")
        log_user_error(callback.from_user.id, "back_to_trajectory_list_error", str(e))




# ===============================
# РЕДАКТИРОВАНИЕ ЭТАПОВ
# ===============================

@router.callback_query(F.data.startswith("edit_stage_view:"))
async def callback_edit_stage_view(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Экран редактирования этапа"""
    try:
        await callback.answer()
        
        stage_id = int(callback.data.split(":")[1])
        
        await _show_stage_editor(callback.message, state, session, stage_id, callback.from_user.id)
        
    except (ValueError, IndexError) as e:
        await callback.answer("Ошибка при обработке данных", show_alert=True)
        log_user_error(callback.from_user.id, "edit_stage_view_error", f"Invalid data: {callback.data}, {str(e)}")
    except Exception as e:
        await callback.answer("Произошла ошибка")
        log_user_error(callback.from_user.id, "edit_stage_view_error", str(e))


@router.callback_query(F.data.startswith("edit_stage_name:"))
async def callback_edit_stage_name(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Начало редактирования названия этапа"""
    try:
        await callback.answer()
        
        stage_id = int(callback.data.split(":")[1])
        
        await callback.message.edit_text(
            "✏️ <b>Редактирование названия этапа</b>\n\n"
            "Введи новое название этапа:",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ Отмена", callback_data=f"edit_stage_view:{stage_id}")]
            ])
        )
        
        await state.set_state(LearningPathStates.editing_stage_name)
        await state.update_data(stage_id=stage_id)
        
    except (ValueError, IndexError) as e:
        await callback.answer("Ошибка при обработке данных", show_alert=True)
        log_user_error(callback.from_user.id, "edit_stage_name_start_error", f"Invalid data: {callback.data}, {str(e)}")
    except Exception as e:
        await callback.answer("Произошла ошибка")
        log_user_error(callback.from_user.id, "edit_stage_name_start_error", str(e))


@router.message(LearningPathStates.editing_stage_name)
async def process_stage_name(message: Message, state: FSMContext, session: AsyncSession):
    """Обработка нового названия этапа"""
    user = await get_user_by_tg_id(session, message.from_user.id)
    if not user:
        await message.answer("❌ Ты не зарегистрирован в системе.")
        return
    
    try:
        new_name = message.text.strip()
        
        if not validate_name(new_name):
            await message.answer("❌ Некорректное название этапа. Попробуй еще раз:")
            return
        
        data = await state.get_data()
        stage_id = data.get('stage_id')
        path_id = data.get('path_id')
        
        if not stage_id:
            await message.answer("❌ Ошибка: не найден ID этапа")
            await state.clear()
            return
        
        # Обновляем название этапа
        success = await update_learning_stage_name(session, stage_id, new_name, company_id=user.company_id)
        
        if not success:
            await message.answer("❌ Не удалось обновить название этапа. Попробуй еще раз:")
            return
        
        # Возвращаемся к экрану редактирования этапа
        await _show_stage_editor(message, state, session, stage_id, message.from_user.id)
        
        log_user_action(message.from_user.id, "updated_stage_name", f"Stage ID: {stage_id}, New name: {new_name}")
        
    except Exception as e:
        await message.answer("Произошла ошибка при обновлении названия этапа")
        log_user_error(message.from_user.id, "process_stage_name_error", str(e))


@router.callback_query(F.data.startswith("delete_stage:"))
async def callback_delete_stage(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Подтверждение удаления этапа"""
    user = await get_user_by_tg_id(session, callback.from_user.id)
    if not user:
        await callback.answer("❌ Ты не зарегистрирован в системе.", show_alert=True)
        return
    
    try:
        await callback.answer()
        
        stage_id = int(callback.data.split(":")[1])
        
        # Получаем этап для получения path_id
        result = await session.execute(
            select(LearningStage).where(LearningStage.id == stage_id)
        )
        stage = result.scalar_one_or_none()
        
        if not stage:
            await callback.answer("Этап не найден", show_alert=True)
            return
        
        # Проверяем наличие стажеров
        has_trainees = await check_stage_has_trainees(session, stage_id, company_id=user.company_id)
        
        if has_trainees:
            await callback.message.edit_text(
                "❌ <b>Невозможно удалить этап</b>\n\n"
                "Этот этап используется в активных траекториях стажеров.\n"
                "Для удаления сначала заверши или отмени назначения траекторий.",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="⬅️ Назад", callback_data=f"edit_stage_view:{stage_id}")]
                ])
            )
            return
        
        text = (
            f"⚠️ <b>Подтверждение удаления этапа</b>\n\n"
            f"Этап: <b>{stage.name}</b>\n\n"
            f"ВСЕ СЕССИИ ЭТАПА БУДУТ УДАЛЕНЫ\n"
            f"ВСЕ ТЕСТЫ ИЗ СЕССИЙ БУДУТ ОТКЛЮЧЕНЫ ОТ СЕССИЙ\n"
            f"МАТЕРИАЛЫ И ТЕСТЫ СОХРАНЯТСЯ В БАЗЕ ДАННЫХ\n\n"
            f"Ты уверен, что хочешь удалить этот этап?"
        )
        
        keyboard = get_stage_deletion_confirmation_keyboard(stage_id, stage.learning_path_id)
        
        await callback.message.edit_text(
            text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        
        await state.set_state(LearningPathStates.deleting_stage_confirmation)
        await state.update_data(stage_id=stage_id, path_id=stage.learning_path_id)
        
    except (ValueError, IndexError) as e:
        await callback.answer("Ошибка при обработке данных", show_alert=True)
        log_user_error(callback.from_user.id, "delete_stage_start_error", f"Invalid data: {callback.data}, {str(e)}")
    except Exception as e:
        await callback.answer("Произошла ошибка")
        log_user_error(callback.from_user.id, "delete_stage_start_error", str(e))


@router.callback_query(F.data.startswith("confirm_delete_stage:"), LearningPathStates.deleting_stage_confirmation)
async def callback_confirm_delete_stage(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Подтверждение и удаление этапа"""
    try:
        await callback.answer()
        
        stage_id = int(callback.data.split(":")[1])
        
        data = await state.get_data()
        path_id = data.get('path_id')
        
        # Удаляем этап
        success = await delete_learning_stage(session, stage_id)
        
        if not success:
            await callback.message.edit_text(
                "❌ <b>Ошибка удаления этапа</b>\n\n"
                "Не удалось удалить этап. Возможно, этап используется стажерами.",
                parse_mode="HTML",
                reply_markup=get_back_to_editor_keyboard(path_id)
            )
            return
        
        await callback.message.edit_text(
            "✅ <b>Этап успешно удален</b>",
            parse_mode="HTML",
            reply_markup=get_back_to_editor_keyboard(path_id)
        )
        
        # Возвращаемся в главное меню редактора
        await state.set_state(LearningPathStates.editor_main_menu)
        
        log_user_action(callback.from_user.id, "deleted_stage", f"Stage ID: {stage_id}")
        
    except (ValueError, IndexError) as e:
        await callback.answer("Ошибка при обработке данных", show_alert=True)
        log_user_error(callback.from_user.id, "confirm_delete_stage_error", f"Invalid data: {callback.data}, {str(e)}")
    except Exception as e:
        await callback.answer("Произошла ошибка")
        log_user_error(callback.from_user.id, "confirm_delete_stage_error", str(e))


# ===============================
# РЕДАКТИРОВАНИЕ СЕССИЙ
# ===============================

@router.callback_query(F.data.startswith("edit_session_view:"))
async def callback_edit_session_view(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Экран управления тестами сессии"""
    try:
        await callback.answer()
        
        session_id = int(callback.data.split(":")[1])
        
        await _show_session_editor(callback.message, state, session, session_id, callback.from_user.id)
        
    except (ValueError, IndexError) as e:
        await callback.answer("Ошибка при обработке данных", show_alert=True)
        log_user_error(callback.from_user.id, "edit_session_view_error", f"Invalid data: {callback.data}, {str(e)}")
    except Exception as e:
        await callback.answer("Произошла ошибка")
        log_user_error(callback.from_user.id, "edit_session_view_error", str(e))


@router.callback_query(F.data.startswith("edit_session_name:"))
async def callback_edit_session_name(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Начало редактирования названия сессии"""
    try:
        await callback.answer()
        
        session_id = int(callback.data.split(":")[1])
        
        await callback.message.edit_text(
            "✏️ <b>Редактирование названия сессии</b>\n\n"
            "Введи новое название сессии:",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ Отмена", callback_data=f"edit_session_view:{session_id}")]
            ])
        )
        
        await state.set_state(LearningPathStates.editing_session_name)
        await state.update_data(session_id=session_id)
        
    except (ValueError, IndexError) as e:
        await callback.answer("Ошибка при обработке данных", show_alert=True)
        log_user_error(callback.from_user.id, "edit_session_name_start_error", f"Invalid data: {callback.data}, {str(e)}")
    except Exception as e:
        await callback.answer("Произошла ошибка")
        log_user_error(callback.from_user.id, "edit_session_name_start_error", str(e))


@router.message(LearningPathStates.editing_session_name)
async def process_session_name(message: Message, state: FSMContext, session: AsyncSession):
    """Обработка нового названия сессии"""
    try:
        new_name = message.text.strip()
        
        if not validate_name(new_name):
            await message.answer("❌ Некорректное название сессии. Попробуй еще раз:")
            return
        
        data = await state.get_data()
        session_id = data.get('session_id')
        
        if not session_id:
            await message.answer("❌ Ошибка: не найден ID сессии")
            await state.clear()
            return
        
        # Обновляем название сессии
        success = await update_learning_session_name(session, session_id, new_name)
        
        if not success:
            await message.answer("❌ Не удалось обновить название сессии. Попробуй еще раз:")
            return
        
        # Возвращаемся к экрану редактирования сессии
        await _show_session_editor(message, state, session, session_id, message.from_user.id)
        
        log_user_action(message.from_user.id, "updated_session_name", f"Session ID: {session_id}, New name: {new_name}")
        
    except Exception as e:
        await message.answer("Произошла ошибка при обновлении названия сессии")
        log_user_error(message.from_user.id, "process_session_name_error", str(e))


@router.callback_query(F.data.startswith("delete_session:"))
async def callback_delete_session(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Подтверждение удаления сессии"""
    try:
        await callback.answer()
        
        session_id = int(callback.data.split(":")[1])
        
        # Получаем сессию для получения stage_id
        result = await session.execute(
            select(LearningSession).where(LearningSession.id == session_id)
            .options(selectinload(LearningSession.stage))
        )
        learning_session = result.scalar_one_or_none()
        
        if not learning_session:
            await callback.answer("Сессия не найдена", show_alert=True)
            return
        
        # Получаем company_id для изоляции
        data = await state.get_data()
        company_id = data.get('company_id')
        
        # Проверяем наличие стажеров
        has_trainees = await check_session_has_trainees(session, session_id, company_id=company_id)
        
        if has_trainees:
            await callback.message.edit_text(
                "❌ <b>Невозможно удалить сессию</b>\n\n"
                "Эта сессия используется в активных траекториях стажеров.\n"
                "Для удаления сначала заверши или отмени назначения траекторий.",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="⬅️ Назад", callback_data=f"edit_session_view:{session_id}")]
                ])
            )
            return
        
        text = (
            f"⚠️ <b>Подтверждение удаления сессии</b>\n\n"
            f"Сессия: <b>{learning_session.name}</b>\n\n"
            f"ВСЕ ТЕСТЫ БУДУТ ОТКЛЮЧЕНЫ ОТ СЕССИИ\n"
            f"ВСЕ МАТЕРИАЛЫ СЕССИИ СОХРАНЯЮТСЯ В БЗ\n"
            f"ВСЕ ТЕСТЫ СОХРАНЯЮТСЯ В ТЕСТАХ\n"
            f"удаляется только сессия из траектории\n\n"
            f"Ты уверен, что хочешь удалить эту сессию?"
        )
        
        keyboard = get_session_deletion_confirmation_keyboard(session_id, learning_session.stage_id)
        
        await callback.message.edit_text(
            text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        
        await state.set_state(LearningPathStates.deleting_session_confirmation)
        await state.update_data(session_id=session_id, stage_id=learning_session.stage_id)
        
    except (ValueError, IndexError) as e:
        await callback.answer("Ошибка при обработке данных", show_alert=True)
        log_user_error(callback.from_user.id, "delete_session_start_error", f"Invalid data: {callback.data}, {str(e)}")
    except Exception as e:
        await callback.answer("Произошла ошибка")
        log_user_error(callback.from_user.id, "delete_session_start_error", str(e))


@router.callback_query(F.data.startswith("confirm_delete_session:"), LearningPathStates.deleting_session_confirmation)
async def callback_confirm_delete_session(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Подтверждение и удаление сессии"""
    try:
        await callback.answer()
        
        session_id = int(callback.data.split(":")[1])
        
        data = await state.get_data()
        stage_id = data.get('stage_id')
        
        # Удаляем сессию
        success = await delete_learning_session(session, session_id)
        
        if not success:
            await callback.message.edit_text(
                "❌ <b>Ошибка удаления сессии</b>\n\n"
                "Не удалось удалить сессию. Возможно, сессия используется стажерами.",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="⬅️ Назад", callback_data=f"edit_stage_view:{stage_id}")]
                ])
            )
            return
        
        await callback.message.edit_text(
            "✅ <b>Сессия успешно удалена</b>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ Назад к этапу", callback_data=f"edit_stage_view:{stage_id}")]
            ])
        )
        
        log_user_action(callback.from_user.id, "deleted_session", f"Session ID: {session_id}")
        
    except (ValueError, IndexError) as e:
        await callback.answer("Ошибка при обработке данных", show_alert=True)
        log_user_error(callback.from_user.id, "confirm_delete_session_error", f"Invalid data: {callback.data}, {str(e)}")
    except Exception as e:
        await callback.answer("Произошла ошибка")
        log_user_error(callback.from_user.id, "confirm_delete_session_error", str(e))


# ===============================
# УПРАВЛЕНИЕ ТЕСТАМИ В СЕССИИ
# ===============================

@router.callback_query(F.data.startswith("add_test_to_session:"))
async def callback_add_test_to_session(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Добавление теста в сессию - выбор теста"""
    try:
        await callback.answer()
        
        session_id = int(callback.data.split(":")[1])
        
        # Получаем все активные тесты
        company_id = await ensure_company_id(session, state, callback.from_user.id)
        all_tests = await get_all_active_tests(session, company_id)
        
        # Получаем тесты, уже добавленные в сессию
        existing_tests = await get_session_tests(session, session_id, company_id=company_id)
        existing_test_ids = [test.id for test in existing_tests]
        
        # Фильтруем тесты, убирая уже добавленные
        available_tests = [test for test in all_tests if test.id not in existing_test_ids]
        
        if not available_tests:
            await callback.message.edit_text(
                "📝 <b>Нет доступных тестов</b>\n\n"
                "Все тесты уже добавлены в эту сессию.",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="⬅️ Назад", callback_data=f"edit_session_view:{session_id}")]
                ])
            )
            return
        
        text = (
            "📝 <b>Добавление теста в сессию</b>\n\n"
            "Выбери тест для добавления:"
        )
        
        keyboard = get_test_selection_for_session_keyboard(available_tests, session_id, existing_test_ids)
        
        await callback.message.edit_text(
            text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        
        await state.set_state(LearningPathStates.selecting_test_to_add)
        await state.update_data(session_id=session_id)
        
    except (ValueError, IndexError) as e:
        await callback.answer("Ошибка при обработке данных", show_alert=True)
        log_user_error(callback.from_user.id, "add_test_to_session_start_error", f"Invalid data: {callback.data}, {str(e)}")
    except Exception as e:
        await callback.answer("Произошла ошибка")
        log_user_error(callback.from_user.id, "add_test_to_session_start_error", str(e))


@router.callback_query(F.data.startswith("select_test_for_session:"), LearningPathStates.selecting_test_to_add)
async def callback_select_test_for_session(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Выбор теста для добавления в сессию"""
    try:
        await callback.answer()
        
        parts = callback.data.split(":")
        session_id = int(parts[1])
        test_id = int(parts[2])
        
        # Получаем company_id для изоляции
        user = await get_user_by_tg_id(session, callback.from_user.id)
        if not user:
            await callback.answer("❌ Ты не зарегистрирован в системе.", show_alert=True)
            return
        
        # Добавляем тест в сессию
        success = await add_test_to_session_from_editor(session, session_id, test_id, company_id=user.company_id)
        
        if not success:
            await callback.answer("Не удалось добавить тест", show_alert=True)
            return
        
        await callback.answer("✅ Тест добавлен", show_alert=False)
        
        # Возвращаемся к экрану управления тестами сессии
        await _show_session_editor(callback.message, state, session, session_id, callback.from_user.id)
        
        log_user_action(callback.from_user.id, "added_test_to_session", f"Session ID: {session_id}, Test ID: {test_id}")
        
    except (ValueError, IndexError) as e:
        await callback.answer("Ошибка при обработке данных", show_alert=True)
        log_user_error(callback.from_user.id, "select_test_for_session_error", f"Invalid data: {callback.data}, {str(e)}")
    except Exception as e:
        await callback.answer("Произошла ошибка")
        log_user_error(callback.from_user.id, "select_test_for_session_error", str(e))


@router.callback_query(F.data.startswith("remove_test_from_session:"))
async def callback_remove_test_from_session(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Удаление теста из сессии"""
    user = await get_user_by_tg_id(session, callback.from_user.id)
    if not user:
        await callback.answer("❌ Ты не зарегистрирован в системе.", show_alert=True)
        return
    
    try:
        await callback.answer()
        
        parts = callback.data.split(":")
        session_id = int(parts[1])
        test_id = int(parts[2])
        
        # Получаем тест для отображения названия
        from database.db import get_test_by_id
        test = await get_test_by_id(session, test_id, company_id=user.company_id)
        if not test:
            await callback.answer("Тест не найден", show_alert=True)
            return
        
        # Удаляем тест из сессии
        success = await remove_test_from_session(session, session_id, test_id, company_id=user.company_id)
        
        if not success:
            await callback.answer("Не удалось удалить тест из сессии", show_alert=True)
            return
        
        await callback.answer("✅ Тест удален из сессии", show_alert=False)
        
        # Возвращаемся к экрану управления тестами сессии
        await _show_session_editor(callback.message, state, session, session_id, callback.from_user.id)
        
        log_user_action(callback.from_user.id, "removed_test_from_session", f"Session ID: {session_id}, Test ID: {test_id}")
        
    except (ValueError, IndexError) as e:
        await callback.answer("Ошибка при обработке данных", show_alert=True)
        log_user_error(callback.from_user.id, "remove_test_from_session_error", f"Invalid data: {callback.data}, {str(e)}")
    except Exception as e:
        await callback.answer("Произошла ошибка")
        log_user_error(callback.from_user.id, "remove_test_from_session_error", str(e))


# ===============================
# УПРАВЛЕНИЕ АТТЕСТАЦИЕЙ
# ===============================

@router.callback_query(F.data.startswith("edit_trajectory_attestation:"))
async def callback_edit_trajectory_attestation(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Управление аттестацией траектории"""
    user = await get_user_by_tg_id(session, callback.from_user.id)
    if not user:
        await callback.answer("❌ Ты не зарегистрирован в системе.", show_alert=True)
        return
    
    try:
        await callback.answer()
        
        path_id = int(callback.data.split(":")[1])
        
        learning_path = await get_learning_path_by_id(session, path_id, company_id=user.company_id)
        if not learning_path:
            await callback.answer("Траектория не найдена", show_alert=True)
            return
        
        has_attestation = learning_path.attestation is not None
        attestation_id = learning_path.attestation.id if learning_path.attestation else None
        
        text = (
            "🔍 <b>Управление аттестацией траектории</b>\n\n"
            f"<b>Траектория:</b> {learning_path.name}\n\n"
        )
        
        if has_attestation:
            text += f"<b>Текущая аттестация:</b> {learning_path.attestation.name}\n\n"
        else:
            text += "<b>Аттестация:</b> не назначена\n\n"
        
        keyboard = get_trajectory_attestation_management_keyboard(path_id, has_attestation, attestation_id)
        
        await callback.message.edit_text(
            text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        
        await state.update_data(path_id=path_id)
        
    except (ValueError, IndexError) as e:
        await callback.answer("Ошибка при обработке данных", show_alert=True)
        log_user_error(callback.from_user.id, "edit_trajectory_attestation_error", f"Invalid data: {callback.data}, {str(e)}")
    except Exception as e:
        await callback.answer("Произошла ошибка")
        log_user_error(callback.from_user.id, "edit_trajectory_attestation_error", str(e))


@router.callback_query(F.data.startswith("add_trajectory_attestation:") | F.data.startswith("replace_trajectory_attestation:"))
async def callback_select_attestation_for_trajectory(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Выбор аттестации для траектории"""
    try:
        await callback.answer()
        
        path_id = int(callback.data.split(":")[1])
        
        # Получаем все аттестации
        company_id = await ensure_company_id(session, state, callback.from_user.id)
        attestations = await get_all_attestations(session, company_id)
        
        if not attestations:
            await callback.message.edit_text(
                "❌ <b>Нет доступных аттестаций</b>\n\n"
                "Сначала создай аттестацию.",
                parse_mode="HTML",
                reply_markup=get_back_to_editor_keyboard(path_id)
            )
            return
        
        text = (
            "🔍 <b>Выбор аттестации для траектории</b>\n\n"
            "Выбери аттестацию:"
        )
        
        keyboard = get_attestation_selection_for_trajectory_keyboard(attestations, path_id, page=0)
        
        await callback.message.edit_text(
            text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        
        await state.set_state(LearningPathStates.selecting_attestation_for_trajectory)
        await state.update_data(path_id=path_id, attestation_page=0)
        
    except (ValueError, IndexError) as e:
        await callback.answer("Ошибка при обработке данных", show_alert=True)
        log_user_error(callback.from_user.id, "select_attestation_for_trajectory_error", f"Invalid data: {callback.data}, {str(e)}")
    except Exception as e:
        await callback.answer("Произошла ошибка")
        log_user_error(callback.from_user.id, "select_attestation_for_trajectory_error", str(e))


@router.callback_query(F.data.startswith("select_attestation_for_trajectory:"))
async def callback_confirm_attestation_selection(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Подтверждение выбора аттестации"""
    try:
        await callback.answer()
        
        parts = callback.data.split(":")
        path_id = int(parts[1])
        attestation_id = int(parts[2])
        
        # Получаем company_id для изоляции
        user = await get_user_by_tg_id(session, callback.from_user.id)
        if not user:
            await callback.answer("❌ Ты не зарегистрирован в системе.", show_alert=True)
            return
        
        # Обновляем аттестацию траектории
        success = await update_learning_path_attestation(session, path_id, attestation_id, company_id=user.company_id)
        
        if not success:
            await callback.answer("Не удалось обновить аттестацию", show_alert=True)
            return
        
        await callback.answer("✅ Аттестация назначена", show_alert=False)
        
        # Возвращаемся в главное меню редактора
        await _show_editor_main_menu(callback.message, state, session, path_id, callback.from_user.id)
        
        log_user_action(callback.from_user.id, "updated_trajectory_attestation", f"Path ID: {path_id}, Attestation ID: {attestation_id}")
        
    except (ValueError, IndexError) as e:
        await callback.answer("Ошибка при обработке данных", show_alert=True)
        log_user_error(callback.from_user.id, "confirm_attestation_selection_error", f"Invalid data: {callback.data}, {str(e)}")
    except Exception as e:
        await callback.answer("Произошла ошибка")
        log_user_error(callback.from_user.id, "confirm_attestation_selection_error", str(e))


# Просмотр аттестации в редакторе
@router.callback_query(F.data.startswith("view_trajectory_attestation:"))
async def callback_view_trajectory_attestation(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Просмотр аттестации траектории с пагинацией вопросов"""
    try:
        await callback.answer()
        
        user = await get_user_by_tg_id(session, callback.from_user.id)
        if not user:
            await callback.answer("❌ Ты не зарегистрирован в системе.", show_alert=True)
            return
        
        parts = callback.data.split(":")
        path_id = int(parts[1])
        attestation_id = int(parts[2])
        
        text, keyboard = await render_attestation_page_for_editor(session, attestation_id, path_id, page=0, company_id=user.company_id)
        
        await callback.message.edit_text(
            text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        
        await state.update_data(path_id=path_id, attestation_id=attestation_id, attestation_page=0)
        
    except (ValueError, IndexError) as e:
        await callback.answer("Ошибка при обработке данных", show_alert=True)
        log_user_error(callback.from_user.id, "view_trajectory_attestation_error", f"Invalid data: {callback.data}, {str(e)}")
    except Exception as e:
        await callback.answer("Произошла ошибка")
        log_user_error(callback.from_user.id, "view_trajectory_attestation_error", str(e))


# Пагинация вопросов аттестации в редакторе
@router.callback_query(F.data.startswith("editor_attestation_page_prev:"))
async def callback_editor_attestation_page_prev(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Переход на предыдущую страницу вопросов аттестации в редакторе"""
    try:
        await callback.answer()
        
        user = await get_user_by_tg_id(session, callback.from_user.id)
        if not user:
            await callback.answer("❌ Ты не зарегистрирован в системе.", show_alert=True)
            return
        
        parts = callback.data.split(":")
        path_id = int(parts[1])
        attestation_id = int(parts[2])
        new_page = int(parts[3])
        
        text, keyboard = await render_attestation_page_for_editor(session, attestation_id, path_id, new_page, company_id=user.company_id)
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
        
        await state.update_data(attestation_page=new_page)
        
    except (ValueError, IndexError) as e:
        await callback.answer("Ошибка при обработке данных", show_alert=True)
        log_user_error(callback.from_user.id, "editor_attestation_page_prev_error", f"Invalid data: {callback.data}, {str(e)}")
    except Exception as e:
        await callback.answer("Произошла ошибка")
        log_user_error(callback.from_user.id, "editor_attestation_page_prev_error", str(e))


@router.callback_query(F.data.startswith("editor_attestation_page_next:"))
async def callback_editor_attestation_page_next(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Переход на следующую страницу вопросов аттестации в редакторе"""
    try:
        await callback.answer()
        
        user = await get_user_by_tg_id(session, callback.from_user.id)
        if not user:
            await callback.answer("❌ Ты не зарегистрирован в системе.", show_alert=True)
            return
        
        parts = callback.data.split(":")
        path_id = int(parts[1])
        attestation_id = int(parts[2])
        new_page = int(parts[3])
        
        text, keyboard = await render_attestation_page_for_editor(session, attestation_id, path_id, new_page, company_id=user.company_id)
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
        
        await state.update_data(attestation_page=new_page)
        
    except (ValueError, IndexError) as e:
        await callback.answer("Ошибка при обработке данных", show_alert=True)
        log_user_error(callback.from_user.id, "editor_attestation_page_next_error", f"Invalid data: {callback.data}, {str(e)}")
    except Exception as e:
        await callback.answer("Произошла ошибка")
        log_user_error(callback.from_user.id, "editor_attestation_page_next_error", str(e))


@router.callback_query(F.data.startswith("remove_trajectory_attestation:"))
async def callback_remove_trajectory_attestation(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Удаление аттестации из траектории"""
    try:
        await callback.answer()
        
        path_id = int(callback.data.split(":")[1])
        
        # Получаем company_id для изоляции
        user = await get_user_by_tg_id(session, callback.from_user.id)
        if not user:
            await callback.answer("❌ Ты не зарегистрирован в системе.", show_alert=True)
            return
        
        # Удаляем аттестацию (устанавливаем в None)
        success = await update_learning_path_attestation(session, path_id, None, company_id=user.company_id)
        
        if not success:
            await callback.answer("Не удалось удалить аттестацию", show_alert=True)
            return
        
        await callback.answer("✅ Аттестация удалена", show_alert=False)
        
        # Возвращаемся в главное меню редактора
        await _show_editor_main_menu(callback.message, state, session, path_id, callback.from_user.id)
        
        log_user_action(callback.from_user.id, "removed_trajectory_attestation", f"Path ID: {path_id}")
        
    except (ValueError, IndexError) as e:
        await callback.answer("Ошибка при обработке данных", show_alert=True)
        log_user_error(callback.from_user.id, "remove_trajectory_attestation_error", f"Invalid data: {callback.data}, {str(e)}")
    except Exception as e:
        await callback.answer("Произошла ошибка")
        log_user_error(callback.from_user.id, "remove_trajectory_attestation_error", str(e))


# Пагинация аттестаций
@router.callback_query(F.data.startswith("attestations_page_prev:") | F.data.startswith("attestations_page_next:"))
async def callback_attestations_page(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Навигация по страницам аттестаций"""
    try:
        await callback.answer()
        
        parts = callback.data.split(":")
        path_id = int(parts[1])
        page = int(parts[2])
        
        company_id = await ensure_company_id(session, state, callback.from_user.id)
        attestations = await get_all_attestations(session, company_id)
        
        text = (
            "🔍 <b>Выбор аттестации для траектории</b>\n\n"
            "Выбери аттестацию:"
        )
        
        keyboard = get_attestation_selection_for_trajectory_keyboard(attestations, path_id, page=page)
        
        await callback.message.edit_text(
            text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        
        await state.update_data(attestation_page=page)
        
    except (ValueError, IndexError) as e:
        await callback.answer("Ошибка при обработке данных", show_alert=True)
        log_user_error(callback.from_user.id, "attestations_page_error", f"Invalid data: {callback.data}, {str(e)}")
    except Exception as e:
        await callback.answer("Произошла ошибка")
        log_user_error(callback.from_user.id, "attestations_page_error", str(e))


# ===============================
# УПРАВЛЕНИЕ ГРУППАМИ
# ===============================

@router.callback_query(F.data.startswith("edit_trajectory_group:"))
async def callback_edit_trajectory_group(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Выбор группы для траектории"""
    try:
        await callback.answer()
        
        path_id = int(callback.data.split(":")[1])
        
        # Получаем все группы
        company_id = await ensure_company_id(session, state, callback.from_user.id)
        groups = await get_all_groups(session, company_id)
        
        if not groups:
            await callback.message.edit_text(
                "❌ <b>Нет доступных групп</b>\n\n"
                "Сначала создай группу.",
                parse_mode="HTML",
                reply_markup=get_back_to_editor_keyboard(path_id)
            )
            return
        
        text = (
            "🗂️ <b>Выбор группы для траектории</b>\n\n"
            "Выбери группу:"
        )
        
        keyboard = get_group_selection_for_trajectory_keyboard(groups, path_id)
        
        await callback.message.edit_text(
            text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        
        await state.set_state(LearningPathStates.selecting_group_for_trajectory)
        await state.update_data(path_id=path_id)
        
    except (ValueError, IndexError) as e:
        await callback.answer("Ошибка при обработке данных", show_alert=True)
        log_user_error(callback.from_user.id, "edit_trajectory_group_error", f"Invalid data: {callback.data}, {str(e)}")
    except Exception as e:
        await callback.answer("Произошла ошибка")
        log_user_error(callback.from_user.id, "edit_trajectory_group_error", str(e))


@router.callback_query(F.data.startswith("select_group_for_trajectory:"), LearningPathStates.selecting_group_for_trajectory)
async def callback_confirm_group_selection(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Подтверждение выбора группы"""
    try:
        await callback.answer()
        
        parts = callback.data.split(":")
        path_id = int(parts[1])
        group_id = int(parts[2])
        
        # Получаем company_id для изоляции
        data = await state.get_data()
        company_id = data.get('company_id')
        if not company_id:
            user = await get_user_by_tg_id(session, callback.from_user.id)
            company_id = user.company_id if user else None
        
        # Обновляем группу траектории
        success = await update_learning_path_group(session, path_id, group_id, company_id=company_id)
        
        if not success:
            await callback.answer("Не удалось обновить группу", show_alert=True)
            return
        
        await callback.answer("✅ Группа обновлена", show_alert=False)
        
        # Возвращаемся в главное меню редактора
        await _show_editor_main_menu(callback.message, state, session, path_id, callback.from_user.id)
        
        log_user_action(callback.from_user.id, "updated_trajectory_group", f"Path ID: {path_id}, Group ID: {group_id}")
        
    except (ValueError, IndexError) as e:
        await callback.answer("Ошибка при обработке данных", show_alert=True)
        log_user_error(callback.from_user.id, "confirm_group_selection_error", f"Invalid data: {callback.data}, {str(e)}")
    except Exception as e:
        await callback.answer("Произошла ошибка")
        log_user_error(callback.from_user.id, "confirm_group_selection_error", str(e))


# ===============================
# СОЗДАНИЕ НОВЫХ ЭТАПОВ И СЕССИЙ
# ===============================

@router.callback_query(F.data.startswith("add_stage_to_trajectory:"))
async def callback_add_stage_to_trajectory(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Начало создания нового этапа в редакторе"""
    user = await get_user_by_tg_id(session, callback.from_user.id)
    if not user:
        await callback.answer("❌ Ты не зарегистрирован в системе.", show_alert=True)
        return
    
    try:
        await callback.answer()
        
        path_id = int(callback.data.split(":")[1])
        
        # Получаем траекторию для отображения структуры
        learning_path = await get_learning_path_by_id(session, path_id, company_id=user.company_id)
        if not learning_path:
            await callback.answer("Траектория не найдена", show_alert=True)
            return
        
        # Вычисляем номер нового этапа
        existing_stages = sorted(learning_path.stages, key=lambda s: s.order_number) if learning_path.stages else []
        new_stage_number = (existing_stages[-1].order_number + 1) if existing_stages else 1
        
        # Форматируем структуру с новым этапом
        text = format_trajectory_structure_with_new_stage(learning_path, new_stage_number)
        
        await callback.message.edit_text(
            text,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ Отмена", callback_data=f"editor_main_menu:{path_id}")]
            ])
        )
        
        await state.set_state(LearningPathStates.creating_stage_name)
        await state.update_data(path_id=path_id, new_stage_order=new_stage_number)
        
        log_user_action(callback.from_user.id, "started_creating_stage", f"Path ID: {path_id}")
        
    except (ValueError, IndexError) as e:
        await callback.answer("Ошибка при обработке данных", show_alert=True)
        log_user_error(callback.from_user.id, "add_stage_to_trajectory_error", f"Invalid data: {callback.data}, {str(e)}")
    except Exception as e:
        await callback.answer("Произошла ошибка")
        log_user_error(callback.from_user.id, "add_stage_to_trajectory_error", str(e))


@router.message(LearningPathStates.creating_stage_name)
async def process_creating_stage_name(message: Message, state: FSMContext, session: AsyncSession):
    """Обработка названия нового этапа"""
    try:
        stage_name = message.text.strip()
        
        if not validate_name(stage_name):
            await message.answer("❌ Некорректное название этапа. Попробуй еще раз:")
            return
        
        data = await state.get_data()
        path_id = data.get('path_id')
        stage_order = data.get('new_stage_order')
        
        if not path_id or not stage_order:
            await message.answer("❌ Ошибка: не найдены данные траектории")
            await state.clear()
            return
        
        # Проверяем существование траектории
        result = await session.execute(
            select(LearningPath).where(LearningPath.id == path_id)
        )
        learning_path = result.scalar_one_or_none()
        
        if not learning_path:
            await message.answer("❌ Траектория не найдена")
            await state.clear()
            return
        
        # Создаем новый этап (инкрементальный флоу: этап → сессии → тесты)
        new_stage = LearningStage(
            name=stage_name,
            description='',
            learning_path_id=path_id,
            order_number=stage_order
        )
        session.add(new_stage)
        await session.commit()
        
        await message.answer(
            f"✅ Этап '{stage_name}' создан\n\n"
            f"Теперь добавь сессии к этому этапу.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="➡️ Продолжить", callback_data=f"edit_stage_view:{new_stage.id}")]
            ])
        )
        
        await state.clear()
        
        log_user_action(message.from_user.id, "created_stage_in_editor", f"Path ID: {path_id}, Stage: {stage_name}")
        
    except Exception as e:
        await session.rollback()
        await message.answer("❌ Произошла ошибка при создании этапа. Попробуй еще раз.")
        log_user_error(message.from_user.id, "process_creating_stage_name_error", str(e))


@router.callback_query(F.data.startswith("add_session_to_stage:"))
async def callback_add_session_to_stage(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Начало создания новой сессии в этапе"""
    try:
        await callback.answer()
        
        stage_id = int(callback.data.split(":")[1])
        
        # Получаем этап с траекторией и сессиями
        result = await session.execute(
            select(LearningStage).where(LearningStage.id == stage_id)
            .options(
                selectinload(LearningStage.learning_path),
                selectinload(LearningStage.sessions)
            )
        )
        stage = result.scalar_one_or_none()
        
        if not stage:
            await callback.answer("Этап не найден", show_alert=True)
            return
        
        # Вычисляем номер новой сессии
        existing_sessions = sorted(stage.sessions, key=lambda s: s.order_number) if stage.sessions else []
        new_session_number = (existing_sessions[-1].order_number + 1) if existing_sessions else 1
        
        await callback.message.edit_text(
            f"➕ <b>Создание новой сессии</b>\n\n"
            f"Этап: <b>{stage.name}</b>\n\n"
            f"Введи название для Сессии {new_session_number}:",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ Отмена", callback_data=f"edit_stage_view:{stage_id}")]
            ])
        )
        
        await state.set_state(LearningPathStates.creating_session_name)
        await state.update_data(stage_id=stage_id, new_session_order=new_session_number)
        
        log_user_action(callback.from_user.id, "started_creating_session", f"Stage ID: {stage_id}")
        
    except Exception as e:
        await callback.answer("Произошла ошибка")
        log_user_error(callback.from_user.id, "add_session_to_stage_error", str(e))


@router.message(LearningPathStates.creating_session_name)
async def process_creating_session_name(message: Message, state: FSMContext, session: AsyncSession):
    """Обработка названия новой сессии"""
    try:
        session_name = message.text.strip()
        
        if not validate_name(session_name):
            await message.answer("❌ Некорректное название сессии. Попробуй еще раз:")
            return
        
        data = await state.get_data()
        stage_id = data.get('stage_id')
        session_order = data.get('new_session_order')
        
        if not stage_id or not session_order:
            await message.answer("❌ Ошибка: не найдены данные этапа")
            await state.clear()
            return
        
        # Проверяем существование этапа
        result = await session.execute(
            select(LearningStage).where(LearningStage.id == stage_id)
        )
        stage = result.scalar_one_or_none()
        
        if not stage:
            await message.answer("❌ Этап не найден")
            await state.clear()
            return
        
        # Создаем новую сессию (инкрементальный флоу: сессия → тесты)
        new_session = LearningSession(
            name=session_name,
            description='',
            stage_id=stage_id,
            order_number=session_order
        )
        session.add(new_session)
        await session.commit()
        
        await message.answer(
            f"✅ Сессия '{session_name}' создана\n\n"
            f"Теперь добавь тесты к этой сессии.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="➡️ Продолжить", callback_data=f"edit_session_view:{new_session.id}")]
            ])
        )
        
        await state.clear()
        
        log_user_action(message.from_user.id, "created_session_in_editor", f"Stage ID: {stage_id}, Session: {session_name}")
        
    except Exception as e:
        await session.rollback()
        await message.answer("❌ Произошла ошибка при создании сессии. Попробуй еще раз.")
        log_user_error(message.from_user.id, "process_creating_session_name_error", str(e))

