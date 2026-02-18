from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy.ext.asyncio import AsyncSession

from config import MAIN_MENU_IMAGE_FILE_ID, MAIN_MENU_IMAGE_URL, MAIN_MENU_IMAGE_PATH, MENTOR_MENU_IMAGE_FILE_ID, MENTOR_MENU_IMAGE_PATH, TRAINEE_MENU_IMAGE_FILE_ID, TRAINEE_MENU_IMAGE_PATH
from database.db import get_user_by_tg_id, get_user_roles, check_user_permission
from handlers.auth import check_auth
from keyboards.keyboards import format_help_message
from utils.logger import logger, log_user_action

router = Router()


def _get_mentor_menu_photo():
    """Получает источник фото для меню наставника"""
    if MENTOR_MENU_IMAGE_FILE_ID:
        return MENTOR_MENU_IMAGE_FILE_ID
    if MENTOR_MENU_IMAGE_PATH:
        try:
            return FSInputFile(MENTOR_MENU_IMAGE_PATH)
        except Exception:
            pass
    return None


def _get_trainee_menu_photo():
    """Получает источник фото для меню стажера"""
    if TRAINEE_MENU_IMAGE_FILE_ID:
        return TRAINEE_MENU_IMAGE_FILE_ID
    if TRAINEE_MENU_IMAGE_PATH:
        try:
            return FSInputFile(TRAINEE_MENU_IMAGE_PATH)
        except Exception as e:
            logger.warning(f"Не удалось загрузить изображение меню стажера: {e}")
    return None


async def format_profile_text(user, session: AsyncSession) -> str:
    """Универсальная функция формирования текста профиля для всех ролей"""
    # Получаем роли и определяем приоритетную
    roles = await get_user_roles(session, user.id)
    role_priority = {
        "Руководитель": 5,
        "Рекрутер": 4, 
        "Наставник": 3,
        "Сотрудник": 2,
        "Стажер": 1
    }
    user_roles = [r.name for r in roles]
    primary_role = max(user_roles, key=lambda r: role_priority.get(r, 0))
    
    # Формируем информацию о группах
    groups_str = ", ".join([group.name for group in user.groups]) if user.groups else "Не указана"
    groups_label = "Группы" if user.groups and len(user.groups) > 1 else "Группа"
    
    # Формируем информацию об объектах
    internship_obj = user.internship_object.name if user.internship_object else "Не указан"
    work_obj = user.work_object.name if user.work_object else "Не указан"
    
    # Формируем username с экранированием
    username_display = f"@{user.username}" if user.username else "Не указан"
    if user.username and "_" in user.username:
        username_display = f"@{user.username.replace('_', '_')}"
    
    profile_text = f"""🦸🏻‍♂️ <b>Пользователь:</b> {user.full_name}

<b>Телефон:</b> {user.phone_number}
<b>Username:</b> {username_display}
<b>Номер:</b> #{user.id}
<b>Дата регистрации:</b> {user.registration_date.strftime('%d.%m.%Y %H:%M')}

━━━━━━━━━━━━

🗂️ <b>Статус ▾</b>
<b>{groups_label}:</b> {groups_str}
<b>Роль:</b> {primary_role}

━━━━━━━━━━━━

📍 <b>Объект ▾</b>"""

    # Добавляем информацию об объектах в зависимости от роли
    if primary_role == "Стажер":
        profile_text += f"""
<b>Стажировки:</b> {internship_obj}
<b>Работы:</b> {work_obj}"""
    else:
        profile_text += f"""
<b>Работы:</b> {work_obj}"""
    
    return profile_text


