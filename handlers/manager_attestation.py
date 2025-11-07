"""
Обработчики для управления аттестациями руководителями (Task 7).
Включает просмотр назначенных аттестаций, изменение даты/времени, проведение аттестации.
"""

from datetime import datetime
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from database.db import (
    get_user_by_tg_id, get_user_by_id, check_user_permission,
    get_manager_assigned_attestations, update_attestation_schedule, start_attestation_session,
    get_trainee_attestation_by_id, save_attestation_question_result, complete_attestation_session,
    get_attestation_by_id, change_trainee_to_employee, create_attestation_result
)
from handlers.auth import check_auth
from keyboards.keyboards import get_main_menu_keyboard, get_keyboard_by_role
from states.states import ManagerAttestationStates
from utils.logger import log_user_action, log_user_error

router = Router()


# ===============================
# Обработчики для Task 7: ЛК руководителя для управления аттестациями
# ===============================

@router.message(F.text.in_(["Аттестация", "Аттестация ✔️"]))
async def cmd_manager_attestations(message: Message, state: FSMContext, session: AsyncSession):
    """Обработчик кнопки 'Аттестация' в ЛК руководителя (ТЗ шаг 1-4)"""
    try:
        # Проверка авторизации
        is_auth = await check_auth(message, state, session)
        if not is_auth:
            return

        # Получение пользователя
        user = await get_user_by_tg_id(session, message.from_user.id)
        if not user:
            await message.answer("Ты не зарегистрирован в системе.")
            return

        # Проверка роли руководителя
        has_permission = await check_user_permission(session, user.id, "conduct_attestations")
        if not has_permission:
            await message.answer(
                "❌ <b>Недостаточно прав</b>\n\n"
                "У тебя нет прав для проведения аттестаций.\n"
                "Обратись к администратору.",
                parse_mode="HTML"
            )
            return

        # Получаем список назначенных аттестаций
        assigned_attestations = await get_manager_assigned_attestations(session, user.id)

        if not assigned_attestations:
            await message.answer(
                "🔍<b>Аттестация🔍</b>\n\n"
                "❌ <b>Стажеры не найдены</b>\n\n"
                "У тебя нет назначенных стажеров на аттестацию.\n"
                "Обратись к наставнику для назначения стажеров.",
                parse_mode="HTML",
                reply_markup=get_main_menu_keyboard()
            )
            return

        # Формируем список стажеров согласно ТЗ
        message_text = (
            "🔍<b>Аттестация🔍</b>\n"
            "Ниже список сотрудников, которые готовы пройти аттестацию👇\n\n"
        )

        keyboard = InlineKeyboardMarkup(inline_keyboard=[])

        for assignment in assigned_attestations:
            trainee = assignment.trainee
            attestation = assignment.attestation

            # Добавляем информацию о стажере согласно ТЗ
            message_text += (
                f"🧑 <b>ФИО:</b> {trainee.full_name}\n"
                f"🏁<b>Аттестация:</b> {attestation.name} ⛔️\n"
                f"📍<b>2️⃣Объект работы:</b> {trainee.work_object.name if trainee.work_object else 'Не указан'}\n"
                f"🟢<b>Дата:</b> {assignment.scheduled_date or ''}\n"
                f"🟢<b>Время:</b> {assignment.scheduled_time or ''}\n\n"
            )

            # Добавляем кнопку для выбора стажера
            keyboard.inline_keyboard.append([
                InlineKeyboardButton(
                    text=f"{trainee.full_name}",
                    callback_data=f"select_trainee_attestation:{assignment.id}"
                )
            ])

        message_text += "Выбери стажёра на клавиатуре"

        # Кнопка "Назад"
        keyboard.inline_keyboard.append([
            InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu")
        ])

        await message.answer(
            message_text,
            parse_mode="HTML",
            reply_markup=keyboard
        )

        log_user_action(user.tg_id, "manager_attestations_opened", "Открыт список назначенных аттестаций")

    except Exception as e:
        await message.answer("Произошла ошибка при открытии списка аттестаций")
        log_user_error(message.from_user.id, "manager_attestations_error", str(e))


