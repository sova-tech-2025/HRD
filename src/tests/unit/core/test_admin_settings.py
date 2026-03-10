"""Тесты для get_admin_settings и validate_admin_token с config."""

from unittest.mock import AsyncMock, patch

import pytest

DB_MODULE = "bot.database.db"
REG_MODULE = "bot.handlers.core.registration"


class TestGetAdminSettings:
    @pytest.mark.asyncio
    async def test_returns_config_values(self):
        """get_admin_settings возвращает значения из config"""
        from bot.handlers.core.registration import get_admin_settings

        with (
            patch(f"{REG_MODULE}.config.MAX_ADMINS", 10),
            patch(f"{REG_MODULE}.config.ADMIN_INIT_TOKENS", "token1,token2"),
        ):
            max_admins, tokens = await get_admin_settings()

        assert max_admins == 10
        assert tokens == "token1,token2"

    @pytest.mark.asyncio
    async def test_returns_defaults(self):
        """get_admin_settings с дефолтными значениями"""
        from bot.handlers.core.registration import get_admin_settings

        with (
            patch(f"{REG_MODULE}.config.MAX_ADMINS", 5),
            patch(f"{REG_MODULE}.config.ADMIN_INIT_TOKENS", ""),
        ):
            max_admins, tokens = await get_admin_settings()

        assert max_admins == 5
        assert tokens == ""


class TestValidateAdminToken:
    @pytest.mark.asyncio
    async def test_no_tokens_configured(self):
        """Нет настроенных токенов — возвращает False"""
        from bot.database.db import validate_admin_token

        session = AsyncMock()

        with patch(f"{DB_MODULE}.config.ADMIN_INIT_TOKENS", ""):
            result = await validate_admin_token(session, "any_token")

        assert result is False

    @pytest.mark.asyncio
    async def test_invalid_token(self):
        """Неверный токен — возвращает False"""
        from bot.database.db import validate_admin_token

        session = AsyncMock()

        with (
            patch(f"{DB_MODULE}.config.ADMIN_INIT_TOKENS", "valid_token"),
            patch(f"{DB_MODULE}.config.MAX_ADMINS", 5),
        ):
            result = await validate_admin_token(session, "wrong_token")

        assert result is False

    @pytest.mark.asyncio
    async def test_valid_single_token(self):
        """Валидный единственный токен — возвращает True"""
        from bot.database.db import validate_admin_token

        session = AsyncMock()

        with (
            patch(f"{DB_MODULE}.config.ADMIN_INIT_TOKENS", "valid_token"),
            patch(f"{DB_MODULE}.config.MAX_ADMINS", 5),
            patch(f"{DB_MODULE}.get_users_by_role", return_value=[]),
        ):
            result = await validate_admin_token(session, "valid_token")

        assert result is True

    @pytest.mark.asyncio
    async def test_valid_token_from_multiple(self):
        """Один из нескольких валидных токенов — возвращает True"""
        from bot.database.db import validate_admin_token

        session = AsyncMock()

        with (
            patch(f"{DB_MODULE}.config.ADMIN_INIT_TOKENS", "token1,token2,token3"),
            patch(f"{DB_MODULE}.config.MAX_ADMINS", 5),
            patch(f"{DB_MODULE}.get_users_by_role", return_value=[]),
        ):
            result = await validate_admin_token(session, "token2")

        assert result is True

    @pytest.mark.asyncio
    async def test_admin_limit_reached(self):
        """Лимит администраторов достигнут — возвращает False"""
        from bot.database.db import validate_admin_token

        session = AsyncMock()
        fake_users = [object() for _ in range(3)]

        with (
            patch(f"{DB_MODULE}.config.ADMIN_INIT_TOKENS", "valid_token"),
            patch(f"{DB_MODULE}.config.MAX_ADMINS", 5),
            patch(f"{DB_MODULE}.get_users_by_role", side_effect=[fake_users, fake_users[:2]]),
        ):
            result = await validate_admin_token(session, "valid_token")

        assert result is False

    @pytest.mark.asyncio
    async def test_admin_limit_not_reached(self):
        """Лимит не достигнут — возвращает True"""
        from bot.database.db import validate_admin_token

        session = AsyncMock()

        with (
            patch(f"{DB_MODULE}.config.ADMIN_INIT_TOKENS", "valid_token"),
            patch(f"{DB_MODULE}.config.MAX_ADMINS", 5),
            patch(f"{DB_MODULE}.get_users_by_role", side_effect=[[], []]),
        ):
            result = await validate_admin_token(session, "valid_token")

        assert result is True

    @pytest.mark.asyncio
    async def test_token_with_spaces_trimmed(self):
        """Токены с пробелами корректно обрабатываются"""
        from bot.database.db import validate_admin_token

        session = AsyncMock()

        with (
            patch(f"{DB_MODULE}.config.ADMIN_INIT_TOKENS", " token1 , token2 "),
            patch(f"{DB_MODULE}.config.MAX_ADMINS", 5),
            patch(f"{DB_MODULE}.get_users_by_role", return_value=[]),
        ):
            result = await validate_admin_token(session, "token2")

        assert result is True