@router.message(Command("help"))
async def cmd_help(message: Message, state: FSMContext, session: AsyncSession):
    """Показывает справку в зависимости от роли"""
    # Сначала проверяем авторизацию
    is_auth = await check_auth(message, state, session)
    if not is_auth:
        await message.answer(format_help_message("Неавторизованный"))
        return
    
    # Получаем роль из состояния или базы данных
    data = await state.get_data()
    role = data.get("role")
    
    # Если роли нет в состоянии, получаем из БД
    if not role:
        user = await get_user_by_tg_id(session, message.from_user.id)
        if user:
            roles = await get_user_roles(session, user.id)
            if roles:
                # Определяем приоритетную роль (по иерархии)
                role_priority = {
                    "Руководитель": 5,
                    "Рекрутер": 4, 
                    "Наставник": 3,
                    "Сотрудник": 2,
                    "Стажер": 1
                }
                # Берем роль с наивысшим приоритетом
                user_roles = [r.name for r in roles]
                role = max(user_roles, key=lambda r: role_priority.get(r, 0))
            else:
                role = "Неавторизованный"
        else:
            role = "Неавторизованный"

    await message.answer(format_help_message(role))

@router.message(Command("profile"))
async def cmd_profile(message: Message, state: FSMContext, session: AsyncSession):
    is_auth = await check_auth(message, state, session)
    if not is_auth:
        return
    
    user = await get_user_by_tg_id(session, message.from_user.id)
    
    has_permission = await check_user_permission(session, user.id, "view_profile")
    if not has_permission:
        await message.answer("У тебя нет прав для просмотра профиля.")
        return
    
    # Используем универсальную функцию формирования профиля
    profile_text = await format_profile_text(user, session)
    profile_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="☰ Главное меню", callback_data="main_menu")]
    ])
    await message.answer(profile_text, parse_mode="HTML", reply_markup=profile_keyboard)

@router.message(F.text.in_(["Мой профиль", "🦸🏻‍♂️ Мой профиль", "Мой профиль 🦸🏻‍♂️"]))
async def button_profile(message: Message, state: FSMContext, session: AsyncSession):
    await cmd_profile(message, state, session)

@router.message(F.text.in_(["Помощь", "❓ Помощь", "Помощь ❓"]))
async def button_help(message: Message, state: FSMContext, session: AsyncSession):
    await cmd_help(message, state, session)

@router.message(F.text == "☰ Главное меню")
async def cmd_inline_main_menu(message: Message, state: FSMContext, session: AsyncSession):
    """Обработчик reply-кнопки 'Главное меню' для наставника и стажера"""
    is_auth = await check_auth(message, state, session)
    if not is_auth:
        return

    user = await get_user_by_tg_id(session, message.from_user.id)
    if not user:
        return

    from keyboards.keyboards import get_mentor_inline_menu, get_trainee_inline_menu

    roles = await get_user_roles(session, user.id)
    role_priority = {"Руководитель": 5, "Рекрутер": 4, "Наставник": 3, "Сотрудник": 2, "Стажер": 1}
    primary_role = max(roles, key=lambda r: role_priority.get(r.name, 0))

    main_menu_text = (
        "☰ <b>Главное меню</b>\n\n"
        "Используй команды бота или кнопки клавиатуры для навигации по системе"
    )

    if primary_role.name == "Стажер":
        keyboard = get_trainee_inline_menu()
        photo_source = _get_trainee_menu_photo()
    if primary_role.name == "Наставник":
        keyboard = get_mentor_inline_menu()
        photo_source = _get_mentor_menu_photo()

    if photo_source:
        try:
            await message.answer_photo(
                photo=photo_source,
                caption=main_menu_text,
                parse_mode="HTML",
                reply_markup=keyboard
            )
        except Exception as e:
            logger.warning(f"Не удалось отправить фото меню: {e}")
            await message.answer(main_menu_text, parse_mode="HTML", reply_markup=keyboard)
    else:
        await message.answer(main_menu_text, parse_mode="HTML", reply_markup=keyboard)

    await state.clear()
    log_user_action(message.from_user.id, message.from_user.username, "opened_inline_main_menu")


