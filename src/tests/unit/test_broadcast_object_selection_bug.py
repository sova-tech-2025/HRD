"""Регрессия: шаг выбора объектов в рассылке ломался, если в FSM нет company_id.

Хендлеры читали company_id сырым `data.get("company_id")`, а `get_all_objects`
при company_id=None по deny-by-default отдаёт пустой список. В итоге ни отметка
отдельного объекта, ни «Выбрать все» не работали, и рассылку нельзя было отправить.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

COMPANY_ID = 7
OBJECTS = [
    SimpleNamespace(id=11, name="Кофейня на Ленина"),
    SimpleNamespace(id=12, name="Кофейня на Мира"),
]


def make_callback(data: str) -> MagicMock:
    callback = MagicMock()
    callback.data = data
    callback.answer = AsyncMock()
    callback.message = MagicMock()
    callback.message.edit_text = AsyncMock()
    callback.message.edit_reply_markup = AsyncMock()
    callback.from_user.id = 941173405
    return callback


def make_state(data: dict) -> MagicMock:
    """FSM без company_id — как его отдаёт MemoryStorage, если middleware его не положил."""
    state = MagicMock()
    stored = dict(data)
    state.get_data = AsyncMock(side_effect=lambda: dict(stored))
    state.update_data = AsyncMock(side_effect=lambda **kwargs: stored.update(kwargs))
    state.set_state = AsyncMock()
    state.clear = AsyncMock()
    state.stored = stored
    return state


async def fake_get_all_objects(session, company_id=None):
    """Повторяет deny-by-default из db.get_all_objects."""
    if company_id is None:
        return []
    return OBJECTS if company_id == COMPANY_ID else []


def broadcast_patches(user):
    """Патчим зависимости хендлера и db.get_user_by_tg_id (его зовёт ensure_company_id)."""
    return (
        patch("bot.handlers.tests.broadcast.get_user_by_tg_id", AsyncMock(return_value=user)),
        patch("bot.database.db.get_user_by_tg_id", AsyncMock(return_value=user)),
        patch("bot.handlers.tests.broadcast.get_scope_object_ids", AsyncMock(return_value=None)),
        patch("bot.handlers.tests.broadcast.get_all_objects", AsyncMock(side_effect=fake_get_all_objects)),
    )


def selected_object_ids(state) -> list:
    return state.stored.get("selected_object_ids", [])


@pytest.mark.asyncio
async def test_toggle_object_without_company_id_in_fsm():
    """Отметка объекта работает, даже если company_id отсутствует в FSM."""
    from bot.handlers.tests.broadcast import callback_toggle_broadcast_object

    callback = make_callback("broadcast_object:11")
    state = make_state({"selected_object_ids": []})
    user = SimpleNamespace(id=1, tg_id=callback.from_user.id, company_id=COMPANY_ID, roles=[])

    with patch("bot.handlers.tests.broadcast.log_user_error"):
        p1, p2, p3, p4 = broadcast_patches(user)
        with p1, p2, p3, p4:
            await callback_toggle_broadcast_object(callback, state, AsyncMock())

    assert selected_object_ids(state) == [11]
    callback.answer.assert_awaited()
    assert all(call.args[:1] != ("Объект недоступен",) for call in callback.answer.await_args_list)
    callback.message.edit_reply_markup.assert_awaited_once()


@pytest.mark.asyncio
async def test_select_all_objects_without_company_id_in_fsm():
    """«Выбрать все доступные» отмечает все объекты, а не сбрасывает выбор."""
    from bot.handlers.tests.broadcast import callback_select_all_objects

    callback = make_callback("broadcast_objects_all")
    state = make_state({"selected_object_ids": []})
    user = SimpleNamespace(id=1, tg_id=callback.from_user.id, company_id=COMPANY_ID, roles=[])

    with patch("bot.handlers.tests.broadcast.log_user_error"):
        p1, p2, p3, p4 = broadcast_patches(user)
        with p1, p2, p3, p4:
            await callback_select_all_objects(callback, state, AsyncMock())

    assert sorted(selected_object_ids(state)) == [11, 12]
    callback.message.edit_reply_markup.assert_awaited_once()


@pytest.mark.asyncio
async def test_select_all_toggles_off_when_everything_selected():
    """Повторное нажатие снимает выбор — поведение «Снять все» сохраняется."""
    from bot.handlers.tests.broadcast import callback_select_all_objects

    callback = make_callback("broadcast_objects_all")
    state = make_state({"selected_object_ids": [11, 12]})
    user = SimpleNamespace(id=1, tg_id=callback.from_user.id, company_id=COMPANY_ID, roles=[])

    with patch("bot.handlers.tests.broadcast.log_user_error"):
        p1, p2, p3, p4 = broadcast_patches(user)
        with p1, p2, p3, p4:
            await callback_select_all_objects(callback, state, AsyncMock())

    assert selected_object_ids(state) == []


@pytest.mark.asyncio
async def test_toggle_rejects_object_outside_scope():
    """Объект вне области видимости по-прежнему отклоняется."""
    from bot.handlers.tests.broadcast import callback_toggle_broadcast_object

    callback = make_callback("broadcast_object:12")
    state = make_state({"selected_object_ids": []})
    user = SimpleNamespace(id=1, tg_id=callback.from_user.id, company_id=COMPANY_ID, roles=[])

    with patch("bot.handlers.tests.broadcast.log_user_error"):
        p1, p2, _p3, p4 = broadcast_patches(user)
        with p1, p2, p4, patch("bot.handlers.tests.broadcast.get_scope_object_ids", AsyncMock(return_value={11})):
            await callback_toggle_broadcast_object(callback, state, AsyncMock())

    assert selected_object_ids(state) == []
    assert any(call.args[:1] == ("Объект недоступен",) for call in callback.answer.await_args_list)
