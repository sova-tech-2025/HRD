import re

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy.ext.asyncio import AsyncSession

from database.db import (
    check_company_access,
    check_company_name_unique,
    check_invite_code_unique,
    check_phone_exists,
    create_company,
    create_user_with_company,
    get_company_by_id,
    get_company_by_invite_code,
    get_user_by_tg_id,
    update_company_description,
    update_company_name,
)
from database.models import Company
from keyboards.keyboards import (
    get_company_bot_link_keyboard,
    get_company_code_keyboard,
    get_company_code_only_keyboard,
    get_company_edit_description_keyboard,
    get_company_edit_name_keyboard,
    get_company_info_keyboard,
    get_contact_keyboard,
)
from states.states import CompanyCreationStates, CompanyJoinStates, CompanyManagementStates
from utils.handlers.menu import send_mentor_menu, send_trainee_menu
from utils.logger import log_user_action, log_user_error
from utils.validation.input import validate_full_name, validate_phone_number

router = Router()


# ==============================================================================
# СОЗДАНИЕ КОМПАНИИ
# ==============================================================================


@router.callback_query(F.data == "company:create")
async def callback_create_company(callback: CallbackQuery, state: FSMContext):
    """Начало создания компании"""
    await callback.message.edit_text(
        "🏢 <b>Создание компании</b>\n\nВведи название компании (будет видно всем участникам):",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_company_selection")]]
        ),
    )
    await state.set_state(CompanyCreationStates.waiting_for_name)
    log_user_action(callback.from_user.id, callback.from_user.username, "started company creation")
    await callback.answer()


@router.message(CompanyCreationStates.waiting_for_name)
async def process_company_name(message: Message, state: FSMContext, session: AsyncSession):
    """Обработка названия компании"""
    name = message.text.strip()

    # Валидация длины
    if len(name) < 3:
        await message.answer("❌ Название компании должно содержать минимум 3 символа.")
        return

    if len(name) > 100:
        await message.answer("❌ Название компании не может быть длиннее 100 символов.")
        return

    # Проверка уникальности
    if not await check_company_name_unique(session, name):
        await message.answer("❌ Компания с таким названием уже существует.\nПожалуйста, выбери другое название.")
        return

    await state.update_data(company_name=name)
    log_user_action(message.from_user.id, message.from_user.username, "provided company name", {"name": name})

    await message.answer(
        "✅ Отлично!\n\n"
        "Теперь введи краткое описание компании (необязательно, до 500 символов).\n\n"
        "Или нажми /skip чтобы пропустить:",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="⏭️ Пропустить", callback_data="company:skip_description")]]
        ),
    )
    await state.set_state(CompanyCreationStates.waiting_for_description)


@router.callback_query(CompanyCreationStates.waiting_for_description, F.data == "company:skip_description")
async def skip_description(callback: CallbackQuery, state: FSMContext):
    """Пропуск описания компании"""
    await state.update_data(company_description="")
    await callback.message.edit_text(
        "📝 <b>Создание кода приглашения</b>\n\n"
        "Придумай уникальный код приглашения для твоей компании.\n\n"
        "⚠️ <b>ВАЖНО: Используй только латинские буквы (A-Z) и цифры (0-9)</b>\n\n"
        "Требования:\n"
        "• Только латинские буквы и цифры\n"
        "• Без пробелов\n"
        "• От 6 до 20 символов\n\n"
        "Пример: MYCOMPANY2025",
        parse_mode="HTML",
    )
    await state.set_state(CompanyCreationStates.waiting_for_invite_code)
    await callback.answer()


@router.message(CompanyCreationStates.waiting_for_description)
async def process_company_description(message: Message, state: FSMContext):
    """Обработка описания компании"""
    if message.text.strip().lower() == "/skip":
        await state.update_data(company_description="")
    else:
        description = message.text.strip()

        if len(description) > 500:
            await message.answer("❌ Описание не может быть длиннее 500 символов.")
            return

        await state.update_data(company_description=description)

    await message.answer(
        "📝 <b>Создание кода приглашения</b>\n\n"
        "Придумай уникальный код приглашения для твоей компании.\n\n"
        "⚠️ <b>ВАЖНО: Используй только латинские буквы (A-Z) и цифры (0-9)</b>\n\n"
        "Требования:\n"
        "• Только латинские буквы и цифры\n"
        "• Без пробелов\n"
        "• От 6 до 20 символов\n\n"
        "Пример: MYCOMPANY2025",
        parse_mode="HTML",
    )
    await state.set_state(CompanyCreationStates.waiting_for_invite_code)


