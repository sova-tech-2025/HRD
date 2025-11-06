import asyncio
import logging
import sys
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties

from config import BOT_TOKEN, LOG_LEVEL
from database.db import init_db
from handlers import auth, registration, common, admin, role_permissions, tests, mentorship, test_taking, groups, objects, user_activation, user_edit, learning_paths, trajectory_editor, mentor_assignment, trainee_trajectory, manager_attestation, manager_menu, employee_transition, broadcast, knowledge_base, fallback
from middlewares.db_middleware import DatabaseMiddleware
from middlewares.role_middleware import RoleMiddleware
from middlewares.bot_middleware import BotMiddleware
from utils.errors import router as error_router
from utils.config_validator import validate_env_vars
from utils.logger import logger
from utils.bot_commands import set_bot_commands

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    stream=sys.stdout
)

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

dp.include_router(error_router)
dp.include_router(auth.router)
dp.include_router(registration.router)
dp.include_router(admin.router)
dp.include_router(role_permissions.router)
dp.include_router(broadcast.router)  # Массовая рассылка тестов (Task 8) - ДОЛЖЕН БЫТЬ РАНЬШЕ tests.router
dp.include_router(tests.router)
dp.include_router(user_activation.router)  # ВАЖНО: РАНЬШЕ mentorship.router
dp.include_router(mentorship.router)
dp.include_router(mentor_assignment.router)  # Назначение наставников
dp.include_router(manager_attestation.router)  # Проведение аттестаций руководителями
dp.include_router(manager_menu.router)  # Меню руководителя
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
        from database.db import fix_knowledge_base_permissions, fix_recruiter_take_tests_permission, async_session
        async with async_session() as session:
            await fix_knowledge_base_permissions(session)
            await fix_recruiter_take_tests_permission(session)
            await session.commit()
        
        # Установка команд бота
        logger.info("Настройка команд бота...")
        await set_bot_commands(bot)
        
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