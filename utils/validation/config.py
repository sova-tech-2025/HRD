import os
from typing import List, Dict, Optional
import re

from utils.logger import logger

def validate_bot_token(token: str) -> bool:
    """Проверяет формат токена Telegram бота"""

    pattern = r'^\d+:[\w-]+$'
    return bool(re.match(pattern, token))

def validate_postgres_config(config: Dict[str, str]) -> bool:
    """Проверяет конфигурацию PostgreSQL"""

    required_keys = ['POSTGRES_USER', 'POSTGRES_DB', 'POSTGRES_HOST', 'POSTGRES_PORT']
    
    for key in required_keys:
        if key not in config or not config[key]:
            logger.error(f"Отсутствует обязательный параметр PostgreSQL: {key}")
            return False
    
    try:
        port = int(config['POSTGRES_PORT'])
        if port <= 0 or port > 65535:
            logger.error(f"Неверный порт PostgreSQL: {port}")
            return False
    except ValueError:
        logger.error(f"Порт PostgreSQL не является числом: {config['POSTGRES_PORT']}")
        return False
    
    return True

def validate_env_vars() -> bool:
    """Проверяет все необходимые переменные окружения"""

    bot_token = os.getenv('BOT_TOKEN')
    if not bot_token:
        logger.error("BOT_TOKEN не задан")
        return False
    
    if not validate_bot_token(bot_token):
        logger.error(f"Неверный формат BOT_TOKEN: {bot_token}")
        return False
    
    postgres_config = {
        'POSTGRES_USER': os.getenv('POSTGRES_USER'),
        'POSTGRES_PASSWORD': os.getenv('POSTGRES_PASSWORD'),
        'POSTGRES_DB': os.getenv('POSTGRES_DB'),
        'POSTGRES_HOST': os.getenv('POSTGRES_HOST'),
        'POSTGRES_PORT': os.getenv('POSTGRES_PORT')
    }
    
    if not validate_postgres_config(postgres_config):
        return False
    
    logger.info("Проверка переменных окружения успешно пройдена")
    return True 