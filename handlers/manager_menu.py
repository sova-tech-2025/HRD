"""
Обработчики меню руководителя.
Включает управление аттестациями и стажерами.
"""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from database.db import (
    get_user_by_tg_id, get_manager_trainees, get_attestation_results,
    check_user_permission
)
from handlers.auth import check_auth
from keyboards.keyboards import get_main_menu_keyboard
from utils.logger import log_user_action, log_user_error

router = Router()


@router.message(F.text == "🎯 Мои аттестации")
async def cmd_my_attestations(message: Message, state: FSMContext, session: AsyncSession):
    """
    Обработчик кнопки "Мои аттестации"
    """
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

        # Получаем company_id для изоляции
        data = await state.get_data()
        company_id = data.get('company_id') or user.company_id

        # Получаем стажеров руководителя с изоляцией по компании
        trainees = await get_manager_trainees(session, user.id, company_id=company_id)

        if not trainees:
            await message.answer(
                "🎯 <b>МОИ АТТЕСТАЦИИ</b>\n\n"
                "❌ <b>Стажеры не найдены</b>\n\n"
                "У тебя нет назначенных стажеров для проведения аттестаций.\n"
                "Обратись к наставнику для назначения стажеров.",
                parse_mode="HTML",
                reply_markup=get_main_menu_keyboard()
            )
            log_user_action(user.tg_id, "no_trainees_for_manager", "У руководителя нет стажеров")
            return

        # Формируем меню аттестаций
        attestation_menu = (
            "🎯 <b>МОИ АТТЕСТАЦИИ</b>\n\n"
            f"👨‍🏫 <b>Руководитель:</b> {user.full_name}\n"
            f"📊 <b>Всего стажеров:</b> {len(trainees)}\n\n"
            "📋 <b>Выбери стажера для проведения аттестации:</b>"
        )

        keyboard = InlineKeyboardMarkup(inline_keyboard=[])

        for trainee_manager in trainees:
            trainee = trainee_manager.trainee

            # Получаем результаты аттестаций стажера с изоляцией по компании
            results = await get_attestation_results(session, trainee.id, company_id=company_id)
            last_result = results[0] if results else None

            status_text = "Не проводилась"
            if last_result:
                status_text = "✅ Пройдена" if last_result.is_passed else "❌ Не пройдена"

            keyboard.inline_keyboard.append([
                InlineKeyboardButton(
                    text=f"{trainee.full_name} ({status_text})",
                    callback_data=f"select_trainee_for_attestation:{trainee.id}"
                )
            ])

        keyboard.inline_keyboard.append([
            InlineKeyboardButton(text="≡ Главное меню", callback_data="main_menu")
        ])

        await message.answer(
            attestation_menu,
            parse_mode="HTML",
            reply_markup=keyboard
        )

        log_user_action(user.tg_id, "my_attestations_opened", f"Открыто меню аттестаций с {len(trainees)} стажерами")

    except Exception as e:
        await message.answer("Произошла ошибка при открытии меню аттестаций")
        log_user_error(message.from_user.id, "my_attestations_error", str(e))