@router.message(CompanyCreationStates.waiting_for_invite_code)
async def process_invite_code_creation(message: Message, state: FSMContext, session: AsyncSession):
    """Обработка ввода invite code при создании"""
    invite_code = message.text.strip().upper()

    # Валидация формата
    if not re.match(r"^[A-Z0-9]{6,20}$", invite_code):
        await message.answer(
            "❌ Неверный формат кода.\n\n"
            "⚠️ Код должен содержать ТОЛЬКО латинские буквы (A-Z) и цифры (0-9), без пробелов и других символов.\n"
            "📏 Длина: от 6 до 20 символов.\n\n"
            "Пример: MYCOMPANY2025",
            parse_mode="HTML",
        )
        return

    # Проверка уникальности
    if not await check_invite_code_unique(session, invite_code, exclude_company_id=None):
        await message.answer(
            "❌ Этот код приглашения уже используется другой компанией.\nПожалуйста, придумай другой код."
        )
        return

    await state.update_data(company_invite_code=invite_code)
    log_user_action(message.from_user.id, message.from_user.username, "provided invite code", {"code": invite_code})

    await message.answer(
        f"✅ Код приглашения: <code>{invite_code}</code>\n\n"
        "Теперь введи своё ФИО (будет видно в системе):\n\n"
        "Пример: Иванов Иван",
        parse_mode="HTML",
    )
    await state.set_state(CompanyCreationStates.waiting_for_full_name)


@router.message(CompanyCreationStates.waiting_for_full_name)
async def process_company_creator_full_name(message: Message, state: FSMContext):
    """Обработка ФИО создателя компании"""
    is_valid, formatted_name = validate_full_name(message.text)

    if not is_valid:
        await message.answer(
            "❌ Некорректный формат ФИО.\n\nПожалуйста, введи имя и фамилию, используя только буквы, пробелы и дефисы."
        )
        return

    await state.update_data(full_name=formatted_name)
    log_user_action(
        message.from_user.id,
        message.from_user.username,
        "provided full name for company creation",
        {"name": formatted_name},
    )

    await message.answer(
        "✅ Отлично!\n\nДля завершения регистрации отправь свой номер телефона:", reply_markup=get_contact_keyboard()
    )
    await state.set_state(CompanyCreationStates.waiting_for_phone)


@router.message(CompanyCreationStates.waiting_for_phone, F.contact)
async def process_company_creator_phone_contact(message: Message, state: FSMContext, session: AsyncSession, bot):
    """Обработка номера телефона создателя компании (через контакт)"""
    phone_number = message.contact.phone_number
    is_valid, normalized_phone = validate_phone_number(phone_number)

    if not is_valid:
        await message.answer(
            "❌ Некорректный формат номера телефона. Пожалуйста, введи номер в формате +7XXXXXXXXXX.",
            reply_markup=get_contact_keyboard(),
        )
        return

    if await check_phone_exists(session, normalized_phone):
        await message.answer("❌ Этот номер телефона уже зарегистрирован в системе.")
        await state.clear()
        return

    await finalize_company_creation(message, state, session, normalized_phone, bot)


@router.message(CompanyCreationStates.waiting_for_phone)
async def process_company_creator_phone_manual(message: Message, state: FSMContext, session: AsyncSession, bot):
    """Обработка номера телефона создателя компании (вручную)"""
    is_valid, normalized_phone = validate_phone_number(message.text)

    if not is_valid:
        await message.answer(
            "❌ Некорректный формат номера телефона. Пожалуйста, введи номер в формате +7XXXXXXXXXX.",
            reply_markup=get_contact_keyboard(),
        )
        return

    if await check_phone_exists(session, normalized_phone):
        await message.answer("❌ Этот номер телефона уже зарегистрирован в системе.")
        await state.clear()
        return

    await finalize_company_creation(message, state, session, normalized_phone, bot)


