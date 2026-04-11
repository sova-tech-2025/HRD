"""
Обработчики назначения экзаменов: выбор экзаменатора, фильтрация сдающих, назначение.
"""

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.db import get_all_groups, get_all_objects, get_user_by_id, get_user_by_tg_id
from bot.keyboards.keyboards import (
    exam_filters,
    get_exam_examiner_list_keyboard,
    is_main_menu_text,
)
from bot.repositories import AssessmentAssignmentRepository, AssessmentRepository
from bot.states.states import ExamStates
from bot.utils.logger import log_user_action, log_user_error

router = Router()


# ================== Flow E: Назначение экзамена ==================


@router.callback_query(F.data.startswith("exam_assign:"), ExamStates.viewing_exam)
async def callback_exam_assign(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Начало назначения экзамена — показываем список экзаменаторов"""
    try:
        await callback.answer()

        exam_id = int(callback.data.split(":")[1])
        data = await state.get_data()
        company_id = data.get("company_id")

        exam = await AssessmentRepository(session).get_by_id(exam_id, company_id=company_id)
        if not exam:
            await callback.message.edit_text("Экзамен не найден")
            return

        examiners = await AssessmentAssignmentRepository(session).get_examiners(company_id=company_id)

        if not examiners:
            await callback.message.edit_text(
                "❌ Нет доступных экзаменаторов (руководителей, сотрудников или рекрутеров).",
                reply_markup=InlineKeyboardMarkup(
                    inline_keyboard=[[InlineKeyboardButton(text="🔙 Назад", callback_data="exam_back_to_menu")]]
                ),
            )
            return

        text = (
            f"🔖<b>РЕДАКТОР Экзаменов</b>\n"
            f"📋 <b>Экзамен:</b> {exam.name}\n"
            f"📋 <b>Всего вопросов:</b> {len(exam.questions)}\n\n"
            "👨‍⚖️ <b>Экзаменатор:</b>\nВыбери экзаменатора из списка"
        )

        await state.update_data(
            assign_exam_id=exam_id,
            exam_examiner_ids=[u.id for u in examiners],
        )
        await callback.message.edit_text(
            text, parse_mode="HTML", reply_markup=get_exam_examiner_list_keyboard(examiners)
        )
        await state.set_state(ExamStates.selecting_examiner)

    except Exception as e:
        await callback.message.edit_text("Произошла ошибка")
        log_user_error(callback.from_user.id, "exam_assign_error", str(e))


@router.callback_query(F.data.startswith("exam_examiner_page:"), ExamStates.selecting_examiner)
async def callback_exam_examiner_page(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Пагинация списка экзаменаторов"""
    try:
        await callback.answer()
        page = int(callback.data.split(":")[1])
        data = await state.get_data()
        examiner_ids = data.get("exam_examiner_ids", [])

        examiners = []
        for uid in examiner_ids:
            u = await get_user_by_id(session, uid)
            if u:
                examiners.append(u)

        await callback.message.edit_reply_markup(reply_markup=get_exam_examiner_list_keyboard(examiners, page=page))
    except Exception as e:
        log_user_error(callback.from_user.id, "exam_examiner_page_error", str(e))


@router.callback_query(F.data == "exam_back_to_card")
async def callback_exam_back_to_card(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Возврат к карточке экзамена"""
    try:
        await callback.answer()
        data = await state.get_data()
        exam_id = data.get("assign_exam_id") or data.get("current_exam_id")
        if exam_id:
            # Имитируем просмотр карточки
            callback.data = f"exam_view:{exam_id}"
            await state.set_state(ExamStates.main_menu)
            from bot.handlers.exams.exam_menu import callback_exam_view

            await callback_exam_view(callback, state, session)
        else:
            from bot.handlers.exams.exam_menu import show_exam_menu

            await show_exam_menu(callback, state, session)
    except Exception as e:
        log_user_error(callback.from_user.id, "exam_back_to_card_error", str(e))


@router.callback_query(F.data.startswith("exam_examiner:"), ExamStates.selecting_examiner)
async def callback_exam_examiner_selected(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Выбран экзаменатор — показываем фильтры для сдающего"""
    try:
        await callback.answer()

        examiner_id = int(callback.data.split(":")[1])
        examiner = await get_user_by_id(session, examiner_id)
        if not examiner:
            await callback.message.edit_text("Экзаменатор не найден")
            return

        data = await state.get_data()
        company_id = data.get("company_id")
        exam_id = data.get("assign_exam_id")

        exam = await AssessmentRepository(session).get_by_id(exam_id, company_id=company_id)

        await state.update_data(assign_examiner_id=examiner_id, assign_examiner_name=examiner.full_name)

        groups = await get_all_groups(session, company_id=company_id)
        objects = await get_all_objects(session, company_id=company_id)

        text = (
            f"🔖<b>РЕДАКТОР Экзаменов</b>\n"
            f"📋 <b>Экзамен:</b> {exam.name}\n"
            f"📋 <b>Всего вопросов:</b> {len(exam.questions)}\n"
            f"👨‍⚖️ <b>Экзаменатор:</b> {examiner.full_name}\n\n"
            "👤 <b>Сдающий:</b>\nВыберите способ поиска сдающего"
        )

        await callback.message.edit_text(
            text,
            parse_mode="HTML",
            reply_markup=exam_filters.filter_menu(groups, objects),
        )
        await state.set_state(ExamStates.selecting_examinee_filter)

    except Exception as e:
        await callback.message.edit_text("Произошла ошибка")
        log_user_error(callback.from_user.id, "exam_examiner_selected_error", str(e))


# ================== Фильтрация сдающих ==================


@router.callback_query(F.data == exam_filters.cb_back)
async def callback_exam_back_to_filters(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Возврат к фильтрам сдающих"""
    try:
        await callback.answer()
        data = await state.get_data()
        company_id = data.get("company_id")
        exam_id = data.get("assign_exam_id")
        examiner_name = data.get("assign_examiner_name", "")

        exam = await AssessmentRepository(session).get_by_id(exam_id, company_id=company_id)
        groups = await get_all_groups(session, company_id=company_id)
        objects = await get_all_objects(session, company_id=company_id)

        text = (
            f"🔖<b>РЕДАКТОР Экзаменов</b>\n"
            f"📋 <b>Экзамен:</b> {exam.name if exam else '?'}\n"
            f"👨‍⚖️ <b>Экзаменатор:</b> {examiner_name}\n\n"
            "👤 <b>Сдающий:</b>\nВыберите способ поиска сдающего"
        )

        await callback.message.edit_text(
            text,
            parse_mode="HTML",
            reply_markup=exam_filters.filter_menu(groups, objects),
        )
        await state.set_state(ExamStates.selecting_examinee_filter)

    except Exception as e:
        log_user_error(callback.from_user.id, "exam_back_to_filters_error", str(e))


@router.callback_query(F.data == exam_filters.cb_all, ExamStates.selecting_examinee_filter)
async def callback_exam_filter_all(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Фильтр: все пользователи"""
    try:
        await callback.answer()
        data = await state.get_data()
        company_id = data.get("company_id")

        users = await AssessmentAssignmentRepository(session).get_users_for_exam_assignment(
            company_id, filter_type="all"
        )
        await _show_examinee_list(callback, state, users)
    except Exception as e:
        log_user_error(callback.from_user.id, "exam_filter_all_error", str(e))


@router.callback_query(F.data == exam_filters.cb_groups, ExamStates.selecting_examinee_filter)
async def callback_exam_filter_groups(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Фильтр: по группам — показать список групп"""
    try:
        await callback.answer()
        data = await state.get_data()
        company_id = data.get("company_id")

        groups = await get_all_groups(session, company_id=company_id)

        await callback.message.edit_text(
            "🗂️ <b>Выбери группу:</b>",
            parse_mode="HTML",
            reply_markup=exam_filters.group_list(groups),
        )
    except Exception as e:
        log_user_error(callback.from_user.id, "exam_filter_groups_error", str(e))


@router.callback_query(F.data.startswith(exam_filters.prefix + "_group:"))
async def callback_exam_group_selected(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Выбрана группа — показать пользователей группы"""
    try:
        await callback.answer()
        group_id = int(callback.data.split(":")[1])
        data = await state.get_data()
        company_id = data.get("company_id")

        users = await AssessmentAssignmentRepository(session).get_users_for_exam_assignment(
            company_id, filter_type="group", filter_id=group_id
        )
        await state.update_data(exam_filter_type="group", exam_filter_id=group_id)
        await _show_examinee_list(callback, state, users)
    except Exception as e:
        log_user_error(callback.from_user.id, "exam_group_selected_error", str(e))


@router.callback_query(F.data == exam_filters.cb_objects, ExamStates.selecting_examinee_filter)
async def callback_exam_filter_objects(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Фильтр: по объектам — показать список объектов"""
    try:
        await callback.answer()
        data = await state.get_data()
        company_id = data.get("company_id")

        objects = await get_all_objects(session, company_id=company_id)

        await callback.message.edit_text(
            "📍 <b>Выбери объект:</b>",
            parse_mode="HTML",
            reply_markup=exam_filters.object_list(objects),
        )
    except Exception as e:
        log_user_error(callback.from_user.id, "exam_filter_objects_error", str(e))


@router.callback_query(F.data.startswith(exam_filters.prefix + "_object:"))
async def callback_exam_object_selected(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Выбран объект — показать пользователей объекта"""
    try:
        await callback.answer()
        object_id = int(callback.data.split(":")[1])
        data = await state.get_data()
        company_id = data.get("company_id")

        users = await AssessmentAssignmentRepository(session).get_users_for_exam_assignment(
            company_id, filter_type="object", filter_id=object_id
        )
        await state.update_data(exam_filter_type="object", exam_filter_id=object_id)
        await _show_examinee_list(callback, state, users)
    except Exception as e:
        log_user_error(callback.from_user.id, "exam_object_selected_error", str(e))


@router.callback_query(F.data == exam_filters.cb_search, ExamStates.selecting_examinee_filter)
async def callback_exam_filter_search(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Фильтр: поиск по ФИО"""
    try:
        await callback.answer()

        await callback.message.edit_text(
            "🟣 <b>Поиск по ФИО</b>\n\nВведи имя или часть имени:",
            parse_mode="HTML",
        )
        await state.set_state(ExamStates.searching_examinee_by_name)
    except Exception as e:
        log_user_error(callback.from_user.id, "exam_filter_search_error", str(e))


@router.message(ExamStates.searching_examinee_by_name)
async def process_exam_search_query(message: Message, state: FSMContext, session: AsyncSession):
    """Обработка поискового запроса по ФИО"""
    try:
        query = message.text.strip()

        if is_main_menu_text(query):
            return

        data = await state.get_data()
        company_id = data.get("company_id")

        users = await AssessmentAssignmentRepository(session).get_users_for_exam_assignment(
            company_id, filter_type="search", search_query=query
        )

        if not users:
            await message.answer(
                f"❌ По запросу «{query}» никого не найдено. Попробуй другое имя:",
            )
            return

        # Сохраняем список для пагинации
        await state.update_data(
            exam_filtered_users=[u.id for u in users],
            exam_filter_type="search",
        )

        keyboard = exam_filters.user_list(users)
        await message.answer(
            f"🔍 Найдено: {len(users)}\nВыбери сдающего:",
            reply_markup=keyboard,
        )
        await state.set_state(ExamStates.selecting_examinee)

    except Exception as e:
        await message.answer("Произошла ошибка при поиске")
        log_user_error(message.from_user.id, "process_exam_search_error", str(e))


async def _show_examinee_list(callback: CallbackQuery, state: FSMContext, users: list):
    """Показ списка сдающих"""
    if not users:
        await callback.message.edit_text(
            "❌ Пользователи не найдены.",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[[InlineKeyboardButton(text="🔙 Назад", callback_data=exam_filters.cb_back)]]
            ),
        )
        return

    await state.update_data(exam_filtered_users=[u.id for u in users])

    keyboard = exam_filters.user_list(users)
    await callback.message.edit_text(
        f"👤 Найдено: {len(users)}\nВыбери сдающего:",
        reply_markup=keyboard,
    )
    await state.set_state(ExamStates.selecting_examinee)


# ================== Пагинация сдающих ==================


@router.callback_query(F.data.startswith(exam_filters.prefix + "_upage:"), ExamStates.selecting_examinee)
async def callback_exam_examinee_page(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Пагинация списка сдающих"""
    try:
        await callback.answer()
        page = int(callback.data.split(":")[1])
        data = await state.get_data()
        user_ids = data.get("exam_filtered_users", [])

        # Загружаем пользователей
        users = []
        for uid in user_ids:
            u = await get_user_by_id(session, uid)
            if u:
                users.append(u)

        keyboard = exam_filters.user_list(users, page=page)
        await callback.message.edit_text(
            f"👤 Найдено: {len(users)}\nВыбери сдающего:",
            reply_markup=keyboard,
        )
    except Exception as e:
        log_user_error(callback.from_user.id, "exam_examinee_page_error", str(e))


# ================== Карточка сдающего + назначение ==================


@router.callback_query(F.data.startswith(exam_filters.prefix + "_user:"), ExamStates.selecting_examinee)
async def callback_exam_examinee_selected(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Выбран сдающий — показываем его карточку"""
    try:
        await callback.answer()

        examinee_id = int(callback.data.split(":")[1])
        examinee = await get_user_by_id(session, examinee_id)
        if not examinee:
            await callback.message.edit_text("Пользователь не найден")
            return

        data = await state.get_data()
        exam_id = data.get("assign_exam_id")
        examiner_name = data.get("assign_examiner_name", "")
        company_id = data.get("company_id")

        exam = await AssessmentRepository(session).get_by_id(exam_id, company_id=company_id)

        role_name = examinee.roles[0].name if examinee.roles else "Без роли"
        group_name = examinee.groups[0].name if examinee.groups else "Не указана"

        text = (
            f"📋 <b>Экзамен:</b> {exam.name if exam else '?'}\n"
            f"👨‍⚖️ <b>Экзаменатор:</b> {examiner_name}\n\n"
            f"👤 <b>Карточка пользователя</b>\n"
            f"📞 <b>Номер:</b> {examinee.phone_number}\n"
            f"📅 <b>Дата регистрации:</b> {examinee.registration_date.strftime('%d.%m.%Y') if examinee.registration_date else '-'}\n"
            f"🔵 <b>Статус:</b> {'Активен' if examinee.is_activated else 'Не активирован'}\n"
            f"🗂️ <b>Группа:</b> {group_name}\n"
            f"👑 <b>Роль:</b> {role_name}\n"
            f"📍 <b>Объект работы:</b> {examinee.work_object.name if examinee.work_object else 'Не указан'}"
        )

        await state.update_data(assign_examinee_id=examinee_id, assign_examinee_name=examinee.full_name)

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="📌 Назначить экзамен", callback_data="exam_confirm_assign")],
                [InlineKeyboardButton(text="🔙 Назад", callback_data=exam_filters.cb_back)],
            ]
        )

        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)
        await state.set_state(ExamStates.viewing_examinee_card)

    except Exception as e:
        await callback.message.edit_text("Произошла ошибка")
        log_user_error(callback.from_user.id, "exam_examinee_selected_error", str(e))


@router.callback_query(F.data == "exam_confirm_assign", ExamStates.viewing_examinee_card)
async def callback_exam_confirm_assign(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Подтверждение назначения экзамена"""
    try:
        await callback.answer()

        data = await state.get_data()
        exam_id = data.get("assign_exam_id")
        examiner_id = data.get("assign_examiner_id")
        examinee_id = data.get("assign_examinee_id")
        examiner_name = data.get("assign_examiner_name", "")
        examinee_name = data.get("assign_examinee_name", "")
        company_id = data.get("company_id")

        if not all([exam_id, examiner_id, examinee_id]):
            await callback.message.edit_text("❌ Недостаточно данных для назначения")
            return

        user = await get_user_by_tg_id(session, callback.from_user.id)

        # Назначаем экзамен (используем тот же механизм что и аттестации)
        assignment = await AssessmentAssignmentRepository(session).assign(
            trainee_id=examinee_id,
            manager_id=examiner_id,
            attestation_id=exam_id,
            assigned_by_id=user.id,
            company_id=company_id,
        )

        if not assignment:
            await callback.message.edit_text("❌ Ошибка при назначении экзамена")
            return

        await session.commit()

        exam = await AssessmentRepository(session).get_by_id(exam_id, company_id=company_id)

        text = (
            "🔖<b>РЕДАКТОР Экзамена</b>🔖\n"
            "✅ <b>ЭКЗАМЕН НАЗНАЧЕН</b> ✅\n\n"
            f"📋 <b>Экзамен:</b> {exam.name if exam else '?'}\n"
            f"📋 <b>Всего вопросов:</b> {len(exam.questions) if exam else 0}\n"
            f"👨‍⚖️ <b>Экзаменатор:</b> {examiner_name}\n"
            f"💛 <b>Сдающий:</b> {examinee_name}\n\n"
            "Уведомление об экзамене направлено экзаменатору и сдающему 📩"
        )

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="≡ Главное меню", callback_data="main_menu")]]
        )

        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)

        # Отправляем уведомления
        await _send_exam_notifications(
            session,
            callback.message.bot,
            exam,
            examiner_id,
            examinee_id,
            examiner_name,
            examinee_name,
        )

        await state.clear()
        # Восстанавливаем company_id
        await state.update_data(company_id=company_id)

        log_user_action(
            callback.from_user.id,
            "exam_assigned",
            f"Экзамен {exam.name if exam else exam_id} назначен: экзаменатор={examiner_name}, сдающий={examinee_name}",
        )

    except Exception as e:
        await callback.message.edit_text("Произошла ошибка при назначении экзамена")
        log_user_error(callback.from_user.id, "exam_confirm_assign_error", str(e))


# ================== Уведомления ==================


async def _send_exam_notifications(
    session: AsyncSession,
    bot,
    exam,
    examiner_id: int,
    examinee_id: int,
    examiner_name: str,
    examinee_name: str,
):
    """Отправка уведомлений экзаменатору и сдающему"""
    try:
        examiner = await get_user_by_id(session, examiner_id)
        examinee = await get_user_by_id(session, examinee_id)

        # Уведомление экзаменатору
        if examiner:
            examiner_text = (
                "📝 <b>Тебе назначен экзамен для проведения</b>\n\n"
                f"📋 <b>Экзамен:</b> {exam.name}\n"
                f"💛 <b>Сдающий:</b> {examinee_name}\n"
                f"📍 <b>Объект работы:</b> {examinee.work_object.name if examinee and examinee.work_object else 'Не указан'}\n\n"
                "Свяжись со сдающим, чтобы подтвердить все детали"
            )
            try:
                await bot.send_message(chat_id=examiner.tg_id, text=examiner_text, parse_mode="HTML")
            except Exception as e:
                log_user_error(0, "exam_notification_examiner_error", str(e))

        # Уведомление сдающему (Flow G)
        if examinee:
            examinee_text = (
                f"📝 <b>Тебе назначен Экзамен: {exam.name}</b>\n\n"
                f"👨‍⚖️ <b>Экзаменатор:</b> {examiner_name}\n"
                f"🏪 <b>Объект стажировки:</b> {examinee.internship_object.name if examinee.internship_object else 'Не указан'}\n"
                f"📍 <b>Объект работы:</b> {examinee.work_object.name if examinee.work_object else 'Не указан'}\n\n"
                "Свяжись с руководителем, чтобы точно подтвердить все детали"
            )
            try:
                await bot.send_message(chat_id=examinee.tg_id, text=examinee_text, parse_mode="HTML")
            except Exception as e:
                log_user_error(0, "exam_notification_examinee_error", str(e))

    except Exception as e:
        log_user_error(0, "send_exam_notifications_error", str(e))
