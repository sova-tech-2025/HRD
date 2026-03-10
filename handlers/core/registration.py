from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy.ext.asyncio import AsyncSession

import config
from database.db import (
    check_phone_exists,
    create_admin_with_role,
    create_user,
    create_user_without_role,
    get_user_by_tg_id,
    get_users_by_role,
    validate_admin_token,
)
from keyboards.keyboards import get_company_selection_keyboard, get_contact_keyboard
from states.states import RegistrationStates
from utils.bot.commands import set_bot_commands
from utils.logger import log_user_action, log_user_error
from utils.validation.input import validate_full_name, validate_phone_number

router = Router()


async def get_admin_settings() -> tuple[int, str]:
    """Получает настройки администраторов из конфигурации"""
    return config.MAX_ADMINS, config.ADMIN_INIT_TOKENS


async def _clear_state_if_no_company(state: FSMContext, user_data: dict) -> None:
    """Очищает FSM-состояние, только если пользователь не присоединяется к компании."""
    if not user_data.get("company_id"):
        await state.clear()


def _admin_success_message(role_name: str, company_name: str | None) -> str:
    """Формирует сообщение об успешном создании администратора."""
    role_display = "👑 Руководителем" if role_name == "Руководитель" else "👨‍💼 Рекрутером"
    if company_name:
        return (
            f"🎉 <b>Поздравляем!</b>\n\n"
            f"Ты успешно стал {role_display} компании <b>{company_name}</b>.\n"
            "Используй команду /login для входа."
        )
    return f"🎉 <b>Поздравляем!</b>\n\nТы успешно стал {role_display} системы.\nИспользуй команду /login для входа."


async def _complete_phone_registration(message: Message, state: FSMContext, session: AsyncSession, bot) -> None:
    """Завершает регистрацию после успешной валидации телефона.

    Общая логика для process_contact и process_phone_manually.
    """
    user_data = await state.get_data()
    user_data["tg_id"] = message.from_user.id
    user_data["username"] = message.from_user.username

    if user_data.get("registration_flow") == "code_first":
        try:
            if user_data.get("selected_admin_role"):
                success = await create_admin_with_role(session, user_data, user_data["selected_admin_role"])

                if success:
                    await message.answer(
                        _admin_success_message(user_data["selected_admin_role"], user_data.get("company_name")),
                        parse_mode="HTML",
                    )
                    log_user_action(
                        message.from_user.id,
                        message.from_user.username,
                        f"admin_created_with_role_{user_data['selected_admin_role']}_from_code_first",
                        {
                            "full_name": user_data["full_name"],
                            "phone": user_data["phone_number"],
                            "role": user_data["selected_admin_role"],
                            "company_id": user_data.get("company_id"),
                        },
                    )
                    await state.clear()
                else:
                    await message.answer("❌ Произошла ошибка при создании администратора. Попробуй еще раз позже.")
                    await _clear_state_if_no_company(state, user_data)
            else:
                await create_user_without_role(session, user_data, bot)
                await message.answer(
                    "✅Регистрация завершена!\n\n"
                    "Данные отправлены рекрутеру на проверку. Тебе придет уведомление, как только доступ активируют, и дальше сразу можно будет пользоваться ботом"
                )
                log_user_action(
                    message.from_user.id,
                    message.from_user.username,
                    "registration completed from code_first flow",
                    {"full_name": user_data["full_name"], "phone": user_data["phone_number"]},
                )
                await state.clear()
        except Exception as e:
            log_user_error(
                message.from_user.id, message.from_user.username, "registration error from code_first flow", str(e)
            )
            await message.answer(
                "❌ Произошла ошибка при регистрации. Попробуй еще раз позже или обратись к администратору."
            )
            await _clear_state_if_no_company(state, user_data)
        return

    # Стандартная регистрация (не code_first)
    try:
        await create_user_without_role(session, user_data, bot)
        await message.answer(
            "✅Регистрация завершена!\n\n"
            "Данные отправлены рекрутеру на проверку. Тебе придет уведомление, как только доступ активируют, и дальше сразу можно будет пользоваться ботом"
        )
        log_user_action(
            message.from_user.id,
            message.from_user.username,
            "registration completed (waiting activation)",
            {"full_name": user_data["full_name"], "phone": user_data["phone_number"]},
        )
        await state.clear()
    except Exception as e:
        log_user_error(message.from_user.id, message.from_user.username, "registration error", str(e))
        await message.answer(
            "❌ Произошла ошибка при регистрации. Попробуй еще раз позже или обратись к администратору."
        )
        await _clear_state_if_no_company(state, user_data)