async def finalize_company_creation(message: Message, state: FSMContext, session: AsyncSession, phone_number: str, bot):
    """Финализация создания компании"""
    try:
        user_data = await state.get_data()

        # Создание компании
        company_data = {
            "name": user_data["company_name"],
            "description": user_data.get("company_description", ""),
            "invite_code": user_data["company_invite_code"],
            "trial_period_days": 14,
        }

        company = await create_company(session, company_data)

        # Создание пользователя (Рекрутер)
        user_data_dict = {
            "tg_id": message.from_user.id,
            "username": message.from_user.username,
            "full_name": user_data["full_name"],
            "phone_number": phone_number,
        }

        user = await create_user_with_company(session, user_data_dict, company.id, "Рекрутер", bot)

        if user:
            # Обновление created_by_id (используем явное обновление через update() для надежности в асинхронном контексте)
            from sqlalchemy import update

            await session.execute(update(Company).where(Company.id == company.id).values(created_by_id=user.id))
            await session.commit()

            description_text = company.description if company.description else "Не указано"
            await message.answer(
                f"🎉 <b>Компания создана!</b>\n\n"
                f"📌 Название: {company.name}\n"
                f"📝 Описание: {description_text}\n"
                f"🔑 Код приглашения: <code>{company.invite_code}</code>\n"
                f"⏰ Пробный период: 14 дней\n"
                f"👥 Лимит пользователей: {company.members_limit}\n\n"
                f"Ты получил роль <b>Рекрутер</b> и можешь управлять всеми функциями.\n\n"
                f"Отправь код <code>{company.invite_code}</code> своим коллегам для присоединения к компании!",
                parse_mode="HTML",
            )

            log_user_action(
                message.from_user.id,
                message.from_user.username,
                "company_created",
                {"company_id": company.id, "company_name": company.name},
            )

            # Автоматический вход в личный кабинет рекрутера
            from database.db import get_user_roles
            from keyboards.keyboards import get_keyboard_by_role
            from utils.bot.commands import set_bot_commands

            roles = await get_user_roles(session, user.id)
            if roles:
                primary_role = roles[0].name

                # Установка состояния FSM
                await state.update_data(
                    user_id=user.id,
                    role=primary_role,
                    is_authenticated=True,
                    auth_time=message.date.timestamp(),
                    company_id=user.company_id,
                )

                # Установка команд бота
                await set_bot_commands(bot, primary_role)

                # Приветственное сообщение с клавиатурой
                if primary_role in ("Наставник", "Стажер"):
                    from aiogram.types import ReplyKeyboardRemove

                    await message.answer(
                        f"Добро пожаловать, {user.full_name}! Ты вошел как {primary_role}.",
                        reply_markup=ReplyKeyboardRemove(),
                    )
                    if primary_role == "Наставник":
                        await send_mentor_menu(message)
                    if primary_role == "Стажер":
                        await send_trainee_menu(message)
                else:
                    await message.answer(
                        f"Добро пожаловать, {user.full_name}! Ты вошел как {primary_role}.",
                        reply_markup=get_keyboard_by_role(primary_role),
                    )

                log_user_action(
                    message.from_user.id,
                    message.from_user.username,
                    "auto_login_after_company_creation",
                    {"role": primary_role, "user_id": user.id, "company_id": user.company_id},
                )
            else:
                await message.answer("Используй команду /login для входа в систему.")

        else:
            await message.answer("❌ Произошла ошибка при создании пользователя.")

        await state.clear()

    except Exception as e:
        log_user_error(message.from_user.id, message.from_user.username, "company creation error", str(e))
        await message.answer("❌ Произошла ошибка при создании компании. Попробуй позже.")
        await state.clear()


# ==============================================================================
# ПРИСОЕДИНЕНИЕ К КОМПАНИИ
# ==============================================================================


@router.callback_query(F.data == "company:join")
async def callback_join_company(callback: CallbackQuery, state: FSMContext):
    """Начало присоединения к компании"""
    await callback.message.edit_text(
        "🔗 <b>Присоединение к компании</b>\n\nВведи код приглашения от своей компании:",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_company_selection")]]
        ),
    )
    await state.set_state(CompanyJoinStates.waiting_for_invite_code)
    log_user_action(callback.from_user.id, callback.from_user.username, "started company join")
    await callback.answer()