@router.callback_query(F.data.startswith("select_trainee_attestation:"))
async def callback_select_trainee_attestation(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Обработчик выбора стажера для управления аттестацией (ТЗ шаг 5-6)"""
    try:
        await callback.answer()

        assignment_id = int(callback.data.split(":")[1])

        # Получаем данные назначенной аттестации
        assignment = await get_trainee_attestation_by_id(session, assignment_id)
        if not assignment:
            await callback.message.edit_text("Аттестация не найдена")
            return

        trainee = assignment.trainee
        attestation = assignment.attestation

        # Сохраняем ID в состоянии
        await state.update_data(assignment_id=assignment_id)

        # Формируем сообщение согласно ТЗ
        message_text = (
            "🔍<b>Аттестация🔍</b>\n"
            "🙋‍♂️<b>Управление стажёром</b>\n\n"
            f"🧑 <b>ФИО:</b> {trainee.full_name}\n"
            f"🏁<b>Аттестация:</b> {attestation.name} ⛔️\n"
            f"📍<b>2️⃣Объект работы:</b> {trainee.work_object.name if trainee.work_object else 'Не указан'}\n"
            f"🟢<b>Дата:</b> {assignment.scheduled_date or ''}\n"
            f"🟢<b>Время:</b> {assignment.scheduled_time or ''}"
        )

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🚀 Начать аттестацию", callback_data=f"start_attestation:{assignment_id}")],
            [InlineKeyboardButton(text="📅 Изменить дату", callback_data=f"change_attestation_date:{assignment_id}")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_attestations")]
        ])

        await callback.message.edit_text(
            message_text,
            parse_mode="HTML",
            reply_markup=keyboard
        )

        log_user_action(callback.from_user.id, "trainee_attestation_selected", f"Выбран стажер {trainee.full_name} для управления аттестацией")

    except Exception as e:
        await callback.message.edit_text("Произошла ошибка при выборе стажера")
        log_user_error(callback.from_user.id, "select_trainee_attestation_error", str(e))


@router.callback_query(F.data.startswith("change_attestation_date:"))
async def callback_change_attestation_date(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Обработчик изменения даты аттестации (ТЗ шаг 7-8)"""
    try:
        await callback.answer()

        assignment_id = int(callback.data.split(":")[1])
        await state.update_data(assignment_id=assignment_id)

        # Получаем данные аттестации
        assignment = await get_trainee_attestation_by_id(session, assignment_id)
        if not assignment:
            await callback.message.edit_text("Аттестация не найдена")
            return

        trainee = assignment.trainee
        attestation = assignment.attestation

        # Формируем сообщение для ввода даты согласно ТЗ
        message_text = (
            "🔍<b>Аттестация🔍</b>\n"
            "🙋‍♂️<b>Управление стажёром</b>\n\n"
            f"🧑 <b>ФИО:</b> {trainee.full_name}\n"
            f"🏁<b>Аттестация:</b> {attestation.name} ⛔️\n"
            f"📍<b>2️⃣Объект работы:</b> {trainee.work_object.name if trainee.work_object else 'Не указан'}\n"
            "🟡<b>Дата:</b> \n"
            "🟡<b>Время:</b>\n\n"
            "<b>Укажите новую дату аттестации:</b>"
        )

        await callback.message.edit_text(
            message_text,
            parse_mode="HTML"
        )

        await state.set_state(ManagerAttestationStates.waiting_for_date)
        log_user_action(callback.from_user.id, "date_change_requested", f"Запрошено изменение даты аттестации для стажера {trainee.full_name}")

    except Exception as e:
        await callback.message.edit_text("Произошла ошибка при изменении даты")
        log_user_error(callback.from_user.id, "change_date_error", str(e))


@router.message(ManagerAttestationStates.waiting_for_date)
async def process_new_date(message: Message, state: FSMContext, session: AsyncSession):
    """Обработчик ввода новой даты (ТЗ шаг 9-10)"""
    try:
        new_date = message.text.strip()
        
        # Сохраняем дату в состоянии
        await state.update_data(new_date=new_date)
        
        state_data = await state.get_data()
        assignment_id = state_data.get("assignment_id")
        
        # Получаем данные аттестации
        assignment = await get_trainee_attestation_by_id(session, assignment_id)
        if not assignment:
            await message.answer("Аттестация не найдена")
            return

        trainee = assignment.trainee
        attestation = assignment.attestation

        # Формируем сообщение для ввода времени согласно ТЗ
        message_text = (
            "🔍<b>Аттестация🔍</b>\n"
            "🙋‍♂️<b>Управление стажёром</b>\n\n"
            f"🧑 <b>ФИО:</b> {trainee.full_name}\n"
            f"🏁<b>Аттестация:</b> {attestation.name} ⛔️\n"
            f"📍<b>2️⃣Объект работы:</b> {trainee.work_object.name if trainee.work_object else 'Не указан'}\n"
            f"🟢<b>Дата:</b> {new_date}\n"
            "🟡<b>Время:</b>\n"
            "<b>Укажите новое время аттестации:</b>"
        )

        await message.answer(
            message_text,
                parse_mode="HTML"
            )

        await state.set_state(ManagerAttestationStates.waiting_for_time)
        log_user_action(message.from_user.id, "date_entered", f"Введена дата: {new_date}")

    except Exception as e:
        await message.answer("Произошла ошибка при обработке даты")
        log_user_error(message.from_user.id, "process_date_error", str(e))


@router.message(ManagerAttestationStates.waiting_for_time)
async def process_new_time(message: Message, state: FSMContext, session: AsyncSession):
    """Обработчик ввода нового времени (ТЗ шаг 11-13)"""
    try:
        new_time = message.text.strip()
        
        state_data = await state.get_data()
        assignment_id = state_data.get("assignment_id")
        new_date = state_data.get("new_date")
        
        # Получаем данные аттестации
        assignment = await get_trainee_attestation_by_id(session, assignment_id)
        if not assignment:
            await message.answer("Аттестация не найдена")
            return

        trainee = assignment.trainee
        attestation = assignment.attestation

        # Формируем сообщение подтверждения согласно ТЗ
        message_text = (
            "🔍<b>Аттестация🔍</b>\n"
            "🙋‍♂️<b>Управление стажёром</b>\n\n"
            f"🧑 <b>ФИО:</b> {trainee.full_name}\n"
            f"🏁<b>Аттестация:</b> {attestation.name} ⛔️\n"
            f"📍<b>2️⃣Объект работы:</b> {trainee.work_object.name if trainee.work_object else 'Не указан'}\n"
            f"🟢<b>Дата:</b> {new_date}\n"
            f"🟢<b>Время:</b> {new_time}\n\n"
            "🟡<b>Сохранить новую дату и время?</b>"
        )

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Да", callback_data="save_new_schedule"),
                InlineKeyboardButton(text="❌ Отменить", callback_data="cancel_schedule_change")
            ]
        ])

        # Сохраняем время в состоянии
        await state.update_data(new_time=new_time)

        await message.answer(
            message_text,
            parse_mode="HTML",
            reply_markup=keyboard
        )

        await state.set_state(ManagerAttestationStates.confirming_schedule)
        log_user_action(message.from_user.id, "time_entered", f"Введено время: {new_time}")

    except Exception as e:
        await message.answer("Произошла ошибка при обработке времени")
        log_user_error(message.from_user.id, "process_time_error", str(e))


