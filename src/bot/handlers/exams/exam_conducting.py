"""
Обработчики проведения экзаменов: список для экзаменатора, прохождение вопросов,
результаты, список для сдающего.
"""

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.db import get_user_by_tg_id
from bot.keyboards.keyboards import is_main_menu_text
from bot.repositories import AssessmentAssignmentRepository, AssessmentResultRepository
from bot.states.states import ExamStates
from bot.utils.logger import log_user_action, log_user_error

router = Router()


# ================== Flow F: Провести экзамен (экзаменатор) ==================


@router.callback_query(F.data == "exam_conduct", ExamStates.main_menu)
async def callback_exam_conduct(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Список назначенных экзаменов для экзаменатора"""
    try:
        await callback.answer()

        user = await get_user_by_tg_id(session, callback.from_user.id)
        if not user:
            await callback.message.edit_text("Ты не зарегистрирован в системе.")
            return

        data = await state.get_data()
        company_id = data.get("company_id")

        assignments = await AssessmentAssignmentRepository(session).get_exam_assignments_for_examiner(
            user.id, company_id=company_id
        )

        if not assignments:
            await callback.message.edit_text(
                "🔍<b>Экзамены 🔍</b>\n\n❌ Нет назначенных экзаменов для проведения.",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(
                    inline_keyboard=[[InlineKeyboardButton(text="🔙 Назад", callback_data="exam_back_to_menu")]]
                ),
            )
            return

        # Формируем список сдающих
        text = "🔍<b>Экзамены 🔍</b>\nСписок сотрудников, которые готовы пройти экзамен 👋\n\n"

        keyboard = InlineKeyboardMarkup(inline_keyboard=[])

        for assignment in assignments:
            examinee = assignment.trainee
            exam = assignment.attestation

            text += (
                f"── 🟢 <b>ФИО:</b> {examinee.full_name}\n"
                f"   📊 <b>Экзамен:</b> {exam.name}\n"
                f"   📍 <b>Объект работы:</b> {examinee.work_object.name if examinee.work_object else 'Не указан'}\n\n"
            )

            keyboard.inline_keyboard.append(
                [
                    InlineKeyboardButton(
                        text=examinee.full_name,
                        callback_data=f"exam_conduct_select:{assignment.id}",
                    )
                ]
            )

        text += "Выбери сотрудника на клавиатуре"
        keyboard.inline_keyboard.append([InlineKeyboardButton(text="🔙 Назад", callback_data="exam_back_to_menu")])

        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)
        await state.set_state(ExamStates.selecting_examinee_for_exam)

        log_user_action(user.tg_id, "exam_conduct_list", f"Открыт список для проведения: {len(assignments)} экзаменов")

    except Exception as e:
        await callback.message.edit_text("Произошла ошибка")
        log_user_error(callback.from_user.id, "exam_conduct_error", str(e))


@router.callback_query(F.data.startswith("exam_conduct_select:"), ExamStates.selecting_examinee_for_exam)
async def callback_exam_conduct_select(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Выбран сдающий — карточка управления экзаменом"""
    try:
        await callback.answer()

        assignment_id = int(callback.data.split(":")[1])
        data = await state.get_data()
        company_id = data.get("company_id")

        assignment = await AssessmentAssignmentRepository(session).get_by_id(assignment_id, company_id=company_id)
        if not assignment:
            await callback.message.edit_text("Экзамен не найден")
            return

        examinee = assignment.trainee
        exam = assignment.attestation

        text = (
            "🔍<b>Экзамен 🔍</b>\n"
            "Управление экзаменом\n\n"
            f"👤 <b>ФИО:</b> {examinee.full_name}\n"
            f"📊 <b>Экзамен:</b> {exam.name}\n"
            f"📍 <b>Объект стажировки:</b> {examinee.internship_object.name if examinee.internship_object else 'Не указан'}\n"
            f"📍 <b>Объект работы:</b> {examinee.work_object.name if examinee.work_object else 'Не указан'}"
        )

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🚀 Начать экзамен", callback_data=f"exam_start:{assignment_id}")],
                [InlineKeyboardButton(text="🔙 Назад", callback_data="exam_conduct")],
            ]
        )

        await state.update_data(exam_assignment_id=assignment_id)
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)
        await state.set_state(ExamStates.viewing_exam_details)

    except Exception as e:
        await callback.message.edit_text("Произошла ошибка")
        log_user_error(callback.from_user.id, "exam_conduct_select_error", str(e))