@router.callback_query(F.data.startswith("select_trainee_for_attestation:"))
async def callback_select_trainee_for_attestation(callback: CallbackQuery, session: AsyncSession):
    """
    Обработчик выбора стажера для аттестации
    """
    try:
        await callback.answer()

        # Получаем ID стажера
        trainee_id = int(callback.data.split(":")[1])

        # Получаем стажера
        from database.db import get_user_by_id
        trainee = await get_user_by_id(session, trainee_id)
        if not trainee:
            await callback.message.edit_text("Стажер не найден")
            return

        # Получаем company_id для изоляции
        company_id = trainee.company_id

        # Получаем результаты аттестаций с изоляцией по компании
        results = await get_attestation_results(session, trainee_id, company_id=company_id)

        # Формируем информацию о стажере
        trainee_info = (
            "🎯 <b>ИНФОРМАЦИЯ О СТАЖЕРЕ</b>\n\n"
            f"👤 <b>ФИО:</b> {trainee.full_name}\n"
            f"📞 <b>Телефон:</b> {trainee.phone_number}\n"
            f"🗂️ <b>Группа:</b> {', '.join([group.name for group in trainee.groups]) if trainee.groups else 'Не указана'}\n"
            f"📍<b>1️⃣Объект стажировки:</b> {trainee.internship_object.name if trainee.internship_object else 'Не указан'}\n"
            f"📍<b>2️⃣Объект работы:</b> {trainee.work_object.name if trainee.work_object else 'Не указан'}\n\n"
        )

        if results:
            trainee_info += "📊 <b>ИСТОРИЯ АТТЕСТАЦИЙ:</b>\n\n"
            for result in results[:3]:  # Показываем последние 3 аттестации
                status = "✅ Пройдена" if result.is_passed else "❌ Не пройдена"
                trainee_info += (
                    f"📅 <b>{result.completed_date.strftime('%d.%m.%Y')}</b>\n"
                    f"📋 <b>{result.attestation.name}</b>\n"
                    f"📊 <b>Результат:</b> {result.total_score:.1f}/{result.max_score:.1f}\n"
                    f"🎯 <b>Статус:</b> {status}\n\n"
                )
        else:
            trainee_info += "📊 <b>АТТЕСТАЦИИ:</b> Не проводились\n\n"

        trainee_info += "🎯 <b>Выбери действие:</b>"

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="📝 Провести аттестацию", callback_data=f"conduct_attestation:{trainee_id}")
            ],
            [
                InlineKeyboardButton(text="📊 Посмотреть результаты", callback_data=f"view_attestation_results:{trainee_id}")
            ],
            [
                InlineKeyboardButton(text="↩️ Назад к списку", callback_data="back_to_my_attestations")
            ]
        ])

        await callback.message.edit_text(
            trainee_info,
            parse_mode="HTML",
            reply_markup=keyboard
        )

        log_user_action(callback.from_user.id, "trainee_selected_for_attestation", f"Выбран стажер {trainee.full_name} для аттестации")

    except Exception as e:
        await callback.message.edit_text("Произошла ошибка при выборе стажера")
        log_user_error(callback.from_user.id, "select_trainee_error", str(e))


@router.callback_query(F.data == "back_to_my_attestations")
async def callback_back_to_my_attestations(callback: CallbackQuery, session: AsyncSession):
    """
    Обработчик возврата к списку аттестаций
    """
    try:
        await callback.answer()

        # Получаем пользователя
        user = await get_user_by_tg_id(session, callback.from_user.id)
        if not user:
            await callback.message.edit_text("Пользователь не найден")
            return

        # Получаем company_id для изоляции
        company_id = user.company_id

        # Получаем стажеров руководителя с изоляцией по компании
        trainees = await get_manager_trainees(session, user.id, company_id=company_id)

        if not trainees:
            await callback.message.edit_text(
                "У тебя нет назначенных стажеров для проведения аттестаций."
            )
            return

        # Формируем меню аттестаций
        attestation_menu = (
            "🎯 <b>МОИ АТТЕСТАЦИИ</b>\n\n"
            f"👨‍🏫 <b>Руководитель:</b> {user.full_name}\n"
            f"📊 <b>Всего стажеров:</b> {len(trainees)}\n\n"
            "📋 <b>Выбери стажера для проведения аттестации:</b>"
        )

        keyboard = InlineKeyboardMarkup(inline_keyboard=[])

        for trainee_manager in trainees:
            trainee = trainee_manager.trainee

            # Получаем результаты аттестаций стажера с изоляцией по компании
            results = await get_attestation_results(session, trainee.id, company_id=company_id)
            last_result = results[0] if results else None

            status_text = "Не проводилась"
            if last_result:
                status_text = "✅ Пройдена" if last_result.is_passed else "❌ Не пройдена"

            keyboard.inline_keyboard.append([
                InlineKeyboardButton(
                    text=f"{trainee.full_name} ({status_text})",
                    callback_data=f"select_trainee_for_attestation:{trainee.id}"
                )
            ])

        keyboard.inline_keyboard.append([
            InlineKeyboardButton(text="≡ Главное меню", callback_data="main_menu")
        ])

        await callback.message.edit_text(
            attestation_menu,
            parse_mode="HTML",
            reply_markup=keyboard
        )

    except Exception as e:
        await callback.message.edit_text("Произошла ошибка при возврате к списку аттестаций")
        log_user_error(callback.from_user.id, "back_to_attestations_error", str(e))


