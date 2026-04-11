import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from bot.config import (
    BOT_TOKEN,
    PROXY_ENABLED,
    PROXY_HOST,
    PROXY_LOGIN,
    PROXY_PASSWORD,
    PROXY_PORT,
    PROXY_TYPE,
)
from bot.database.db import init_db
from bot.handlers import fallback
from bot.handlers.company import company, groups, objects
from bot.handlers.core import auth, common, registration
from bot.handlers.exams import exam_assignment, exam_conducting, exam_menu
from bot.handlers.knowledge import knowledge_base
from bot.handlers.management import employee_transition, manager_attestation, manager_menu
from bot.handlers.tests import broadcast, test_taking, tests
from bot.handlers.training import learning_paths, mentor_assignment, mentorship, trainee_trajectory, trajectory_editor
from bot.handlers.users import admin, role_permissions, user_activation, user_edit
from bot.middlewares.bot_middleware import BotMiddleware
from bot.middlewares.company_middleware import CompanyMiddleware
from bot.middlewares.db_middleware import DatabaseMiddleware
from bot.middlewares.role_middleware import RoleMiddleware
from bot.utils.bot.commands import set_bot_commands
from bot.utils.bot.errors import router as error_router
from bot.utils.logger import log_format, logger
from bot.utils.validation.config import validate_env_vars

# Настраиваем root logger с московским временем (для aiogram и других библиотек)
root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)
root_handler = logging.StreamHandler(sys.stdout)
root_handler.setFormatter(log_format)
root_logger.addHandler(root_handler)

# Настройка прокси для Telegram API
session = None
if PROXY_ENABLED and PROXY_HOST and PROXY_PORT:
    protocol = "https" if PROXY_TYPE == "https" else "socks5"
    if PROXY_LOGIN and PROXY_PASSWORD:
        proxy_url = f"{protocol}://{PROXY_LOGIN}:{PROXY_PASSWORD}@{PROXY_HOST}:{PROXY_PORT}"
    else:
        proxy_url = f"{protocol}://{PROXY_HOST}:{PROXY_PORT}"
    session = AiohttpSession(proxy=proxy_url)
    logger.info(f"Прокси включён: {protocol}://{PROXY_HOST}:{PROXY_PORT}")

bot = Bot(token=BOT_TOKEN, session=session, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

dp.include_router(error_router)
dp.include_router(auth.router)
dp.include_router(company.router)  # Управление компаниями - ВАЖНО: после auth
dp.include_router(registration.router)  # Регистрация - используется при присоединении к компании
dp.include_router(admin.router)
dp.include_router(role_permissions.router)
dp.include_router(broadcast.router)  # Массовая рассылка тестов (Task 8) - ДОЛЖЕН БЫТЬ РАНЬШЕ tests.router
dp.include_router(tests.router)
dp.include_router(user_activation.router)  # ВАЖНО: РАНЬШЕ mentorship.router
dp.include_router(mentorship.router)
dp.include_router(mentor_assignment.router)  # Назначение наставников
dp.include_router(manager_attestation.router)  # Проведение аттестаций руководителями
dp.include_router(manager_menu.router)  # Меню руководителя
dp.include_router(exam_menu.router)  # Экзамены: меню, создание, карточка
dp.include_router(exam_assignment.router)  # Экзамены: назначение
dp.include_router(exam_conducting.router)  # Экзамены: проведение, сдача
dp.include_router(test_taking.router)  # Прохождение тестов (должен быть раньше trainee_trajectory)
dp.include_router(trainee_trajectory.router)  # Прохождение траекторий стажерами
dp.include_router(groups.router)
dp.include_router(objects.router)
dp.include_router(user_edit.router)  # ПОСЛЕ groups/objects, т.к. имеет глобальный обработчик cancel_edit
dp.include_router(learning_paths.router)  # Траектории обучения
dp.include_router(trajectory_editor.router)  # Редактор траекторий
dp.include_router(knowledge_base.router)  # База знаний (Task 9)
dp.include_router(employee_transition.router)  # Переход стажеров в сотрудники (Task 7)
dp.include_router(common.router)
# Fallback роутер должен быть в конце!
dp.include_router(fallback.router)

dp.update.middleware(DatabaseMiddleware())
dp.update.middleware(BotMiddleware())
dp.update.middleware(CompanyMiddleware())  # Проверка подписки компании
dp.update.middleware(RoleMiddleware())


async def main():
    if not validate_env_vars():
        logger.critical("Ошибка проверки переменных окружения. Выход...")
        return

    try:
        # Инициализация базы данных
        logger.info("Инициализация базы данных...")
        await init_db()

        # Исправление прав доступа к базе знаний (если нужно)
        logger.info("Проверка прав доступа к базе знаний...")
        from bot.database.db import async_session, fix_knowledge_base_permissions, fix_recruiter_take_tests_permission

        async with async_session() as session:
            await fix_knowledge_base_permissions(session)
            await fix_recruiter_take_tests_permission(session)
            await session.commit()

        # Установка команд бота
        logger.info("Настройка команд бота...")
        await set_bot_commands(bot)

        # Запуск планировщика задач для проверки подписок
        logger.info("Запуск планировщика задач...")
        from bot.utils.bot.scheduler import start_scheduler

        scheduler = start_scheduler(bot)

        # Запуск бота
        logger.info("Запуск бота...")
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
    except Exception as e:
        logger.error(f"Ошибка запуска: {e}")
    finally:
        # Корректное завершение работы бота
        logger.info("Завершение работы...")
        await bot.session.close()
        logger.info("Бот остановлен")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен по прерыванию с клавиатуры")
    except Exception as e:
        logger.critical(f"Непредвиденная ошибка: {e}")
        sys.exit(1)