@router.callback_query(F.data == "save_new_schedule", ManagerAttestationStates.confirming_schedule)
async def callback_save_new_schedule(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Обработчик сохранения нового расписания (ТЗ шаг 13-16)"""
    try:
        await callback.answer()

        state_data = await state.get_data()
        assignment_id = state_data.get("assignment_id")
        new_date = state_data.get("new_date")
        new_time = state_data.get("new_time")

        if not all([assignment_id, new_date, new_time]):
            await callback.message.edit_text("Ошибка: недостаточно данных")
            return

        # Обновляем расписание аттестации
        success = await update_attestation_schedule(session, assignment_id, new_date, new_time)
        if not success:
            await callback.message.edit_text("❌ Ошибка при сохранении расписания")
            return

        # Получаем обновленные данные
        assignment = await get_trainee_attestation_by_id(session, assignment_id)
        trainee = assignment.trainee

        # Отправляем уведомление стажеру согласно ТЗ (шаг 14)
        await send_schedule_change_notification_to_trainee(session, callback.message.bot, assignment_id)

        # Подтверждение руководителю (шаг 15)
        await callback.message.edit_text(
            "✅<b>Дата и время успешно изменены</b>",
            parse_mode="HTML"
        )

        # Сразу показываем меню управления (шаг 16)
        message_text = (
            "🔍<b>Аттестация🔍</b>\n"
            "🙋‍♂️<b>Управление стажёром</b>\n\n"
            f"🧑 <b>ФИО:</b> {trainee.full_name}\n"
            f"🏁<b>Аттестация:</b> {assignment.attestation.name} ⛔️\n"
            f"📍<b>2️⃣Объект работы:</b> {trainee.work_object.name if trainee.work_object else 'Не указан'}\n"
            f"🟢<b>Дата:</b> {assignment.scheduled_date}\n"
            f"🟢<b>Время:</b> {assignment.scheduled_time}"
        )

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🚀 Начать аттестацию", callback_data=f"start_attestation:{assignment_id}")],
            [InlineKeyboardButton(text="📅 Изменить дату", callback_data=f"change_attestation_date:{assignment_id}")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_attestations")]
        ])

        await callback.message.answer(
            message_text,
            parse_mode="HTML",
            reply_markup=keyboard
        )

        await state.clear()
        log_user_action(callback.from_user.id, "schedule_saved", f"Сохранено новое расписание: {new_date} {new_time}")

    except Exception as e:
        await callback.message.edit_text("Произошла ошибка при сохранении расписания")
        log_user_error(callback.from_user.id, "save_schedule_error", str(e))


@router.callback_query(F.data.startswith("start_attestation:"))
async def callback_start_attestation(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Обработчик начала аттестации (ТЗ части 3, шаг 1-4)"""
    try:
        await callback.answer()

        assignment_id = int(callback.data.split(":")[1])
        await state.update_data(assignment_id=assignment_id)

        # Получаем данные аттестации
        assignment = await get_trainee_attestation_by_id(session, assignment_id)
        if not assignment:
            await callback.message.edit_text("Аттестация не найдена")
            return

        trainee = assignment.trainee
        attestation = assignment.attestation

        # Формируем сообщение подтверждения начала согласно ТЗ
        message_text = (
            "🔍<b>Аттестация🔍</b>\n"
            "🚀<b>Старт🚀</b>\n\n"
            f"🧑 <b>ФИО:</b> {trainee.full_name}\n"
            f"🏁<b>Аттестация:</b> {attestation.name} ⛔️\n"
            f"📍<b>2️⃣Объект работы:</b> {trainee.work_object.name if trainee.work_object else 'Не указан'}\n"
            f"🟢<b>Дата:</b> {assignment.scheduled_date or ''}\n"
            f"🟢<b>Время:</b> {assignment.scheduled_time or ''}\n\n"
            "<b>Начать аттестацию для стажёра?</b>"
        )

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Да", callback_data="confirm_start_attestation"),
                InlineKeyboardButton(text="❌ Нет", callback_data=f"select_trainee_attestation:{assignment_id}")
            ]
        ])

        await callback.message.edit_text(
            message_text,
            parse_mode="HTML",
            reply_markup=keyboard
        )

        log_user_action(callback.from_user.id, "attestation_start_requested", f"Запрошено начало аттестации для стажера {trainee.full_name}")

    except Exception as e:
        await callback.message.edit_text("Произошла ошибка при начале аттестации")
        log_user_error(callback.from_user.id, "start_attestation_error", str(e))


