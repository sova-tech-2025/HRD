"""
Unit-тесты для AssessmentResultRepository.

Проверяют операции с результатами аттестаций: создание результата,
сохранение ответов на вопросы, получение результатов стажера,
получение ожидающих решений руководителя, проведение аттестации.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from bot.repositories.assessment_result_repo import AssessmentResultRepository


def make_scalars_result(items: list) -> MagicMock:
    """Создать мок результата session.execute() с scalars().all()."""
    scalars_mock = MagicMock()
    scalars_mock.all.return_value = items
    result = MagicMock()
    result.scalars.return_value = scalars_mock
    return result


def make_scalar_one_or_none_result(value) -> MagicMock:
    """Создать мок результата session.execute() с scalar_one_or_none()."""
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    return result


# ==========================================================================
# create()
# ==========================================================================


class TestCreate:
    """Создание результата аттестации."""

    @pytest.mark.asyncio
    async def test_create_success(self):
        """create() с company_id добавляет AttestationResult, вызывает flush."""
        session = AsyncMock()
        repo = AssessmentResultRepository(session)

        trainee_mock = MagicMock()
        trainee_mock.company_id = 10

        attestation_mock = MagicMock()
        attestation_mock.id = 5

        with (
            patch("bot.database.db.get_user_by_id", new_callable=AsyncMock, return_value=trainee_mock),
            patch("bot.database.db.get_attestation_by_id", new_callable=AsyncMock, return_value=attestation_mock),
        ):
            result = await repo.create(
                trainee_id=1,
                attestation_id=5,
                manager_id=2,
                total_score=80.0,
                max_score=100.0,
                is_passed=True,
                company_id=10,
            )

        assert result is not None
        session.add.assert_called_once()
        session.flush.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_create_company_isolation(self):
        """create() возвращает None, если trainee из другой компании."""
        session = AsyncMock()
        repo = AssessmentResultRepository(session)

        trainee_mock = MagicMock()
        trainee_mock.company_id = 99  # Другая компания

        with patch("bot.database.db.get_user_by_id", new_callable=AsyncMock, return_value=trainee_mock):
            result = await repo.create(
                trainee_id=1,
                attestation_id=5,
                manager_id=2,
                total_score=80.0,
                max_score=100.0,
                is_passed=True,
                company_id=10,
            )

        assert result is None
        session.add.assert_not_called()
        session.flush.assert_not_awaited()


# ==========================================================================
# save_question_result()
# ==========================================================================


class TestSaveQuestionResult:
    """Сохранение результата ответа на вопрос аттестации."""

    @pytest.mark.asyncio
    async def test_save_question_result_success(self):
        """save_question_result() добавляет AttestationQuestionResult, возвращает True."""
        session = AsyncMock()
        repo = AssessmentResultRepository(session)

        result = await repo.save_question_result(
            result_id=1,
            question_id=10,
            points_awarded=4.0,
            max_points=5.0,
        )

        assert result is True
        session.add.assert_called_once()
        session.flush.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_save_question_result_error(self):
        """save_question_result() при ошибке flush возвращает False."""
        session = AsyncMock()
        session.flush.side_effect = Exception("DB error")
        repo = AssessmentResultRepository(session)

        result = await repo.save_question_result(
            result_id=1,
            question_id=10,
            points_awarded=4.0,
            max_points=5.0,
        )

        assert result is False


# ==========================================================================
# get_for_trainee()
# ==========================================================================


class TestGetForTrainee:
    """Получение результатов аттестаций стажера."""

    @pytest.mark.asyncio
    async def test_get_for_trainee_returns_list(self):
        """get_for_trainee() выполняет запрос и возвращает список результатов."""
        session = AsyncMock()

        result1 = MagicMock()
        result1.id = 1
        result2 = MagicMock()
        result2.id = 2

        session.execute.return_value = make_scalars_result([result1, result2])

        repo = AssessmentResultRepository(session)
        results = await repo.get_for_trainee(trainee_id=1)

        assert len(results) == 2
        assert result1 in results
        assert result2 in results
        session.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_for_trainee_company_filter(self):
        """get_for_trainee(company_id=1) добавляет фильтр по компании."""
        session = AsyncMock()

        result1 = MagicMock()
        result1.id = 1

        session.execute.return_value = make_scalars_result([result1])

        repo = AssessmentResultRepository(session)
        results = await repo.get_for_trainee(trainee_id=1, company_id=1)

        assert len(results) == 1
        assert result1 in results
        session.execute.assert_awaited_once()


# ==========================================================================
# get_specific()
# ==========================================================================


class TestGetSpecific:
    """Получение результата конкретной аттестации для стажера."""

    @pytest.mark.asyncio
    async def test_get_specific_success(self):
        """get_specific() возвращает результат аттестации."""
        session = AsyncMock()

        result_mock = MagicMock()
        result_mock.id = 1
        result_mock.trainee_id = 10
        result_mock.attestation_id = 5

        session.execute.return_value = make_scalar_one_or_none_result(result_mock)

        repo = AssessmentResultRepository(session)
        result = await repo.get_specific(trainee_id=10, attestation_id=5, company_id=1)

        assert result is result_mock
        session.execute.assert_awaited_once()


# ==========================================================================
# get_pending_decisions()
# ==========================================================================


class TestGetPendingDecisions:
    """Получение ожидающих решения аттестаций для руководителя."""

    @pytest.mark.asyncio
    async def test_get_pending_decisions_returns_list(self):
        """get_pending_decisions() возвращает список ожидающих решений."""
        session = AsyncMock()

        pending1 = MagicMock()
        pending1.id = 1
        pending1.manager_decision = None
        pending2 = MagicMock()
        pending2.id = 2
        pending2.manager_decision = None

        session.execute.return_value = make_scalars_result([pending1, pending2])

        repo = AssessmentResultRepository(session)
        results = await repo.get_pending_decisions(manager_id=3, company_id=1)

        assert len(results) == 2
        assert pending1 in results
        assert pending2 in results
        session.execute.assert_awaited_once()


# ==========================================================================
# conduct()
# ==========================================================================


class TestConduct:
    """Проведение аттестации руководителем."""

    @pytest.mark.asyncio
    async def test_conduct_success_passed(self):
        """conduct() при score >= passing_score создает результат с is_passed=True."""
        session = AsyncMock()

        attestation_mock = MagicMock()
        attestation_mock.passing_score = 70.0
        attestation_mock.max_score = 100.0

        session.execute.return_value = make_scalar_one_or_none_result(attestation_mock)

        repo = AssessmentResultRepository(session)

        created_result = MagicMock()
        created_result.id = 1
        created_result.is_passed = True
        repo.create = AsyncMock(return_value=created_result)

        scores = {1: 40.0, 2: 35.0}  # total = 75.0 >= 70.0
        result = await repo.conduct(
            trainee_id=10,
            attestation_id=5,
            manager_id=3,
            scores=scores,
            company_id=1,
        )

        assert result is created_result
        repo.create.assert_awaited_once_with(
            10,
            5,
            3,
            75.0,
            100.0,
            True,
            company_id=1,
        )

    @pytest.mark.asyncio
    async def test_conduct_success_failed(self):
        """conduct() при score < passing_score создает результат с is_passed=False."""
        session = AsyncMock()

        attestation_mock = MagicMock()
        attestation_mock.passing_score = 70.0
        attestation_mock.max_score = 100.0

        session.execute.return_value = make_scalar_one_or_none_result(attestation_mock)

        repo = AssessmentResultRepository(session)

        created_result = MagicMock()
        created_result.id = 1
        created_result.is_passed = False
        repo.create = AsyncMock(return_value=created_result)

        scores = {1: 20.0, 2: 30.0}  # total = 50.0 < 70.0
        result = await repo.conduct(
            trainee_id=10,
            attestation_id=5,
            manager_id=3,
            scores=scores,
            company_id=1,
        )

        assert result is created_result
        repo.create.assert_awaited_once_with(
            10,
            5,
            3,
            50.0,
            100.0,
            False,
            company_id=1,
        )