@router.message(Command("register"))
async def cmd_register(message: Message, state: FSMContext, session: AsyncSession, bot):
    """Обработчик команды /register - для незарегистрированных пользователей показывает выбор компании"""
    # Сбрасываем возможные «зависшие» состояния перед началом регистрации
    await state.clear()
    user = await get_user_by_tg_id(session, message.from_user.id)

    if user:
        await message.answer("Ты уже зарегистрирован в системе. Используй команду /login для входа.")
        log_user_action(message.from_user.id, message.from_user.username, "attempted to register again")
        return

    # Для незарегистрированных пользователей показываем выбор: создать или присоединиться к компании
    await set_bot_commands(bot)
    await message.answer(
        "Привет! Добро пожаловать в чат-бот.\n\n🏢 Выбери действие:", reply_markup=get_company_selection_keyboard()
    )
    log_user_action(message.from_user.id, message.from_user.username, "started registration via /register")


@router.message(RegistrationStates.waiting_for_full_name)
async def process_full_name(message: Message, state: FSMContext):
    is_valid, formatted_name = validate_full_name(message.text)

    if not is_valid:
        await message.answer(
            "Некорректный формат ФИО. Пожалуйста, введи имя и фамилию, используя только буквы, пробелы и дефисы."
        )
        log_user_error(message.from_user.id, message.from_user.username, f"invalid full name: {message.text}")
        return

    await state.update_data(full_name=formatted_name)
    log_user_action(
        message.from_user.id, message.from_user.username, "provided full name", {"full_name": formatted_name}
    )

    await message.answer(
        "Спасибо!\nТеперь отправь свой номер: можешь просто нажать кнопку Отправить контакт или написать вручную в формате +7XXXXXXXXXX",
        reply_markup=get_contact_keyboard(),
    )
    await state.set_state(RegistrationStates.waiting_for_phone)


@router.message(RegistrationStates.waiting_for_phone, F.contact)
async def process_contact(message: Message, state: FSMContext, session: AsyncSession, bot):
    phone_number = message.contact.phone_number

    is_valid, normalized_phone = validate_phone_number(phone_number)

    if not is_valid:
        await message.answer(
            "Некорректный формат номера телефона. Пожалуйста, введи номер в формате +7XXXXXXXXXX.",
            reply_markup=get_contact_keyboard(),
        )
        log_user_error(message.from_user.id, message.from_user.username, f"invalid phone from contact: {phone_number}")
        return

    if await check_phone_exists(session, normalized_phone):
        await message.answer(
            "Этот номер телефона уже зарегистрирован в системе. "
            "Один пользователь не может регистрироваться с разных аккаунтов Telegram."
        )
        log_user_error(
            message.from_user.id,
            message.from_user.username,
            f"attempted to register with existing phone: {normalized_phone}",
        )
        await _clear_state_if_no_company(state, await state.get_data())
        return

    await state.update_data(phone_number=normalized_phone)
    log_user_action(
        message.from_user.id, message.from_user.username, "provided phone via contact", {"phone": normalized_phone}
    )

    await _complete_phone_registration(message, state, session, bot)


