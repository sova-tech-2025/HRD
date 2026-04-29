"""Регрессионные тесты на проверку роли в `callback_exam_create`.

Баг: ADMIN с активной ролью «Рекрутер» (через FSM `is_admin=True`/`role="Рекрутер"`)
получал отказ «❌ Только рекрутер может создавать экзамены», потому что проверка
шла только по физическим `user.roles`, без учёта FSM-роли.

Сравни с уже корректным паттерном в `show_exam_menu`/`cmd_exams`/`callback_exam_view`:
    active_role = data.get("role") if data.get("is_admin") else None
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _make_callback():
    callback = AsyncMock()
    callback.from_user = MagicMock()
    callback.from_user.id = 123
    callback.data = "exam_create"
    callback.message = AsyncMock()
    callback.message.edit_text = AsyncMock()
    callback.answer = AsyncMock()
    return callback


def _make_state(data):
    state = AsyncMock()
    state.get_data = AsyncMock(return_value=data)
    state.set_state = AsyncMock()
    state.update_data = AsyncMock()
    return state


def _make_user(role_names):
    """Пользователь с указанным набором физических ролей в БД."""
    user = MagicMock()
    user.id = 1
    user.tg_id = 123
    user.full_name = "Test User"
    user.roles = [MagicMock(name=name) for name in role_names]
    # MagicMock(name=...) задаёт repr, но не атрибут .name → выставим вручную
    for r, name in zip(user.roles, role_names):
        r.name = name
    return user


ERROR_TEXT = "❌ Только рекрутер может создавать экзамены."


class TestExamCreateRoleCheck:
    """Доступ к созданию экзамена должен учитывать FSM-роль ADMIN."""

    @pytest.mark.asyncio
    async def test_admin_with_active_recruiter_role_can_create_exam(self):
        """РЕГРЕССИЯ: ADMIN с active_role='Рекрутер' получал отказ из-за проверки
        по `user.roles` без учёта FSM. Теперь должен пройти к созданию экзамена.
        """
        from bot.handlers.exams.exam_menu import callback_exam_create

        callback = _make_callback()
        state = _make_state({"is_admin": True, "role": "Рекрутер"})
        session = AsyncMock()
        user = _make_user(["ADMIN"])  # никакой «Рекрутер» в БД

        with patch("bot.handlers.exams.exam_menu.get_user_by_tg_id", return_value=user):
            await callback_exam_create(callback, state, session)

        text = callback.message.edit_text.call_args[0][0]
        assert ERROR_TEXT not in text, f"ADMIN с активной ролью «Рекрутер» не должен получать отказ. Получено: {text!r}"
        # Должна стартовать FSM-цепочка ввода названия
        state.set_state.assert_called_once()

    @pytest.mark.asyncio
    async def test_admin_with_active_mentor_role_cannot_create_exam(self):
        """ADMIN с активной ролью «Наставник» — НЕ может создавать экзамены."""
        from bot.handlers.exams.exam_menu import callback_exam_create

        callback = _make_callback()
        state = _make_state({"is_admin": True, "role": "Наставник"})
        session = AsyncMock()
        user = _make_user(["ADMIN"])

        with patch("bot.handlers.exams.exam_menu.get_user_by_tg_id", return_value=user):
            await callback_exam_create(callback, state, session)

        text = callback.message.edit_text.call_args[0][0]
        assert ERROR_TEXT in text
        state.set_state.assert_not_called()

    @pytest.mark.asyncio
    async def test_regular_recruiter_can_create_exam(self):
        """Обычный пользователь с физической ролью «Рекрутер» (без is_admin) — может."""
        from bot.handlers.exams.exam_menu import callback_exam_create

        callback = _make_callback()
        state = _make_state({})  # нет is_admin/role в FSM
        session = AsyncMock()
        user = _make_user(["Рекрутер"])

        with patch("bot.handlers.exams.exam_menu.get_user_by_tg_id", return_value=user):
            await callback_exam_create(callback, state, session)

        text = callback.message.edit_text.call_args[0][0]
        assert ERROR_TEXT not in text
        state.set_state.assert_called_once()

    @pytest.mark.asyncio
    async def test_regular_mentor_cannot_create_exam(self):
        """Обычный наставник без admin-роли — отказ."""
        from bot.handlers.exams.exam_menu import callback_exam_create

        callback = _make_callback()
        state = _make_state({})
        session = AsyncMock()
        user = _make_user(["Наставник"])

        with patch("bot.handlers.exams.exam_menu.get_user_by_tg_id", return_value=user):
            await callback_exam_create(callback, state, session)

        text = callback.message.edit_text.call_args[0][0]
        assert ERROR_TEXT in text
        state.set_state.assert_not_called()

    @pytest.mark.asyncio
    async def test_unregistered_user_cannot_create_exam(self):
        """`get_user_by_tg_id` вернул None — отказ."""
        from bot.handlers.exams.exam_menu import callback_exam_create

        callback = _make_callback()
        state = _make_state({})
        session = AsyncMock()

        with patch("bot.handlers.exams.exam_menu.get_user_by_tg_id", return_value=None):
            await callback_exam_create(callback, state, session)

        text = callback.message.edit_text.call_args[0][0]
        assert ERROR_TEXT in text
        state.set_state.assert_not_called()
