"""
Утилиты для форматирования прогресса тестов в траектории стажера.

Этот модуль реализует Single Responsibility Principle (SRP):
- get_test_status_icon() - определение иконки по статусу
- format_test_line() - базовое форматирование строки теста
- format_test_with_percentage() - форматирование с процентами

Использование:
    from utils.test_progress_formatters import (
        get_test_status_icon,
        format_test_line,
        format_test_with_percentage,
    )
"""

from typing import Optional


# Константы для иконок статуса теста
TEST_ICON_PASSED = "✅"
TEST_ICON_AVAILABLE = "♻️"
TEST_ICON_CLOSED = "❌"


def get_test_status_icon(is_passed: bool, is_stage_opened: bool) -> str:
    """
    Определяет иконку статуса теста.

    Args:
        is_passed: Пройден ли тест
        is_stage_opened: Открыт ли этап

    Returns:
        Строка с эмодзи-иконкой

    Логика (единая для всего приложения):
        - Пройден И этап открыт: ✅
        - Не пройден И этап открыт: ♻️
        - Этап закрыт: ❌
    """
    if is_passed and is_stage_opened:
        return TEST_ICON_PASSED
    elif is_stage_opened:
        return TEST_ICON_AVAILABLE
    else:
        return TEST_ICON_CLOSED


def format_test_line(test_num: int, test_name: str, icon: str) -> str:
    """
    Форматирует базовую строку теста.

    Args:
        test_num: Номер теста (начиная с 1)
        test_name: Название теста
        icon: Иконка статуса

    Returns:
        Отформатированная строка с переводом строки в конце
    """
    return f"{icon}<b>Тест {test_num}:</b> {test_name}\n"


def format_test_with_percentage(
    test_num: int,
    test_name: str,
    icon: str,
    score: Optional[float] = None,
    max_score: Optional[float] = None
) -> str:
    """
    Форматирует строку теста с процентом выполнения.

    Args:
        test_num: Номер теста (начиная с 1)
        test_name: Название теста
        icon: Иконка статуса
        score: Набранные баллы (None если тест не пройден)
        max_score: Максимальные баллы (None если тест не пройден)

    Returns:
        Отформатированная строка с процентами (если есть) и переводом строки
    """
    if score is not None and max_score is not None and max_score > 0:
        percentage = (score / max_score) * 100
        return f"{icon}<b>Тест {test_num}:</b> {test_name} - {percentage:.0f}%\n"
    else:
        return format_test_line(test_num, test_name, icon)


def format_test_line_figma(test_name: str, icon: str) -> str:
    """Форматирует строку теста в стиле Figma (без номера)."""
    return f"{icon} Тест: {test_name}\n"