@router.callback_query(F.data == "main_menu")
async def process_main_menu(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Универсальный обработчик возврата в главное меню с обновлением клавиатуры согласно роли"""
    try:
        # Получаем пользователя
        user = await get_user_by_tg_id(session, callback.from_user.id)
        if not user:
            await callback.answer("❌ Пользователь не найден", show_alert=True)
            return

        if not user.is_active:
            await callback.answer("❌ Твой аккаунт деактивирован", show_alert=True)
            return

        # Получаем роли пользователя
        roles = await get_user_roles(session, user.id)
        if not roles:
            await callback.answer("❌ Роли не назначены", show_alert=True)
            return

        # Определяем приоритетную роль
        role_priority = {
            "Руководитель": 5,
            "Рекрутер": 4, 
            "Наставник": 3,
            "Сотрудник": 2,
            "Стажер": 1
        }
        
        primary_role = max(roles, key=lambda r: role_priority.get(r.name, 0))

        # Специальная обработка для Наставника и Стажера — инлайн-меню с баннером
        if primary_role.name in ("Наставник", "Стажер"):
            from keyboards.keyboards import get_mentor_inline_menu, get_trainee_inline_menu

            main_menu_text = (
                "☰ <b>Главное меню</b>\n\n"
                "Используй команды бота или кнопки клавиатуры для навигации по системе"
            )

            if primary_role.name == "Стажер":
                keyboard = get_trainee_inline_menu()
                photo_source = _get_trainee_menu_photo()
            if primary_role.name == "Наставник":
                keyboard = get_mentor_inline_menu()
                photo_source = _get_mentor_menu_photo()

            try:
                await callback.message.delete()
            except Exception:
                pass

            if photo_source:
                try:
                    await callback.message.answer_photo(
                        photo=photo_source,
                        caption=main_menu_text,
                        parse_mode="HTML",
                        reply_markup=keyboard
                    )
                except Exception as e:
                    logger.warning(f"Не удалось отправить фото меню: {e}")
                    await callback.message.answer(main_menu_text, parse_mode="HTML", reply_markup=keyboard)
            else:
                await callback.message.answer(main_menu_text, parse_mode="HTML", reply_markup=keyboard)

            await state.clear()
            await callback.answer()
            log_user_action(callback.from_user.id, callback.from_user.username, "returned_to_main_menu")
            return

        # Получаем клавиатуру согласно роли
        from keyboards.keyboards import get_keyboard_by_role
        keyboard = get_keyboard_by_role(primary_role.name)

        main_menu_text = (
            "☰ Главное меню\n\n"
            "Используй команды бота или кнопки клавиатуры для навигации по системе."
        )

        # Отправляем изображение главного меню, если оно настроено
        message_sent = False
        photo_source = None
        if MAIN_MENU_IMAGE_FILE_ID:
            photo_source = MAIN_MENU_IMAGE_FILE_ID
        elif MAIN_MENU_IMAGE_URL:
            photo_source = MAIN_MENU_IMAGE_URL
        elif MAIN_MENU_IMAGE_PATH:
            try:
                photo_source = FSInputFile(MAIN_MENU_IMAGE_PATH)
            except Exception as file_error:
                logger.warning(f"Не удалось загрузить изображение главного меню из файла: {file_error}")

        if photo_source:
            try:
                await callback.message.answer_photo(
                    photo=photo_source,
                    caption=main_menu_text,
                    parse_mode="HTML",
                    reply_markup=keyboard
                )
                message_sent = True
            except Exception as photo_error:
                logger.warning(f"Не удалось отправить изображение главного меню: {photo_error}")

        if not message_sent:
            # Отправляем новое сообщение с правильной клавиатурой (ReplyKeyboardMarkup нельзя использовать в edit_text)
            await callback.message.answer(
                main_menu_text,
                parse_mode="HTML",
                reply_markup=keyboard
            )

        # Удаляем старое inline сообщение
        try:
            await callback.message.delete()
        except:
            pass
        
        # Очищаем состояние
        await state.clear()
        await callback.answer()
        
        # Логируем действие
        log_user_action(callback.from_user.id, callback.from_user.username, "returned_to_main_menu")
        
    except Exception as e:
        logger.error(f"Ошибка в process_main_menu: {e}")
        await callback.answer("❌ Ошибка при возврате в главное меню", show_alert=True)


@router.callback_query(F.data == "reload_menu")
async def process_reload_menu(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Обработчик кнопки 'Перезагрузка' - обновляет клавиатуру согласно роли пользователя"""
    try:
        # Получаем пользователя
        user = await get_user_by_tg_id(session, callback.from_user.id)
        if not user:
            await callback.answer("❌ Пользователь не найден", show_alert=True)
            return

        if not user.is_active:
            await callback.answer("❌ Твой аккаунт деактивирован", show_alert=True)
            return

        # Получаем роли пользователя
        roles = await get_user_roles(session, user.id)
        if not roles:
            await callback.answer("❌ Роли не назначены", show_alert=True)
            return

        # Определяем приоритетную роль
        role_priority = {
            "Руководитель": 5,
            "Рекрутер": 4, 
            "Наставник": 3,
            "Сотрудник": 2,
            "Стажер": 1
        }
        
        primary_role = max(roles, key=lambda r: role_priority.get(r.name, 0))
        
        # Для стажера и наставника — инлайн-меню
        if primary_role.name in ("Наставник", "Стажер"):
            from keyboards.keyboards import get_mentor_inline_menu, get_trainee_inline_menu
            if primary_role.name == "Стажер":
                keyboard = get_trainee_inline_menu()
            if primary_role.name == "Наставник":
                keyboard = get_mentor_inline_menu()

            try:
                await callback.message.delete()
            except Exception:
                pass

            await callback.message.answer(
                "☰ <b>Главное меню</b>\n\n"
                "Используй кнопки для навигации по системе",
                parse_mode="HTML",
                reply_markup=keyboard
            )
            await state.clear()
            await callback.answer()
            log_user_action(callback.from_user.id, callback.from_user.username, "reloaded_menu")
            return

        # Получаем клавиатуру согласно роли
        from keyboards.keyboards import get_keyboard_by_role
        keyboard = get_keyboard_by_role(primary_role.name)

        # Отправляем новое сообщение с правильной клавиатурой
        await callback.message.answer(
            "🔄 <b>Клавиатура обновлена</b>\n\n"
            "Твоя клавиатура обновлена согласно текущей роли. Используй кнопки для навигации по системе.",
            parse_mode="HTML",
            reply_markup=keyboard
        )

        # Удаляем старое inline сообщение
        try:
            await callback.message.delete()
        except Exception:
            pass

        # Очищаем состояние
        await state.clear()
        await callback.answer()

        # Логируем действие
        log_user_action(callback.from_user.id, callback.from_user.username, "reloaded_menu")
        
    except Exception as e:
        logger.error(f"Ошибка в process_reload_menu: {e}")
        await callback.answer("❌ Ошибка при обновлении клавиатуры", show_alert=True)


@router.callback_query(F.data == "trainee_profile")
async def callback_trainee_profile(callback: CallbackQuery, session: AsyncSession):
    """Обработчик 'Мой профиль' из инлайн-меню стажера"""
    user = await get_user_by_tg_id(session, callback.from_user.id)
    if not user:
        await callback.answer("❌ Не зарегистрирован", show_alert=True)
        return

    profile_text = await format_profile_text(user, session)

    try:
        await callback.message.delete()
    except Exception as e:
        logger.warning(f"Не удалось удалить сообщение: {e}")

    await callback.message.answer(
        profile_text,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="☰ Главное меню", callback_data="main_menu")]
        ])
    )
    await callback.answer()


@router.callback_query(F.data == "trainee_help")
async def callback_trainee_help(callback: CallbackQuery, session: AsyncSession):
    """Обработчик 'Помощь' из инлайн-меню стажера"""
    user = await get_user_by_tg_id(session, callback.from_user.id)
    if not user:
        await callback.answer("❌ Не зарегистрирован", show_alert=True)
        return

    roles = await get_user_roles(session, user.id)
    role_name = "Стажер"
    if roles:
        role_name = roles[0].name

    help_text = format_help_message(role_name)

    try:
        await callback.message.delete()
    except Exception as e:
        logger.warning(f"Не удалось удалить сообщение: {e}")

    await callback.message.answer(
        help_text,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="☰ Главное меню", callback_data="main_menu")]
        ])
    )
    await callback.answer()