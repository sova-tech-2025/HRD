"""
Unit-тесты для ObjectRepository.

Проверяют мягкое удаление объектов: успешное удаление,
блокировку при наличии активных пользователей.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from bot.repositories.object_repo import ObjectRepository


def make_scalar_one_or_none_result(value) -> MagicMock:
    """Создать мок результата session.execute() с scalar_one_or_none()."""
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    return result


def make_count_result(count: int) -> MagicMock:
    """Создать мок результата session.execute() с scalar() для count-запросов."""
    result = MagicMock()
    result.scalar.return_value = count
    return result


def make_update_result(rowcount: int) -> MagicMock:
    """Создать мок результата session.execute() с rowcount."""
    result = MagicMock()
    result.rowcount = rowcount
    return result


# ==========================================================================
# delete()
# ==========================================================================


class TestDelete:
    """Удаление объекта."""

    @pytest.mark.asyncio
    async def test_delete_success(self):
        """delete() мягко удаляет объект при отсутствии зависимостей."""
        session = AsyncMock()

        obj_mock = MagicMock()
        obj_mock.id = 1
        obj_mock.name = "Кафе на Арбате"

        # execute вызывается 3 раза:
        # 1. SELECT Object -> scalar_one_or_none (found)
        # 2. SELECT count() users -> scalar() = 0
        # 3. _soft_delete(Object) -> rowcount=1
        session.execute = AsyncMock(
            side_effect=[
                make_scalar_one_or_none_result(obj_mock),  # object found
                make_count_result(0),  # users count
                make_update_result(1),  # _soft_delete
            ]
        )

        repo = ObjectRepository(session)
        result = await repo.delete(object_id=1, company_id=10)

        assert result is True
        session.commit.assert_awaited_once()
        session.rollback.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_delete_not_found(self):
        """delete() возвращает False, если объект не найден."""
        session = AsyncMock()

        # 1. SELECT Object -> scalar_one_or_none (None)
        session.execute = AsyncMock(
            side_effect=[
                make_scalar_one_or_none_result(None),  # object not found
            ]
        )

        repo = ObjectRepository(session)
        result = await repo.delete(object_id=999, company_id=10)

        assert result is False
        session.commit.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_delete_blocked_has_users(self):
        """delete() возвращает False, если у объекта есть активные пользователи."""
        session = AsyncMock()

        obj_mock = MagicMock()
        obj_mock.id = 1

        # 1. SELECT Object -> found
        # 2. SELECT count() users -> 5
        session.execute = AsyncMock(
            side_effect=[
                make_scalar_one_or_none_result(obj_mock),  # object found
                make_count_result(5),  # users count > 0
            ]
        )

        repo = ObjectRepository(session)
        result = await repo.delete(object_id=1, company_id=10)

        assert result is False
        session.commit.assert_not_awaited()
