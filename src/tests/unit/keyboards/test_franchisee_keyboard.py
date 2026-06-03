"""Unit-тесты меню «Франчайзи», приоритета роли и набора прав провизионинга."""

from bot.keyboards.keyboards import (
    get_admin_role_picker_keyboard,
    get_franchisee_keyboard,
    get_keyboard_by_role,
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
        for forbidden in ["Группы 🗂️", "Объекты 📍", "Мои тесты 📋", "Компания 🏢"]:
            assert forbidden not in texts

    def test_get_keyboard_by_role_returns_franchisee_menu(self):
        texts = _reply_texts(get_keyboard_by_role("Франчайзи"))
        assert "Все пользователи 🚸" in texts
        assert "Группы 🗂️" not in texts

    def test_admin_picker_has_franchisee(self):
        markup = get_admin_role_picker_keyboard()
        callbacks = {btn.callback_data for row in markup.inline_keyboard for btn in row}
        assert "admin_role:Франчайзи" in callbacks


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

    def test_franchisee_lacks_content_permissions(self):
        for perm in ["create_tests", "edit_tests", "manage_groups", "manage_objects", "manage_roles", "take_tests"]:
            assert perm not in FRANCHISEE_PERMISSIONS

    def test_new_permissions_declared(self):
        assert set(NEW_PERMISSIONS) == {"send_broadcast", "view_tests", "view_learning_paths"}
