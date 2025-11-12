from typing import Callable, Dict, Any, Awaitable
from datetime import datetime
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from database.db import get_user_by_tg_id
from utils.logger import logger


class CompanyMiddleware(BaseMiddleware):
    """
    Middleware для проверки подписки компании.
    
    Проверяет:
    - Наличие компании у пользователя
    - Активность подписки компании
    
    Добавляет в data:
    - company: объект компании
    - company_id: ID компании
    """
    
    # Команды, которые не требуют проверки компании
    SKIP_COMMANDS = ['/start', '/login', '/help']
    
    # Callback data, которые не требуют проверки
    SKIP_CALLBACKS = ['company:create', 'company:join', 'back_to_company_selection', 'company:skip_description', 'role_join:']
    
    async def __call__(
        self,
        handler: Callable[[Message | CallbackQuery, Dict[str, Any]], Awaitable[Any]],
        event: Message | CallbackQuery,
        data: Dict[str, Any]
    ) -> Any:
        # Получаем сессию БД
        session: AsyncSession = data.get('session')
        if not session:
            logger.warning("CompanyMiddleware: session not found in data")
            return await handler(event, data)
        
        # Определяем тип события
        if isinstance(event, Message):
            user_id = event.from_user.id
            
            # Пропускаем команды, которые не требуют проверки
            if event.text and any(event.text.startswith(cmd) for cmd in self.SKIP_COMMANDS):
                return await handler(event, data)
        
        elif isinstance(event, CallbackQuery):
            user_id = event.from_user.id
            
            # Пропускаем callback, которые не требуют проверки
            if event.data and any(event.data.startswith(skip) for skip in self.SKIP_CALLBACKS):
                return await handler(event, data)
        else:
            # Неизвестный тип события
            return await handler(event, data)
        
        try:
            # Получаем пользователя
            user = await get_user_by_tg_id(session, user_id)
            
            if not user:
                # Пользователь не зарегистрирован - пропускаем middleware
                return await handler(event, data)
            
            # Проверяем наличие компании
            if not user.company_id:
                # У пользователя нет компании - это ошибка
                error_msg = "❌ Ты не привязан ни к одной компании. Обратись к администратору."
                
                if isinstance(event, Message):
                    await event.answer(error_msg)
                elif isinstance(event, CallbackQuery):
                    await event.answer(error_msg, show_alert=True)
                
                logger.warning(f"User {user_id} has no company")
                return
            
            # Получаем компанию (через relationship)
            company = user.company
            
            if not company:
                error_msg = "❌ Компания не найдена. Обратись к администратору."
                
                if isinstance(event, Message):
                    await event.answer(error_msg)
                elif isinstance(event, CallbackQuery):
                    await event.answer(error_msg, show_alert=True)
                
                logger.error(f"Company {user.company_id} not found for user {user_id}")
                return
            
            # Проверяем активность подписки
            if not company.subscribe:
                error_msg = (
                    "❌ Подписка компании истекла (заморожена).\n\n"
                    "Обратись к администратору компании для продления подписки."
                )
                
                if isinstance(event, Message):
                    await event.answer(error_msg)
                elif isinstance(event, CallbackQuery):
                    await event.answer(error_msg, show_alert=True)
                
                logger.warning(f"Company {company.id} subscription expired for user {user_id}")
                return
            
            # Проверка даты окончания подписки (по ТЗ: если finish_date прошла - доступ блокируется)
            if company.finish_date and company.finish_date < datetime.now():
                error_msg = (
                    "❌ Подписка компании истекла (заморожена).\n\n"
                    "Обратись к администратору компании для продления подписки."
                )
                
                if isinstance(event, Message):
                    await event.answer(error_msg)
                elif isinstance(event, CallbackQuery):
                    await event.answer(error_msg, show_alert=True)
                
                logger.warning(f"Company {company.id} finish_date expired for user {user_id}")
                return
            
            # Добавляем компанию в контекст
            data['company'] = company
            data['company_id'] = company.id
            
            # КРИТИЧЕСКИ ВАЖНО: Сохраняем company_id в state.data для использования в handlers
            if 'state' in data:
                state: FSMContext = data['state']
                await state.update_data(company_id=company.id)
            
            logger.debug(f"CompanyMiddleware: user {user_id} in company {company.id}")
            
        except Exception as e:
            logger.error(f"Error in CompanyMiddleware: {e}")
            # При ошибке пропускаем middleware и продолжаем
            pass
        
        return await handler(event, data)

