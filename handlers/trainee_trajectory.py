"""
Обработчики для прохождения траекторий стажерами.
Включает просмотр траектории, выбор этапов, сессий и прохождение тестов.
"""

from aiogram import Router, F
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from database.db import (
    get_trainee_learning_path, get_trainee_stage_progress,
    get_stage_session_progress, get_learning_path_stages,
    complete_stage_for_trainee, complete_session_for_trainee,
    get_user_test_result, get_user_by_tg_id, get_user_by_id, check_user_permission,
    get_trainee_attestation_status
)
from config import TRAINEE_TRAJECTORY_IMAGE_FILE_ID, TRAINEE_TRAJECTORY_IMAGE_PATH
from handlers.auth import check_auth, ensure_callback_auth, get_current_user
from keyboards.keyboards import get_main_menu_keyboard, get_mentor_contact_keyboard
from utils.logger import logger, log_user_action, log_user_error
from utils.test_progress_formatters import get_test_status_icon, format_test_line_figma

router = Router()


# ==============================
# Вспомогательные функции
# ==============================

async def build_trajectory_text(session, user, trainee_path, company_id=None):
    """
    Собирает полный текст траектории в формате Figma 17.4.
    Возвращает (text, stages_progress).
    """
    if company_id is None:
        company_id = user.company_id

    path_name = trainee_path.learning_path.name if trainee_path.learning_path else "Не найдена"
    text = f"📖 Тебе назначена траектория: <b>{path_name}</b>\n\n"

    stages_progress = await get_trainee_stage_progress(session, trainee_path.id, company_id=company_id)

    for stage_progress in stages_progress:
        stage = stage_progress.stage
        sessions_progress = await get_stage_session_progress(session, stage_progress.id)

        # Подсчет тестов в этапе
        total_tests = 0
        passed_tests = 0
        for sp in sessions_progress:
            if hasattr(sp.session, 'tests') and sp.session.tests:
                for test in sp.session.tests:
                    total_tests += 1
                    test_result = await get_user_test_result(session, user.id, test.id, company_id=company_id)
                    if test_result and test_result.is_passed:
                        passed_tests += 1

        all_completed = (passed_tests == total_tests and total_tests > 0)

        # Статус доступа этапа (Figma)
        if all_completed and stage_progress.is_opened:
            access_text = "этап пройден ✅"
        elif stage_progress.is_opened:
            access_text = "открыт ♻️"
        else:
            access_text = "закрыт ❌"

        text += f"<b>Этап {stage.order_number} ▾</b>\n"
        text += f"{stage.name}\n"
        text += f"Доступ: {access_text}\n\n"

        # Сессии (дни) и тесты
        for sp in sessions_progress:
            if not sp.session:
                continue
            text += f"<b>{sp.session.name}</b>\n"
            if hasattr(sp.session, 'tests') and sp.session.tests:
                for test in sp.session.tests:
                    test_result = await get_user_test_result(session, user.id, test.id, company_id=company_id)
                    is_passed = bool(test_result and test_result.is_passed)
                    icon = get_test_status_icon(is_passed, stage_progress.is_opened)
                    text += format_test_line_figma(test.name, icon)

        # Прогресс этапа
        if all_completed and stage_progress.is_opened:
            text += "\n👉 Этап завершен!\n"
        elif total_tests > 0:
            text += f"\n👉 Пройдено: {passed_tests}/{total_tests} тестов\n"

        text += "______________________________\n\n"

    # Аттестация
    text += await format_attestation_status(session, user.id, trainee_path)

    return text, stages_progress


def get_no_trajectory_text() -> str:
    """Текст при отсутствии назначенной траектории (Figma 17.5)."""
    return (
        "Твой наставник пока не назначил тебе траекторию обучения 🥹\n\n"
        "Как только он это сделает, ты сможешь приступить к обучению. "
        "Если хочешь ускорить процесс — свяжись с наставником напрямую"
    )