@router.message(RegistrationStates.waiting_for_phone)
async def process_phone_manually(message: Message, state: FSMContext, session: AsyncSession, bot):
    is_valid, normalized_phone = validate_phone_number(message.text)

    if not is_valid:
        await message.answer(
            "Некорректный формат номера телефона. Пожалуйста, введи номер в формате +7XXXXXXXXXX или используй кнопку 'Отправить контакт'.",
            reply_markup=get_contact_keyboard(),
        )
        log_user_error(message.from_user.id, message.from_user.username, f"invalid phone manual entry: {message.text}")
        return

    if await check_phone_exists(session, normalized_phone):
        await message.answer(
            "Этот номер телефона уже зарегистрирован в системе. "
            "Один пользователь не может регистрироваться с разных аккаунтов Telegram."
        )
        log_user_error(
            message.from_user.id,
            message.from_user.username,
            f"attempted to register with existing phone: {normalized_phone}",
        )
        await _clear_state_if_no_company(state, await state.get_data())
        return

    await state.update_data(phone_number=normalized_phone)
    log_user_action(
        message.from_user.id, message.from_user.username, "provided phone manually", {"phone": normalized_phone}
    )

    await _complete_phone_registration(message, state, session, bot)


@router.message(RegistrationStates.waiting_for_admin_token)
async def process_admin_token(message: Message, state: FSMContext, session: AsyncSession, bot):
    """Обработка токена администратора (только для регистрации с кодом)"""
    user_data = await state.get_data()

    # Проверяем, присоединяется ли пользователь к компании
    back_callback = "back_to_company_join_welcome" if user_data.get("company_id") else "back_to_welcome"

    # Этот обработчик только для регистрации с кодом (code_first)
    # Обычная регистрация не должна доходить до этого состояния
    if user_data.get("registration_flow") != "code_first":
        await message.answer(
            "❌ Ошибка: токен администратора доступен только при регистрации с кодом.\n"
            'Используй кнопку "⬅️ Назад" для возврата.',
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[[InlineKeyboardButton(text="⬅️ Назад", callback_data=back_callback)]]
            ),
        )
        await _clear_state_if_no_company(state, user_data)
        return

    user_data["tg_id"] = message.from_user.id
    user_data["username"] = message.from_user.username

    # Проверяем токен
    if await validate_admin_token(session, message.text.strip()):
        # Токен верный - предлагаем выбрать роль администратора
        await message.answer(
            "🎉 <b>Токен администратора принят!</b>\n\nТеперь выбери роль, которую ты хочешь получить:",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(text="👑 Руководитель", callback_data="select_admin_role:Руководитель"),
                        InlineKeyboardButton(text="👨‍💼 Рекрутер", callback_data="select_admin_role:Рекрутер"),
                    ],
                    [InlineKeyboardButton(text="🚫 Отменить", callback_data="cancel_admin_role_selection")],
                ]
            ),
        )
        await state.set_state(RegistrationStates.waiting_for_admin_role_selection)
        log_user_action(
            message.from_user.id,
            message.from_user.username,
            "admin_token_validated in code_first flow, selecting admin role",
        )
    else:
        # Токен неверный - показываем ошибку и предлагаем попробовать снова
        await message.answer(
            "❌ <b>Неверный токен</b>\n\n"
            "Токен инициализации неверный или недействительный.\n\n"
            'Попробуй ввести токен еще раз или используй кнопку "⬅️ Назад" для возврата к выбору типа регистрации.',
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[[InlineKeyboardButton(text="⬅️ Назад", callback_data=back_callback)]]
            ),
        )

        # Остаемся в состоянии waiting_for_admin_token, чтобы пользователь мог повторно ввести токен
        log_user_action(message.from_user.id, message.from_user.username, "invalid admin token in code_first flow")


