"""Тесты callback-хэндлеров из handlers/core/common.py"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def make_callback(user_id=123, username="testuser"):
    """Создаёт мок CallbackQuery."""
    callback = AsyncMock()
    callback.from_user = MagicMock()
    callback.from_user.id = user_id
    callback.from_user.username = username
    callback.message = AsyncMock()
    callback.answer = AsyncMock()
    return callback


def make_user(user_id=1, is_active=True):
    """Создаёт мок пользователя."""
    user = MagicMock()
    user.id = user_id
    user.is_active = is_active
    return user


class FakeRole:
    def __init__(self, name):
        self.name = name


# --- callback_trainee_profile ---


class TestCallbackTraineeProfile:
    @pytest.mark.asyncio
    async def test_inactive_user_blocked(self):
        """Деактивированный пользователь не может открыть профиль"""
        from bot.handlers.core.common import callback_trainee_profile

        callback = make_callback()
        user = make_user(is_active=False)
        session = AsyncMock()

        with patch("bot.handlers.core.common.get_validated_user", return_value=None) as mock_validate:
            await callback_trainee_profile(callback, session)

        mock_validate.assert_awaited_once_with(session, callback)
        callback.message.answer.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_user_not_found_blocked(self):
        """Несуществующий пользователь не может открыть профиль"""
        from bot.handlers.core.common import callback_trainee_profile

        callback = make_callback()
        session = AsyncMock()

        with patch("bot.handlers.core.common.get_validated_user", return_value=None):
            await callback_trainee_profile(callback, session)

        callback.message.answer.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_valid_user_sees_profile(self):
        """Активный пользователь получает текст профиля"""
        from bot.handlers.core.common import callback_trainee_profile

        callback = make_callback()
        user = make_user()
        session = AsyncMock()

        with (
            patch("bot.handlers.core.common.get_validated_user", return_value=user),
            patch("bot.handlers.core.common.format_profile_text", return_value="<b>Профиль</b>") as mock_fmt,
        ):
            await callback_trainee_profile(callback, session)

        mock_fmt.assert_awaited_once_with(user, session)
        callback.message.answer.assert_awaited_once()
        call_kwargs = callback.message.answer.call_args
        assert (
            "<b>Профиль</b>" in call_kwargs.args
            or call_kwargs.kwargs.get("text") == "<b>Профиль</b>"
            or "<b>Профиль</b>" == call_kwargs[0][0]
        )


# --- callback_trainee_help ---


class TestCallbackTraineeHelp:
    @pytest.mark.asyncio
    async def test_inactive_user_blocked(self):
        """Деактивированный пользователь не может открыть помощь"""
        from bot.handlers.core.common import callback_trainee_help

        callback = make_callback()
        session = AsyncMock()

        with patch("bot.handlers.core.common.get_validated_user", return_value=None):
            await callback_trainee_help(callback, session)

        callback.message.answer.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_user_not_found_blocked(self):
        """Несуществующий пользователь не может открыть помощь"""
        from bot.handlers.core.common import callback_trainee_help

        callback = make_callback()
        session = AsyncMock()

        with patch("bot.handlers.core.common.get_validated_user", return_value=None):
            await callback_trainee_help(callback, session)

        callback.message.answer.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_valid_user_sees_help(self):
        """Активный пользователь получает текст помощи"""
        from bot.handlers.core.common import callback_trainee_help

        callback = make_callback()
        user = make_user()
        session = AsyncMock()
        roles = [FakeRole("Стажер")]

        with (
            patch("bot.handlers.core.common.get_validated_user", return_value=user),
            patch("bot.handlers.core.common.get_user_roles", return_value=roles),
            patch("bot.handlers.core.common.format_help_message", return_value="Справка") as mock_help,
        ):
            await callback_trainee_help(callback, session)

        mock_help.assert_called_once()
        callback.message.answer.assert_awaited_once()
