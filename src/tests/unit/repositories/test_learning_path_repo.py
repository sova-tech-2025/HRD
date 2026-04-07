"""
Unit-тесты для LearningPathRepository.

Проверяют мягкое удаление траекторий, этапов и сессий
с каскадным soft delete и проверками привязки стажёров.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from bot.repositories.learning_path_repo import LearningPathRepository


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


def make_all_result(rows: list) -> MagicMock:
    """Создать мок результата session.execute() с .all()."""
    result = MagicMock()
    result.all.return_value = rows
    return result


# ==========================================================================
# delete()
# ==========================================================================


class TestDelete:
    """Мягкое удаление траектории с каскадом."""

    @pytest.mark.asyncio
    async def test_delete_success(self):
        """delete() удаляет траекторию с attestation_id, этапами и сессиями → True."""
        session = AsyncMock()

        trajectory_mock = MagicMock()
        trajectory_mock.id = 1
        trajectory_mock.name = "Траектория повара"
        trajectory_mock.attestation_id = 5

        # execute вызывается 6 раз:
        # 1. SELECT LearningPath → scalar_one_or_none (trajectory found)
        # 2. UPDATE LearningPath SET attestation_id=NULL
        # 3. _soft_delete LearningPath → rowcount=1
        # 4. SELECT stage_ids → .all() returns [(1,), (2,)]
        # 5. _bulk_soft_delete LearningStage → rowcount=2
        # 6. _bulk_soft_delete LearningSession → rowcount=3
        # 7. UPDATE TraineeLearningPath SET is_active=False
        session.execute = AsyncMock(
            side_effect=[
                make_scalar_one_or_none_result(trajectory_mock),  # SELECT trajectory
                MagicMock(),  # UPDATE attestation_id=NULL
                make_update_result(1),  # _soft_delete
                make_all_result([(1,), (2,)]),  # SELECT stage_ids
                make_update_result(2),  # _bulk_soft_delete stages
                make_update_result(3),  # _bulk_soft_delete sessions
                MagicMock(),  # UPDATE TraineeLearningPath
            ]
        )

        repo = LearningPathRepository(session)
        result = await repo.delete(trajectory_id=1, company_id=10)

        assert result is True
        session.commit.assert_awaited_once()
        session.rollback.assert_not_awaited()
        assert session.execute.await_count == 7

    @pytest.mark.asyncio
    async def test_delete_not_found(self):
        """delete() возвращает False, если траектория не найдена."""
        session = AsyncMock()

        session.execute = AsyncMock(
            return_value=make_scalar_one_or_none_result(None),
        )

        repo = LearningPathRepository(session)
        result = await repo.delete(trajectory_id=999, company_id=10)

        assert result is False
        session.commit.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_delete_no_attestation(self):
        """delete() пропускает UPDATE attestation_id, если attestation_id=None → True."""
        session = AsyncMock()

        trajectory_mock = MagicMock()
        trajectory_mock.id = 2
        trajectory_mock.name = "Траектория без аттестации"
        trajectory_mock.attestation_id = None

        # Без attestation_id — на один execute меньше (6 вместо 7):
        # 1. SELECT LearningPath → scalar_one_or_none
        # (skip UPDATE attestation_id)
        # 2. _soft_delete LearningPath → rowcount=1
        # 3. SELECT stage_ids → .all() returns [(10,)]
        # 4. _bulk_soft_delete LearningStage → rowcount=1
        # 5. _bulk_soft_delete LearningSession → rowcount=1
        # 6. UPDATE TraineeLearningPath
        session.execute = AsyncMock(
            side_effect=[
                make_scalar_one_or_none_result(trajectory_mock),  # SELECT trajectory
                make_update_result(1),  # _soft_delete
                make_all_result([(10,)]),  # SELECT stage_ids
                make_update_result(1),  # _bulk_soft_delete stages
                make_update_result(1),  # _bulk_soft_delete sessions
                MagicMock(),  # UPDATE TraineeLearningPath
            ]
        )

        repo = LearningPathRepository(session)
        result = await repo.delete(trajectory_id=2, company_id=10)

        assert result is True
        session.commit.assert_awaited_once()
        session.rollback.assert_not_awaited()
        assert session.execute.await_count == 6


# ==========================================================================
# delete_stage()
# ==========================================================================


class TestDeleteStage:
    """Мягкое удаление этапа с каскадом по сессиям."""

    @pytest.mark.asyncio
    @patch("bot.database.db.check_stage_has_trainees", new_callable=AsyncMock, return_value=False)
    async def test_delete_stage_success(self, mock_check):
        """delete_stage() удаляет этап без стажёров → True."""
        session = AsyncMock()

        stage_mock = MagicMock()
        stage_mock.id = 1
        stage_mock.name = "Этап 1"

        # execute вызывается 3 раза:
        # 1. SELECT LearningStage → scalar_one_or_none
        # 2. UPDATE LearningStage SET is_active=False (soft delete этапа)
        # 3. _bulk_soft_delete LearningSession → rowcount
        session.execute = AsyncMock(
            side_effect=[
                make_scalar_one_or_none_result(stage_mock),  # SELECT stage
                MagicMock(),  # UPDATE stage is_active=False
                make_update_result(2),  # _bulk_soft_delete sessions
            ]
        )

        repo = LearningPathRepository(session)
        result = await repo.delete_stage(stage_id=1)

        assert result is True
        session.commit.assert_awaited_once()
        session.rollback.assert_not_awaited()
        mock_check.assert_awaited_once_with(session, 1)

    @pytest.mark.asyncio
    @patch("bot.database.db.check_stage_has_trainees", new_callable=AsyncMock, return_value=True)
    async def test_delete_stage_has_trainees(self, mock_check):
        """delete_stage() возвращает False, если у этапа есть стажёры."""
        session = AsyncMock()

        stage_mock = MagicMock()
        stage_mock.id = 3
        stage_mock.name = "Этап 3"

        session.execute = AsyncMock(
            return_value=make_scalar_one_or_none_result(stage_mock),
        )

        repo = LearningPathRepository(session)
        result = await repo.delete_stage(stage_id=3)

        assert result is False
        session.commit.assert_not_awaited()
        mock_check.assert_awaited_once_with(session, 3)


# ==========================================================================
# delete_session()
# ==========================================================================


class TestDeleteSession:
    """Мягкое удаление сессии."""

    @pytest.mark.asyncio
    @patch("bot.database.db.check_session_has_trainees", new_callable=AsyncMock, return_value=False)
    async def test_delete_session_success(self, mock_check):
        """delete_session() удаляет сессию без стажёров → True."""
        session = AsyncMock()

        learning_session_mock = MagicMock()
        learning_session_mock.id = 7
        learning_session_mock.name = "Сессия 7"

        # execute вызывается 2 раза:
        # 1. SELECT LearningSession → scalar_one_or_none
        # 2. UPDATE LearningSession SET is_active=False
        session.execute = AsyncMock(
            side_effect=[
                make_scalar_one_or_none_result(learning_session_mock),  # SELECT
                MagicMock(),  # UPDATE soft delete
            ]
        )

        repo = LearningPathRepository(session)
        result = await repo.delete_session(session_id=7)

        assert result is True
        session.commit.assert_awaited_once()
        session.rollback.assert_not_awaited()
        mock_check.assert_awaited_once_with(session, 7)

    @pytest.mark.asyncio
    @patch("bot.database.db.check_session_has_trainees", new_callable=AsyncMock, return_value=True)
    async def test_delete_session_has_trainees(self, mock_check):
        """delete_session() возвращает False, если у сессии есть стажёры."""
        session = AsyncMock()

        learning_session_mock = MagicMock()
        learning_session_mock.id = 8
        learning_session_mock.name = "Сессия 8"

        session.execute = AsyncMock(
            return_value=make_scalar_one_or_none_result(learning_session_mock),
        )

        repo = LearningPathRepository(session)
        result = await repo.delete_session(session_id=8)

        assert result is False
        session.commit.assert_not_awaited()
        mock_check.assert_awaited_once_with(session, 8)
