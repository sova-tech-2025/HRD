import re
import json
from typing import Tuple, Optional, Any, List, Union

def validate_phone_number(phone: str) -> Tuple[bool, Optional[str]]:
    """Валидация номера телефона"""

    cleaned_phone = re.sub(r'[^\d+]', '', phone)
    phone_pattern = r'^(?:\+7|7|8)(\d{10})$'
    match = re.match(phone_pattern, cleaned_phone)
    
    if not match:
        return False, None
    
    normalized_phone = f"+7{match.group(1)}"
    return True, normalized_phone

def validate_full_name(full_name: str) -> Tuple[bool, Optional[str]]:
    """Валидация ФИО"""

    cleaned_name = ' '.join(full_name.split()).strip()
    
    if len(cleaned_name) < 5 or len(cleaned_name.split()) < 2:
        return False, None

    if not re.match(r'^[а-яА-ЯёЁa-zA-Z\s-]+$', cleaned_name):
        return False, None

    formatted_name = ' '.join(word.capitalize() for word in cleaned_name.split())
    return True, formatted_name

def validate_username(username: Optional[str]) -> Tuple[bool, Optional[str]]:
    """Валидация имени пользователя Telegram"""

    if username is None:
        return True, None
    
    cleaned_username = username.strip('@')
    
    if not re.match(r'^[a-zA-Z0-9_]{3,32}$', cleaned_username):
        return False, None
    
    return True, cleaned_username

def validate_json_data(data: Any, max_depth: int = 5, max_size: int = 1024) -> Tuple[bool, Optional[str]]:
    """Валидация JSON данных для JSONB полей"""
    try:
        # Преобразуем в JSON строку для проверки размера
        json_str = json.dumps(data, ensure_ascii=False)
        
        # Проверка размера
        if len(json_str.encode('utf-8')) > max_size:
            return False, f"JSON данные слишком большие (максимум {max_size} байт)"
        
        # Проверка глубины вложенности
        def check_depth(obj, depth=0):
            if depth > max_depth:
                return False
            if isinstance(obj, dict):
                return all(check_depth(v, depth + 1) for v in obj.values())
            elif isinstance(obj, list):
                return all(check_depth(item, depth + 1) for item in obj)
            return True
        
        if not check_depth(data):
            return False, f"JSON данные слишком глубоко вложены (максимум {max_depth} уровней)"
        
        # Проверка на запрещенные ключи/значения
        def check_forbidden_content(obj):
            forbidden_keys = ['__proto__', 'constructor', 'prototype']
            if isinstance(obj, dict):
                for key in obj.keys():
                    if key in forbidden_keys or not isinstance(key, str):
                        return False
                    if not check_forbidden_content(obj[key]):
                        return False
            elif isinstance(obj, list):
                return all(check_forbidden_content(item) for item in obj)
            elif isinstance(obj, str):
                # Проверка на потенциально опасные строки
                dangerous_patterns = ['<script', 'javascript:', 'data:', 'vbscript:']
                return not any(pattern in obj.lower() for pattern in dangerous_patterns)
            return True
        
        if not check_forbidden_content(data):
            return False, "JSON содержит запрещенные элементы"
        
        return True, None
        
    except (TypeError, ValueError) as e:
        return False, f"Неверный формат JSON: {str(e)}"

def validate_test_options(options: List[str]) -> Tuple[bool, Optional[str]]:
    """Валидация вариантов ответов для тестов"""
    if not isinstance(options, list):
        return False, "Варианты ответов должны быть списком"
    
    if len(options) < 2:
        return False, "Должно быть минимум 2 варианта ответа"
    
    if len(options) > 10:
        return False, "Максимум 10 вариантов ответа"
    
    for i, option in enumerate(options):
        if not isinstance(option, str):
            return False, f"Вариант {i+1} должен быть строкой"
        
        if len(option.strip()) < 1:
            return False, f"Вариант {i+1} не может быть пустым"
        
        if len(option) > 500:
            return False, f"Вариант {i+1} слишком длинный (максимум 500 символов)"
    
    return True, None

def validate_name(name: str) -> bool:
    """Валидация названия группы, теста и других сущностей"""
    if not name or not isinstance(name, str):
        return False
    
    # Убираем лишние пробелы
    cleaned_name = name.strip()
    
    # Проверка длины
    if len(cleaned_name) < 2 or len(cleaned_name) > 100:
        return False
    
    # Проверка на разрешенные символы: буквы, цифры, пробелы, основные знаки препинания
    if not re.match(r'^[а-яА-ЯёЁa-zA-Z0-9\s\-_.,!?()\[\]{}":;]+$', cleaned_name):
        return False
    
    # Проверка что не состоит только из пробелов и знаков препинания
    if not re.search(r'[а-яА-ЯёЁa-zA-Z0-9]', cleaned_name):
        return False
    
    return True

def validate_object_name(name: str) -> bool:
    """Валидация названия объекта (разрешает слеш для адресов)"""
    if not name or not isinstance(name, str):
        return False
    
    # Убираем лишние пробелы
    cleaned_name = name.strip()
    
    # Проверка длины
    if len(cleaned_name) < 2 or len(cleaned_name) > 100:
        return False
    
    # Проверка на разрешенные символы: буквы, цифры, пробелы, знаки препинания + слеш для адресов
    if not re.match(r'^[а-яА-ЯёЁa-zA-Z0-9\s\-_.,!?()\[\]{}":;/]+$', cleaned_name):
        return False
    
    # Проверка что не состоит только из пробелов и знаков препинания
    if not re.search(r'[а-яА-ЯёЁa-zA-Z0-9]', cleaned_name):
        return False
    
    return True 