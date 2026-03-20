"""
Утилиты для E2E-тестов: извлечение данных из сообщений бота, задержки.
"""

import asyncio
import re
from typing import Optional


def extract_invite_code(text: str) -> Optional[str]:
    """
    Извлечь инвайт-код компании из сообщения бота.

    Ищет паттерны:
    - "Код приглашения: XXXXX"
    - "код: XXXXX"
    - Код в обратных кавычках: `XXXXX`
    """
    # Паттерн 1: "Код приглашения: XXXXX" или "Код: XXXXX"
    match = re.search(r"[Кк]од(?:\s+приглашения)?[:\s]+([A-Za-z0-9А-Яа-яёЁ_-]{4,30})", text)
    if match:
        return match.group(1).strip()

    # Паттерн 2: код в обратных кавычках
    match = re.search(r"`([A-Za-z0-9_-]{4,30})`", text)
    if match:
        return match.group(1)

    return None


def extract_emoji_status(text: str, item_name: str) -> Optional[str]:
    """
    Найти статус-иконку (✅/🟡/⛔️) для элемента в тексте.

    Args:
        text: текст сообщения бота
        item_name: название элемента (тест, этап)

    Returns:
        Эмодзи-статус или None
    """
    # Ищем иконку рядом с названием элемента
    pattern = rf"(✅|🟡|⛔️|⛔|❌)\s*{re.escape(item_name)}"
    match = re.search(pattern, text)
    if match:
        return match.group(1)

    # Обратный порядок: название затем иконка
    pattern = rf"{re.escape(item_name)}\s*(✅|🟡|⛔️|⛔|❌)"
    match = re.search(pattern, text)
    if match:
        return match.group(1)

    return None


def contains_access_denied(text: str) -> bool:
    """Проверить, содержит ли сообщение отказ в доступе."""
    denial_patterns = [
        "Доступ запрещен",
        "доступ запрещен",
        "Доступ запрещён",
        "доступ запрещён",
        "нет доступа",
        "Нет доступа",
        "У вас нет доступа",
        "у вас нет доступа",
        "Недостаточно прав",
        "недостаточно прав",
    ]
    return any(p in text for p in denial_patterns)


def contains_test_passed(text: str) -> bool:
    """Проверить, содержит ли сообщение информацию об успешном прохождении теста."""
    pass_patterns = [
        "Тест пройден",
        "тест пройден",
        "Вы прошли тест",
        "вы прошли тест",
        "Результат: Пройден",
        "✅",
    ]
    return any(p in text for p in pass_patterns)


def extract_score(text: str) -> Optional[int]:
    """Извлечь набранные баллы из результата теста."""
    match = re.search(r"(\d+)\s*(?:из|/)\s*\d+\s*(?:баллов|балл|б\.)", text)
    if match:
        return int(match.group(1))

    match = re.search(r"(?:Баллы|Результат|Набрано)[:\s]+(\d+)", text)
    if match:
        return int(match.group(1))

    return None


async def wait_between_actions(seconds: float = 1.0) -> None:
    """Явная задержка между действиями для стабильности."""
    await asyncio.sleep(seconds)
