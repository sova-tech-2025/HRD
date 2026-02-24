"""
Тесты для reset_stage_for_trainee: сброс этапа стажера.

Функция должна:
1. Удалить TestResult для всех тестов этапа
2. Удалить TraineeTestAccess для всех тестов этапа
3. Сбросить TraineeSessionProgress (is_opened=False, is_completed=False, opened_date=None, completed_date=None)
4. Сбросить TraineeStageProgress (is_opened=False, is_completed=False, opened_date=None, completed_date=None)
Всё с фильтрацией по company_id (multi-tenancy).
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call
from datetime import datetime


def make_test(test_id: int) -> MagicMock:
    """Создать мок теста."""
    test = MagicMock()
    test.id = test_id
    return test


def make_session_obj(session_id: int, tests: list) -> MagicMock:
    """Создать мок LearningSession."""
    s = MagicMock()
    s.id = session_id
    s.tests = tests
    return s


def make_session_progress(sp_id: int, session_obj: MagicMock) -> MagicMock:
    """Создать мок TraineeSessionProgress."""
    sp = MagicMock()
    sp.id = sp_id
    sp.session = session_obj
    return sp


def make_stage_progress(stage_progress_id: int, session_progress_list: list) -> MagicMock:
    """Создать мок TraineeStageProgress."""
    sp = MagicMock()
    sp.id = stage_progress_id
    sp.session_progress = session_progress_list
    return sp


def make_execute_result(scalar_value=None, scalars_all=None):
    """Создать мок результата session.execute()."""
    result = MagicMock()
    result.scalar_one_or_none.return_value = scalar_value
    if scalars_all is not None:
        result.scalars.return_value.all.return_value = scalars_all
    return result


class TestResetStageForTrainee:
    """Тесты для reset_stage_for_trainee."""

    @pytest.mark.asyncio
    async def test_reset_stage_deletes_test_results_and_access(self):
        """
        Сброс этапа должен удалить TestResult и TraineeTestAccess
        для всех тестов в этапе.
        """
        from database.db import reset_stage_for_trainee

        session = AsyncMock()

        # Мок: тесты в этапе
        test1 = make_test(10)
        test2 = make_test(20)
        session_obj = make_session_obj(1, [test1, test2])
        session_progress = make_session_progress(100, session_obj)
        stage_progress = make_stage_progress(50, [session_progress])

        # Порядок execute вызовов:
        # 1. get TraineeStageProgress → stage_progress
        # 2. delete TestResult → success
        # 3. delete TraineeTestAccess → success
        # 4. update TraineeSessionProgress → success
        # 5. update TraineeStageProgress → success
        session.execute = AsyncMock(side_effect=[
            make_execute_result(scalar_value=stage_progress),  # get stage progress
            MagicMock(rowcount=3),   # delete TestResult
            MagicMock(rowcount=2),   # delete TraineeTestAccess
            MagicMock(),             # update TraineeSessionProgress
            MagicMock(),             # update TraineeStageProgress
        ])

        result = await reset_stage_for_trainee(session, trainee_id=100, stage_id=5, company_id=1)

        assert result is True
        # Должен быть коммит
        session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_reset_stage_returns_false_when_stage_not_found(self):
        """Если TraineeStageProgress не найден, возвращает False."""
        from database.db import reset_stage_for_trainee

        session = AsyncMock()
        session.execute = AsyncMock(return_value=make_execute_result(scalar_value=None))

        result = await reset_stage_for_trainee(session, trainee_id=100, stage_id=999, company_id=1)

        assert result is False
        session.commit.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_reset_stage_returns_test_ids(self):
        """Функция должна возвращать количество удалённых результатов или True."""
        from database.db import reset_stage_for_trainee

        session = AsyncMock()

        test1 = make_test(10)
        session_obj = make_session_obj(1, [test1])
        session_progress = make_session_progress(100, session_obj)
        stage_progress = make_stage_progress(50, [session_progress])

        session.execute = AsyncMock(side_effect=[
            make_execute_result(scalar_value=stage_progress),
            MagicMock(rowcount=1),   # delete TestResult
            MagicMock(rowcount=1),   # delete TraineeTestAccess
            MagicMock(),             # update TraineeSessionProgress
            MagicMock(),             # update TraineeStageProgress
        ])

        result = await reset_stage_for_trainee(session, trainee_id=100, stage_id=5, company_id=1)
        assert result is True

    @pytest.mark.asyncio
    async def test_reset_stage_rollback_on_error(self):
        """При ошибке должен быть rollback."""
        from database.db import reset_stage_for_trainee

        session = AsyncMock()

        stage_progress = make_stage_progress(50, [])

        session.execute = AsyncMock(side_effect=[
            make_execute_result(scalar_value=stage_progress),
            Exception("DB error"),
        ])

        result = await reset_stage_for_trainee(session, trainee_id=100, stage_id=5, company_id=1)

        assert result is False
        session.rollback.assert_awaited_once()
