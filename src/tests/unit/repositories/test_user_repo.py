"""
Unit-тесты для UserRepository.

Проверяют мягкое удаление пользователя: soft delete, hard delete M2M,
деактивация связанных записей, nullify created_by_id.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from bot.repositories.user_repo import UserRepository


def make_scalar_one_or_none_result(value) -> MagicMock:
    """Создать мок результата session.execute() с scalar_one_or_none()."""
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    return result


def make_update_result(rowcount: int) -> MagicMock:
    """Создать мок результата session.execute() для UPDATE с rowcount."""
    result = MagicMock()
    result.rowcount = rowcount
    return result


# ==========================================================================
# delete()
# ==========================================================================


class TestDelete:
    """Мягкое удаление пользователя с каскадной очисткой связей."""

    @pytest.mark.asyncio
    async def test_delete_success(self):
        """delete() удаляет пользователя из правильной компании → True.

        Порядок execute вызовов (18 шт):
        1. SELECT User → scalar_one_or_none
        2. _soft_delete User → rowcount=1
        3-5. DELETE user_roles, user_groups, user_objects
        6-10. UPDATE Mentorship, TraineeTestAccess, TraineeLearningPath,
              TraineeAttestation, TraineeManager
        11-18. UPDATE nullify creator_id: Test, Attestation, LearningPath,
               KnowledgeMaterial, KnowledgeFolder, Object, Group, Company
        """
        session = AsyncMock()

        user_mock = MagicMock()
        user_mock.id = 42
        user_mock.full_name = "Иванов Иван"
        user_mock.company_id = 10

        # Первые 2 вызова нуждаются в специфичных return values,
        # остальные 16 — просто MagicMock (UPDATE/DELETE без чтения результата)
        side_effects = [
            make_scalar_one_or_none_result(user_mock),  # 1. SELECT User
            make_update_result(1),  # 2. _soft_delete
        ]
        # 3-18: DELETE M2M (3) + UPDATE deactivate (5) + UPDATE nullify (8)
        side_effects.extend([MagicMock() for _ in range(16)])

        session.execute = AsyncMock(side_effect=side_effects)

        repo = UserRepository(session)
        result = await repo.delete(user_id=42, company_id=10)

        assert result is True
        session.commit.assert_awaited_once()
        session.rollback.assert_not_awaited()
        assert session.execute.await_count == 18

    @pytest.mark.asyncio
    async def test_delete_not_found(self):
        """delete() возвращает False, если пользователь не найден."""
        session = AsyncMock()

        session.execute = AsyncMock(
            return_value=make_scalar_one_or_none_result(None),
        )

        repo = UserRepository(session)
        result = await repo.delete(user_id=999, company_id=10)

        assert result is False
        session.commit.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_delete_wrong_company(self):
        """delete() возвращает False, если пользователь из другой компании."""
        session = AsyncMock()

        user_mock = MagicMock()
        user_mock.id = 42
        user_mock.full_name = "Петров Пётр"
        user_mock.company_id = 20  # принадлежит компании 20

        session.execute = AsyncMock(
            return_value=make_scalar_one_or_none_result(user_mock),
        )

        repo = UserRepository(session)
        result = await repo.delete(user_id=42, company_id=10)  # запрос от компании 10

        assert result is False
        session.commit.assert_not_awaited()