@router.callback_query(F.data == "confirm_start_attestation")
async def callback_confirm_start_attestation(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Обработчик подтверждения начала аттестации - начало прохождения вопросов (ТЗ шаг 5-11)"""
    try:
        await callback.answer()

        state_data = await state.get_data()
        assignment_id = state_data.get("assignment_id")

        # Получаем данные аттестации
        assignment = await get_trainee_attestation_by_id(session, assignment_id)
        if not assignment:
            await callback.message.edit_text("Аттестация не найдена")
            return

        # Начинаем сессию аттестации
        await start_attestation_session(session, assignment_id)

        # Инициализируем прохождение вопросов
        await state.update_data(
            assignment_id=assignment_id,
            current_question_index=0,
            answers=[]
        )

        # Показываем первый вопрос
        await show_attestation_question(callback, state, session)

    except Exception as e:
        await callback.message.edit_text("Произошла ошибка при подтверждении начала аттестации")
        log_user_error(callback.from_user.id, "confirm_start_error", str(e))


async def show_attestation_question(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Показ вопроса аттестации согласно ТЗ (шаг 5-9)"""
    try:
        state_data = await state.get_data()
        assignment_id = state_data.get("assignment_id")
        current_index = state_data.get("current_question_index", 0)

        # Получаем данные аттестации
        assignment = await get_trainee_attestation_by_id(session, assignment_id)
        attestation = assignment.attestation
        questions = attestation.questions

        if current_index >= len(questions):
            # Все вопросы пройдены, показываем результат
            await show_attestation_results_message(callback.message, state, session)
            return

        question = questions[current_index]

        # Формируем вопрос согласно ТЗ (шаг 5) с полными критериями оценки
        question_text = (
            f"<b>Вопрос {current_index + 1}:</b>\n\n"
            f"{question.question_text}\n\n"
            f"🎯 <b>Максимальный балл:</b> {question.max_points:.1f}\n\n"
            "💡 <b>Инструкция:</b> Задай вопрос стажеру голосом, выслушай ответ и введи балл согласно критериям в вопросе."
        )

        await callback.message.edit_text(
            question_text,
            parse_mode="HTML"
        )

        # Руководитель должен задать вопрос стажеру голосом, выслушать ответ,
        # а затем ввести балл (шаги 6-9)
        
        # Ждем ввода балла от руководителя
        await state.set_state(ManagerAttestationStates.waiting_for_score)
        
        log_user_action(callback.from_user.id, "question_shown", f"Показан вопрос {current_index + 1}")

    except Exception as e:
        await callback.message.edit_text("Произошла ошибка при показе вопроса")
        log_user_error(callback.from_user.id, "show_question_error", str(e))


@router.message(ManagerAttestationStates.waiting_for_score)
async def process_question_score(message: Message, state: FSMContext, session: AsyncSession):
    """Обработчик ввода балла за вопрос (ТЗ шаг 9-11)"""
    try:
        # Получаем балл
        try:
            score = float(message.text.strip())
        except ValueError:
            await message.answer("❌ Введи корректный балл (число)")
            return

        state_data = await state.get_data()
        assignment_id = state_data.get("assignment_id")
        current_index = state_data.get("current_question_index", 0)
        answers = state_data.get("answers", [])

        # Получаем данные аттестации
        assignment = await get_trainee_attestation_by_id(session, assignment_id)
        attestation = assignment.attestation
        questions = attestation.questions

        if current_index >= len(questions):
            await message.answer("Ошибка: неверный индекс вопроса")
            return

        question = questions[current_index]

        # Проверяем что балл не превышает максимум
        if score > question.max_points:
            await message.answer(f"❌ Балл не может быть больше {question.max_points:.1f}")
            return

        if score < 0:
            await message.answer("❌ Балл не может быть отрицательным")
            return

        # Сохраняем ответ
        answers.append({
            "question_id": question.id,
            "score": score,
            "max_score": question.max_points
        })

        # Переходим к следующему вопросу
        next_index = current_index + 1
        await state.update_data(
            current_question_index=next_index,
            answers=answers
        )

        log_user_action(message.from_user.id, "score_entered", f"Введен балл {score} за вопрос {current_index + 1}")
        
        # Подтверждаем принятие балла
        await message.answer(f"✅ Балл {score:.1f} принят за вопрос {current_index + 1}")

        # Показываем следующий вопрос или результат
        if next_index < len(questions):
            # Есть еще вопросы
            question = questions[next_index]
            question_text = (
                f"<b>Вопрос {next_index + 1}:</b>\n\n"
                f'"{question.question_text}"\n\n'
            )

            await message.answer(question_text, parse_mode="HTML")
        else:
            # Все вопросы завершены
            await show_attestation_results_message(message, state, session)

    except Exception as e:
        await message.answer("Произошла ошибка при обработке балла")
        log_user_error(message.from_user.id, "process_score_error", str(e))


async def show_attestation_results_message(message: Message, state: FSMContext, session: AsyncSession):
    """Показ результатов аттестации (ТЗ часть 3-2, шаг 12)"""
    try:
        state_data = await state.get_data()
        assignment_id = state_data.get("assignment_id")
        answers = state_data.get("answers", [])

        # Получаем данные аттестации
        assignment = await get_trainee_attestation_by_id(session, assignment_id)
        trainee = assignment.trainee
        attestation = assignment.attestation

        # Подсчитываем результат
        total_score = sum(answer["score"] for answer in answers)
        max_score = sum(answer["max_score"] for answer in answers)
        is_passed = total_score >= attestation.passing_score

        # Создаем результат аттестации
        attestation_result = await create_attestation_result(
            session, trainee.id, attestation.id, assignment.manager_id,
            total_score, max_score, is_passed
        )

        # Сохраняем детали по вопросам
        for answer in answers:
            await save_attestation_question_result(
                session, attestation_result.id, answer["question_id"], 
                answer["score"], answer["max_score"]
            )

        # Завершаем сессию аттестации
        await complete_attestation_session(session, assignment_id, total_score, max_score, is_passed)
        
        # Сохраняем все изменения в базу данных
        await session.commit()

        if is_passed:
            # Успех аттестации (ТЗ шаг 12-3)
            message_text = (
                "✅<b>Аттестация успешно пройдена</b>\n\n"
                f"🧑 <b>ФИО:</b> {trainee.full_name}\n"
                f"🏁<b>Проходной балл:</b> {attestation.passing_score:.1f}\n"
                f"🎯<b>Набрано баллов:</b> {total_score:.1f}\n"
                f"🏁<b>Аттестация:</b> {attestation.name} ✅\n"
                f"📍<b>2️⃣Объект работы:</b> {trainee.work_object.name if trainee.work_object else 'Не указан'}\n"
                f"🟢<b>Дата:</b> {assignment.scheduled_date or ''}\n"
                f"🟢<b>Время:</b> {assignment.scheduled_time or ''}"
            )

            # Отправляем результат руководителю
            await message.answer(message_text, parse_mode="HTML")
            
            # Уведомляем стажера об успехе (ТЗ шаг 12-4)
            await send_attestation_success_notification(
                session, message.bot, trainee, attestation, total_score, attestation.passing_score,
                assignment.manager.full_name, assignment.manager.username,
                assignment.scheduled_date, assignment.scheduled_time
            )

        else:
            # Провал аттестации (ТЗ шаг 12-1)
            message_text = (
                "❌<b>Аттестация провалена❌</b>\n\n"
                f"🧑 <b>ФИО:</b> {trainee.full_name}\n"
                f"🏁<b>Проходной балл:</b> {attestation.passing_score:.1f}\n"
                f"🎯<b>Набрано баллов:</b> {total_score:.1f}\n"
                f"🏁<b>Аттестация:</b> {attestation.name} ⛔️\n"
                f"📍<b>2️⃣Объект работы:</b> {trainee.work_object.name if trainee.work_object else 'Не указан'}\n"
                f"🟢<b>Дата:</b> {assignment.scheduled_date or ''}\n"
                f"🟢<b>Время:</b> {assignment.scheduled_time or ''}"
            )

            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🚀 Начать аттестацию", callback_data=f"start_attestation:{assignment_id}")],
                [InlineKeyboardButton(text="👨‍💼 Сделать сотрудником", callback_data=f"make_employee_anyway:{assignment_id}")],
                [InlineKeyboardButton(text="📅 Изменить дату", callback_data=f"change_attestation_date:{assignment_id}")],
                [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_attestations")]
            ])

            await message.answer(
                message_text,
                parse_mode="HTML",
                reply_markup=keyboard if not is_passed else None
            )

            # Уведомляем стажера о провале (ТЗ шаг 12-2)  
            await send_attestation_failure_notification(
                session, message.bot, trainee, attestation, total_score, attestation.passing_score,
                assignment.manager.full_name, assignment.manager.username,
                assignment.scheduled_date, assignment.scheduled_time
            )

        await state.clear()
        log_user_action(message.from_user.id, "attestation_completed", f"Завершена аттестация для {trainee.full_name}: {total_score}/{max_score}, пройдена: {is_passed}")

    except Exception as e:
        await message.answer("Произошла ошибка при показе результатов")
        log_user_error(message.from_user.id, "show_results_error", str(e))


