from aiogram import Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from states.states import CompanyManagementStates

router = Router()


@router.message(StateFilter(CompanyManagementStates.waiting_for_company_name_edit))
async def handle_unexpected_company_name_edit_input(message: Message, state: FSMContext):
    """Обработчик неожиданного ввода при редактировании названия компании"""
    await message.answer(
        "❌ <b>Ожидается текстовое сообщение</b>\n\n"
        "Пожалуйста, введи новое название для компании текстом.\n"
        "Название должно содержать от 3 до 100 символов.",
        parse_mode="HTML",
    )


@router.message(StateFilter(CompanyManagementStates.waiting_for_company_description_edit))
async def handle_unexpected_company_description_edit_input(message: Message, state: FSMContext):
    """Обработчик неожиданного ввода при редактировании описания компании"""
    await message.answer(
        "❌ <b>Ожидается текстовое сообщение</b>\n\n"
        "Пожалуйста, введи новое описание для компании текстом.\n"
        "Описание не должно превышать 500 символов.",
        parse_mode="HTML",
    )
