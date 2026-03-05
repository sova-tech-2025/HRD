"""Тесты check_auth из handlers/core/auth.py"""

import time
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def make_message(user_id=123, username="testuser"):
    """Создаёт мок Message."""
    msg = AsyncMock()
    msg.from_user = MagicMock()
    msg.from_user.id = user_id
    msg.from_user.username = username
    msg.date = MagicMock()
    msg.date.timestamp.return_value = time.time()
    msg.answer = AsyncMock()
    return msg


def make_state(data=None):
    """Создаёт мок FSMContext."""
    state = AsyncMock()
    state.get_data = AsyncMock(return_value=data or {})
    state.clear = AsyncMock()
    state.update_data = AsyncMock()
    return state


def make_user(user_id=1, is_active=True, company_id=10):
    """Создаёт мок пользователя."""
    user = MagicMock()
    user.id = user_id
    user.is_active = is_active
    user.company_id = company_id
    return user


def make_company(subscribe=True, finish_date=None):
    """Создаёт мок компании."""
    company = MagicMock()
    company.subscribe = subscribe
    company.finish_date = finish_date
    return company


class FakeRole:
    def __init__(self, name):
        self.name = name


AUTH_MODULE = "utils.auth.auth"


# --- Ветка: уже аутентифицирован ---


class TestCheckAuthAuthenticated:
    @pytest.mark.asyncio
    async def test_expired_session_clears_state(self):
        """Сессия старше 24ч — state.clear() и возврат False"""
        from utils.auth.auth import check_auth

        expired_time = time.time() - 90000  # > 86400
        msg = make_message()
        state = make_state({"is_authenticated": True, "auth_time": expired_time})
        session = AsyncMock()

        result = await check_auth(msg, state, session)

        assert result is False
        state.clear.assert_awaited_once()
        msg.answer.assert_awaited_once()
        assert "сессия завершена" in msg.answer.call_args[0][0]

    @pytest.mark.asyncio
    async def test_authenticated_user_not_found_clears_state(self):
        """Аутентифицирован, но пользователь не найден в БД"""
        from utils.auth.auth import check_auth

        msg = make_message()
        state = make_state({"is_authenticated": True, "auth_time": time.time()})
        session = AsyncMock()

        with (
            patch(f"{AUTH_MODULE}.get_user_by_tg_id", return_value=None),
            patch(f"{AUTH_MODULE}.get_user_by_id", return_value=None),
        ):
            result = await check_auth(msg, state, session)

        assert result is False
        state.clear.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_authenticated_inactive_user_blocked(self):
        """Аутентифицирован, но пользователь деактивирован"""
        from utils.auth.auth import check_auth

        msg = make_message()
        state = make_state({"is_authenticated": True, "auth_time": time.time()})
        session = AsyncMock()
        user = make_user(is_active=False)

        with patch(f"{AUTH_MODULE}.get_user_by_tg_id", return_value=user):
            result = await check_auth(msg, state, session)

        assert result is False
        state.clear.assert_awaited_once()
        assert "деактивирован" in msg.answer.call_args[0][0]

    @pytest.mark.asyncio
    async def test_authenticated_no_company_blocked(self):
        """Аутентифицирован, но нет company_id"""
        from utils.auth.auth import check_auth

        msg = make_message()
        state = make_state({"is_authenticated": True, "auth_time": time.time()})
        session = AsyncMock()
        user = make_user(company_id=None)

        with patch(f"{AUTH_MODULE}.get_user_by_tg_id", return_value=user):
            result = await check_auth(msg, state, session)

        assert result is False
        state.clear.assert_awaited_once()
        assert "не привязан" in msg.answer.call_args[0][0]

    @pytest.mark.asyncio
    async def test_authenticated_subscription_inactive(self):
        """Аутентифицирован, подписка компании заморожена"""
        from utils.auth.auth import check_auth

        msg = make_message()
        state = make_state({"is_authenticated": True, "auth_time": time.time()})
        session = AsyncMock()
        user = make_user()
        company = make_company(subscribe=False)

        with (
            patch(f"{AUTH_MODULE}.get_user_by_tg_id", return_value=user),
            patch(f"{AUTH_MODULE}.get_company_by_id", return_value=company),
        ):
            result = await check_auth(msg, state, session)

        assert result is False
        state.clear.assert_awaited_once()
        assert "истекла" in msg.answer.call_args[0][0]

    @pytest.mark.asyncio
    async def test_authenticated_subscription_expired_by_date(self):
        """Аутентифицирован, finish_date в прошлом"""
        from utils.auth.auth import check_auth

        msg = make_message()
        state = make_state({"is_authenticated": True, "auth_time": time.time()})
        session = AsyncMock()
        user = make_user()
        past_date = datetime(2020, 1, 1)
        company = make_company(subscribe=True, finish_date=past_date)

        with (
            patch(f"{AUTH_MODULE}.get_user_by_tg_id", return_value=user),
            patch(f"{AUTH_MODULE}.get_company_by_id", return_value=company),
            patch(f"{AUTH_MODULE}.moscow_now", return_value=datetime(2026, 3, 5)),
        ):
            result = await check_auth(msg, state, session)

        assert result is False
        state.clear.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_authenticated_valid_returns_true(self):
        """Полностью валидный аутентифицированный пользователь"""
        from utils.auth.auth import check_auth

        msg = make_message()
        state = make_state({"is_authenticated": True, "auth_time": time.time()})
        session = AsyncMock()
        user = make_user()
        company = make_company(subscribe=True, finish_date=None)

        with (
            patch(f"{AUTH_MODULE}.get_user_by_tg_id", return_value=user),
            patch(f"{AUTH_MODULE}.get_company_by_id", return_value=company),
        ):
            result = await check_auth(msg, state, session)

        assert result is True
        state.clear.assert_not_awaited()


