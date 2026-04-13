"""
Обработчики для РЕДАКТОРА Экзаменов: меню, создание, карточка, удаление.
"""

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.db import get_user_by_tg_id
from bot.keyboards.keyboards import (
    get_exam_card_keyboard,
    get_exam_confirm_delete_keyboard,
    get_exam_menu_keyboard,
    get_exam_questions_keyboard,
    is_main_menu_text,
)
from bot.repositories import AssessmentRepository
from bot.states.states import ExamStates
from bot.utils.auth.auth import check_auth
from bot.utils.logger import log_user_action, log_user_error

router = Router()


def _user_has_role(user, role_name: str) -> bool:
    """Проверяет наличие роли у пользователя"""
    return any(r.name == role_name for r in user.roles)


async def _get_user_exam_roles(user, active_role: str = None) -> dict:
    """Определяет ролевые флаги пользователя для экзаменов.

    Если active_role задан (ADMIN в определённом ЛК), используем только эту роль.
    """
    if active_role:
        is_recruiter = active_role == "Рекрутер"
        is_mentor = active_role == "Наставник"
        is_manager = active_role == "Руководитель"
        is_employee = active_role == "Сотрудник"
    else:
        is_recruiter = _user_has_role(user, "Рекрутер")
        is_mentor = _user_has_role(user, "Наставник")
        is_manager = _user_has_role(user, "Руководитель")
        is_employee = _user_has_role(user, "Сотрудник")
    # Экзаменатор: руководитель, сотрудник или рекрутер
    is_examiner = is_manager or is_employee or is_recruiter
    return {
        "is_recruiter": is_recruiter,
        "is_mentor": is_mentor,
        "is_examiner": is_examiner,
    }


async def show_exam_menu(message_or_callback, state: FSMContext, session: AsyncSession, user=None):
    """Показ главного меню экзаменов"""
    try:
        if user is None:
            tg_id = (
                message_or_callback.from_user.id
                if hasattr(message_or_callback, "from_user")
                else message_or_callback.message.from_user.id
            )
            user = await get_user_by_tg_id(session, tg_id)

        if not user:
            return

        data = await state.get_data()
        active_role = data.get("role") if data.get("is_admin") else None
        roles = await _get_user_exam_roles(user, active_role=active_role)
        company_id = data.get("company_id")

        exams = await AssessmentRepository(session).get_all(company_id, assessment_type="exam")

        text = "🔖<b>РЕДАКТОР Экзаменов</b>\nВыбери нужное действие"

        keyboard = get_exam_menu_keyboard(exams, **roles)

        if isinstance(message_or_callback, CallbackQuery):
            await message_or_callback.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)
        else:
            await message_or_callback.answer(text, parse_mode="HTML", reply_markup=keyboard)

        await state.set_state(ExamStates.main_menu)

    except Exception as e:
        log_user_error(0, "show_exam_menu_error", str(e))


# ================== Flow B: Вход в меню экзаменов ==================


@router.message(F.text == "Экзамены 📝")
async def cmd_exams(message: Message, state: FSMContext, session: AsyncSession):
    """Обработчик reply-кнопки «Экзамены 📝»"""
    try:
        is_auth = await check_auth(message, state, session)
        if not is_auth:
            return

        user = await get_user_by_tg_id(session, message.from_user.id)
        if not user:
            await message.answer("Ты не зарегистрирован в системе.")
            return

        # Стажёрам экзамены недоступны (ADMIN: проверяем FSM-роль)
        data = await state.get_data()
        active_role = data.get("role") if data.get("is_admin") else None
        if active_role:
            if active_role in ("Стажер", "Стажёр"):
                await message.answer("❌ Экзамены не доступны для стажёров.")
                return
        elif _user_has_role(user, "Стажер") or _user_has_role(user, "Стажёр"):
            await message.answer("❌ Экзамены не доступны для стажёров.")
            return

        await show_exam_menu(message, state, session, user)
        log_user_action(user.tg_id, "exam_menu_opened", "Открыто меню экзаменов")

    except Exception as e:
        await message.answer("Произошла ошибка при открытии экзаменов")
        log_user_error(message.from_user.id, "cmd_exams_error", str(e))