@router.callback_query(RegistrationStates.waiting_for_role, F.data.startswith("role:"))
async def process_role_selection(callback: CallbackQuery, state: FSMContext, session: AsyncSession, bot):
    selected_role = callback.data.split(":")[1]

    user_data = await state.get_data()

    user_data["tg_id"] = callback.from_user.id
    user_data["username"] = callback.from_user.username

    try:
        await create_user(session, user_data, selected_role, bot)

        await callback.message.answer(
            f"🎉 Поздравляем! Ты успешно зарегистрирован как {selected_role}.\n\nТы можешь сразу начать работу - авторизация произойдет автоматически."
        )

        await callback.message.edit_reply_markup(reply_markup=None)

        log_user_action(
            callback.from_user.id,
            callback.from_user.username,
            "completed registration",
            {"role": selected_role, "full_name": user_data["full_name"]},
        )

        await state.clear()
    except Exception as e:
        log_user_error(callback.from_user.id, callback.from_user.username, "registration error", e)
        await callback.message.answer(
            "Произошла ошибка при регистрации. Пожалуйста, попробуй позже или обратись к рекрутеру."
        )

    await callback.answer()


@router.callback_query(RegistrationStates.waiting_for_role, F.data == "cancel_registration")
async def process_cancel_registration(callback: CallbackQuery, state: FSMContext):
    # Проверяем, присоединяется ли пользователь к компании
    user_data = await state.get_data()
    company_id = user_data.get("company_id")

    if company_id:
        # Пользователь присоединяется к компании - возвращаем к выбору типа регистрации
        from handlers.company.company import callback_back_to_company_join_welcome

        callback.data = "back_to_company_join_welcome"
        await callback_back_to_company_join_welcome(callback, state)
        return

    # Обычная отмена - очищаем состояние
    await state.clear()

    await callback.message.answer("Регистрация отменена. Используй /register, чтобы начать заново.")

    await callback.message.edit_reply_markup(reply_markup=None)

    log_user_action(callback.from_user.id, callback.from_user.username, "cancelled registration via button")

    await callback.answer()


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state is None:
        await message.answer("Нет активных операций для отмены.")
        return

    # Проверяем, присоединяется ли пользователь к компании
    user_data = await state.get_data()
    company_id = user_data.get("company_id")

    if company_id:
        # Пользователь присоединяется к компании - возвращаем к выбору типа регистрации

        from handlers.company.company import callback_back_to_company_join_welcome

        # Создаем временный callback для вызова обработчика
        class TempCallback:
            def __init__(self, message):
                self.from_user = message.from_user
                self.message = message
                self.data = "back_to_company_join_welcome"

            async def answer(self):
                pass

        temp_callback = TempCallback(message)
        await callback_back_to_company_join_welcome(temp_callback, state)
        log_user_action(message.from_user.id, message.from_user.username, "cancelled registration (company join)")
        return

    # Обычная отмена - очищаем состояние
    await state.clear()
    await message.answer("Регистрация отменена. Используй /register, чтобы начать заново.")
    log_user_action(message.from_user.id, message.from_user.username, "cancelled registration")


@router.message(RegistrationStates.waiting_for_role)
async def role_selection_error(message: Message, state: FSMContext, session: AsyncSession):
    # Проверяем, может быть пользователь пытается ввести токен администратора
    max_admins, admin_tokens_str = await get_admin_settings()
    # В контексте регистрации company_id еще не установлен, поэтому получаем всех руководителей
    existing_managers = await get_users_by_role(session, "Руководитель", company_id=None)

    # Если есть токены, проверяем введенный текст как потенциальный токен
    if admin_tokens_str:
        user_data = await state.get_data()
        user_data["tg_id"] = message.from_user.id
        user_data["username"] = message.from_user.username

        # Проверяем токен
        if await validate_admin_token(session, message.text.strip()):
            # Токен верный, предлагаем выбрать роль
            await message.answer(
                "🎉 <b>Токен администратора принят!</b>\n\nТеперь выбери роль, которую ты хочешь получить:",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(
                    inline_keyboard=[
                        [
                            InlineKeyboardButton(
                                text="👑 Руководитель", callback_data="select_admin_role:Руководитель"
                            ),
                            InlineKeyboardButton(text="👨‍💼 Рекрутер", callback_data="select_admin_role:Рекрутер"),
                        ],
                        [InlineKeyboardButton(text="🚫 Отменить", callback_data="cancel_admin_role_selection")],
                    ]
                ),
            )
            await state.set_state(RegistrationStates.waiting_for_admin_role_selection)
            log_user_action(
                message.from_user.id,
                message.from_user.username,
                "admin_token_validated",
                {"full_name": user_data["full_name"]},
            )
            return

    await message.answer("Пожалуйста, выберите роль из предложенного списка.")


