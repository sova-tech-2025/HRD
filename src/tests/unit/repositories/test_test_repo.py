"""
Unit-тесты для TestRepository.

Проверяют мягкое удаление тестов и вопросов: каскадное удаление,
пересчёт max_score, проверку принадлежности к компании.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from bot.repositories.test_repo import TestRepository


def make_scalar_one_or_none_result(value) -> MagicMock:
    """Создать мок результата session.execute() с scalar_one_or_none()."""
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    return result


def make_update_result(rowcount: int) -> MagicMock:
    """Создать мок результата session.execute() с rowcount."""
    result = MagicMock()
    result.rowcount = rowcount
    return result


def make_scalar_result(value) -> MagicMock:
    """Создать мок результата session.execute() с scalar() для агрегатов."""
    result = MagicMock()
    result.scalar.return_value = value
    return result


# ==========================================================================
# delete()
# ==========================================================================


class TestDelete:
    """Удаление теста."""

    @pytest.mark.asyncio
    async def test_delete_success(self):
        """delete() мягко удаляет тест и каскадно вопросы."""
        session = AsyncMock()

        # execute вызывается 2 раза:
        # 1. _soft_delete(Test) -> rowcount=1
        # 2. _bulk_soft_delete(TestQuestion) -> rowcount=3
        session.execute = AsyncMock(
            side_effect=[
                make_update_result(1),  # _soft_delete Test
                make_update_result(3),  # _bulk_soft_delete TestQuestion
            ]
        )

        repo = TestRepository(session)
        result = await repo.delete(test_id=1, company_id=10)

        assert result is True
        session.commit.assert_awaited_once()
        session.rollback.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_delete_not_found(self):
        """delete() возвращает False, если тест не найден."""
        session = AsyncMock()

        # 1. _soft_delete(Test) -> rowcount=0 (не найден)
        session.execute = AsyncMock(
            side_effect=[
                make_update_result(0),  # _soft_delete Test -> not found
            ]
        )

        repo = TestRepository(session)
        result = await repo.delete(test_id=999, company_id=10)

        assert result is False
        session.commit.assert_not_awaited()


# ==========================================================================
# delete_question()
# ==========================================================================


class TestDeleteQuestion:
    """Удаление вопроса теста."""

    @pytest.mark.asyncio
    async def test_delete_question_success(self):
        """delete_question() удаляет вопрос и пересчитывает max_score теста."""
        session = AsyncMock()

        question_mock = MagicMock()
        question_mock.id = 5
        question_mock.test_id = 1
        question_mock.points = 10.0

        test_mock = MagicMock()
        test_mock.id = 1
        test_mock.company_id = 10

        # execute вызывается 5 раз:
        # 1. SELECT TestQuestion -> scalar_one_or_none (found)
        # 2. SELECT Test -> scalar_one_or_none (belongs to company)
        # 3. UPDATE TestQuestion SET is_active=False
        # 4. SELECT sum(points) -> scalar() = 25.0
        # 5. UPDATE Test SET max_score
        session.execute = AsyncMock(
            side_effect=[
                make_scalar_one_or_none_result(question_mock),  # question found
                make_scalar_one_or_none_result(test_mock),  # test belongs to company
                MagicMock(),  # UPDATE question is_active=False
                make_scalar_result(25.0),  # sum(points)
                MagicMock(),  # UPDATE test max_score
            ]
        )

        repo = TestRepository(session)
        result = await repo.delete_question(question_id=5, company_id=10)

        assert result is True
        session.commit.assert_awaited_once()
        session.rollback.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_delete_question_not_found(self):
        """delete_question() возвращает False, если вопрос не найден."""
        session = AsyncMock()

        # 1. SELECT TestQuestion -> scalar_one_or_none (None)
        session.execute = AsyncMock(
            side_effect=[
                make_scalar_one_or_none_result(None),  # question not found
            ]
        )

        repo = TestRepository(session)
        result = await repo.delete_question(question_id=999, company_id=10)

        assert result is False
        session.commit.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_delete_question_wrong_company(self):
        """delete_question() возвращает False, если тест не принадлежит компании."""
        session = AsyncMock()

        question_mock = MagicMock()
        question_mock.id = 5
        question_mock.test_id = 1

        # 1. SELECT TestQuestion -> found
        # 2. SELECT Test -> scalar_one_or_none (None — wrong company)
        session.execute = AsyncMock(
            side_effect=[
                make_scalar_one_or_none_result(question_mock),  # question found
                make_scalar_one_or_none_result(None),  # test not in company
            ]
        )

        repo = TestRepository(session)
        result = await repo.delete_question(question_id=5, company_id=99)

        assert result is False
        session.commit.assert_not_awaited()
