import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from utils.logger import logger

load_dotenv()

def get_required_env(name: str) -> str:
    """Получает обязательную переменную окружения или завершает программу при её отсутствии"""

    value = os.getenv(name)
    if value is None:
        logger.critical(f"Обязательная переменная окружения {name} не задана")
        sys.exit(1)
    return value

BOT_TOKEN = get_required_env("BOT_TOKEN")

DB_USER = get_required_env("POSTGRES_USER")
DB_PASS = os.getenv("POSTGRES_PASSWORD", "")
DB_NAME = get_required_env("POSTGRES_DB")
DB_HOST = get_required_env("POSTGRES_HOST")
DB_PORT = get_required_env("POSTGRES_PORT")

DATABASE_URL = f"postgresql+asyncpg://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# Получаем ID управляющих из переменных окружения
MANAGER_IDS_STR = os.getenv("MANAGER_IDS", "")
MANAGER_IDS = [int(id.strip()) for id in MANAGER_IDS_STR.split(",") if id.strip().isdigit()] if MANAGER_IDS_STR else []

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# Роль по умолчанию для новых пользователей
DEFAULT_ROLE = os.getenv("DEFAULT_ROLE", "Стажер")

# =================================================================
# НАСТРОЙКИ КОМПАНИЙ И ПОДПИСОК
# =================================================================

# Период пробной подписки (в днях)
TRIAL_PERIOD_DAYS = int(os.getenv("TRIAL_PERIOD_DAYS", "5"))

# Лимит пользователей по умолчанию для новых компаний
DEFAULT_MEMBERS_LIMIT = int(os.getenv("DEFAULT_MEMBERS_LIMIT", "15"))

# Длина кода приглашения
INVITE_CODE_LENGTH = int(os.getenv("INVITE_CODE_LENGTH", "10"))

# Префикс для кода приглашения (опционально)
INVITE_CODE_PREFIX = os.getenv("INVITE_CODE_PREFIX", "")

# Дни предупреждения об окончании подписки
SUBSCRIPTION_WARNING_DAYS = [int(d) for d in os.getenv("SUBSCRIPTION_WARNING_DAYS", "3,7,14").split(",")] 

# =================================================================
# МЕДИА РЕСУРСЫ
# =================================================================

_BASE_DIR = Path(__file__).resolve().parent
_DEFAULT_MAIN_MENU_IMAGE_PATH = _BASE_DIR / "assets" / "images" / "main_menu" / "main_menu.jpg"
_DEFAULT_MY_TESTS_IMAGE_PATH = _BASE_DIR / "assets" / "images" / "tests" / "my_tests_banner.jpg"

MAIN_MENU_IMAGE_FILE_ID = os.getenv("MAIN_MENU_IMAGE_FILE_ID")
MAIN_MENU_IMAGE_URL = os.getenv("MAIN_MENU_IMAGE_URL")

_env_image_path = os.getenv("MAIN_MENU_IMAGE_PATH")
if _env_image_path:
    MAIN_MENU_IMAGE_PATH = str(Path(_env_image_path))
elif _DEFAULT_MAIN_MENU_IMAGE_PATH.exists():
    MAIN_MENU_IMAGE_PATH = str(_DEFAULT_MAIN_MENU_IMAGE_PATH)
else:
    MAIN_MENU_IMAGE_PATH = None
MY_TESTS_IMAGE_FILE_ID = os.getenv("MY_TESTS_IMAGE_FILE_ID")
MY_TESTS_IMAGE_URL = os.getenv("MY_TESTS_IMAGE_URL")

_env_my_tests_image_path = os.getenv("MY_TESTS_IMAGE_PATH")
if _env_my_tests_image_path:
    MY_TESTS_IMAGE_PATH = str(Path(_env_my_tests_image_path))
elif _DEFAULT_MY_TESTS_IMAGE_PATH.exists():
    MY_TESTS_IMAGE_PATH = str(_DEFAULT_MY_TESTS_IMAGE_PATH)
else:
    MY_TESTS_IMAGE_PATH = None
