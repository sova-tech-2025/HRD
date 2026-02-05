"""Тесты для клавиатуры мультивыбора групп пользователя"""
import pytest
from dataclasses import dataclass
from keyboards.keyboards import get_user_groups_multiselect_keyboard


@dataclass
class MockGroup:
    """Мок для модели Group"""
    id: int
    name: str


class TestGetUserGroupsMultiselectKeyboard:
    """Тесты для функции get_user_groups_multiselect_keyboard"""

    def test_selected_group_has_checkmark_prefix(self):
        """Выбранная группа имеет префикс с галочкой"""
        groups = [
            MockGroup(id=1, name="Кухня"),
            MockGroup(id=2, name="Зал"),
        ]
        selected_ids = [1]  # Первая группа выбрана

        keyboard = get_user_groups_multiselect_keyboard(groups, selected_ids)

        buttons = keyboard.inline_keyboard
        # Первая кнопка (выбранная группа) должна иметь галочку
        assert buttons[0][0].text.startswith("✅")
        # Вторая кнопка (невыбранная) не должна иметь галочку
        assert not buttons[1][0].text.startswith("✅")

    def test_callback_data_uses_user_edit_namespace(self):
        """callback_data использует namespace user_edit_, а не kb_*"""
        groups = [MockGroup(id=1, name="Кухня")]
        selected_ids = []

        keyboard = get_user_groups_multiselect_keyboard(groups, selected_ids)

        buttons = keyboard.inline_keyboard
        # Кнопка группы должна использовать правильный callback
        assert buttons[0][0].callback_data == "user_edit_toggle_group:1"
        # Не должно быть старого формата kb_*
        assert not buttons[0][0].callback_data.startswith("kb_")

    def test_save_button_shown_when_selection_not_empty(self):
        """Кнопка 'Сохранить' показывается только при непустом выборе"""
        groups = [MockGroup(id=1, name="Кухня")]
        selected_ids = [1]

        keyboard = get_user_groups_multiselect_keyboard(groups, selected_ids)

        # Ищем кнопку Сохранить
        all_buttons = [btn for row in keyboard.inline_keyboard for btn in row]
        save_buttons = [btn for btn in all_buttons if btn.callback_data == "user_edit_save_groups"]
        assert len(save_buttons) == 1

    def test_save_button_hidden_when_selection_empty(self):
        """Кнопка 'Сохранить' скрыта при пустом выборе"""
        groups = [MockGroup(id=1, name="Кухня")]
        selected_ids = []

        keyboard = get_user_groups_multiselect_keyboard(groups, selected_ids)

        # Ищем кнопку Сохранить
        all_buttons = [btn for row in keyboard.inline_keyboard for btn in row]
        save_buttons = [btn for btn in all_buttons if btn.callback_data == "user_edit_save_groups"]
        assert len(save_buttons) == 0

    def test_back_button_exists(self):
        """Кнопка 'Назад' присутствует"""
        groups = [MockGroup(id=1, name="Кухня")]
        selected_ids = []

        keyboard = get_user_groups_multiselect_keyboard(groups, selected_ids)

        all_buttons = [btn for row in keyboard.inline_keyboard for btn in row]
        back_buttons = [btn for btn in all_buttons if btn.callback_data == "cancel_edit"]
        assert len(back_buttons) == 1

    def test_main_menu_button_exists(self):
        """Кнопка 'Главное меню' присутствует"""
        groups = [MockGroup(id=1, name="Кухня")]
        selected_ids = []

        keyboard = get_user_groups_multiselect_keyboard(groups, selected_ids)

        all_buttons = [btn for row in keyboard.inline_keyboard for btn in row]
        menu_buttons = [btn for btn in all_buttons if btn.callback_data == "main_menu"]
        assert len(menu_buttons) == 1

    def test_pagination_shows_next_page_button(self):
        """При наличии следующей страницы показывается кнопка навигации"""
        groups = [MockGroup(id=i, name=f"Группа {i}") for i in range(1, 8)]  # 7 групп
        selected_ids = []

        keyboard = get_user_groups_multiselect_keyboard(groups, selected_ids, page=0, per_page=5)

        all_buttons = [btn for row in keyboard.inline_keyboard for btn in row]
        next_buttons = [btn for btn in all_buttons if btn.callback_data == "user_edit_groups_page:1"]
        assert len(next_buttons) == 1

    def test_pagination_shows_prev_page_button(self):
        """На второй странице показывается кнопка возврата"""
        groups = [MockGroup(id=i, name=f"Группа {i}") for i in range(1, 8)]  # 7 групп
        selected_ids = []

        keyboard = get_user_groups_multiselect_keyboard(groups, selected_ids, page=1, per_page=5)

        all_buttons = [btn for row in keyboard.inline_keyboard for btn in row]
        prev_buttons = [btn for btn in all_buttons if btn.callback_data == "user_edit_groups_page:0"]
        assert len(prev_buttons) == 1

    def test_only_current_page_groups_shown(self):
        """Показываются только группы текущей страницы"""
        groups = [MockGroup(id=i, name=f"Группа {i}") for i in range(1, 8)]  # 7 групп
        selected_ids = []

        keyboard = get_user_groups_multiselect_keyboard(groups, selected_ids, page=0, per_page=5)

        # На первой странице должно быть 5 кнопок групп
        group_buttons = [
            btn for row in keyboard.inline_keyboard for btn in row
            if btn.callback_data.startswith("user_edit_toggle_group:")
        ]
        assert len(group_buttons) == 5

    def test_long_group_name_truncated(self):
        """Длинные названия групп обрезаются"""
        groups = [MockGroup(id=1, name="Очень длинное название группы которое не поместится")]
        selected_ids = []

        keyboard = get_user_groups_multiselect_keyboard(groups, selected_ids)

        buttons = keyboard.inline_keyboard
        # Название должно быть обрезано (макс 20 символов + "...")
        assert len(buttons[0][0].text) <= 30  # С учетом скобок и ...
