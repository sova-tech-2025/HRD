"""
Обработчики для перехода стажера в сотрудника (Task 7).
Включает переход из роли стажера в роль сотрудника после успешной аттестации.
"""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from database.db import (
    get_user_by_tg_id, change_trainee_to_employee, check_user_permission,
    get_employee_tests_from_recruiter, get_user_test_result
)
from handlers.auth import check_auth
from keyboards.keyboards import get_keyboard_by_role
from utils.logger import log_user_action, log_user_error

router = Router()


# ===============================
# Обработчики для Task 7: Переход стажера в сотрудника
# ===============================

@router.callback_query(F.data == "become_employee")
async def callback_become_employee(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Обработчик кнопки 'Стать сотрудником' после успешной аттестации (ТЗ шаг 12-5)"""
    try:
        await callback.answer()
        
        # Получаем пользователя
        user = await get_user_by_tg_id(session, callback.from_user.id)
        if not user:
            await callback.message.edit_text("❌ Ты не зарегистрирован в системе.")
            return
            
        # Проверяем что пользователь - стажер
        user_roles = [role.name for role in user.roles]
        if "Стажер" not in user_roles:
            await callback.message.edit_text("❌ Только стажеры могут стать сотрудниками.")
            return
            
        # Получаем company_id для изоляции
        company_id = user.company_id
            
        # Меняем роль стажера на сотрудника с изоляцией по компании
        success = await change_trainee_to_employee(session, user.id, None, company_id=company_id)  # attestation_result_id не нужен в данном контексте
        
        if not success:
            await callback.message.edit_text(
                "❌ Произошла ошибка при смене роли.\n"
                "Обратись к администратору."
            )
            return
        
        # Показываем ЛК сотрудника согласно ТЗ (шаг 12-8)
        await show_employee_profile(callback, session, show_congratulation=True)
        
        log_user_action(callback.from_user.id, "became_employee", f"Пользователь {user.full_name} стал сотрудником")
        
    except Exception as e:
        await callback.message.edit_text("Произошла ошибка при переходе в сотрудника")
        log_user_error(callback.from_user.id, "become_employee_error", str(e))


async def show_employee_profile(callback: CallbackQuery, session: AsyncSession, show_congratulation: bool = False):
    """Показ профиля сотрудника согласно ТЗ (шаг 12-8)
    show_congratulation - показывать ли поздравительное сообщение (только при первом переходе)"""
    try:
        # Получаем обновленные данные пользователя
        user = await get_user_by_tg_id(session, callback.from_user.id)
        if not user:
            await callback.message.edit_text("❌ Ошибка получения данных пользователя")
            return
        
        # Используем универсальную функцию формирования профиля
        from handlers.common import format_profile_text
        profile_text = await format_profile_text(user, session)
        
        # Клавиатура для ЛК сотрудника согласно ТЗ
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📚 База знаний", callback_data="knowledge_base")]
        ])
        
        await callback.message.edit_text(
            profile_text,
            parse_mode="HTML",
            reply_markup=keyboard
        )

        # Показываем поздравительное сообщение только при первом переходе в сотрудника
        if show_congratulation:
            # Обновляем reply клавиатуру на роль сотрудника
            employee_keyboard = get_keyboard_by_role(["Сотрудник"])

            await callback.message.answer(
                "🎉 <b>Поздравляем!</b> Ты успешно стал сотрудником!",
                parse_mode="HTML",
                reply_markup=employee_keyboard
            )
        
        log_user_action(callback.from_user.id, "employee_profile_shown", "Показан профиль сотрудника")
        
    except Exception as e:
        await callback.message.edit_text("Произошла ошибка при показе профиля сотрудника")
        log_user_error(callback.from_user.id, "show_employee_profile_error", str(e))


# УДАЛЕНО: Заглушка для базы знаний заменена на реальную функциональность в handlers/knowledge_base.py


@router.callback_query(F.data == "back_to_employee_profile")
async def callback_back_to_employee_profile(callback: CallbackQuery, session: AsyncSession):
    """Возврат к профилю сотрудника"""
    try:
        await show_employee_profile(callback, session, show_congratulation=False)

    except Exception as e:
        await callback.message.edit_text("Произошла ошибка при возврате к профилю")
        log_user_error(callback.from_user.id, "back_to_profile_error", str(e))


@router.message(F.text.in_(["Мои данные", "Мой профиль 🦸🏻‍♂️"]))
async def cmd_employee_profile(message: Message, state: FSMContext, session: AsyncSession):
    """Обработчик команды 'Мой профиль' для сотрудника - использует общую функцию"""
    # Используем общую функцию профиля из common.py
    from handlers.common import cmd_profile
    await cmd_profile(message, state, session)


# Обработчик "Мои тесты 📋" для сотрудников перенесен в handlers/test_taking.py
# для избежания дублирования и централизации логики
