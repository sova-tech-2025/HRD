"""Тесты фильтра «По ролям» в разделе рекрутера «Все пользователи»."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from bot.handlers.users import user_edit

MODULE = "bot.handlers.users.user_edit"


def make_role(role_id: int, name: str) -> MagicMock:
    role = MagicMock()
    role.id = role_id
    role.name = name
    return role


ALL_ROLES = [
    make_role(1, "ADMIN"),
    make_role(2, "Рекрутер"),
    make_role(3, "Наставник"),
    make_role(4, "Сотрудник"),
    make_role(5, "Стажер"),
]


def make_user(user_id: int, full_name: str = "Иванов Иван", company_id: int = 1) -> MagicMock:
    user = MagicMock()
    user.id = user_id
    user.full_name = full_name
    user.company_id = company_id
    user.roles = [make_role(3, "Наставник")]
    return user


def make_callback(data: str) -> MagicMock:
    callback = MagicMock()
    callback.data = data
    callback.from_user.id = 555
    callback.answer = AsyncMock()
    callback.message.edit_text = AsyncMock()
    callback.message.edit_reply_markup = AsyncMock()
    return callback


def make_state(data: dict | None = None) -> MagicMock:
    state = MagicMock()
    state.get_data = AsyncMock(return_value=data or {})
    state.set_state = AsyncMock()
    state.update_data = AsyncMock()
    return state


class TestRolesForFilter:
    @pytest.mark.asyncio
    async def test_admin_is_excluded(self):
        """ADMIN — служебная мульти-роль, в фильтре её быть не должно."""
        with patch(f"{MODULE}.get_all_roles", AsyncMock(return_value=ALL_ROLES)):
            roles = await user_edit._roles_for_filter(AsyncMock())

        names = [role.name for role in roles]
        assert "ADMIN" not in names
        assert names == ["Рекрутер", "Наставник", "Сотрудник", "Стажер"]

    @pytest.mark.asyncio
    async def test_role_name_by_id(self):
        with patch(f"{MODULE}.get_all_roles", AsyncMock(return_value=ALL_ROLES)):
            assert await user_edit._role_name_by_id(AsyncMock(), 3) == "Наставник"
            assert await user_edit._role_name_by_id(AsyncMock(), 999) == "Неизвестная"


class TestRoleFilterHandlers:
    @pytest.mark.asyncio
    async def test_filter_menu_shows_role_button(self):
        """Кнопка «Фильтр по ролям» появляется в меню фильтров."""
        callback = make_callback("uf_back")
        state = make_state()

        with (
            patch(f"{MODULE}.ensure_company_id", AsyncMock(return_value=1)),
            patch(f"{MODULE}.get_user_by_tg_id", AsyncMock(return_value=make_user(1))),
            patch(f"{MODULE}.get_scope_object_ids", AsyncMock(return_value=None)),
            patch(f"{MODULE}.get_all_groups", AsyncMock(return_value=[])),
            patch(f"{MODULE}.get_all_objects", AsyncMock(return_value=[])),
            patch(f"{MODULE}.get_all_roles", AsyncMock(return_value=ALL_ROLES)),
            patch(f"{MODULE}.ScopedUserRepository") as repo_cls,
        ):
            repo_cls.return_value.list_activated = AsyncMock(return_value=[])
            await user_edit.callback_back_to_filters(callback, state, AsyncMock())

        keyboard = callback.message.edit_text.call_args.kwargs["reply_markup"]
        callbacks = [button.callback_data for row in keyboard.inline_keyboard for button in row]
        assert "uf_roles" in callbacks

    @pytest.mark.asyncio
    async def test_role_list_shown_without_admin(self):
        """Нажатие «Фильтр по ролям» показывает список ролей без ADMIN."""
        callback = make_callback("uf_roles")
        state = make_state()

        with patch(f"{MODULE}.get_all_roles", AsyncMock(return_value=ALL_ROLES)):
            await user_edit.callback_filter_by_roles(callback, state, AsyncMock())

        keyboard = callback.message.edit_text.call_args.kwargs["reply_markup"]
        callbacks = [button.callback_data for row in keyboard.inline_keyboard for button in row]
        assert "uf_role:1" not in callbacks
        assert {"uf_role:2", "uf_role:3", "uf_role:4", "uf_role:5"} <= set(callbacks)

    @pytest.mark.asyncio
    async def test_selected_role_lists_users(self):
        """Выбор роли отдаёт scoped-список пользователей и запоминает фильтр."""
        callback = make_callback("uf_role:3")
        state = make_state()
        recruiter = make_user(1, company_id=7)
        users = [make_user(2, "Сидорова Мария", company_id=7)]
        list_by_role = AsyncMock(return_value=users)

        with (
            patch(f"{MODULE}.get_user_by_tg_id", AsyncMock(return_value=recruiter)),
            patch(f"{MODULE}.get_scope_object_ids", AsyncMock(return_value={11, 12})),
            patch(f"{MODULE}.get_all_roles", AsyncMock(return_value=ALL_ROLES)),
            patch(f"{MODULE}.ScopedUserRepository") as repo_cls,
        ):
            repo_cls.return_value.list_by_role = list_by_role
            await user_edit.callback_filter_role(callback, state, AsyncMock())

        list_by_role.assert_awaited_once_with(3, 7, {11, 12})
        assert "РОЛЬ: Наставник" in callback.message.edit_text.call_args[0][0]
        state.update_data.assert_awaited_once_with(current_users=users, filter_type="role:3", current_page=0)

        keyboard = callback.message.edit_text.call_args.kwargs["reply_markup"]
        assert keyboard.inline_keyboard[0][0].callback_data == "uf_user:2"
        assert keyboard.inline_keyboard[0][0].text == "👤 Сидорова Мария (Наставник)"

    @pytest.mark.asyncio
    async def test_empty_role_returns_to_filter_menu(self):
        """Роль без пользователей возвращает меню фильтров, а не пустой список."""
        callback = make_callback("uf_role:5")
        state = make_state()

        with (
            patch(f"{MODULE}.get_user_by_tg_id", AsyncMock(return_value=make_user(1))),
            patch(f"{MODULE}.get_scope_object_ids", AsyncMock(return_value=None)),
            patch(f"{MODULE}.get_all_roles", AsyncMock(return_value=ALL_ROLES)),
            patch(f"{MODULE}.ensure_company_id", AsyncMock(return_value=1)),
            patch(f"{MODULE}.get_all_groups", AsyncMock(return_value=[])),
            patch(f"{MODULE}.get_all_objects", AsyncMock(return_value=[])),
            patch(f"{MODULE}.ScopedUserRepository") as repo_cls,
        ):
            repo_cls.return_value.list_by_role = AsyncMock(return_value=[])
            await user_edit.callback_filter_role(callback, state, AsyncMock())

        assert "пока нет пользователей" in callback.message.edit_text.call_args[0][0]
        keyboard = callback.message.edit_text.call_args.kwargs["reply_markup"]
        callbacks = [button.callback_data for row in keyboard.inline_keyboard for button in row]
        assert "uf_roles" in callbacks

    @pytest.mark.asyncio
    async def test_pagination_keeps_role_header(self):
        """При листании списка заголовок остаётся ролевым."""
        callback = make_callback("uf_upage:1")
        state = make_state({"current_users": [make_user(2)], "filter_type": "role:3"})

        with patch(f"{MODULE}.get_all_roles", AsyncMock(return_value=ALL_ROLES)):
            await user_edit.callback_users_pagination(callback, state, AsyncMock())

        callback.message.edit_reply_markup.assert_awaited_once()
        state.update_data.assert_awaited_once_with(current_page=1)