# --- Ветка: не аутентифицирован ---


class TestCheckAuthNotAuthenticated:
    @pytest.mark.asyncio
    async def test_user_not_found(self):
        """Не аутентифицирован и не найден в БД"""
        from utils.auth.auth import check_auth

        msg = make_message()
        state = make_state({})
        session = AsyncMock()

        with (
            patch(f"{AUTH_MODULE}.get_user_by_tg_id", return_value=None),
            patch(f"{AUTH_MODULE}.get_user_by_id", return_value=None),
        ):
            result = await check_auth(msg, state, session)

        assert result is False
        assert "не зарегистрирован" in msg.answer.call_args[0][0]

    @pytest.mark.asyncio
    async def test_user_inactive(self):
        """Не аутентифицирован, пользователь деактивирован"""
        from utils.auth.auth import check_auth

        msg = make_message()
        state = make_state({})
        session = AsyncMock()
        user = make_user(is_active=False)

        with patch(f"{AUTH_MODULE}.get_user_by_tg_id", return_value=user):
            result = await check_auth(msg, state, session)

        assert result is False
        assert "деактивирован" in msg.answer.call_args[0][0]

    @pytest.mark.asyncio
    async def test_no_company(self):
        """Не аутентифицирован, нет компании"""
        from utils.auth.auth import check_auth

        msg = make_message()
        state = make_state({})
        session = AsyncMock()
        user = make_user(company_id=None)

        with patch(f"{AUTH_MODULE}.get_user_by_tg_id", return_value=user):
            result = await check_auth(msg, state, session)

        assert result is False
        assert "не привязан" in msg.answer.call_args[0][0]

    @pytest.mark.asyncio
    async def test_subscription_inactive(self):
        """Не аутентифицирован, подписка заморожена"""
        from utils.auth.auth import check_auth

        msg = make_message()
        state = make_state({})
        session = AsyncMock()
        user = make_user()
        company = make_company(subscribe=False)

        with (
            patch(f"{AUTH_MODULE}.get_user_by_tg_id", return_value=user),
            patch(f"{AUTH_MODULE}.get_company_by_id", return_value=company),
        ):
            result = await check_auth(msg, state, session)

        assert result is False
        assert "истекла" in msg.answer.call_args[0][0]

    @pytest.mark.asyncio
    async def test_subscription_expired_by_date(self):
        """Не аутентифицирован, finish_date в прошлом"""
        from utils.auth.auth import check_auth

        msg = make_message()
        state = make_state({})
        session = AsyncMock()
        user = make_user()
        past_date = datetime(2020, 1, 1)
        company = make_company(subscribe=True, finish_date=past_date)

        with (
            patch(f"{AUTH_MODULE}.get_user_by_tg_id", return_value=user),
            patch(f"{AUTH_MODULE}.get_company_by_id", return_value=company),
            patch(f"{AUTH_MODULE}.moscow_now", return_value=datetime(2026, 3, 5)),
        ):
            result = await check_auth(msg, state, session)

        assert result is False
        assert "истекла" in msg.answer.call_args[0][0]

    @pytest.mark.asyncio
    async def test_auto_auth_disabled(self):
        """Авто-аутентификация отключена"""
        from utils.auth.auth import check_auth

        msg = make_message()
        state = make_state({})
        session = AsyncMock()
        user = make_user()
        company = make_company()

        with (
            patch(f"{AUTH_MODULE}.get_user_by_tg_id", return_value=user),
            patch(f"{AUTH_MODULE}.get_company_by_id", return_value=company),
            patch.dict("os.environ", {"ALLOW_AUTO_AUTH": "false"}),
        ):
            result = await check_auth(msg, state, session)

        assert result is False
        assert "/login" in msg.answer.call_args[0][0]

    @pytest.mark.asyncio
    async def test_no_roles(self):
        """Пользователь без ролей"""
        from utils.auth.auth import check_auth

        msg = make_message()
        state = make_state({})
        session = AsyncMock()
        user = make_user()
        company = make_company()

        with (
            patch(f"{AUTH_MODULE}.get_user_by_tg_id", return_value=user),
            patch(f"{AUTH_MODULE}.get_company_by_id", return_value=company),
            patch(f"{AUTH_MODULE}.get_user_roles", return_value=[]),
            patch.dict("os.environ", {"ALLOW_AUTO_AUTH": "true"}),
        ):
            result = await check_auth(msg, state, session)

        assert result is False
        assert "нет назначенных ролей" in msg.answer.call_args[0][0]

    @pytest.mark.asyncio
    async def test_auto_auth_success(self):
        """Успешная авто-аутентификация"""
        from utils.auth.auth import check_auth

        msg = make_message()
        state = make_state({})
        session = AsyncMock()
        user = make_user(user_id=42, company_id=10)
        company = make_company()
        roles = [FakeRole("Стажер")]

        with (
            patch(f"{AUTH_MODULE}.get_user_by_tg_id", return_value=user),
            patch(f"{AUTH_MODULE}.get_company_by_id", return_value=company),
            patch(f"{AUTH_MODULE}.get_user_roles", return_value=roles),
            patch(f"{AUTH_MODULE}.log_user_action"),
            patch.dict("os.environ", {"ALLOW_AUTO_AUTH": "true"}),
        ):
            result = await check_auth(msg, state, session)

        assert result is True
        state.update_data.assert_awaited_once()
        call_kwargs = state.update_data.call_args[1]
        assert call_kwargs["user_id"] == 42
        assert call_kwargs["role"] == "Стажер"
        assert call_kwargs["is_authenticated"] is True
        assert call_kwargs["company_id"] == 10


