"""Unit-тесты клавиатуры выбора ролей для рассылки (включая роль «Франчайзи»)."""

from bot.keyboards.keyboards import BROADCAST_ROLE_NAMES, get_broadcast_roles_selection_keyboard


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
