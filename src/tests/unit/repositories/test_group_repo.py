"""
Unit-тесты для GroupRepository.

Проверяют мягкое удаление групп: успешное удаление, блокировку
при наличии зависимостей (пользователи, траектории, папки БЗ).
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from bot.repositories.group_repo import GroupRepository


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
    """Удаление группы."""

    @pytest.mark.asyncio
    async def test_delete_success(self):
        """delete() мягко удаляет группу при отсутствии зависимостей."""
        session = AsyncMock()

        group_mock = MagicMock()
        group_mock.id = 1
        group_mock.name = "Повара"

        # execute вызывается 7 раз:
        # 1. SELECT Group -> scalar_one_or_none (found)
        # 2. SELECT count() users -> scalar() = 0
        # 3. SELECT count() learning paths -> scalar() = 0
        # 4. SELECT count() knowledge folders -> scalar() = 0
        # 5. _soft_delete(Group) -> rowcount=1
        # 6. DELETE user_groups
        # 7. DELETE folder_group_access
        session.execute = AsyncMock(
            side_effect=[
                make_scalar_one_or_none_result(group_mock),  # group found
                make_count_result(0),  # users count
                make_count_result(0),  # paths count
                make_count_result(0),  # folders count
                make_update_result(1),  # _soft_delete
                MagicMock(),  # DELETE user_groups
                MagicMock(),  # DELETE folder_group_access
            ]
        )

        repo = GroupRepository(session)
        result = await repo.delete(group_id=1, company_id=10)

        assert result is True
        session.commit.assert_awaited_once()
        session.rollback.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_delete_not_found(self):
        """delete() возвращает False, если группа не найдена."""
        session = AsyncMock()

        # 1. SELECT Group -> scalar_one_or_none (None)
        session.execute = AsyncMock(
            side_effect=[
                make_scalar_one_or_none_result(None),  # group not found
            ]
        )

        repo = GroupRepository(session)
        result = await repo.delete(group_id=999, company_id=10)

        assert result is False
        session.commit.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_delete_blocked_has_users(self):
        """delete() возвращает False, если в группе есть активные пользователи."""
        session = AsyncMock()

        group_mock = MagicMock()
        group_mock.id = 1

        # 1. SELECT Group -> found
        # 2. SELECT count() users -> 3
        session.execute = AsyncMock(
            side_effect=[
                make_scalar_one_or_none_result(group_mock),  # group found
                make_count_result(3),  # users count > 0
            ]
        )

        repo = GroupRepository(session)
        result = await repo.delete(group_id=1, company_id=10)

        assert result is False
        session.commit.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_delete_blocked_has_paths(self):
        """delete() возвращает False, если группа используется в траекториях."""
        session = AsyncMock()

        group_mock = MagicMock()
        group_mock.id = 1

        # 1. SELECT Group -> found
        # 2. SELECT count() users -> 0
        # 3. SELECT count() learning paths -> 2
        session.execute = AsyncMock(
            side_effect=[
                make_scalar_one_or_none_result(group_mock),  # group found
                make_count_result(0),  # users count
                make_count_result(2),  # paths count > 0
            ]
        )

        repo = GroupRepository(session)
        result = await repo.delete(group_id=1, company_id=10)

        assert result is False
        session.commit.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_delete_blocked_has_folders(self):
        """delete() возвращает False, если группа используется в базе знаний."""
        session = AsyncMock()

        group_mock = MagicMock()
        group_mock.id = 1

        # 1. SELECT Group -> found
        # 2. SELECT count() users -> 0
        # 3. SELECT count() learning paths -> 0
        # 4. SELECT count() knowledge folders -> 1
        session.execute = AsyncMock(
            side_effect=[
                make_scalar_one_or_none_result(group_mock),  # group found
                make_count_result(0),  # users count
                make_count_result(0),  # paths count
                make_count_result(1),  # folders count > 0
            ]
        )

        repo = GroupRepository(session)
        result = await repo.delete(group_id=1, company_id=10)

        assert result is False
        session.commit.assert_not_awaited()