def _get_trajectory_photo():
    """Получает источник фото для баннера траектории"""
    if TRAINEE_TRAJECTORY_IMAGE_FILE_ID:
        return TRAINEE_TRAJECTORY_IMAGE_FILE_ID
    if TRAINEE_TRAJECTORY_IMAGE_PATH:
        try:
            return FSInputFile(TRAINEE_TRAJECTORY_IMAGE_PATH)
        except Exception:
            pass
    return None


async def _safe_edit_message(message, text, reply_markup=None, parse_mode=None):
    """Редактирует сообщение, корректно обрабатывая фото-сообщения (edit_caption вместо edit_text)."""
    if message.photo:
        try:
            await message.edit_caption(
                caption=text,
                reply_markup=reply_markup,
                parse_mode=parse_mode
            )
            return
        except TelegramBadRequest:
            pass
        # Fallback: удалить и отправить заново
        try:
            await message.delete()
        except Exception:
            pass
        photo_source = _get_trajectory_photo()
        if photo_source:
            try:
                await message.answer_photo(
                    photo=photo_source,
                    caption=text,
                    reply_markup=reply_markup,
                    parse_mode=parse_mode
                )
                return
            except Exception:
                pass
        await message.answer(text, reply_markup=reply_markup, parse_mode=parse_mode)
    else:
        await message.edit_text(
            text,
            reply_markup=reply_markup,
            parse_mode=parse_mode
        )


# ==============================
# Обработчики команд
# ==============================

@router.message(Command("trajectory"))
async def cmd_trajectory_slash(message: Message, state: FSMContext, session: AsyncSession):
    """Обработчик команды /trajectory для стажеров"""
    await cmd_trajectory(message, state, session)


@router.message(F.text.in_(["Траектория", "📖 Траектория обучения", "Траектория обучения 📖"]))
async def cmd_trajectory(message: Message, state: FSMContext, session: AsyncSession):
    """Обработчик команды 'Траектория' для стажеров"""
    try:
        is_auth = await check_auth(message, state, session)
        if not is_auth:
            return

        user = await get_current_user(message, state, session)
        if not user:
            await message.answer("Ты не зарегистрирован в системе.")
            return

        # Траектории доступны ТОЛЬКО стажерам
        user_roles = [role.name for role in user.roles]
        if "Стажер" not in user_roles:
            await message.answer(
                "❌ <b>Доступ запрещен</b>\n\n"
                "Траектории обучения доступны только стажерам.\n"
                "После перехода в сотрудники ты получаешь доступ к тестам от рекрутера через рассылку.",
                parse_mode="HTML"
            )
            log_user_action(user.tg_id, "trajectory_access_denied", f"Пользователь с ролью {user_roles} попытался получить доступ к траектории")
            return

        company_id = user.company_id
        trainee_path = await get_trainee_learning_path(session, user.id, company_id=company_id)

        if not trainee_path:
            photo_source = _get_trajectory_photo()
            no_traj_text = get_no_trajectory_text()
            no_traj_keyboard = get_mentor_contact_keyboard()
            if photo_source:
                try:
                    await message.answer_photo(
                        photo=photo_source,
                        caption=no_traj_text,
                        reply_markup=no_traj_keyboard,
                        parse_mode="HTML"
                    )
                except Exception as e:
                    logger.warning(f"Не удалось отправить фото траектории: {e}")
                    await message.answer(no_traj_text, parse_mode="HTML", reply_markup=no_traj_keyboard)
            else:
                await message.answer(no_traj_text, parse_mode="HTML", reply_markup=no_traj_keyboard)
            log_user_action(user.tg_id, "trajectory_not_assigned", "Стажер попытался открыть траекторию, но она не назначена")
            return

        trajectory_text, stages_progress = await build_trajectory_text(session, user, trainee_path, company_id)

        available_stages = [sp for sp in stages_progress if sp.is_opened and not sp.is_completed]

        keyboard_buttons = []
        if available_stages:
            trajectory_text += "Выбери этап траектории 👇"
            for sp in available_stages:
                keyboard_buttons.append([
                    InlineKeyboardButton(
                        text=f"Этап {sp.stage.order_number}",
                        callback_data=f"select_stage:{sp.stage.id}"
                    )
                ])
        else:
            trajectory_text += "❌ Нет открытых этапов для прохождения"

        keyboard_buttons.append([
            InlineKeyboardButton(text="☰ Главное меню", callback_data="main_menu")
        ])

        photo_source = _get_trajectory_photo()
        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
        if photo_source:
            try:
                await message.answer_photo(
                    photo=photo_source,
                    caption=trajectory_text,
                    reply_markup=keyboard,
                    parse_mode="HTML"
                )
            except Exception as e:
                logger.warning(f"Не удалось отправить фото траектории: {e}")
                await message.answer(trajectory_text, reply_markup=keyboard, parse_mode="HTML")
        else:
            await message.answer(trajectory_text, reply_markup=keyboard, parse_mode="HTML")

        log_user_action(user.tg_id, "trajectory_opened", f"Открыта траектория {trainee_path.learning_path.name}")

    except Exception as e:
        await message.answer("Произошла ошибка при открытии траектории")
        log_user_error(message.from_user.id, "trajectory_error", str(e))