# --- Ветка: fallback по user_id из FSM ---


class TestCheckAuthFallbackUserId:
    @pytest.mark.asyncio
    async def test_authenticated_fallback_to_fsm_user_id(self):
        """Аутентифицирован, get_user_by_tg_id=None, но есть user_id в FSM"""
        from utils.auth.auth import check_auth

        msg = make_message()
        state = make_state(
            {
                "is_authenticated": True,
                "auth_time": time.time(),
                "user_id": 42,
            }
        )
        session = AsyncMock()
        user = make_user(user_id=42)
        company = make_company()

        with (
            patch(f"{AUTH_MODULE}.get_user_by_tg_id", return_value=None),
            patch(f"{AUTH_MODULE}.get_user_by_id", return_value=user),
            patch(f"{AUTH_MODULE}.get_company_by_id", return_value=company),
        ):
            result = await check_auth(msg, state, session)

        assert result is True

    @pytest.mark.asyncio
    async def test_not_authenticated_fallback_to_fsm_user_id(self):
        """Не аутентифицирован, get_user_by_tg_id=None, fallback на user_id из FSM"""
        from utils.auth.auth import check_auth

        msg = make_message()
        state = make_state({"user_id": 42})
        session = AsyncMock()
        user = make_user(user_id=42)
        company = make_company()
        roles = [FakeRole("Стажер")]

        with (
            patch(f"{AUTH_MODULE}.get_user_by_tg_id", return_value=None),
            patch(f"{AUTH_MODULE}.get_user_by_id", return_value=user),
            patch(f"{AUTH_MODULE}.get_company_by_id", return_value=company),
            patch(f"{AUTH_MODULE}.get_user_roles", return_value=roles),
            patch(f"{AUTH_MODULE}.log_user_action"),
            patch.dict("os.environ", {"ALLOW_AUTO_AUTH": "true"}),
        ):
            result = await check_auth(msg, state, session)

        assert result is True


# --- Ветка: исключение ---


class TestCheckAuthException:
    @pytest.mark.asyncio
    async def test_exception_returns_false(self):
        """Исключение в check_auth — возврат False и сообщение об ошибке"""
        from utils.auth.auth import check_auth

        msg = make_message()
        state = make_state({})
        session = AsyncMock()

        with (
            patch(f"{AUTH_MODULE}.get_user_by_tg_id", side_effect=Exception("DB error")),
            patch(f"{AUTH_MODULE}.log_user_error"),
        ):
            result = await check_auth(msg, state, session)

        assert result is False
        assert "ошибка" in msg.answer.call_args[0][0].lower()