# Вспомогательные функции для уведомлений

async def send_schedule_change_notification_to_trainee(session: AsyncSession, bot, assignment_id: int):
    """Отправка уведомления стажеру об изменении даты/времени (ТЗ шаг 14)"""
    try:
        assignment = await get_trainee_attestation_by_id(session, assignment_id)
        if not assignment:
            return

        trainee = assignment.trainee
        manager = assignment.manager
        attestation = assignment.attestation

        notification_text = (
            "❗️<b>Изменены дата и время аттестации</b>\n\n"
            f"🏁<b>Аттестация:</b> {attestation.name} ⛔️\n"
            f"🟢<b>Руководитель:</b> {manager.full_name}\n"
            f"👤 <b>Username:</b> @{manager.username or 'не указан'}\n"
            f"🟢<b>Дата:</b> {assignment.scheduled_date}\n"
            f"🟢<b>Время:</b> {assignment.scheduled_time}"
        )

        await bot.send_message(
            chat_id=trainee.tg_id,
            text=notification_text,
            parse_mode="HTML"
        )

    except Exception as e:
        log_user_error(0, "schedule_change_notification_error", str(e))


async def send_attestation_success_notification(session: AsyncSession, bot, trainee, attestation, 
                                              score, passing_score, manager_name, manager_username, date, time):
    """Уведомление стажеру об успешной аттестации (ТЗ шаг 12-4)"""
    try:
        notification_text = (
            "✅<b>Аттестация успешно пройдена</b>\n\n"
            f"🏁<b>Проходной балл:</b> {passing_score:.1f}\n"
            f"🎯<b>Набрано баллов:</b> {score:.1f}\n"
            f"🏁<b>Аттестация:</b> {attestation.name} ✅\n"
            f"🟢<b>Руководитель:</b> {manager_name}\n"
            f"👤 <b>Username:</b> @{manager_username or 'не указан'}\n"
            f"🟢<b>Дата:</b> {date or ''}\n"
            f"🟢<b>Время:</b> {time or ''}\n\n"
            "🚀<b>Нажми на кнопку, чтобы стать сотрудником!👇</b>"
            )

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="👨‍💼 Стать сотрудником", callback_data="become_employee")]
        ])

        await bot.send_message(
            chat_id=trainee.tg_id,
            text=notification_text,
            parse_mode="HTML",
            reply_markup=keyboard
        )

    except Exception as e:
        log_user_error(0, "success_notification_error", str(e))