@router.callback_query(F.data == "exam_menu")
async def callback_exam_menu(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Обработчик inline-кнопки «Экзамены» (для наставника)"""
    try:
        await callback.answer()

        user = await get_user_by_tg_id(session, callback.from_user.id)
        if not user:
            await callback.message.edit_text("Ты не зарегистрирован в системе.")
            return

        await show_exam_menu(callback, state, session, user)
        log_user_action(user.tg_id, "exam_menu_opened", "Открыто меню экзаменов (inline)")

    except Exception as e:
        await callback.message.edit_text("Произошла ошибка при открытии экзаменов")
        log_user_error(callback.from_user.id, "callback_exam_menu_error", str(e))


@router.callback_query(F.data == "exam_back_to_menu")
async def callback_exam_back_to_menu(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Возврат в меню экзаменов"""
    try:
        await callback.answer()
        await show_exam_menu(callback, state, session)
    except Exception as e:
        log_user_error(callback.from_user.id, "exam_back_to_menu_error", str(e))


# ================== Flow C: Создание экзамена ==================


@router.callback_query(F.data == "exam_create", ExamStates.main_menu)
async def callback_exam_create(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Начало создания экзамена"""
    try:
        await callback.answer()

        user = await get_user_by_tg_id(session, callback.from_user.id)
        if not user or not _user_has_role(user, "Рекрутер"):
            await callback.message.edit_text("❌ Только рекрутер может создавать экзамены.")
            return

        text = "🔖<b>РЕДАКТОР Экзаменов</b> / Создание экзамена\n🟡<b>Название:</b> отправь название"

        await callback.message.edit_text(text, parse_mode="HTML")
        await state.set_state(ExamStates.waiting_for_exam_name)

        log_user_action(callback.from_user.id, "exam_create_started", "Начато создание экзамена")

    except Exception as e:
        await callback.message.edit_text("Произошла ошибка")
        log_user_error(callback.from_user.id, "exam_create_error", str(e))


@router.message(ExamStates.waiting_for_exam_name)
async def process_exam_name(message: Message, state: FSMContext, session: AsyncSession):
    """Обработка названия экзамена"""
    try:
        name = message.text.strip()

        if is_main_menu_text(name):
            return

        if len(name) < 2 or len(name) > 200:
            await message.answer("❌ Название должно быть от 2 до 200 символов. Попробуй еще раз:")
            return

        await state.update_data(exam_name=name, exam_questions=[])

        text = (
            "🔖<b>РЕДАКТОР Экзаменов</b> / Создание экзамена\n"
            f"🟢<b>Название:</b> {name}\n"
            "🟡<b>Вопрос 1:</b> введи текст вопроса и описание возможных критериев ответа цифрой\n\n"
            "💡 <b>Введи ВЕСЬ БЛОК</b> (вопрос + правильный ответ + критерии оценки)"
        )

        await message.answer(text, parse_mode="HTML")
        await state.set_state(ExamStates.waiting_for_exam_question)

        log_user_action(message.from_user.id, "exam_name_set", f"Название экзамена: {name}")

    except Exception as e:
        await message.answer("Произошла ошибка при обработке названия")
        log_user_error(message.from_user.id, "process_exam_name_error", str(e))


@router.message(ExamStates.waiting_for_exam_question)
async def process_exam_question(message: Message, state: FSMContext, session: AsyncSession):
    """Обработка вопросов экзамена"""
    try:
        question_text = message.text.strip()

        if is_main_menu_text(question_text):
            return

        data = await state.get_data()
        questions = data.get("exam_questions") or []
        exam_name = data.get("exam_name", "")

        question_number = len(questions) + 1
        questions.append(
            {
                "number": question_number,
                "text": question_text,
                "max_points": 10,
            }
        )

        await state.update_data(exam_questions=questions)

        # Показываем прогресс
        questions_text = ""
        recent = questions[-3:] if len(questions) > 3 else questions

        for q in recent:
            questions_text += f"✅ <b>Вопрос {q['number']}:</b>\n{q['text']}\n\n"

        if len(questions) > 3:
            questions_text = f"📝 <i>Добавлено вопросов: {len(questions) - 3} + последние 3:</i>\n\n" + questions_text

        text = (
            "🔖<b>РЕДАКТОР Экзаменов</b> / Создание экзамена\n"
            f"🟢<b>Название:</b> {exam_name}\n"
            f"📊 <b>Всего вопросов:</b> {question_number}\n\n"
            f"{questions_text}"
            f"🟡<b>Вопрос {question_number + 1}:</b> введи текст вопроса\n\n"
            "Для продолжения отправь текст вопроса или сохрани текущие вопросы"
        )

        await message.answer(text, reply_markup=get_exam_questions_keyboard(), parse_mode="HTML")

        log_user_action(message.from_user.id, "exam_question_added", f"Вопрос {question_number}")

    except Exception as e:
        await message.answer("Произошла ошибка при обработке вопроса")
        log_user_error(message.from_user.id, "process_exam_question_error", str(e))


@router.callback_query(F.data == "exam_save_questions", ExamStates.waiting_for_exam_question)
async def callback_exam_save_questions(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Сохранение вопросов экзамена → запрос проходного балла"""
    try:
        await callback.answer()

        data = await state.get_data()
        exam_name = data.get("exam_name", "")
        questions = data.get("exam_questions") or []

        if not questions:
            await callback.answer("Нет вопросов для сохранения", show_alert=True)
            return

        text = (
            "🔖<b>РЕДАКТОР Экзаменов</b> / Создание экзамена\n"
            f"🟢<b>Название:</b> {exam_name}\n\n"
            "✅ Добавление вопросов завершено.\n"
            "Теперь введи проходной балл для экзамена"
        )

        await callback.message.edit_text(text, parse_mode="HTML")
        await state.set_state(ExamStates.waiting_for_exam_passing_score)

    except Exception as e:
        await callback.answer("Произошла ошибка")
        log_user_error(callback.from_user.id, "exam_save_questions_error", str(e))


@router.message(ExamStates.waiting_for_exam_passing_score)
async def process_exam_passing_score(message: Message, state: FSMContext, session: AsyncSession):
    """Обработка проходного балла и создание экзамена в БД"""
    try:
        if is_main_menu_text(message.text.strip()):
            return

        try:
            passing_score = float(message.text.strip())
            if passing_score <= 0:
                await message.answer("❌ Проходной балл должен быть положительным числом")
                return
        except ValueError:
            await message.answer("❌ Введи корректное число (например: 30)")
            return

        data = await state.get_data()
        exam_name = data.get("exam_name")
        questions = data.get("exam_questions") or []
        company_id = data.get("company_id")

        user = await get_user_by_tg_id(session, message.from_user.id)

        # Создаём экзамен в БД
        repo = AssessmentRepository(session)
        exam = await repo.create(
            name=exam_name,
            passing_score=passing_score,
            creator_id=user.id,
            company_id=company_id,
            assessment_type="exam",
        )

        if exam:
            for q in questions:
                await repo.add_question(
                    attestation_id=exam.id,
                    question_text=q["text"],
                    max_points=q["max_points"],
                    question_number=q["number"],
                )

        text = (
            "🔖<b>РЕДАКТОР Экзаменов</b> / Создание экзамена\n"
            f"🟢<b>Название:</b> {exam_name}\n\n"
            f"✅ Экзамен «{exam_name}» успешно создан!\n"
            f"📋 Вопросов добавлено: {len(questions)}\n"
            f"💕 Проходной балл: {passing_score:.1f}\n\n"
            "Теперь ты можешь передать данный экзамен нужному экзаменатору и экзаменуемому"
        )

        await message.answer(text, parse_mode="HTML")

        # Показываем обновленное меню
        await show_exam_menu(message, state, session, user)

        log_user_action(message.from_user.id, "exam_created", f"Экзамен: {exam_name}")

    except Exception as e:
        await message.answer("Произошла ошибка при создании экзамена")
        log_user_error(message.from_user.id, "process_exam_passing_score_error", str(e))


# ================== Flow D: Карточка экзамена ==================


@router.callback_query(F.data.startswith("exam_view:"), ExamStates.main_menu)
async def callback_exam_view(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Просмотр карточки экзамена"""
    try:
        await callback.answer()

        exam_id = int(callback.data.split(":")[1])
        data = await state.get_data()
        company_id = data.get("company_id")

        exam = await AssessmentRepository(session).get_by_id(exam_id, company_id=company_id)
        if not exam:
            await callback.message.edit_text("Экзамен не найден")
            return

        user = await get_user_by_tg_id(session, callback.from_user.id)
        active_role = data.get("role") if data.get("is_admin") else None
        roles = await _get_user_exam_roles(user, active_role=active_role)

        # Формируем текст карточки
        questions_text = ""
        for q in exam.questions:
            questions_text += (
                f"  ✅ <b>Вопрос {q.question_number}:</b>\n     {q.question_text}\n     Ставь {q.max_points:.0f}\n\n"
            )

        text = (
            f"🔖<b>РЕДАКТОР Экзаменов</b>\n"
            f"📋 <b>Экзамен:</b> {exam.name}\n"
            f"📋 <b>Всего вопросов:</b> {len(exam.questions)}\n\n"
            f"{questions_text}"
            f"💕 <b>Проходной балл:</b> {exam.passing_score:.1f}\n"
            f"🎯 <b>Максимальный балл:</b> {exam.max_score:.1f}"
        )

        keyboard = get_exam_card_keyboard(
            exam_id,
            is_recruiter=roles["is_recruiter"],
            can_assign=roles["is_recruiter"] or roles["is_mentor"],
        )

        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)

        await state.update_data(current_exam_id=exam_id)
        await state.set_state(ExamStates.viewing_exam)

        log_user_action(callback.from_user.id, "exam_view", f"Просмотр экзамена: {exam.name}")

    except Exception as e:
        await callback.message.edit_text("Произошла ошибка при просмотре экзамена")
        log_user_error(callback.from_user.id, "exam_view_error", str(e))


# ================== Удаление экзамена ==================


@router.callback_query(F.data.startswith("exam_delete:"), ExamStates.viewing_exam)
async def callback_exam_delete(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Подтверждение удаления экзамена"""
    try:
        await callback.answer()

        exam_id = int(callback.data.split(":")[1])
        data = await state.get_data()
        company_id = data.get("company_id")

        exam = await AssessmentRepository(session).get_by_id(exam_id, company_id=company_id)
        if not exam:
            await callback.message.edit_text("Экзамен не найден")
            return

        text = f"🗑 <b>Удалить экзамен «{exam.name}»?</b>\n\nЭто действие нельзя будет отменить."

        await callback.message.edit_text(
            text, parse_mode="HTML", reply_markup=get_exam_confirm_delete_keyboard(exam_id)
        )

    except Exception as e:
        await callback.message.edit_text("Произошла ошибка")
        log_user_error(callback.from_user.id, "exam_delete_error", str(e))


@router.callback_query(F.data.startswith("exam_confirm_delete:"), ExamStates.viewing_exam)
async def callback_exam_confirm_delete(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Фактическое удаление экзамена"""
    try:
        await callback.answer()

        exam_id = int(callback.data.split(":")[1])
        data = await state.get_data()
        company_id = data.get("company_id")

        success = await AssessmentRepository(session).delete(exam_id, company_id=company_id)

        if success:
            await callback.message.edit_text("✅ Экзамен успешно удалён")
            log_user_action(callback.from_user.id, "exam_deleted", f"Удалён экзамен ID: {exam_id}")
        else:
            await callback.message.edit_text("❌ Не удалось удалить экзамен. Возможно, он используется в траекториях.")

        await show_exam_menu(callback, state, session)

    except Exception as e:
        await callback.message.edit_text("Произошла ошибка при удалении")
        log_user_error(callback.from_user.id, "exam_confirm_delete_error", str(e))