@router.callback_query(F.data == "exam_conduct", ExamStates.viewing_exam_details)
async def callback_exam_back_to_conduct(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Возврат к списку экзаменов (из деталей)"""
    await state.set_state(ExamStates.main_menu)
    await callback_exam_conduct(callback, state, session)


@router.callback_query(F.data.startswith("exam_start:"), ExamStates.viewing_exam_details)
async def callback_exam_start(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Подтверждение старта экзамена"""
    try:
        await callback.answer()

        assignment_id = int(callback.data.split(":")[1])

        text = "🚀 <b>Начать экзамен?</b>"

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text="✅ Да", callback_data="exam_confirm_start"),
                    InlineKeyboardButton(text="❌ Нет", callback_data=f"exam_conduct_select:{assignment_id}"),
                ]
            ]
        )

        await state.update_data(exam_assignment_id=assignment_id)
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)

    except Exception as e:
        await callback.message.edit_text("Произошла ошибка")
        log_user_error(callback.from_user.id, "exam_start_error", str(e))


@router.callback_query(F.data == "exam_confirm_start", ExamStates.viewing_exam_details)
async def callback_exam_confirm_start(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Подтверждение — начинаем прохождение вопросов"""
    try:
        await callback.answer()

        data = await state.get_data()
        assignment_id = data.get("exam_assignment_id")
        company_id = data.get("company_id")

        # Начинаем сессию
        await AssessmentAssignmentRepository(session).start_session(assignment_id, company_id=company_id)

        await state.update_data(exam_current_question=0, exam_answers=[])

        # Показываем первый вопрос
        await _show_exam_question(callback.message, state, session, is_callback=True)

    except Exception as e:
        await callback.message.edit_text("Произошла ошибка при начале экзамена")
        log_user_error(callback.from_user.id, "exam_confirm_start_error", str(e))


async def _show_exam_question(message, state: FSMContext, session: AsyncSession, is_callback: bool = False):
    """Показ вопроса экзамена"""
    try:
        data = await state.get_data()
        assignment_id = data.get("exam_assignment_id")
        current_index = data.get("exam_current_question", 0)
        company_id = data.get("company_id")

        assignment = await AssessmentAssignmentRepository(session).get_by_id(assignment_id, company_id=company_id)
        if not assignment:
            await message.edit_text("Экзамен не найден") if is_callback else await message.answer("Экзамен не найден")
            return

        exam = assignment.attestation
        questions = exam.questions

        if current_index >= len(questions):
            # Все вопросы пройдены
            await _show_exam_results(message, state, session)
            return

        question = questions[current_index]

        text = (
            f"<b>Вопрос {current_index + 1}:</b>\n\n"
            f"{question.question_text}\n\n"
            f"🎯 <b>Максимальный балл:</b> {question.max_points:.1f}\n\n"
            "💡 <b>Инструкция:</b> Задай вопрос сдающему, выслушай ответ и введи балл."
        )

        if is_callback:
            await message.edit_text(text, parse_mode="HTML")
        else:
            await message.answer(text, parse_mode="HTML")

        await state.set_state(ExamStates.waiting_for_exam_score)

    except Exception as e:
        log_user_error(0, "show_exam_question_error", str(e))


@router.message(ExamStates.waiting_for_exam_score)
async def process_exam_score(message: Message, state: FSMContext, session: AsyncSession):
    """Обработка ввода балла за вопрос экзамена"""
    try:
        score_text = message.text.strip()

        if is_main_menu_text(score_text):
            data = await state.get_data()
            company_id = data.get("company_id")
            await state.clear()
            await state.update_data(company_id=company_id)
            return

        try:
            score = float(score_text)
        except ValueError:
            await message.answer("❌ Введи корректный балл (число)")
            return

        data = await state.get_data()
        assignment_id = data.get("exam_assignment_id")
        current_index = data.get("exam_current_question", 0)
        answers = data.get("exam_answers", [])
        company_id = data.get("company_id")

        assignment = await AssessmentAssignmentRepository(session).get_by_id(assignment_id, company_id=company_id)
        exam = assignment.attestation
        questions = exam.questions

        if current_index >= len(questions):
            await message.answer("Ошибка: неверный индекс вопроса")
            return

        question = questions[current_index]

        if score > question.max_points:
            await message.answer(f"❌ Балл не может быть больше {question.max_points:.1f}")
            return

        if score < 0:
            await message.answer("❌ Балл не может быть отрицательным")
            return

        # Сохраняем ответ
        answers.append({"question_id": question.id, "score": score, "max_score": question.max_points})

        next_index = current_index + 1
        await state.update_data(exam_current_question=next_index, exam_answers=answers)

        await message.answer(f"✅ Балл {score:.1f} принят за вопрос {current_index + 1}")

        log_user_action(message.from_user.id, "exam_score_entered", f"Балл {score} за вопрос {current_index + 1}")

        if next_index < len(questions):
            question = questions[next_index]
            text = (
                f"<b>Вопрос {next_index + 1}:</b>\n\n"
                f"{question.question_text}\n\n"
                f"🎯 <b>Максимальный балл:</b> {question.max_points:.1f}\n\n"
                "💡 Введи балл:"
            )
            await message.answer(text, parse_mode="HTML")
        else:
            await _show_exam_results(message, state, session)

    except Exception as e:
        await message.answer("Произошла ошибка при обработке балла")
        log_user_error(message.from_user.id, "process_exam_score_error", str(e))


async def _show_exam_results(message, state: FSMContext, session: AsyncSession):
    """Показ результатов экзамена"""
    try:
        data = await state.get_data()
        assignment_id = data.get("exam_assignment_id")
        answers = data.get("exam_answers", [])
        company_id = data.get("company_id")

        assignment = await AssessmentAssignmentRepository(session).get_by_id(assignment_id, company_id=company_id)
        examinee = assignment.trainee
        exam = assignment.attestation

        total_score = sum(a["score"] for a in answers)
        max_score = sum(a["max_score"] for a in answers)
        is_passed = total_score >= exam.passing_score

        # Создаем результат
        result = await AssessmentResultRepository(session).create(
            examinee.id,
            exam.id,
            assignment.manager_id,
            total_score,
            max_score,
            is_passed,
            company_id=company_id,
        )

        if result:
            for answer in answers:
                await AssessmentResultRepository(session).save_question_result(
                    result.id, answer["question_id"], answer["score"], answer["max_score"]
                )

        # Завершаем сессию
        await AssessmentAssignmentRepository(session).complete_session(
            assignment_id,
            total_score,
            max_score,
            is_passed,
            company_id=company_id,
        )

        await session.commit()

        status_emoji = "🟢" if is_passed else "🔴"
        passed_text = "пройден" if is_passed else "не пройден"

        text = (
            f"{status_emoji} <b>Экзамен {passed_text}</b>\n\n"
            f"{status_emoji} <b>Экзамен:</b> {exam.name}\n"
            f"{status_emoji} <b>Экзаменуемый:</b> {examinee.full_name}\n"
            f"{status_emoji} <b>Набрано баллов:</b> {total_score:.1f}\n"
            f"{status_emoji} <b>Проходной балл:</b> {exam.passing_score:.1f}\n"
            f"📍 <b>Объект стажировки:</b> {examinee.internship_object.name if examinee.internship_object else 'Не указан'}\n"
            f"📍 <b>Объект работы:</b> {examinee.work_object.name if examinee.work_object else 'Не указан'}"
        )

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="≡ Главное меню", callback_data="main_menu")]]
        )

        await message.answer(text, parse_mode="HTML", reply_markup=keyboard)

        # Уведомление сдающему о результате
        await _send_exam_result_notification(session, message.bot, examinee, exam, total_score, is_passed, assignment)

        await state.clear()
        await state.update_data(company_id=company_id)

        log_user_action(
            message.from_user.id,
            "exam_completed",
            f"Экзамен {exam.name} для {examinee.full_name}: {total_score}/{max_score}, пройден: {is_passed}",
        )

    except Exception as e:
        await message.answer("Произошла ошибка при показе результатов")
        log_user_error(message.from_user.id, "show_exam_results_error", str(e))


async def _send_exam_result_notification(
    session: AsyncSession,
    bot,
    examinee,
    exam,
    total_score: float,
    is_passed: bool,
    assignment,
):
    """Уведомление сдающему о результате экзамена"""
    try:
        if is_passed:
            text = (
                f"✅ <b>Экзамен «{exam.name}» пройден!</b>\n\n"
                f"🎯 <b>Набрано баллов:</b> {total_score:.1f}\n"
                f"🏁 <b>Проходной балл:</b> {exam.passing_score:.1f}\n"
                f"👨‍⚖️ <b>Экзаменатор:</b> {assignment.manager.full_name}"
            )
        else:
            text = (
                f"❌ <b>Экзамен «{exam.name}» не пройден</b>\n\n"
                f"🎯 <b>Набрано баллов:</b> {total_score:.1f}\n"
                f"🏁 <b>Проходной балл:</b> {exam.passing_score:.1f}\n"
                f"👨‍⚖️ <b>Экзаменатор:</b> {assignment.manager.full_name}\n\n"
                "Свяжись с руководителем для пересдачи"
            )

        await bot.send_message(chat_id=examinee.tg_id, text=text, parse_mode="HTML")

    except Exception as e:
        log_user_error(0, "exam_result_notification_error", str(e))


# ================== Flow H: Сдать экзамен (read-only для сдающего) ==================


@router.callback_query(F.data == "exam_take", ExamStates.main_menu)
async def callback_exam_take(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Список назначенных экзаменов для сдающего (read-only)"""
    try:
        await callback.answer()

        user = await get_user_by_tg_id(session, callback.from_user.id)
        if not user:
            await callback.message.edit_text("Ты не зарегистрирован в системе.")
            return

        data = await state.get_data()
        company_id = data.get("company_id")

        assignments = await AssessmentAssignmentRepository(session).get_for_examinee(user.id, company_id=company_id)

        if not assignments:
            await callback.message.edit_text(
                "📝 <b>Мои экзамены</b>\n\nУ тебя пока нет назначенных экзаменов.",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(
                    inline_keyboard=[[InlineKeyboardButton(text="🔙 Назад", callback_data="exam_back_to_menu")]]
                ),
            )
            return

        text = "📝 <b>Мои экзамены</b>\n\nНазначенные экзамены:\n\n"

        for assignment in assignments:
            exam = assignment.attestation
            examiner = assignment.manager

            status_map = {
                "assigned": "🟡 Назначен",
                "in_progress": "🔄 В процессе",
                "completed": "✅ Пройден",
                "failed": "❌ Не пройден",
            }
            status = status_map.get(assignment.status, "❓")

            text += (
                f"📋 <b>Экзамен:</b> {exam.name}\n"
                f"👨‍⚖️ <b>Экзаменатор:</b> {examiner.full_name if examiner else '?'}\n"
                f"📊 <b>Статус:</b> {status}\n\n"
            )

        text += "Свяжитесь с руководителем, чтобы подтвердить все детали"

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="🔙 Назад", callback_data="exam_back_to_menu")]]
        )

        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)
        await state.set_state(ExamStates.viewing_my_exams)

        log_user_action(user.tg_id, "exam_take_list", "Просмотр назначенных экзаменов")

    except Exception as e:
        await callback.message.edit_text("Произошла ошибка")
        log_user_error(callback.from_user.id, "exam_take_error", str(e))
