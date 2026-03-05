from aiogram import Bot
from aiogram.types import BotCommand

async def set_bot_commands(bot: Bot, role: str = None):
    """Устанавливает команды в зависимости от роли пользователя"""
    commands = [
        BotCommand(command="start", description="Запуск/перезапуск бота"),
        BotCommand(command="help", description="Получить справку")
    ]

    # Все команды дублируют клавиатуру, поэтому оставляем только базовые команды
    # + logout для всех авторизованных пользователей
    if role in ["Руководитель", "Рекрутер", "Наставник", "Сотрудник", "Стажер"]:
        commands.extend([
            BotCommand(command="logout", description="Выйти из системы")
        ])
    else: # Неавторизованный пользователь
        commands.extend([
            BotCommand(command="register", description="Регистрация"),
            BotCommand(command="login", description="Войти в систему")
        ])

    await bot.set_my_commands(commands) 