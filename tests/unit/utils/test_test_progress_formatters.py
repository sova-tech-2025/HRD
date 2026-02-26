"""Тесты для модуля форматирования прогресса тестов"""
import pytest
from utils.test_progress_formatters import (
    get_test_status_icon,
    format_test_line,
    format_test_with_percentage,
)


class TestGetTestStatusIcon:
    """Тесты для функции определения иконки статуса теста"""

    def test_passed_and_stage_open_returns_checkmark(self):
        """Если тест пройден и этап открыт - зелёная галочка"""
        icon = get_test_status_icon(is_passed=True, is_stage_opened=True)
        assert icon == "✅"

    def test_passed_but_stage_closed_returns_closed(self):
        """Если тест пройден, но этап закрыт - закрытый"""
        icon = get_test_status_icon(is_passed=True, is_stage_opened=False)
        assert icon == "⛔️"

    def test_not_passed_stage_open_returns_available(self):
        """Если тест не пройден и этап открыт - доступен"""
        icon = get_test_status_icon(is_passed=False, is_stage_opened=True)
        assert icon == "🟡"

    def test_not_passed_stage_closed_returns_closed(self):
        """Если тест не пройден и этап закрыт - закрытый"""
        icon = get_test_status_icon(is_passed=False, is_stage_opened=False)
        assert icon == "⛔️"


class TestFormatTestLine:
    """Тесты для форматирования строки теста"""

    def test_formats_basic_line(self):
        """Базовое форматирование строки теста"""
        line = format_test_line(test_num=1, test_name="Основы Python", icon="✅")
        assert line == "✅<b>Тест 1:</b> Основы Python\n"

    def test_formats_with_custom_icon(self):
        """Форматирование с кастомной иконкой"""
        line = format_test_line(test_num=2, test_name="SQL запросы", icon="🟡")
        assert line == "🟡<b>Тест 2:</b> SQL запросы\n"


class TestFormatTestWithPercentage:
    """Тесты для форматирования теста с процентами"""

    def test_formats_with_percentage(self):
        """Форматирование с процентами для пройденного теста"""
        line = format_test_with_percentage(
            test_num=1,
            test_name="Основы Python",
            icon="✅",
            score=85.0,
            max_score=100.0
        )
        assert line == "✅<b>Тест 1:</b> Основы Python - 85%\n"

    def test_formats_without_percentage_when_not_passed(self):
        """Форматирование без процентов для непройденного теста"""
        line = format_test_with_percentage(
            test_num=2,
            test_name="SQL запросы",
            icon="🟡",
            score=None,
            max_score=None
        )
        assert line == "🟡<b>Тест 2:</b> SQL запросы\n"

    def test_rounds_percentage(self):
        """Проценты округляются до целых"""
        line = format_test_with_percentage(
            test_num=1,
            test_name="Тест",
            icon="✅",
            score=78.6,
            max_score=100.0
        )
        assert line == "✅<b>Тест 1:</b> Тест - 79%\n"
