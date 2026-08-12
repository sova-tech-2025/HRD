"""CompanyMiddleware не должен трогать ленивый relationship User.company.

Обращение к незагруженному relationship на AsyncSession вне greenlet-контекста
бросает MissingGreenlet. Раньше это исключение молча глоталось, из-за чего
company_id никогда не попадал в FSM, а проверка подписки не выполнялась.
"""

from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

COMPANY_ID = 7


class LazyCompanyUser:
    """Пользователь, у которого доступ к .company падает, как ленивый relationship."""

    def __init__(self, company_id=COMPANY_ID):
        self.id = 1
        self.tg_id = 941173405
        self.company_id = company_id

    @property
    def company(self):
        raise RuntimeError("greenlet_spawn has not been called; can't call await_only() here")


def make_callback(data: str = "broadcast_object:11") -> MagicMock:
    # spec обязателен: middleware ветвится через isinstance(event, CallbackQuery)
    callback = MagicMock(spec=CallbackQuery)
    callback.data = data
    callback.answer = AsyncMock()
    callback.from_user = SimpleNamespace(id=941173405)
    return callback


def make_data() -> dict:
    state = MagicMock()
    stored = {}
    state.get_data = AsyncMock(side_effect=lambda: dict(stored))
    state.update_data = AsyncMock(side_effect=lambda **kwargs: stored.update(kwargs))
    return {"session": MagicMock(spec=AsyncSession), "state": state, "_stored": stored}


def make_company(**overrides) -> SimpleNamespace:
    company = SimpleNamespace(id=COMPANY_ID, subscribe=True, finish_date=None)
    for key, value in overrides.items():
        setattr(company, key, value)
    return company


@pytest.mark.asyncio
async def test_company_id_lands_in_data_and_fsm():
    from bot.middlewares.company_middleware import CompanyMiddleware

    handler = AsyncMock(return_value="handled")
    event = make_callback()
    data = make_data()

    with (
        patch("bot.middlewares.company_middleware.get_user_by_tg_id", AsyncMock(return_value=LazyCompanyUser())),
        patch("bot.middlewares.company_middleware.get_company_by_id", AsyncMock(return_value=make_company())),
    ):
        result = await CompanyMiddleware()(handler, event, data)

    assert result == "handled"
    handler.assert_awaited_once()
    assert data["company_id"] == COMPANY_ID
    assert data["_stored"]["company_id"] == COMPANY_ID


@pytest.mark.asyncio
async def test_frozen_subscription_blocks_update():
    from bot.middlewares.company_middleware import CompanyMiddleware

    handler = AsyncMock()
    event = make_callback()
    data = make_data()

    with (
        patch("bot.middlewares.company_middleware.get_user_by_tg_id", AsyncMock(return_value=LazyCompanyUser())),
        patch(
            "bot.middlewares.company_middleware.get_company_by_id",
            AsyncMock(return_value=make_company(subscribe=False)),
        ),
    ):
        await CompanyMiddleware()(handler, event, data)

    handler.assert_not_awaited()
    event.answer.assert_awaited_once()


@pytest.mark.asyncio
async def test_expired_finish_date_blocks_update():
    from bot.middlewares.company_middleware import CompanyMiddleware
    from bot.utils.timezone import moscow_now

    handler = AsyncMock()
    event = make_callback()
    data = make_data()
    expired = make_company(finish_date=moscow_now() - timedelta(days=1))

    with (
        patch("bot.middlewares.company_middleware.get_user_by_tg_id", AsyncMock(return_value=LazyCompanyUser())),
        patch("bot.middlewares.company_middleware.get_company_by_id", AsyncMock(return_value=expired)),
    ):
        await CompanyMiddleware()(handler, event, data)

    handler.assert_not_awaited()
    event.answer.assert_awaited_once()


@pytest.mark.asyncio
async def test_skip_callbacks_pass_through_without_company():
    from bot.middlewares.company_middleware import CompanyMiddleware

    handler = AsyncMock(return_value="handled")
    event = make_callback("company:join")
    data = make_data()

    with patch("bot.middlewares.company_middleware.get_user_by_tg_id", AsyncMock()) as get_user:
        result = await CompanyMiddleware()(handler, event, data)

    assert result == "handled"
    get_user.assert_not_awaited()