async def send_attestation_failure_notification(session: AsyncSession, bot, trainee, attestation,
                                              score, passing_score, manager_name, manager_username, date, time):
    """Уведомление стажеру о провале аттестации (ТЗ шаг 12-2)"""
    try:
        notification_text = (
            "❌<b>Аттестация провалена❌</b>\n\n"
            f"🏁<b>Проходной балл:</b> {passing_score:.1f}\n"
            f"🎯<b>Набрано баллов:</b> {score:.1f}\n"
            f"🏁<b>Аттестация:</b> {attestation.name} ⛔️\n"
            f"🟢<b>Руководитель:</b> {manager_name}\n"
            f"👤 <b>Username:</b> @{manager_username or 'не указан'}\n"
            f"🟢<b>Дата:</b> {date or ''}\n"
            f"🟢<b>Время:</b> {time or ''}\n\n"
            "<b>Договорись с руководителем, когда тебе нужно пройти аттестацию повторно</b>"
        )

        await bot.send_message(
            chat_id=trainee.tg_id,
            text=notification_text,
            parse_mode="HTML"
        )

    except Exception as e:
        log_user_error(0, "failure_notification_error", str(e))


@router.callback_query(F.data.startswith("make_employee_anyway:"))
async def callback_make_employee_anyway(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Обработчик кнопки 'Сделать сотрудником' при провале аттестации"""
    try:
        await callback.answer()
        
        assignment_id = int(callback.data.split(":")[1])
        
        # Получаем данные аттестации
        assignment = await get_trainee_attestation_by_id(session, assignment_id)
        if not assignment:
            await callback.message.edit_text("Аттестация не найдена")
            return
            
        trainee = assignment.trainee
        
        # Проверяем права руководителя
        manager = await get_user_by_tg_id(session, callback.from_user.id)
        if not manager or manager.id != assignment.manager_id:
            await callback.message.edit_text("❌ У тебя нет прав для изменения статуса этого стажера")
            return
            
        # Меняем роль стажера на сотрудника несмотря на провал
        success = await change_trainee_to_employee(session, trainee.id, None)
        if not success:
            await callback.message.edit_text("❌ Ошибка при изменении роли стажера")
            return
        
        # Подтверждение руководителю
        await callback.message.edit_text(
            f"✅ <b>Стажер переведен в сотрудники</b>\n\n"
            f"🧑 <b>ФИО:</b> {trainee.full_name}\n"
            f"👑 <b>Новая роль:</b> Сотрудник\n\n"
            "<i>Стажер переведен в сотрудники по решению руководителя, "
            "несмотря на неуспешную аттестацию.</i>",
            parse_mode="HTML"
        )
        
        # Уведомляем стажера о переводе
        await callback.message.bot.send_message(
            chat_id=trainee.tg_id,
            text=(
                "🎉 <b>Поздравляем! Ты стал сотрудником!</b>\n\n"
                f"👨‍💼 <b>Руководитель:</b> {manager.full_name}\n"
                f"📅 <b>Дата перевода:</b> {datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n"
                "<i>Ты переведён в сотрудники по решению руководителя.</i>\n\n"
                "🚀 <b>Используй /start чтобы обновить меню</b>"
            ),
            parse_mode="HTML"
        )
        
        await state.clear()
        log_user_action(callback.from_user.id, "employee_anyway", f"Руководитель {manager.full_name} сделал стажера {trainee.full_name} сотрудником несмотря на провал аттестации")
        
    except Exception as e:
        await callback.message.edit_text("Произошла ошибка при переводе в сотрудники")
        log_user_error(callback.from_user.id, "make_employee_anyway_error", str(e))


# Дополнительные обработчики

@router.callback_query(F.data == "back_to_attestations")
async def callback_back_to_attestations(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Возврат к списку аттестаций"""
    try:
        await callback.answer()
        await state.clear()
        
        # Получаем пользователя и проверяем права
        user = await get_user_by_tg_id(session, callback.from_user.id)
        if not user:
            await callback.message.edit_text("❌ Пользователь не найден")
            return
        
        # Проверяем права доступа
        has_permission = await check_user_permission(session, user.id, "conduct_attestations")
        if not has_permission:
            await callback.message.edit_text(
                "❌ <b>Недостаточно прав</b>\n\n"
                "У тебя нет прав для проведения аттестаций.\n"
                "Обратись к администратору.",
                parse_mode="HTML"
            )
            return
        
        # Получаем аттестации для руководителя
        manager_attestations = await get_manager_assigned_attestations(session, user.id)
        
        if not manager_attestations:
            await callback.message.edit_text(
                "🔍 <b>Аттестация стажеров</b>\n\n"
                "❌ У тебя пока нет назначенных аттестаций.\n\n"
                "Аттестации назначают наставники через кнопку 'Аттестация' в разделе 'Мои стажёры'.",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
                ])
            )
            return
        
        # Формируем список аттестаций
        attestations_list = []
        for i, attestation_data in enumerate(manager_attestations, 1):
            trainee = attestation_data['trainee']
            attestation = attestation_data['attestation']
            assignment = attestation_data['assignment']
            
            status_text = {
                'assigned': '🟡 Назначена',
                'in_progress': '🔄 В процессе',
                'completed': '✅ Завершена',
                'failed': '❌ Провалена'
            }.get(assignment.status, '❓ Неизвестно')
            
            scheduled_info = ""
            if assignment.scheduled_date and assignment.scheduled_time:
                scheduled_info = f"\n   📅 Дата: {assignment.scheduled_date.strftime('%d.%m.%Y')} в {assignment.scheduled_time.strftime('%H:%M')}"
            
            attestations_list.append(
                f"<b>{i}. {trainee.full_name}</b>\n"
                f"   📋 Аттестация: {attestation.name}\n"
                f"   📊 Статус: {status_text}{scheduled_info}"
            )
        
        attestations_display = "\n\n".join(attestations_list)
        
        # Создаем клавиатуру для выбора аттестации
        keyboard = InlineKeyboardMarkup(inline_keyboard=[])
        
        for attestation_data in manager_attestations:
            assignment = attestation_data['assignment']
            trainee = attestation_data['trainee']
            
            keyboard.inline_keyboard.append([
                InlineKeyboardButton(
                    text=f"👤 {trainee.full_name}",
                    callback_data=f"manage_attestation:{assignment.id}"
                )
            ])
        
        keyboard.inline_keyboard.append([
            InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")
        ])
        
        await callback.message.edit_text(
            f"🔍 <b>Аттестация стажеров</b>\n\n"
            f"👨‍💼 <b>Руководитель:</b> {user.full_name}\n"
            f"📊 <b>Всего аттестаций:</b> {len(manager_attestations)}\n\n"
            f"{attestations_display}\n\n"
            "Выбери стажера для управления аттестацией:",
            reply_markup=keyboard,
            parse_mode="HTML"
        )

    except Exception as e:
        await callback.message.edit_text("Произошла ошибка при возврате к списку")
        log_user_error(callback.from_user.id, "back_to_attestations_error", str(e))


@router.callback_query(F.data == "cancel_schedule_change")
async def callback_cancel_schedule_change(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Отмена изменения расписания"""
    try:
        await callback.answer()
        
        state_data = await state.get_data()
        assignment_id = state_data.get("assignment_id")
        
        await state.clear()
        await state.update_data(assignment_id=assignment_id)
        
        # Возвращаемся к управлению стажером
        await callback_select_trainee_attestation(
            type('MockCallback', (), {
                'data': f'select_trainee_attestation:{assignment_id}',
                'message': callback.message,
                'from_user': callback.from_user,
                'answer': lambda *args, **kwargs: None
            })(), 
            state, session
        )
    
    except Exception as e:
        await callback.message.edit_text("Произошла ошибка при отмене")
        log_user_error(callback.from_user.id, "cancel_schedule_error", str(e))