@router.message(CompanyJoinStates.waiting_for_invite_code)
async def process_invite_code_join(message: Message, state: FSMContext, session: AsyncSession):
    """Обработка ввода invite code при присоединении"""
    # Если пользователь прислал команду, не считаем её кодом приглашения
    if message.text and message.text.startswith("/"):
        from keyboards.keyboards import get_company_selection_keyboard

        await state.clear()
        await message.answer(
            "Привет! Добро пожаловать в чат-бот.\n\n🏢 Выбери действие:", reply_markup=get_company_selection_keyboard()
        )
        return

    invite_code = message.text.strip().upper()

    # Поиск компании
    company = await get_company_by_invite_code(session, invite_code)

    if not company:
        await message.answer(
            "❌ Неверный код приглашения.\n\n"
            "Компания с таким кодом не найдена. Проверь правильность кода и попробуй снова."
        )
        return

    # Проверка доступности компании
    access_check = await check_company_access(session, company.id)

    if not access_check["accessible"]:
        if access_check["reason"] == "subscription_expired":
            await message.answer(
                "❌ Подписка компании временно неактивна (заморожена).\n\n"
                "Обратитесь к администратору компании для продления подписки."
            )
        elif access_check["reason"] == "members_limit_reached":
            await message.answer(
                f"❌ В компании достигнут лимит пользователей ({company.members}/{company.members_limit}).\n\n"
                "Обратитесь к администратору компании для увеличения лимита."
            )
        elif access_check["reason"] == "company_inactive":
            await message.answer("❌ Компания деактивирована.\n\nОбратитесь к администратору.")
        return

    # Компания доступна
    await state.update_data(company_id=company.id, company_name=company.name, invite_code=invite_code)

    # Показываем сообщение "Добро пожаловать" и выбор типа регистрации
    from keyboards.keyboards import get_welcome_keyboard

    trial_status = "Да" if company.trial else "Нет"
    await message.answer(
        f"✅ <b>Компания найдена!</b>\n\n"
        f"📌 {company.name}\n"
        f"👥 Пользователей: {company.members}/{company.members_limit}\n"
        f"🆓 Триал: {trial_status}\n\n"
        "Добро пожаловать! Для завершения регистрации выбери способ:",
        parse_mode="HTML",
        reply_markup=get_welcome_keyboard(),
    )
    await state.set_state(CompanyJoinStates.waiting_for_registration_type)


@router.callback_query(CompanyJoinStates.waiting_for_registration_type, F.data == "register:normal")
async def callback_register_normal_join(callback: CallbackQuery, state: FSMContext):
    """Обработчик обычной регистрации при присоединении к компании"""
    await callback.message.edit_text(
        "Начинаем регистрацию 🚩\nПожалуйста, введи свою фамилию и имя\n\nПример: Иванов Иван",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_company_join_welcome")]]
        ),
    )
    await state.set_state(CompanyJoinStates.waiting_for_full_name)
    log_user_action(callback.from_user.id, callback.from_user.username, "started normal registration for company join")
    await callback.answer()


@router.callback_query(CompanyJoinStates.waiting_for_registration_type, F.data == "register:with_code")
async def callback_register_with_code_join(callback: CallbackQuery, state: FSMContext):
    """Обработчик регистрации с кодом при присоединении к компании"""
    # Помечаем, что это регистрация с кода (токен сначала)
    await state.update_data(registration_flow="code_first")

    await callback.message.edit_text(
        "Если ты сюда попал случайно, просто вернись назад ⬅️\n"
        "Этот шаг нужен только тем, кому рекрутер выдал специальный код\n\n"
        "Если есть код, введи его ниже",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_company_join_welcome")]]
        ),
    )
    # Используем RegistrationStates для обработки токена
    from states.states import RegistrationStates

    await state.set_state(RegistrationStates.waiting_for_admin_token)
    log_user_action(
        callback.from_user.id, callback.from_user.username, "started registration with code for company join"
    )
    await callback.answer()


