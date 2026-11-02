"""
Утилиты для форматирования прогресса тестов в траектории стажера.

Этот модуль реализует Single Responsibility Principle (SRP):
- get_test_status_icon() - определение иконки по статусу
- is_stage_passed() - пройден ли этап
- format_test_line() - базовое форматирование строки теста
- format_test_with_percentage() - форматирование с процентами

Использование:
    from bot.utils.formatters.test_progress import (
        get_test_status_icon,
        format_test_line,
        format_test_with_percentage,
    )
"""

from typing import Optional

# Константы для иконок статуса теста
TEST_ICON_PASSED = "✅"
TEST_ICON_AVAILABLE = "⏳"
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
        - Пройден: ✅ (закрытие этапа прохождение не отменяет)
        - Не пройден И этап открыт: ⏳
        - Не пройден И этап закрыт: ❌
    """
    if is_passed:
        return TEST_ICON_PASSED
    elif is_stage_opened:
        return TEST_ICON_AVAILABLE
    else:
        return TEST_ICON_CLOSED


def is_stage_passed(is_completed: bool, total_tests: int, passed_tests: int) -> bool:
    """
    Пройден ли этап.

    Args:
        is_completed: Флаг TraineeStageProgress.is_completed
        total_tests: Всего тестов в этапе
        passed_tests: Сколько из них сдано

    Статус не зависит от is_opened: наставник закрывает пройденный этап, и
    раньше тот выглядел непройденным, хотя кнопки управления этапами в том же
    сообщении показывали «✅ Этап N завершен».
    """
    return bool(is_completed) or (total_tests > 0 and passed_tests == total_tests)


def latest_results_by_test(test_results) -> dict:
    """
    Последняя попытка по каждому тесту: {test_id: TestResult}.

    Выбирает по created_date, а не по порядку списка — перезапись словаря
    по списку из get_user_test_results() (DESC) оставляла самую старую попытку,
    и наставник видел проваленный тест, который стажёр уже пересдал.
    """
    latest = {}
    for result in test_results or []:
        current = latest.get(result.test_id)
        if current is None or result.created_date > current.created_date:
            latest[result.test_id] = result
    return latest


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
    test_num: int, test_name: str, icon: str, score: Optional[float] = None, max_score: Optional[float] = None
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
