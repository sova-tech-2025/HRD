"""
Unit-тесты для AssessmentRepository.

Проверяют CRUD-операции с аттестациями: создание, добавление вопросов,
получение списка, удаление, проверку использования в траекториях.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from bot.repositories.assessment_repo import AssessmentRepository


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
    """Создание аттестации."""

    @pytest.mark.asyncio
    async def test_create_success(self):
        """create() добавляет Attestation в сессию, вызывает flush и commit."""
        session = AsyncMock()
        repo = AssessmentRepository(session)

        with patch("bot.repositories.assessment_repo.Attestation") as MockAttestation:
            attestation_instance = MagicMock()
            attestation_instance.id = 42
            MockAttestation.return_value = attestation_instance

            result = await repo.create(
                name="Итоговая аттестация",
                passing_score=70.0,
                creator_id=1,
                company_id=10,
            )

        assert result is attestation_instance
        session.add.assert_called_once_with(attestation_instance)
        session.flush.assert_awaited_once()
        session.commit.assert_awaited_once()
        session.rollback.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_create_rollback_on_error(self):
        """create() при исключении вызывает rollback и возвращает None."""
        session = AsyncMock()
        session.flush.side_effect = Exception("DB connection lost")
        repo = AssessmentRepository(session)

        with patch("bot.repositories.assessment_repo.Attestation") as MockAttestation:
            MockAttestation.return_value = MagicMock()

            result = await repo.create(
                name="Аттестация",
                passing_score=50.0,
                creator_id=1,
                company_id=10,
            )

        assert result is None
        session.rollback.assert_awaited_once()
        session.commit.assert_not_awaited()


# ==========================================================================
# add_question()
# ==========================================================================


class TestAddQuestion:
    """Добавление вопроса к аттестации."""

    @pytest.mark.asyncio
    async def test_add_question_updates_max_score(self):
        """add_question() увеличивает max_score аттестации на max_points вопроса."""
        session = AsyncMock()

        attestation_mock = MagicMock()
        attestation_mock.max_score = 10.0
        session.get.return_value = attestation_mock

        repo = AssessmentRepository(session)

        with patch("bot.repositories.assessment_repo.AttestationQuestion") as MockQuestion:
            question_instance = MagicMock()
            MockQuestion.return_value = question_instance

            result = await repo.add_question(
                attestation_id=1,
                question_text="Что такое ХАССП?",
                max_points=5.0,
                question_number=1,
            )

        assert result is question_instance
        assert attestation_mock.max_score == 15.0
        session.add.assert_called_once_with(question_instance)
        session.flush.assert_awaited_once()
        session.commit.assert_awaited_once()


# ==========================================================================
# get_all()
# ==========================================================================


class TestGetAll:
    """Получение списка аттестаций."""

    @pytest.mark.asyncio
    async def test_get_all_deny_by_default(self):
        """get_all(company_id=None) возвращает пустой список (deny-by-default)."""
        session = AsyncMock()
        repo = AssessmentRepository(session)

        result = await repo.get_all(company_id=None)

        assert result == []
        session.execute.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_get_all_with_company(self):
        """get_all(company_id=1) выполняет запрос и возвращает список аттестаций."""
        session = AsyncMock()

        att1 = MagicMock()
        att1.id = 1
        att1.name = "Аттестация 1"
        att2 = MagicMock()
        att2.id = 2
        att2.name = "Аттестация 2"

        session.execute.return_value = make_scalars_result([att1, att2])

        repo = AssessmentRepository(session)
        result = await repo.get_all(company_id=1)

        assert len(result) == 2
        assert att1 in result
        assert att2 in result
        session.execute.assert_awaited_once()


# ==========================================================================
# get_by_id()
# ==========================================================================


class TestGetById:
    """Получение аттестации по ID."""

    @pytest.mark.asyncio
    async def test_get_by_id_success(self):
        """get_by_id() с company_id возвращает найденную аттестацию."""
        session = AsyncMock()

        attestation_mock = MagicMock()
        attestation_mock.id = 5
        attestation_mock.name = "Финальная"
        attestation_mock.company_id = 1

        session.execute.return_value = make_scalar_one_or_none_result(attestation_mock)

        repo = AssessmentRepository(session)
        result = await repo.get_by_id(attestation_id=5, company_id=1)

        assert result is attestation_mock
        session.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_by_id_not_found(self):
        """get_by_id() возвращает None, если аттестация не найдена."""
        session = AsyncMock()
        session.execute.return_value = make_scalar_one_or_none_result(None)

        repo = AssessmentRepository(session)
        result = await repo.get_by_id(attestation_id=999, company_id=1)

        assert result is None


# ==========================================================================
# check_in_use()
# ==========================================================================


class TestCheckInUse:
    """Проверка использования аттестации в траекториях."""

    @pytest.mark.asyncio
    async def test_check_in_use_true(self):
        """check_in_use() возвращает True, когда есть траектории с этой аттестацией."""
        session = AsyncMock()

        path_mock = MagicMock()
        path_mock.id = 10
        session.execute.return_value = make_scalars_result([path_mock])

        repo = AssessmentRepository(session)
        result = await repo.check_in_use(attestation_id=5, company_id=1)

        assert result is True

    @pytest.mark.asyncio
    async def test_check_in_use_false(self):
        """check_in_use() возвращает False, когда нет траекторий с этой аттестацией."""
        session = AsyncMock()
        session.execute.return_value = make_scalars_result([])

        repo = AssessmentRepository(session)
        result = await repo.check_in_use(attestation_id=5, company_id=1)

        assert result is False

    @pytest.mark.asyncio
    async def test_check_in_use_error_returns_true(self):
        """check_in_use() при ошибке возвращает True (безопасный дефолт)."""
        session = AsyncMock()
        session.execute.side_effect = Exception("DB error")

        repo = AssessmentRepository(session)
        result = await repo.check_in_use(attestation_id=5, company_id=1)

        assert result is True


# ==========================================================================
# delete()
# ==========================================================================


class TestDelete:
    """Удаление аттестации."""

    @pytest.mark.asyncio
    async def test_delete_success(self):
        """delete() удаляет вопросы и аттестацию, вызывает commit."""
        session = AsyncMock()

        attestation_mock = MagicMock()
        attestation_mock.id = 5
        attestation_mock.name = "Тестовая"

        # execute вызывается 4 раза:
        # 1. check_in_use: scalars().all() -> [] (не используется)
        # 2. select Attestation: scalar_one_or_none() -> attestation_mock
        # 3. delete AttestationQuestion
        # 4. delete Attestation
        session.execute = AsyncMock(
            side_effect=[
                make_scalars_result([]),  # check_in_use
                make_scalar_one_or_none_result(attestation_mock),  # select attestation
                MagicMock(),  # delete questions
                MagicMock(),  # delete attestation
            ]
        )

        repo = AssessmentRepository(session)
        result = await repo.delete(attestation_id=5, company_id=1)

        assert result is True
        session.commit.assert_awaited_once()
        session.rollback.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_delete_blocked_if_in_use(self):
        """delete() возвращает False, если аттестация используется в траектории."""
        session = AsyncMock()

        path_mock = MagicMock()
        path_mock.id = 10
        # check_in_use вернёт True (есть траектория)
        session.execute.return_value = make_scalars_result([path_mock])

        repo = AssessmentRepository(session)
        result = await repo.delete(attestation_id=5, company_id=1)

        assert result is False
        session.commit.assert_not_awaited()