@router.message(RegistrationStates.waiting_for_phone)
async def phone_error(message: Message):
    await message.answer(
        "Пожалуйста, отправь свой номер телефона через кнопку 'Отправить контакт' или введи номер в формате +7XXXXXXXXXX.",
        reply_markup=get_contact_keyboard(),
    )


@router.message(RegistrationStates.waiting_for_full_name)
async def full_name_error(message: Message):
    await message.answer(
        "Пожалуйста, введи свою фамилию и имя, используя только буквы, пробелы и дефисы.\n\nПример: Иванов Иван"
    )


@router.callback_query(F.data.startswith("select_admin_role:"), RegistrationStates.waiting_for_admin_role_selection)
async def callback_select_admin_role(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Обработчик выбора роли администратора"""
    role_name = callback.data.split(":")[1]

    # Получаем данные пользователя
    user_data = await state.get_data()

    # Проверяем тип регистрации
    if user_data.get("registration_flow") == "code_first":
        # Регистрация с кода - сохраняем роль и переходим к ФИО
        await state.update_data(selected_admin_role=role_name)

        role_display = "👑 Руководителя" if role_name == "Руководитель" else "👨‍💼 Рекрутера"

        await callback.message.edit_text(
            f"✅ Выбрана роль {role_display}\n\n"
            "Начинаем регистрацию 🚩\nПожалуйста, введи свою фамилию и имя\n\nПример: Иванов Иван"
        )
        await state.set_state(RegistrationStates.waiting_for_full_name)

        log_user_action(
            callback.from_user.id, callback.from_user.username, f"selected_admin_role_{role_name}_in_code_first_flow"
        )
        await callback.answer()
    else:
        # Обычная регистрация - создаем администратора сразу
        user_data["tg_id"] = callback.from_user.id
        user_data["username"] = callback.from_user.username

        success = await create_admin_with_role(session, user_data, role_name)

        if success:
            await callback.message.edit_text(
                _admin_success_message(role_name, user_data.get("company_name")),
                parse_mode="HTML",
            )

            log_user_action(
                callback.from_user.id,
                callback.from_user.username,
                f"admin_created_with_role_{role_name}",
                {"full_name": user_data["full_name"], "role": role_name, "company_id": user_data.get("company_id")},
            )
            await state.clear()
        else:
            await callback.message.edit_text(
                "❌ <b>Ошибка создания администратора</b>\n\n"
                "Произошла ошибка при создании учетной записи администратора.\n"
                "Попробуй позже или обратись к разработчику.",
                parse_mode="HTML",
            )
            await _clear_state_if_no_company(state, user_data)

        await callback.answer()


@router.callback_query(F.data == "cancel_admin_role_selection", RegistrationStates.waiting_for_admin_role_selection)
async def callback_cancel_admin_role_selection(callback: CallbackQuery, state: FSMContext):
    """Обработчик отмены выбора роли администратора"""
    # Проверяем, присоединяется ли пользователь к компании
    user_data = await state.get_data()
    company_id = user_data.get("company_id")

    if company_id:
        # Пользователь присоединяется к компании - возвращаем к выбору типа регистрации
        from handlers.company.company import callback_back_to_company_join_welcome

        callback.data = "back_to_company_join_welcome"
        await callback_back_to_company_join_welcome(callback, state)
        return

    # Обычная отмена - очищаем состояние
    await callback.message.edit_text(
        "🚫 <b>Регистрация администратора отменена</b>\n\n"
        "Ты можешь начать регистрацию заново с помощью команды /register.",
        parse_mode="HTML",
    )
    await state.clear()
    await callback.answer()