@router.message(F.text == "👨‍🏫 Мои стажеры")
async def cmd_my_trainees(message: Message, state: FSMContext, session: AsyncSession):
    """
    Обработчик кнопки "Мои стажеры" для руководителя
    """
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
                "У тебя нет прав для просмотра стажеров.\n"
                "Обратись к администратору.",
                parse_mode="HTML"
            )
            return

        # Получаем company_id для изоляции
        data = await state.get_data()
        company_id = data.get('company_id') or user.company_id

        # Получаем стажеров руководителя с изоляцией по компании
        trainees = await get_manager_trainees(session, user.id, company_id=company_id)

        if not trainees:
            await message.answer(
                "👨‍🏫 <b>МОИ СТАЖЕРЫ</b>\n\n"
                "❌ <b>Стажеры не найдены</b>\n\n"
                "У тебя нет назначенных стажеров.\n"
                "Обратись к наставнику для назначения стажеров.",
                parse_mode="HTML",
                reply_markup=get_main_menu_keyboard()
            )
            return

        # Формируем список стажеров
        trainees_list = (
            "👨‍🏫 <b>МОИ СТАЖЕРЫ</b>\n\n"
            f"👨‍🏫 <b>Руководитель:</b> {user.full_name}\n"
            f"📊 <b>Всего стажеров:</b> {len(trainees)}\n\n"
            "📋 <b>Список стажеров:</b>\n\n"
        )

        keyboard = InlineKeyboardMarkup(inline_keyboard=[])

        for trainee_manager in trainees:
            trainee = trainee_manager.trainee

            # Получаем результаты аттестаций стажера с изоляцией по компании
            results = await get_attestation_results(session, trainee.id, company_id=company_id)
            last_result = results[0] if results else None

            status_text = "Не проводилась"
            if last_result:
                status_text = "✅ Пройдена" if last_result.is_passed else "❌ Не пройдена"

            trainees_list += (
                f"👤 <b>{trainee.full_name}</b>\n"
                f"📍<b>1️⃣Объект стажировки:</b> {trainee.internship_object.name if trainee.internship_object else 'Не указан'}\n"
                f"📊 <b>Последняя аттестация:</b> {status_text}\n"
                f"📅 <b>Назначен:</b> {trainee_manager.assigned_date.strftime('%d.%m.%Y')}\n\n"
            )

            keyboard.inline_keyboard.append([
                InlineKeyboardButton(
                    text=f"🎯 Аттестация: {trainee.full_name}",
                    callback_data=f"select_trainee_for_attestation:{trainee.id}"
                )
            ])

        keyboard.inline_keyboard.append([
            InlineKeyboardButton(text="≡ Главное меню", callback_data="main_menu")
        ])

        await message.answer(
            trainees_list,
            parse_mode="HTML",
            reply_markup=keyboard
        )

        log_user_action(user.tg_id, "my_trainees_opened", f"Открыт список стажеров ({len(trainees)} человек)")

    except Exception as e:
        await message.answer("Произошла ошибка при открытии списка стажеров")
        log_user_error(message.from_user.id, "my_trainees_error", str(e))
