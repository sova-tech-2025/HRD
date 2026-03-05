import os

from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from database.db import get_user_by_tg_id, get_user_by_id, get_user_roles, get_company_by_id
from utils.logger import log_user_action, log_user_error
from utils.timezone import moscow_now


async def validate_user_access(session: AsyncSession, user) -> tuple[bool, str | None, str | None]:
    """Проверяет доступ пользователя: is_active, company_id, подписку, finish_date, роли.

    Возвращает (True, None, primary_role) если доступ разрешён,
    или (False, "текст ошибки", None) если доступ запрещён.
    Без side effects — не шлёт сообщения.
    """
    if not user.is_active:
        return False, "Твой аккаунт деактивирован. Обратись к администратору.", None

    if not user.company_id:
        return False, (
            "❌ Ты не привязан ни к одной компании.\n\n"
            "Обратись к администратору."
        ), None

    company = await get_company_by_id(session, user.company_id)
    if company and not company.subscribe:
        return False, (
            "❌ Подписка компании истекла (заморожена).\n\n"
            "Обратись к администратору компании для продления подписки."
        ), None

    if company and company.finish_date and company.finish_date < moscow_now():
        return False, (
            "❌ Подписка компании истекла (заморожена).\n\n"
            "Обратись к администратору компании для продления подписки."
        ), None

    roles = await get_user_roles(session, user.id)
    if not roles:
        return False, "У тебя нет назначенных ролей. Обратись к рекрутеру.", None

    return True, None, roles[0].name


async def check_auth(message: Message, state: FSMContext, session: AsyncSession) -> bool:
    try:
        data = await state.get_data()
        is_authenticated = data.get("is_authenticated", False)
        auth_time = data.get("auth_time", 0)

        if is_authenticated and auth_time and (moscow_now().timestamp() - auth_time) > 86400:  # 24 часа
            await state.clear()
            await message.answer(
                "👀 Ты давно не заходил\n\nДля безопасности твоя сессия завершена. Пожалуйста, обновись",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="Войти заново", callback_data="login_again")]
                ])
            )
            return False

        if is_authenticated:
            user = await get_user_by_tg_id(session, message.from_user.id)
            # Fallback: callback.message.from_user — бот, берём user_id из FSM
            if not user and data.get("user_id"):
                user = await get_user_by_id(session, data["user_id"])
            if not user or not user.is_active:
                await state.clear()
                await message.answer("Твой аккаунт деактивирован. Обратись к администратору.")
                return False

            # Проверка наличия компании и подписки
            if not user.company_id:
                await state.clear()
                await message.answer(
                    "❌ Ты не привязан ни к одной компании.\n\n"
                    "Обратись к администратору."
                )
                return False

            # Проверка подписки компании (используем явный запрос вместо lazy loading)
            company = await get_company_by_id(session, user.company_id)
            if company and not company.subscribe:
                await state.clear()
                await message.answer(
                    "❌ Подписка компании истекла (заморожена).\n\n"
                    "Обратись к администратору компании для продления подписки."
                )
                return False

            # Проверка даты окончания подписки (по ТЗ: если finish_date прошла - доступ блокируется)
            if company and company.finish_date and company.finish_date < moscow_now():
                await state.clear()
                await message.answer(
                    "❌ Подписка компании истекла (заморожена).\n\n"
                    "Обратись к администратору компании для продления подписки."
                )
                return False

            return True

        user = await get_user_by_tg_id(session, message.from_user.id)
        # Fallback: callback.message.from_user — бот, берём user_id из FSM
        if not user and data.get("user_id"):
            user = await get_user_by_id(session, data["user_id"])

        if not user:
            await message.answer("Ты не зарегистрирован в системе. Используй команду /start для регистрации.")
            return False

        if not user.is_active:
            await message.answer("Твой аккаунт деактивирован. Обратись к администратору.")
            return False

        # Проверка наличия компании
        if not user.company_id:
            await message.answer(
                "❌ Ты не привязан ни к одной компании.\n\n"
                "Обратись к администратору."
            )
            return False

        # Проверка подписки компании (используем явный запрос вместо lazy loading)
        company = await get_company_by_id(session, user.company_id)
        if company and not company.subscribe:
            await message.answer(
                "❌ Подписка компании истекла (заморожена).\n\n"
                "Обратись к администратору компании для продления подписки."
            )
            return False

        # Проверка даты окончания подписки (по ТЗ: если finish_date прошла - доступ блокируется)
        if company and company.finish_date and company.finish_date < moscow_now():
            await message.answer(
                "❌ Подписка компании истекла (заморожена).\n\n"
                "Обратись к администратору компании для продления подписки."
            )
            return False

        auto_auth_allowed = os.getenv("ALLOW_AUTO_AUTH", "true").lower() == "true"
        if not auto_auth_allowed:
            await message.answer("Пожалуйста, выполни команду /login для входа.")
            return False

        roles = await get_user_roles(session, user.id)

        if not roles:
            await message.answer("У тебя нет назначенных ролей. Обратись к рекрутеру.")
            return False

        primary_role = roles[0].name

        await state.update_data(
            user_id=user.id,
            role=primary_role,
            is_authenticated=True,
            auth_time=message.date.timestamp(),
            company_id=user.company_id  # КРИТИЧНО: сохраняем company_id для изоляции!
        )

        log_user_action(
            message.from_user.id,
            message.from_user.username,
            "auto authentication",
            {"role": primary_role, "user_id": user.id, "company_id": user.company_id}
        )

        return True
    except Exception as e:
        log_user_error(message.from_user.id, message.from_user.username, "authentication check error", e)
        await message.answer("Произошла ошибка при проверке авторизации. Пожалуйста, попробуй позже.")
        return False
