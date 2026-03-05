"""Тесты validate_user_access из utils/auth/auth.py"""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

AUTH_MODULE = "utils.auth.auth"


def make_user(is_active=True, company_id=10, user_id=1):
    user = MagicMock()
    user.id = user_id
    user.is_active = is_active
    user.company_id = company_id
    return user


def make_company(subscribe=True, finish_date=None):
    company = MagicMock()
    company.subscribe = subscribe
    company.finish_date = finish_date
    return company


class FakeRole:
    def __init__(self, name):
        self.name = name


class TestValidateUserAccess:
    @pytest.mark.asyncio
    async def test_inactive_user(self):
        from utils.auth.auth import validate_user_access

        session = AsyncMock()
        user = make_user(is_active=False)

        ok, err, role = await validate_user_access(session, user)

        assert ok is False
        assert "деактивирован" in err
        assert role is None

    @pytest.mark.asyncio
    async def test_no_company(self):
        from utils.auth.auth import validate_user_access

        session = AsyncMock()
        user = make_user(company_id=None)

        ok, err, role = await validate_user_access(session, user)

        assert ok is False
        assert "не привязан" in err
        assert role is None

    @pytest.mark.asyncio
    async def test_subscription_inactive(self):
        from utils.auth.auth import validate_user_access

        session = AsyncMock()
        user = make_user()
        company = make_company(subscribe=False)

        with patch(f"{AUTH_MODULE}.get_company_by_id", return_value=company):
            ok, err, role = await validate_user_access(session, user)

        assert ok is False
        assert "истекла" in err
        assert role is None

    @pytest.mark.asyncio
    async def test_subscription_expired_by_date(self):
        from utils.auth.auth import validate_user_access

        session = AsyncMock()
        user = make_user()
        company = make_company(subscribe=True, finish_date=datetime(2020, 1, 1))

        with (
            patch(f"{AUTH_MODULE}.get_company_by_id", return_value=company),
            patch(f"{AUTH_MODULE}.moscow_now", return_value=datetime(2026, 3, 5)),
        ):
            ok, err, role = await validate_user_access(session, user)

        assert ok is False
        assert "истекла" in err
        assert role is None

    @pytest.mark.asyncio
    async def test_no_roles(self):
        from utils.auth.auth import validate_user_access

        session = AsyncMock()
        user = make_user()
        company = make_company()

        with (
            patch(f"{AUTH_MODULE}.get_company_by_id", return_value=company),
            patch(f"{AUTH_MODULE}.get_user_roles", return_value=[]),
        ):
            ok, err, role = await validate_user_access(session, user)

        assert ok is False
        assert "нет назначенных ролей" in err
        assert role is None

    @pytest.mark.asyncio
    async def test_valid_user(self):
        from utils.auth.auth import validate_user_access

        session = AsyncMock()
        user = make_user()
        company = make_company(subscribe=True, finish_date=None)
        roles = [FakeRole("Рекрутер")]

        with (
            patch(f"{AUTH_MODULE}.get_company_by_id", return_value=company),
            patch(f"{AUTH_MODULE}.get_user_roles", return_value=roles),
        ):
            ok, err, role = await validate_user_access(session, user)

        assert ok is True
        assert err is None
        assert role == "Рекрутер"

    @pytest.mark.asyncio
    async def test_valid_user_with_future_finish_date(self):
        from utils.auth.auth import validate_user_access

        session = AsyncMock()
        user = make_user()
        company = make_company(subscribe=True, finish_date=datetime(2030, 1, 1))
        roles = [FakeRole("Стажер")]

        with (
            patch(f"{AUTH_MODULE}.get_company_by_id", return_value=company),
            patch(f"{AUTH_MODULE}.moscow_now", return_value=datetime(2026, 3, 5)),
            patch(f"{AUTH_MODULE}.get_user_roles", return_value=roles),
        ):
            ok, err, role = await validate_user_access(session, user)

        assert ok is True
        assert err is None
        assert role == "Стажер"

    @pytest.mark.asyncio
    async def test_company_not_found_passes(self):
        """Если компания не найдена в БД — проверки subscribe/finish_date пропускаются."""
        from utils.auth.auth import validate_user_access

        session = AsyncMock()
        user = make_user()
        roles = [FakeRole("Наставник")]

        with (
            patch(f"{AUTH_MODULE}.get_company_by_id", return_value=None),
            patch(f"{AUTH_MODULE}.get_user_roles", return_value=roles),
        ):
            ok, err, role = await validate_user_access(session, user)

        assert ok is True
        assert err is None
        assert role == "Наставник"

    @pytest.mark.asyncio
    async def test_returns_primary_role_name(self):
        """Возвращает имя первой (основной) роли."""
        from utils.auth.auth import validate_user_access

        session = AsyncMock()
        user = make_user()
        company = make_company()
        roles = [FakeRole("Наставник"), FakeRole("Стажер")]

        with (
            patch(f"{AUTH_MODULE}.get_company_by_id", return_value=company),
            patch(f"{AUTH_MODULE}.get_user_roles", return_value=roles),
        ):
            ok, err, role = await validate_user_access(session, user)

        assert ok is True
        assert role == "Наставник"
