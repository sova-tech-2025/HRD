"""Unit-тесты меню «Франчайзи», приоритета роли и набора прав провизионинга."""

from bot.keyboards.keyboards import (
    get_admin_role_picker_keyboard,
    get_franchisee_keyboard,
    get_keyboard_by_role,
    get_test_actions_keyboard,
    get_user_editor_keyboard,
)
from bot.repositories.role_provisioning import FRANCHISEE_PERMISSIONS, NEW_PERMISSIONS
from bot.utils.bot.roles import ROLE_PRIORITY, get_primary_role


def _reply_texts(markup) -> set[str]:
    return {btn.text for row in markup.keyboard for btn in row}


class TestFranchiseeKeyboard:
    def test_contains_expected_buttons(self):
        texts = _reply_texts(get_franchisee_keyboard())
        for expected in [
            "Мой профиль 🦸🏻‍♂️",
            "Рассылка ✈️",
            "Тесты 📄",
            "Мои тесты 📋",
            "Экзамены 📝",
            "Наставники 🦉",
            "Стажеры 🐣",
            "Траектория 📖",
            "База знаний 📁️",
            "Все пользователи 🚸",
            "Новые пользователи ➕",
        ]:
            assert expected in texts

    def test_excludes_content_management_buttons(self):
        texts = _reply_texts(get_franchisee_keyboard())
        for forbidden in ["Группы 🗂️", "Объекты 📍", "Компания 🏢"]:
            assert forbidden not in texts

    def test_test_card_allows_assign_but_not_delete(self):
        """Карточка теста для Франчайзи (роль 'mentor'): можно назначать доступ, нельзя удалять/редактировать."""
        markup = get_test_actions_keyboard(1, "mentor")
        texts = {btn.text for row in markup.inline_keyboard for btn in row}
        assert any("Предоставить доступ" in t for t in texts), texts
        assert not any("Удалить" in t for t in texts), texts
        assert not any("Редактировать" in t for t in texts), texts

    def test_get_keyboard_by_role_returns_franchisee_menu(self):
        texts = _reply_texts(get_keyboard_by_role("Франчайзи"))
        assert "Все пользователи 🚸" in texts
        assert "Группы 🗂️" not in texts

    def test_admin_picker_has_franchisee(self):
        markup = get_admin_role_picker_keyboard()
        callbacks = {btn.callback_data for row in markup.inline_keyboard for btn in row}
        assert "admin_role:Франчайзи" in callbacks


class TestUserEditorFranchiseeObjects:
    @staticmethod
    def _callbacks(markup):
        return {btn.callback_data for row in markup.inline_keyboard for btn in row}

    def test_franchisee_objects_button_shown_for_franchisee(self):
        markup = get_user_editor_keyboard(is_franchisee=True, franchisee_user_id=42)
        assert "franchisee_objects:42" in self._callbacks(markup)

    def test_no_franchisee_objects_button_for_regular_user(self):
        callbacks = self._callbacks(get_user_editor_keyboard())
        assert not any(str(cb).startswith("franchisee_objects:") for cb in callbacks)

    def test_editor_always_has_core_actions(self):
        callbacks = self._callbacks(get_user_editor_keyboard(is_franchisee=True, franchisee_user_id=1))
        assert "edit_work_object" in callbacks
        assert "delete_user" in callbacks


class TestRolePriority:
    def test_franchisee_priority(self):
        assert ROLE_PRIORITY["Франчайзи"] == 5
        assert ROLE_PRIORITY["Рекрутер"] > ROLE_PRIORITY["Франчайзи"]
        assert ROLE_PRIORITY["Франчайзи"] > ROLE_PRIORITY["Сотрудник"]

    def test_primary_role_picks_franchisee_over_employee(self):
        assert get_primary_role(["Сотрудник", "Франчайзи"]) == "Франчайзи"


class TestProvisioningPermissions:
    def test_franchisee_has_admin_scoped_permissions(self):
        for perm in ["manage_users", "manage_trainees", "assign_mentors", "view_test_results", "send_broadcast"]:
            assert perm in FRANCHISEE_PERMISSIONS

    def test_franchisee_can_interact_with_tests(self):
        for perm in ["view_tests", "take_tests", "grant_test_access"]:
            assert perm in FRANCHISEE_PERMISSIONS

    def test_franchisee_lacks_content_permissions(self):
        for perm in ["create_tests", "edit_tests", "manage_groups", "manage_objects", "manage_roles"]:
            assert perm not in FRANCHISEE_PERMISSIONS

    def test_new_permissions_declared(self):
        assert set(NEW_PERMISSIONS) == {"send_broadcast", "view_tests", "view_learning_paths"}
