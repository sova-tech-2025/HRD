import logging
import sys
import os
from logging.handlers import RotatingFileHandler
from datetime import datetime
from zoneinfo import ZoneInfo

_MOSCOW_TZ = ZoneInfo("Europe/Moscow")

logs_dir = os.path.join(os.getcwd(), 'logs')
os.makedirs(logs_dir, exist_ok=True)

current_date = datetime.now(_MOSCOW_TZ).strftime("%Y-%m-%d")
log_file = os.path.join(logs_dir, f'bot_{current_date}.log')

log_format = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
log_format.converter = lambda *args: datetime.now(_MOSCOW_TZ).timetuple()

file_handler = RotatingFileHandler(
    log_file,
    maxBytes=10*1024*1024,
    backupCount=5,
    encoding='utf-8'
)
file_handler.setFormatter(log_format)
file_handler.setLevel(logging.INFO)

# Настройка кодировки для консоли Windows
if sys.platform == "win32":
    import codecs
    sys.stdout.reconfigure(encoding='utf-8')

logger = logging.getLogger('telegram_bot')
logger.setLevel(logging.INFO)
logger.addHandler(file_handler)
# console вывод идёт через root logger (настроен в main.py с МСК-временем)

def log_user_action(user_id, username, action, extra_data=None):
    """Логирует действия пользователя"""

    user_info = f"Пользователь {user_id} (@{username or 'неизвестен'})"
    if extra_data:
        logger.info(f"{user_info} {action}. Данные: {extra_data}")
    else:
        logger.info(f"{user_info} {action}")

# Функция для логирования ошибок, связанных с пользователем
def log_user_error(user_id, username, error_message, exception=None):
    """Логирует ошибки, связанные с действиями пользователя"""

    user_info = f"Пользователь {user_id} (@{username or 'неизвестен'})"
    if exception:
        logger.error(f"{user_info} ошибка: {error_message}. Исключение: {str(exception)}")
    else:
        logger.error(f"{user_info} ошибка: {error_message}")