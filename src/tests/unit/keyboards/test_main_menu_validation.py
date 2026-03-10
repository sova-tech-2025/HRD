"""Тесты для валидации текстов главного меню"""

from bot.keyboards.keyboards import MAIN_MENU_TEXTS, is_main_menu_text


class TestIsMainMenuText:
    """Тесты для функции is_main_menu_text"""

    def test_returns_true_for_trainee_menu_buttons(self):
        """Возвращает True для кнопок меню стажера"""
        assert is_main_menu_text("Мой профиль 🦸🏻‍♂️") is True
        assert is_main_menu_text("Траектория обучения 📖") is True
        assert is_main_menu_text("Мой наставник 🎓") is True
        assert is_main_menu_text("Мои тесты 📋") is True

    def test_returns_true_for_recruiter_menu_buttons(self):
        """Возвращает True для кнопок меню рекрутера"""
        assert is_main_menu_text("Наставники 🦉") is True
        assert is_main_menu_text("Стажеры 🐣") is True
        assert is_main_menu_text("Траектория 📖") is True
        assert is_main_menu_text("Компания 🏢") is True

    def test_returns_true_for_mentor_menu_buttons(self):
        """Возвращает True для кнопок меню наставника"""
        assert is_main_menu_text("Панель наставника 🎓") is True
        assert is_main_menu_text("☰ Главное меню") is True

    def test_returns_false_for_regular_text(self):
        """Возвращает False для обычного текста"""
        assert is_main_menu_text("https://example.com") is False
        assert is_main_menu_text("Привет") is False
        assert is_main_menu_text("Какой-то текст") is False

    def test_returns_false_for_similar_but_different_text(self):
        """Возвращает False для похожего, но отличающегося текста"""
        # Без эмодзи
        assert is_main_menu_text("Мой профиль") is False
        # С другим эмодзи
        assert is_main_menu_text("Мой профиль 👤") is False
        # Частичное совпадение
        assert is_main_menu_text("Мои тесты") is False

    def test_handles_whitespace(self):
        """Корректно обрабатывает пробелы"""
        assert is_main_menu_text("  Мой профиль 🦸🏻‍♂️  ") is True
        assert is_main_menu_text(" Мои тесты 📋 ") is True

    def test_main_menu_texts_is_set(self):
        """MAIN_MENU_TEXTS - это set для быстрого поиска"""
        assert isinstance(MAIN_MENU_TEXTS, set)
        assert len(MAIN_MENU_TEXTS) > 10  # Должно быть много кнопок
