"""Unit-тесты клавиатур рассылки: выбор ролей и поимённый выбор сотрудников."""

from bot.keyboards.keyboards import (
    BROADCAST_ROLE_NAMES,
    get_broadcast_employees_keyboard,
    get_broadcast_roles_selection_keyboard,
)


def _buttons(markup):
    return [(btn.text, btn.callback_data) for row in markup.inline_keyboard for btn in row]


class TestBroadcastRolesKeyboard:
    def test_franchisee_in_role_names(self):
        assert BROADCAST_ROLE_NAMES.get("franchisee") == "Франчайзи"

    def test_keyboard_has_franchisee_button(self):
        buttons = _buttons(get_broadcast_roles_selection_keyboard())
        franchisee = [b for b in buttons if b[1] == "broadcast_role:franchisee"]
        assert franchisee, f"Нет кнопки выбора роли Франчайзи: {buttons}"
        assert "Франчайзи" in franchisee[0][0]

    def test_all_known_roles_present(self):
        callbacks = {cb for _, cb in _buttons(get_broadcast_roles_selection_keyboard())}
        for key in BROADCAST_ROLE_NAMES:
            assert f"broadcast_role:{key}" in callbacks

    def test_all_roles_selected_shows_unselect(self):
        markup = get_broadcast_roles_selection_keyboard(list(BROADCAST_ROLE_NAMES))
        texts = [t for t, _ in _buttons(markup)]
        assert any("Снять все" in t for t in texts), texts

    def test_has_select_employee_button(self):
        callbacks = {cb for _, cb in _buttons(get_broadcast_roles_selection_keyboard())}
        assert "broadcast_select_employee" in callbacks


class TestBroadcastEmployeesKeyboard:
    CANDIDATES = [{"id": 1, "name": "Иванов Иван"}, {"id": 2, "name": "Петров Пётр"}]

    def test_renders_toggle_buttons(self):
        callbacks = {cb for _, cb in _buttons(get_broadcast_employees_keyboard(self.CANDIDATES, []))}
        assert "bc_emp_toggle:1" in callbacks
        assert "bc_emp_toggle:2" in callbacks

    def test_checkmark_for_selected(self):
        buttons = _buttons(get_broadcast_employees_keyboard(self.CANDIDATES, [1]))
        ivan = [t for t, cb in buttons if cb == "bc_emp_toggle:1"][0]
        petr = [t for t, cb in buttons if cb == "bc_emp_toggle:2"][0]
        assert ivan.startswith("✅"), ivan
        assert not petr.startswith("✅"), petr

    def test_search_button_present(self):
        callbacks = {cb for _, cb in _buttons(get_broadcast_employees_keyboard(self.CANDIDATES, []))}
        assert "bc_emp_search" in callbacks

    def test_next_button_only_when_selected(self):
        none_selected = {cb for _, cb in _buttons(get_broadcast_employees_keyboard(self.CANDIDATES, []))}
        assert "bc_emp_next" not in none_selected
        with_selected = {cb for _, cb in _buttons(get_broadcast_employees_keyboard(self.CANDIDATES, [2]))}
        assert "bc_emp_next" in with_selected