@router.callback_query(F.data == "trainee_trajectory")
async def callback_trainee_trajectory(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Обработчик инлайн-кнопки 'Траектория обучения 📖' из меню стажера"""
    if not await ensure_callback_auth(callback, state, session):
        return
    try:
        await callback.message.delete()
    except Exception as e:
        logger.warning(f"Не удалось удалить сообщение: {e}")

    await cmd_trajectory(callback.message, state, session)
    await callback.answer()


@router.callback_query(F.data == "trajectory_command")
async def callback_trajectory_command(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Обработчик возврата к выбору этапов траектории"""
    try:
        await callback.answer()

        user = await get_user_by_tg_id(session, callback.from_user.id)
        if not user:
            await _safe_edit_message(callback.message,"Ты не зарегистрирован в системе.")
            return

        company_id = user.company_id
        trainee_path = await get_trainee_learning_path(session, user.id, company_id=company_id)

        if not trainee_path:
            try:
                await callback.message.delete()
            except Exception:
                pass
            photo_source = _get_trajectory_photo()
            no_traj_text = get_no_trajectory_text()
            no_traj_keyboard = get_mentor_contact_keyboard()
            if photo_source:
                try:
                    await callback.message.answer_photo(
                        photo=photo_source,
                        caption=no_traj_text,
                        reply_markup=no_traj_keyboard,
                        parse_mode="HTML"
                    )
                except Exception as e:
                    logger.warning(f"Не удалось отправить фото траектории: {e}")
                    await callback.message.answer(no_traj_text, parse_mode="HTML", reply_markup=no_traj_keyboard)
            else:
                await callback.message.answer(no_traj_text, parse_mode="HTML", reply_markup=no_traj_keyboard)
            log_user_action(user.tg_id, "trajectory_not_assigned", "Стажер попытался открыть траектории, но она не назначена")
            return

        trajectory_text, stages_progress = await build_trajectory_text(session, user, trainee_path, company_id)

        available_stages = [sp for sp in stages_progress if sp.is_opened and not sp.is_completed]

        keyboard_buttons = []
        if available_stages:
            trajectory_text += "Выбери этап траектории 👇"
            for sp in available_stages:
                keyboard_buttons.append([
                    InlineKeyboardButton(
                        text=f"Этап {sp.stage.order_number}",
                        callback_data=f"select_stage:{sp.stage.id}"
                    )
                ])
        else:
            trajectory_text += "❌ Нет открытых этапов для прохождения"

        keyboard_buttons.append([
            InlineKeyboardButton(text="☰ Главное меню", callback_data="main_menu")
        ])

        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
        photo_source = _get_trajectory_photo()
        if photo_source:
            try:
                await callback.message.delete()
            except Exception:
                pass
            try:
                await callback.message.answer_photo(
                    photo=photo_source,
                    caption=trajectory_text,
                    reply_markup=keyboard,
                    parse_mode="HTML"
                )
            except Exception as e:
                logger.warning(f"Не удалось отправить фото траектории: {e}")
                await callback.message.answer(trajectory_text, reply_markup=keyboard, parse_mode="HTML")
        else:
            try:
                await _safe_edit_message(callback.message,
                    trajectory_text,
                    reply_markup=keyboard,
                    parse_mode="HTML"
                )
            except Exception:
                await callback.message.answer(trajectory_text, reply_markup=keyboard, parse_mode="HTML")

        log_user_action(user.tg_id, "trajectory_opened", f"Открыта траектория {trainee_path.learning_path.name}")

    except Exception as e:
        await _safe_edit_message(callback.message,"Произошла ошибка при открытии траектории")
        log_user_error(callback.from_user.id, "trajectory_command_error", str(e))


@router.callback_query(F.data.startswith("select_stage:"))
async def callback_select_stage(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Обработчик выбора этапа траектории"""
    try:
        await callback.answer()

        stage_id = int(callback.data.split(":")[1])

        user = await get_user_by_tg_id(session, callback.from_user.id)
        if not user:
            await _safe_edit_message(callback.message,"Пользователь не найден")
            return

        company_id = user.company_id
        trainee_path = await get_trainee_learning_path(session, user.id, company_id=company_id)
        if not trainee_path:
            await _safe_edit_message(callback.message,"Траектория не найдена")
            return

        stages_progress = await get_trainee_stage_progress(session, trainee_path.id, company_id=company_id)
        stage_progress = next((sp for sp in stages_progress if sp.stage_id == stage_id), None)

        if not stage_progress or not stage_progress.is_opened:
            await _safe_edit_message(callback.message,"Этап не доступен для прохождения")
            return

        sessions_progress = await get_stage_session_progress(session, stage_progress.id)

        # Полная траектория + кнопки выбора сессии
        trajectory_text, _ = await build_trajectory_text(session, user, trainee_path, company_id)

        available_sessions = [sp for sp in sessions_progress if sp.is_opened and not sp.is_completed]

        keyboard_buttons = []
        trajectory_text += "Выбери сессию в этапе 👇\n\n"

        if available_sessions:
            for sp in available_sessions:
                keyboard_buttons.append([
                    InlineKeyboardButton(
                        text=f"Сессия {sp.session.order_number}",
                        callback_data=f"select_session:{sp.session.id}"
                    )
                ])
        else:
            trajectory_text += "❌ Нет открытых сессий для прохождения"

        keyboard_buttons.append([
            InlineKeyboardButton(text="← назад", callback_data="trajectory_command")
        ])

        await _safe_edit_message(callback.message,
            trajectory_text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_buttons),
            parse_mode="HTML"
        )

        log_user_action(callback.from_user.id, "stage_selected", f"Выбран этап {stage_progress.stage.name}")

    except Exception as e:
        await _safe_edit_message(callback.message,"Произошла ошибка при выборе этапа")
        log_user_error(callback.from_user.id, "select_stage_error", str(e))


@router.callback_query(F.data.startswith("select_session:"))
async def callback_select_session(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Обработчик выбора сессии этапа"""
    try:
        await callback.answer()

        session_id = int(callback.data.split(":")[1])

        user = await get_user_by_tg_id(session, callback.from_user.id)
        if not user:
            await _safe_edit_message(callback.message,"Пользователь не найден")
            return

        company_id = user.company_id
        trainee_path = await get_trainee_learning_path(session, user.id, company_id=company_id)
        if not trainee_path:
            await _safe_edit_message(callback.message,"Траектория не найдена")
            return

        from database.db import get_session_with_tests
        selected_session = await get_session_with_tests(session, session_id, company_id=company_id)
        if not selected_session:
            await _safe_edit_message(callback.message,"Сессия не найдена")
            return

        tests = selected_session.tests if hasattr(selected_session, 'tests') and selected_session.tests else []

        # Полная траектория + кнопки выбора теста
        trajectory_text, _ = await build_trajectory_text(session, user, trainee_path, company_id)

        keyboard_buttons = []
        if tests:
            for i, test in enumerate(tests, 1):
                keyboard_buttons.append([
                    InlineKeyboardButton(
                        text=f"Тест {i}",
                        callback_data=f"take_test:{session_id}:{test.id}"
                    )
                ])

        keyboard_buttons.append([
            InlineKeyboardButton(
                text="← назад",
                callback_data=f"select_stage:{selected_session.stage_id}"
            )
        ])

        await _safe_edit_message(callback.message,
            trajectory_text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_buttons),
            parse_mode="HTML"
        )

        log_user_action(callback.from_user.id, "session_selected", f"Выбрана сессия {selected_session.name}")

    except Exception as e:
        await _safe_edit_message(callback.message,"Произошла ошибка при выборе сессии")
        log_user_error(callback.from_user.id, "select_session_error", str(e))


@router.callback_query(F.data.startswith("take_test:"))
async def callback_take_test(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Обработчик начала прохождения теста из траектории"""
    try:
        await callback.answer()

        parts = callback.data.split(":")

        # Обрабатываем только формат с 3 частями (из траектории)
        # Формат с 2 частями (из уведомлений) должен обрабатываться в test_taking.py
        if len(parts) != 3:
            return

        # Удаляем медиа-файл с материалами, если он был отправлен
        data = await state.get_data()
        if 'material_message_id' in data:
            try:
                await callback.bot.delete_message(
                    chat_id=callback.message.chat.id,
                    message_id=data['material_message_id']
                )
            except Exception:
                pass

        await state.update_data(material_message_id=None, material_text_message_id=None)

        user = await get_user_by_tg_id(session, callback.from_user.id)
        if not user:
            await _safe_edit_message(callback.message,"❌ Ты не зарегистрирован в системе.")
            return

        session_id = int(parts[1])
        test_id = int(parts[2])

        from database.db import get_test_by_id
        test = await get_test_by_id(session, test_id, company_id=user.company_id)
        if not test:
            await _safe_edit_message(callback.message,"Тест не найден")
            return

        test_info = f"""📌 <b>{test.name}</b>

<b>Порог:</b> {test.threshold_score:.1f}/{test.max_score:.1f} б.

{test.description or 'Описание отсутствует'}

Если есть сомнения по теме, сначала прочти прикреплённые обучающие материалы, а потом переходи к тесту"""

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="▶️ Начать тест", callback_data=f"start_test:{test_id}"),
                InlineKeyboardButton(text="📚 Материалы", callback_data=f"show_materials:{session_id}:{test_id}")
            ],
            [
                InlineKeyboardButton(text="← назад", callback_data=f"back_to_session:{session_id}"),
                InlineKeyboardButton(text="☰ Главное меню", callback_data="main_menu")
            ]
        ])

        await _safe_edit_message(callback.message,
            test_info,
            reply_markup=keyboard,
            parse_mode="HTML"
        )

        log_user_action(callback.from_user.id, "test_selected", f"Выбран тест {test.name}")

    except Exception as e:
        await _safe_edit_message(callback.message,"Произошла ошибка при открытии теста")
        log_user_error(callback.from_user.id, "take_test_error", str(e))


# Обработчик start_test: перенесен в test_taking.py для универсального использования


@router.callback_query(F.data.startswith("back_to_session:"))
async def callback_back_to_session(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Обработчик возврата к выбору тестов в сессии"""
    try:
        await callback.answer()

        session_id = int(callback.data.split(":")[1])

        user = await get_user_by_tg_id(session, callback.from_user.id)
        if not user:
            await _safe_edit_message(callback.message,"Пользователь не найден")
            return

        company_id = user.company_id
        trainee_path = await get_trainee_learning_path(session, user.id, company_id=company_id)
        if not trainee_path:
            await _safe_edit_message(callback.message,"Траектория не найдена")
            return

        from database.db import get_session_with_tests
        selected_session = await get_session_with_tests(session, session_id, company_id=company_id)
        if not selected_session:
            await _safe_edit_message(callback.message,"Сессия не найдена")
            return

        tests = selected_session.tests if hasattr(selected_session, 'tests') and selected_session.tests else []

        trajectory_text, _ = await build_trajectory_text(session, user, trainee_path, company_id)

        keyboard_buttons = []
        if tests:
            for i, test in enumerate(tests, 1):
                keyboard_buttons.append([
                    InlineKeyboardButton(
                        text=f"Тест {i}",
                        callback_data=f"take_test:{session_id}:{test.id}"
                    )
                ])

        keyboard_buttons.append([
            InlineKeyboardButton(
                text="← назад",
                callback_data=f"select_stage:{selected_session.stage_id}"
            )
        ])

        await _safe_edit_message(callback.message,
            trajectory_text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_buttons),
            parse_mode="HTML"
        )

        log_user_action(callback.from_user.id, "back_to_session", f"Возврат к сессии {selected_session.name}")

    except Exception as e:
        await _safe_edit_message(callback.message,"Произошла ошибка при возврате к сессии")
        log_user_error(callback.from_user.id, "back_to_session_error", str(e))


@router.callback_query(F.data.startswith("show_materials:"))
async def callback_show_materials(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Обработчик показа материалов для теста"""
    try:
        await callback.answer()

        user = await get_user_by_tg_id(session, callback.from_user.id)
        if not user:
            await _safe_edit_message(callback.message,"❌ Ты не зарегистрирован в системе.")
            return

        parts = callback.data.split(":")
        session_id = int(parts[1])
        test_id = int(parts[2])

        from database.db import get_test_by_id
        test = await get_test_by_id(session, test_id, company_id=user.company_id)
        if not test:
            await _safe_edit_message(callback.message,"Тест не найден")
            return

        if not test.material_link:
            await _safe_edit_message(callback.message,
                "📚 <b>Материалы для изучения</b>\n\n"
                "К этому тесту не прикреплены материалы.",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="▶️ Начать тест", callback_data=f"start_test:{test_id}")],
                    [InlineKeyboardButton(text="← назад", callback_data=f"take_test:{session_id}:{test_id}")]
                ])
            )
            return

        if test.material_file_path:
            try:
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

                await state.update_data(material_message_id=sent_media.message_id)

                sent_text = await callback.message.answer(
                    "📎 Материал отправлен выше.",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="▶️ Начать тест", callback_data=f"start_test:{test_id}")],
                        [InlineKeyboardButton(text="← назад", callback_data=f"take_test:{session_id}:{test_id}")]
                    ])
                )
                await state.update_data(material_text_message_id=sent_text.message_id)
            except Exception as e:
                await _safe_edit_message(callback.message,
                    f"❌ <b>Ошибка загрузки файла</b>\n\n"
                    f"Не удалось загрузить материал.\n\n"
                    f"📌 <b>Тест:</b> {test.name}",
                    parse_mode="HTML",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="▶️ Начать тест", callback_data=f"start_test:{test_id}")],
                        [InlineKeyboardButton(text="← назад", callback_data=f"take_test:{session_id}:{test_id}")]
                    ])
                )
        else:
            await _safe_edit_message(callback.message,
                f"📚 <b>Материалы для изучения</b>\n\n"
                f"📌 <b>Тест:</b> {test.name}\n\n"
                f"🔗 <b>Ссылка:</b>\n{test.material_link}\n\n"
                f"💡 Изучи материалы перед прохождением теста!",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="▶️ Начать тест", callback_data=f"start_test:{test_id}")],
                    [InlineKeyboardButton(text="← назад", callback_data=f"take_test:{session_id}:{test_id}")]
                ])
            )

        log_user_action(callback.from_user.id, "materials_viewed", f"Просмотрены материалы для теста {test.name}")

    except Exception as e:
        await _safe_edit_message(callback.message,"Произошла ошибка при показе материалов")
        log_user_error(callback.from_user.id, "show_materials_error", str(e))


@router.callback_query(F.data.startswith("back_to_trajectory:"))
async def callback_back_to_trajectory(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Обработчик возврата к выбору этапа"""
    try:
        await callback.answer()

        user_id = int(callback.data.split(":")[1])

        user = await get_user_by_id(session, user_id)
        if not user:
            await _safe_edit_message(callback.message,"Пользователь не найден")
            return

        message = callback.message
        message.from_user = callback.from_user
        await cmd_trajectory(message, state, session)

    except Exception as e:
        await _safe_edit_message(callback.message,"Произошла ошибка при возврате к траектории")
        log_user_error(callback.from_user.id, "back_to_trajectory_error", str(e))


@router.callback_query(F.data.startswith("back_to_stage:"))
async def callback_back_to_stage(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Обработчик возврата к выбору сессии"""
    try:
        await callback.answer()

        user_id = int(callback.data.split(":")[1])

        user = await get_user_by_id(session, user_id)
        if not user:
            await _safe_edit_message(callback.message,"Пользователь не найден")
            return

        company_id = user.company_id
        trainee_path = await get_trainee_learning_path(session, user.id, company_id=company_id)
        if not trainee_path:
            await _safe_edit_message(callback.message,"Траектория не найдена")
            return

        stages_progress = await get_trainee_stage_progress(session, trainee_path.id, company_id=company_id)
        opened_stage = next((sp for sp in stages_progress if sp.is_opened and not sp.is_completed), None)

        if opened_stage:
            callback.data = f"select_stage:{opened_stage.stage_id}"
            await callback_select_stage(callback, state, session)
        else:
            await _safe_edit_message(callback.message,"Нет открытых этапов")

    except Exception as e:
        await _safe_edit_message(callback.message,"Произошла ошибка при возврате к этапу")
        log_user_error(callback.from_user.id, "back_to_stage_error", str(e))


# ==============================
# Аттестация
# ==============================

async def format_attestation_status(session, user_id, trainee_path):
    """Форматирование статуса аттестации с правильной индикацией"""
    try:
        if trainee_path and trainee_path.learning_path.attestation:
            user = await get_user_by_id(session, user_id)
            company_id = user.company_id if user else None

            attestation_status = await get_trainee_attestation_status(
                session, user_id, trainee_path.learning_path.attestation.id, company_id=company_id
            )
            return f"🏁 <b>Аттестация:</b> {trainee_path.learning_path.attestation.name} {attestation_status}\n\n"
        else:
            return f"🏁 <b>Аттестация:</b> Не указана ⛔️\n\n"
    except Exception as e:
        log_user_error(user_id, "format_attestation_status_error", str(e))
        return f"🏁 <b>Аттестация:</b> Ошибка загрузки ⛔️\n\n"


@router.callback_query(F.data == "contact_mentor")
async def callback_contact_mentor(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Обработчик кнопки 'Связаться с наставником'"""
    try:
        await callback.answer()

        user = await get_user_by_tg_id(session, callback.from_user.id)
        if not user:
            await _safe_edit_message(callback.message,"❌ Ты не зарегистрирован в системе.")
            return

        from database.db import get_user_mentor
        mentor = await get_user_mentor(session, user.id)

        if not mentor:
            await _safe_edit_message(callback.message,
                "❌ <b>Наставник не назначен</b>\n\n"
                "Тебе еще не назначен наставник.\n"
                "Обратись к рекрутеру для назначения наставника.",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [
                        InlineKeyboardButton(text="← назад", callback_data="trajectory_command"),
                        InlineKeyboardButton(text="☰ Главное меню", callback_data="main_menu")
                    ]
                ])
            )
            return

        mentor_info = f"""👨‍🏫 <b>Твой наставник</b>

🧑 <b>Имя:</b> {mentor.full_name}
📞 <b>Телефон:</b> {mentor.phone_number}
👤 <b>Username:</b> @{mentor.username or 'не указан'}

💬 <b>Свяжись с наставником для назначения траектории обучения</b>"""

        await _safe_edit_message(callback.message,
            mentor_info,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(text="← назад", callback_data="trajectory_command"),
                    InlineKeyboardButton(text="☰ Главное меню", callback_data="main_menu")
                ]
            ])
        )

        log_user_action(user.tg_id, "mentor_contact_viewed", f"Стажер просмотрел контакты наставника: {mentor.full_name}")

    except Exception as e:
        log_user_error(callback.from_user.id, "contact_mentor_error", str(e))
        await _safe_edit_message(callback.message,"❌ Произошла ошибка при получении контактов наставника.")