@router.callback_query(F.data == "back_to_company_join_welcome")
async def callback_back_to_company_join_welcome(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Обработчик возврата к выбору типа регистрации при присоединении к компании"""
    user_data = await state.get_data()
    company_id = user_data.get("company_id")
    company_name = user_data.get("company_name", "компании")

    # Получаем информацию о компании для отображения триала и количества пользователей
    trial_info = ""
    members_info = ""
    if company_id:
        company = await get_company_by_id(session, company_id)
        if company:
            trial_status = "Да" if company.trial else "Нет"
            trial_info = f"\n🆓 Триал: {trial_status}"
            members_info = f"\n👥 Пользователей: {company.members}/{company.members_limit}"

    from keyboards.keyboards import get_welcome_keyboard

    await callback.message.edit_text(
        f"✅ <b>Компания найдена!</b>\n\n"
        f"📌 {company_name}{members_info}{trial_info}\n\n"
        "Добро пожаловать! Для завершения регистрации выбери способ:",
        parse_mode="HTML",
        reply_markup=get_welcome_keyboard(),
    )
    await state.set_state(CompanyJoinStates.waiting_for_registration_type)
    log_user_action(callback.from_user.id, callback.from_user.username, "returned to registration type selection")
    await callback.answer()


@router.message(CompanyJoinStates.waiting_for_full_name)
async def process_join_full_name(message: Message, state: FSMContext):
    """Обработка ФИО при присоединении к компании - переходим в RegistrationStates"""
    is_valid, formatted_name = validate_full_name(message.text)

    if not is_valid:
        await message.answer(
            "❌ Некорректный формат ФИО.\n\nПожалуйста, введи имя и фамилию, используя только буквы, пробелы и дефисы."
        )
        return

    await state.update_data(full_name=formatted_name)
    log_user_action(
        message.from_user.id, message.from_user.username, "provided full name for join", {"name": formatted_name}
    )

    # Переходим в RegistrationStates для продолжения регистрации
    from states.states import RegistrationStates

    await message.answer(
        "Спасибо!\nТеперь отправь свой номер: можешь просто нажать кнопку Отправить контакт или написать вручную в формате +7XXXXXXXXXX",
        reply_markup=get_contact_keyboard(),
    )
    await state.set_state(RegistrationStates.waiting_for_phone)


# Обработка телефона теперь происходит через handlers/registration.py
# Старые обработчики удалены, так как используется общий флоу регистрации


# ==============================================================================
# УПРАВЛЕНИЕ КОМПАНИЕЙ (ДЛЯ РЕКРУТЕРА)
# ==============================================================================


@router.message(F.text == "Компания 🏢")
async def cmd_company_management(message: Message, state: FSMContext, session: AsyncSession):
    """Обработчик текстовой кнопки 'Компания 🏢' для рекрутеров"""
    try:
        user = await get_user_by_tg_id(session, message.from_user.id)

        if not user or not user.company_id:
            await message.answer("❌ Ты не состоишь ни в одной компании")
            return

        # Проверка, что пользователь - рекрутер
        from database.db import get_user_roles

        roles = await get_user_roles(session, user.id)
        role_names = [role.name for role in roles]

        if "Рекрутер" not in role_names:
            await message.answer("❌ Эта функция доступна только рекрутерам")
            return

        company = await get_company_by_id(session, user.company_id)

        if not company:
            await message.answer("❌ Компания не найдена")
            return

        # Форматирование информации о компании согласно ТЗ
        start_date_str = company.start_date.strftime("%d.%m.%Y") if company.start_date else "Не указано"
        finish_date_str = company.finish_date.strftime("%d.%m.%Y") if company.finish_date else "Не указано"

        info_text = (
            f"ℹ️ <b>Информация о компании:</b>\n\n"
            f"Название: {company.name}\n"
            f"Описание: {company.description or 'Не указано'}\n"
            f"Код компании: <code>{company.invite_code}</code>\n"
            f"Кол-во пользователей: {company.members}\n\n"
            f"🔔<b>Ваша подписка</b>\n"
            f"Начало подписки: {start_date_str}\n"
            f"Конец подписки: {finish_date_str}"
        )

        await message.answer(info_text, parse_mode="HTML", reply_markup=get_company_info_keyboard())

        log_user_action(message.from_user.id, message.from_user.username, "opened company management")

    except Exception as e:
        log_user_error(message.from_user.id, message.from_user.username, "company_management_error", str(e))
        await message.answer("❌ Произошла ошибка при загрузке информации о компании")


@router.callback_query(F.data == "company:info")
async def show_company_info(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Показать информацию о компании (только для членов компании)"""
    # Очищаем состояние FSM при возврате к информации о компании
    await state.clear()

    user = await get_user_by_tg_id(session, callback.from_user.id)

    if not user or not user.company_id:
        await callback.answer("❌ Ты не состоишь ни в одной компании", show_alert=True)
        return

    company = await get_company_by_id(session, user.company_id)

    if not company:
        await callback.answer("❌ Компания не найдена", show_alert=True)
        return

    # Форматирование информации о компании согласно ТЗ
    start_date_str = company.start_date.strftime("%d.%m.%Y") if company.start_date else "Не указано"
    finish_date_str = company.finish_date.strftime("%d.%m.%Y") if company.finish_date else "Не указано"

    info_text = (
        f"ℹ️ <b>Информация о компании:</b>\n\n"
        f"Название: {company.name}\n"
        f"Описание: {company.description or 'Не указано'}\n"
        f"Код компании: <code>{company.invite_code}</code>\n"
        f"Кол-во пользователей: {company.members}\n\n"
        f"🔔<b>Ваша подписка</b>\n"
        f"Начало подписки: {start_date_str}\n"
        f"Конец подписки: {finish_date_str}"
    )

    await callback.message.edit_text(info_text, parse_mode="HTML", reply_markup=get_company_info_keyboard())
    await callback.answer()


@router.callback_query(F.data == "back_to_company_selection")
async def back_to_company_selection(callback: CallbackQuery, state: FSMContext):
    """Вернуться к выбору: создать или присоединиться"""
    await state.clear()

    from keyboards.keyboards import get_company_selection_keyboard

    await callback.message.edit_text(
        "🏢 <b>Выбери действие:</b>", parse_mode="HTML", reply_markup=get_company_selection_keyboard()
    )
    await callback.answer()


# ==============================================================================
# РЕДАКТИРОВАНИЕ КОМПАНИИ (ДЛЯ РЕКРУТЕРА)
# ==============================================================================


@router.callback_query(F.data == "company:edit_name")
async def callback_company_edit_name(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Переход к редактированию названия компании"""
    user = await get_user_by_tg_id(session, callback.from_user.id)

    if not user or not user.company_id:
        await callback.answer("❌ Ты не состоишь ни в одной компании", show_alert=True)
        return

    company = await get_company_by_id(session, user.company_id)

    if not company:
        await callback.answer("❌ Компания не найдена", show_alert=True)
        return

    # Форматирование информации с выделением редактируемого поля
    start_date_str = company.start_date.strftime("%d.%m.%Y") if company.start_date else "Не указано"
    finish_date_str = company.finish_date.strftime("%d.%m.%Y") if company.finish_date else "Не указано"

    info_text = (
        f"ℹ️ <b>Информация о компании:</b>\n\n"
        f"✏️<b>Название:</b> {company.name}\n"
        f"Описание: {company.description or 'Не указано'}\n"
        f"Код компании: <code>{company.invite_code}</code>\n"
        f"Кол-во пользователей: {company.members}\n\n"
        f"🔔<b>Ваша подписка</b>\n"
        f"Начало подписки: {start_date_str}\n"
        f"Конец подписки: {finish_date_str}\n\n"
        f"⬇️<b>Введите новое название для вашей компании</b>⬇️"
    )

    await callback.message.edit_text(info_text, parse_mode="HTML", reply_markup=get_company_edit_name_keyboard())
    await state.set_state(CompanyManagementStates.waiting_for_company_name_edit)
    await callback.answer()


@router.callback_query(F.data == "company:edit_description")
async def callback_company_edit_description(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Переход к редактированию описания компании"""
    user = await get_user_by_tg_id(session, callback.from_user.id)

    if not user or not user.company_id:
        await callback.answer("❌ Ты не состоишь ни в одной компании", show_alert=True)
        return

    company = await get_company_by_id(session, user.company_id)

    if not company:
        await callback.answer("❌ Компания не найдена", show_alert=True)
        return

    # Форматирование информации с выделением редактируемого поля
    start_date_str = company.start_date.strftime("%d.%m.%Y") if company.start_date else "Не указано"
    finish_date_str = company.finish_date.strftime("%d.%m.%Y") if company.finish_date else "Не указано"

    info_text = (
        f"ℹ️ <b>Информация о компании:</b>\n\n"
        f"Название: {company.name}\n"
        f"✏️<b>Описание:</b> {company.description or 'Не указано'}\n"
        f"Код компании: <code>{company.invite_code}</code>\n"
        f"Кол-во пользователей: {company.members}\n\n"
        f"🔔<b>Ваша подписка</b>\n"
        f"Начало подписки: {start_date_str}\n"
        f"Конец подписки: {finish_date_str}\n\n"
        f"⬇️<b>Введите новое описание для вашей компании</b>⬇️"
    )

    await callback.message.edit_text(info_text, parse_mode="HTML", reply_markup=get_company_edit_description_keyboard())
    await state.set_state(CompanyManagementStates.waiting_for_company_description_edit)
    await callback.answer()


@router.message(CompanyManagementStates.waiting_for_company_name_edit)
async def process_company_name_edit(message: Message, state: FSMContext, session: AsyncSession):
    """Обработка нового названия компании"""
    new_name = message.text.strip()

    user = await get_user_by_tg_id(session, message.from_user.id)
    if not user or not user.company_id:
        await message.answer("❌ Ты не состоишь ни в одной компании")
        await state.clear()
        return

    # Валидация длины
    if len(new_name) < 3:
        await message.answer("❌ Название компании должно содержать минимум 3 символа.")
        return

    if len(new_name) > 100:
        await message.answer("❌ Название компании не может быть длиннее 100 символов.")
        return

    # Обновление названия
    success = await update_company_name(session, user.company_id, new_name, company_id_check=user.company_id)

    if success:
        await message.answer(f"✅ Название компании успешно обновлено на: <b>{new_name}</b>", parse_mode="HTML")
        log_user_action(
            message.from_user.id, message.from_user.username, "company_name_updated", {"new_name": new_name}
        )

        # Возвращаемся к информации о компании
        company = await get_company_by_id(session, user.company_id)
        if company:
            start_date_str = company.start_date.strftime("%d.%m.%Y") if company.start_date else "Не указано"
            finish_date_str = company.finish_date.strftime("%d.%m.%Y") if company.finish_date else "Не указано"

            info_text = (
                f"ℹ️ <b>Информация о компании:</b>\n\n"
                f"Название: {company.name}\n"
                f"Описание: {company.description or 'Не указано'}\n"
                f"Код компании: <code>{company.invite_code}</code>\n"
                f"Кол-во пользователей: {company.members}\n\n"
                f"🔔<b>Ваша подписка</b>\n"
                f"Начало подписки: {start_date_str}\n"
                f"Конец подписки: {finish_date_str}"
            )

            await message.answer(info_text, parse_mode="HTML", reply_markup=get_company_info_keyboard())
    else:
        await message.answer(
            "❌ Не удалось обновить название компании.\nВозможно, такое название уже используется другой компанией."
        )

    await state.clear()


@router.message(CompanyManagementStates.waiting_for_company_description_edit)
async def process_company_description_edit(message: Message, state: FSMContext, session: AsyncSession):
    """Обработка нового описания компании"""
    new_description = message.text.strip()

    user = await get_user_by_tg_id(session, message.from_user.id)
    if not user or not user.company_id:
        await message.answer("❌ Ты не состоишь ни в одной компании")
        await state.clear()
        return

    # Валидация длины
    if len(new_description) > 500:
        await message.answer("❌ Описание не может быть длиннее 500 символов.")
        return

    # Обновление описания
    success = await update_company_description(
        session, user.company_id, new_description, company_id_check=user.company_id
    )

    if success:
        await message.answer("✅ Описание компании успешно обновлено.", parse_mode="HTML")
        log_user_action(message.from_user.id, message.from_user.username, "company_description_updated")

        # Возвращаемся к информации о компании
        company = await get_company_by_id(session, user.company_id)
        if company:
            start_date_str = company.start_date.strftime("%d.%m.%Y") if company.start_date else "Не указано"
            finish_date_str = company.finish_date.strftime("%d.%m.%Y") if company.finish_date else "Не указано"

            info_text = (
                f"ℹ️ <b>Информация о компании:</b>\n\n"
                f"Название: {company.name}\n"
                f"Описание: {company.description or 'Не указано'}\n"
                f"Код компании: <code>{company.invite_code}</code>\n"
                f"Кол-во пользователей: {company.members}\n\n"
                f"🔔<b>Ваша подписка</b>\n"
                f"Начало подписки: {start_date_str}\n"
                f"Конец подписки: {finish_date_str}"
            )

            await message.answer(info_text, parse_mode="HTML", reply_markup=get_company_info_keyboard())
    else:
        await message.answer("❌ Не удалось обновить описание компании.")

    await state.clear()


@router.callback_query(F.data == "company:view_code")
async def callback_company_view_code(callback: CallbackQuery, session: AsyncSession):
    """Просмотр кода компании"""
    user = await get_user_by_tg_id(session, callback.from_user.id)

    if not user or not user.company_id:
        await callback.answer("❌ Ты не состоишь ни в одной компании", show_alert=True)
        return

    company = await get_company_by_id(session, user.company_id)

    if not company:
        await callback.answer("❌ Компания не найдена", show_alert=True)
        return

    start_date_str = company.start_date.strftime("%d.%m.%Y") if company.start_date else "Не указано"
    finish_date_str = company.finish_date.strftime("%d.%m.%Y") if company.finish_date else "Не указано"

    info_text = (
        f"ℹ️ <b>Информация о компании:</b>\n\n"
        f"Название: {company.name}\n"
        f"Описание: {company.description or 'Не указано'}\n"
        f"Код компании: <code>{company.invite_code}</code>\n"
        f"Кол-во пользователей: {company.members}\n\n"
        f"🔔<b>Ваша подписка</b>\n"
        f"Начало подписки: {start_date_str}\n"
        f"Конец подписки: {finish_date_str}\n\n"
        f"ℹ️Отправь этот код своим коллегам — они смогут подключиться, выбрав «Присоединиться к существующей компании»."
    )

    await callback.message.edit_text(info_text, parse_mode="HTML", reply_markup=get_company_code_keyboard())
    await callback.answer()


@router.callback_query(F.data == "company:code_only")
async def callback_company_code_only(callback: CallbackQuery, session: AsyncSession):
    """Показ кода компании отдельно"""
    user = await get_user_by_tg_id(session, callback.from_user.id)

    if not user or not user.company_id:
        await callback.answer("❌ Ты не состоишь ни в одной компании", show_alert=True)
        return

    company = await get_company_by_id(session, user.company_id)

    if not company:
        await callback.answer("❌ Компания не найдена", show_alert=True)
        return

    code_text = f"🔑 <b>Код компании:</b>\n\n<code>{company.invite_code}</code>"

    await callback.message.edit_text(code_text, parse_mode="HTML", reply_markup=get_company_code_only_keyboard())
    await callback.answer()


@router.callback_query(F.data == "company:bot_link")
async def callback_company_bot_link(callback: CallbackQuery, session: AsyncSession, bot):
    """Показ ссылки на бот"""
    user = await get_user_by_tg_id(session, callback.from_user.id)

    if not user or not user.company_id:
        await callback.answer("❌ Ты не состоишь ни в одной компании", show_alert=True)
        return

    company = await get_company_by_id(session, user.company_id)

    if not company:
        await callback.answer("❌ Компания не найдена", show_alert=True)
        return

    # Получаем username бота
    try:
        bot_info = await bot.get_me()
        bot_username = bot_info.username

        if not bot_username:
            await callback.answer("❌ Не удалось получить username бота", show_alert=True)
            return

        bot_link = f"https://t.me/{bot_username}"

        link_text = f"📎 <b>Ссылка на бот:</b>\n\n{bot_link}"

        await callback.message.edit_text(link_text, parse_mode="HTML", reply_markup=get_company_bot_link_keyboard())
        await callback.answer()

    except Exception as e:
        log_user_error(callback.from_user.id, callback.from_user.username, "bot_link_error", str(e))
        await callback.answer("❌ Произошла ошибка при получении ссылки на бота", show_alert=True)
