"""
Unit-тесты для AssessmentAssignmentRepository.

Проверяют операции назначения аттестаций стажерам: назначение, получение,
обновление расписания, запуск/завершение сессии, статусы, очистка дубликатов.
"""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from bot.repositories.assessment_assignment_repo import AssessmentAssignmentRepository


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


def make_update_result(rowcount: int) -> MagicMock:
    """Создать мок результата session.execute() для UPDATE с rowcount."""
    result = MagicMock()
    result.rowcount = rowcount
    return result


# ==========================================================================
# assign()
# ==========================================================================


class TestAssign:
    """Назначение аттестации стажеру."""

    @pytest.mark.asyncio
    async def test_assign_success(self):
        """assign() создает TraineeAttestation, вызывает add и flush."""
        session = AsyncMock()
        session.add = MagicMock()  # add() синхронный в AsyncSession

        trainee_mock = MagicMock()
        trainee_mock.company_id = 1

        manager_mock = MagicMock()
        manager_mock.company_id = 1

        attestation_mock = MagicMock()

        # execute вызывается 2 раза:
        # 1. SELECT existing TraineeAttestation -> None (нет дубликата)
        # 2. UPDATE деактивация старых назначений
        session.execute = AsyncMock(
            side_effect=[
                make_scalar_one_or_none_result(None),  # нет существующего
                MagicMock(),  # деактивация старых
            ]
        )

        repo = AssessmentAssignmentRepository(session)

        with (
            patch(
                "bot.database.db.get_user_by_id",
                side_effect=[trainee_mock, manager_mock],
            ),
            patch(
                "bot.database.db.get_attestation_by_id",
                return_value=attestation_mock,
            ),
        ):
            result = await repo.assign(
                trainee_id=10,
                manager_id=20,
                attestation_id=30,
                assigned_by_id=5,
                company_id=1,
            )

        assert result is not None
        session.add.assert_called_once()
        session.flush.assert_awaited_once()

        # Проверяем что созданный объект имеет правильные параметры
        added_obj = session.add.call_args[0][0]
        assert added_obj.trainee_id == 10
        assert added_obj.manager_id == 20
        assert added_obj.attestation_id == 30
        assert added_obj.assigned_by_id == 5
        assert added_obj.status == "assigned"

    @pytest.mark.asyncio
    async def test_assign_returns_existing_on_duplicate(self):
        """assign() возвращает существующее назначение при дубликате."""
        session = AsyncMock()

        trainee_mock = MagicMock()
        trainee_mock.company_id = 1

        manager_mock = MagicMock()
        manager_mock.company_id = 1

        attestation_mock = MagicMock()

        existing_assignment = MagicMock()
        existing_assignment.id = 99
        existing_assignment.trainee_id = 10
        existing_assignment.manager_id = 20

        # execute: SELECT existing -> найден дубликат
        session.execute = AsyncMock(return_value=make_scalar_one_or_none_result(existing_assignment))

        repo = AssessmentAssignmentRepository(session)

        with (
            patch(
                "bot.database.db.get_user_by_id",
                side_effect=[trainee_mock, manager_mock],
            ),
            patch(
                "bot.database.db.get_attestation_by_id",
                return_value=attestation_mock,
            ),
        ):
            result = await repo.assign(
                trainee_id=10,
                manager_id=20,
                attestation_id=30,
                assigned_by_id=5,
                company_id=1,
            )

        assert result is existing_assignment
        session.add.assert_not_called()
        session.flush.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_assign_deactivates_old(self):
        """assign() деактивирует старые назначения перед созданием нового."""
        session = AsyncMock()
        session.add = MagicMock()  # add() синхронный в AsyncSession

        trainee_mock = MagicMock()
        trainee_mock.company_id = 1

        manager_mock = MagicMock()
        manager_mock.company_id = 1

        attestation_mock = MagicMock()

        # execute вызывается 2 раза:
        # 1. SELECT existing -> None
        # 2. UPDATE деактивация старых
        session.execute = AsyncMock(
            side_effect=[
                make_scalar_one_or_none_result(None),
                MagicMock(),  # результат UPDATE
            ]
        )

        repo = AssessmentAssignmentRepository(session)

        with (
            patch(
                "bot.database.db.get_user_by_id",
                side_effect=[trainee_mock, manager_mock],
            ),
            patch(
                "bot.database.db.get_attestation_by_id",
                return_value=attestation_mock,
            ),
        ):
            await repo.assign(
                trainee_id=10,
                manager_id=20,
                attestation_id=30,
                assigned_by_id=5,
                company_id=1,
            )

        # execute вызван 2 раза: SELECT + UPDATE
        assert session.execute.await_count == 2

    @pytest.mark.asyncio
    async def test_assign_company_isolation(self):
        """assign() возвращает None, когда trainee не принадлежит компании."""
        session = AsyncMock()

        trainee_mock = MagicMock()
        trainee_mock.company_id = 999  # другая компания

        repo = AssessmentAssignmentRepository(session)

        with (
            patch("bot.database.db.get_user_by_id", return_value=trainee_mock),
            patch(
                "bot.database.db.get_attestation_by_id",
                return_value=MagicMock(),
            ),
        ):
            result = await repo.assign(
                trainee_id=10,
                manager_id=20,
                attestation_id=30,
                assigned_by_id=5,
                company_id=1,
            )

        assert result is None
        session.add.assert_not_called()


# ==========================================================================
# get_for_manager()
# ==========================================================================


class TestGetForManager:
    """Получение назначенных аттестаций для руководителя."""

    @pytest.mark.asyncio
    async def test_get_for_manager_success(self):
        """get_for_manager() выполняет запрос и возвращает список назначений."""
        session = AsyncMock()

        att1 = MagicMock()
        att1.id = 1
        att2 = MagicMock()
        att2.id = 2

        session.execute.return_value = make_scalars_result([att1, att2])

        repo = AssessmentAssignmentRepository(session)
        result = await repo.get_for_manager(manager_id=20, company_id=1)

        assert len(result) == 2
        assert att1 in result
        assert att2 in result
        session.execute.assert_awaited_once()


# ==========================================================================
# get_by_id()
# ==========================================================================


class TestGetById:
    """Получение назначенной аттестации по ID."""

    @pytest.mark.asyncio
    async def test_get_by_id_success(self):
        """get_by_id() возвращает найденное назначение."""
        session = AsyncMock()

        assignment_mock = MagicMock()
        assignment_mock.id = 42

        session.execute.return_value = make_scalar_one_or_none_result(assignment_mock)

        repo = AssessmentAssignmentRepository(session)
        result = await repo.get_by_id(assignment_id=42, company_id=1)

        assert result is assignment_mock
        session.execute.assert_awaited_once()


# ==========================================================================
# update_schedule()
# ==========================================================================


class TestUpdateSchedule:
    """Обновление даты и времени аттестации."""

    @pytest.mark.asyncio
    async def test_update_schedule_success(self):
        """update_schedule() обновляет дату и время, возвращает True."""
        session = AsyncMock()

        assignment_mock = MagicMock()
        assignment_mock.id = 42

        # execute вызывается 2 раза:
        # 1. get_by_id -> SELECT -> scalar_one_or_none -> assignment_mock
        # 2. UPDATE -> rowcount=1
        session.execute = AsyncMock(
            side_effect=[
                make_scalar_one_or_none_result(assignment_mock),
                make_update_result(rowcount=1),
            ]
        )

        repo = AssessmentAssignmentRepository(session)
        result = await repo.update_schedule(
            assignment_id=42,
            date="28.08.2025",
            time="12:00",
            company_id=1,
        )

        assert result is True
        session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_update_schedule_not_found(self):
        """update_schedule() возвращает False, если назначение не найдено."""
        session = AsyncMock()

        # get_by_id -> None
        session.execute.return_value = make_scalar_one_or_none_result(None)

        repo = AssessmentAssignmentRepository(session)
        result = await repo.update_schedule(
            assignment_id=999,
            date="28.08.2025",
            time="12:00",
            company_id=1,
        )

        assert result is False
        session.commit.assert_not_awaited()


# ==========================================================================
# start_session()
# ==========================================================================


class TestStartSession:
    """Начало сессии прохождения аттестации."""

    @pytest.mark.asyncio
    async def test_start_session_success(self):
        """start_session() устанавливает status='in_progress', возвращает True."""
        session = AsyncMock()

        assignment_mock = MagicMock()
        assignment_mock.id = 42

        # execute вызывается 2 раза:
        # 1. get_by_id -> assignment_mock
        # 2. UPDATE status -> rowcount=1
        session.execute = AsyncMock(
            side_effect=[
                make_scalar_one_or_none_result(assignment_mock),
                make_update_result(rowcount=1),
            ]
        )

        repo = AssessmentAssignmentRepository(session)
        result = await repo.start_session(assignment_id=42, company_id=1)

        assert result is True
        session.commit.assert_awaited_once()


# ==========================================================================
# complete_session()
# ==========================================================================


class TestCompleteSession:
    """Завершение сессии аттестации."""

    @pytest.mark.asyncio
    async def test_complete_session_passed(self):
        """complete_session(is_passed=True) -> status='completed', возвращает True."""
        session = AsyncMock()

        assignment_mock = MagicMock()
        assignment_mock.id = 42

        # execute вызывается 2 раза:
        # 1. get_by_id -> assignment_mock
        # 2. UPDATE status -> rowcount=1
        session.execute = AsyncMock(
            side_effect=[
                make_scalar_one_or_none_result(assignment_mock),
                make_update_result(rowcount=1),
            ]
        )

        repo = AssessmentAssignmentRepository(session)
        result = await repo.complete_session(
            assignment_id=42,
            total_score=85.0,
            max_score=100.0,
            is_passed=True,
            company_id=1,
        )

        assert result is True

    @pytest.mark.asyncio
    async def test_complete_session_failed(self):
        """complete_session(is_passed=False) -> status='failed', возвращает True."""
        session = AsyncMock()

        assignment_mock = MagicMock()
        assignment_mock.id = 42

        # execute вызывается 2 раза:
        # 1. get_by_id -> assignment_mock
        # 2. UPDATE status -> rowcount=1
        session.execute = AsyncMock(
            side_effect=[
                make_scalar_one_or_none_result(assignment_mock),
                make_update_result(rowcount=1),
            ]
        )

        repo = AssessmentAssignmentRepository(session)
        result = await repo.complete_session(
            assignment_id=42,
            total_score=30.0,
            max_score=100.0,
            is_passed=False,
            company_id=1,
        )

        assert result is True


# ==========================================================================
# get_status()
# ==========================================================================


class TestGetStatus:
    """Получение статуса аттестации стажера."""

    @pytest.mark.asyncio
    async def test_get_status_not_assigned(self):
        """get_status() возвращает '⛔️', когда аттестация не назначена."""
        session = AsyncMock()

        session.execute.return_value = make_scalar_one_or_none_result(None)

        repo = AssessmentAssignmentRepository(session)
        result = await repo.get_status(trainee_id=10, attestation_id=30, company_id=1)

        assert result == "\u26d4\ufe0f"

    @pytest.mark.asyncio
    async def test_get_status_assigned(self):
        """get_status() возвращает '🟡', когда статус 'assigned'."""
        session = AsyncMock()

        assignment_mock = MagicMock()
        assignment_mock.status = "assigned"

        session.execute.return_value = make_scalar_one_or_none_result(assignment_mock)

        repo = AssessmentAssignmentRepository(session)
        result = await repo.get_status(trainee_id=10, attestation_id=30, company_id=1)

        assert result == "\U0001f7e1"

    @pytest.mark.asyncio
    async def test_get_status_completed(self):
        """get_status() возвращает '✅', когда статус 'completed'."""
        session = AsyncMock()

        assignment_mock = MagicMock()
        assignment_mock.status = "completed"

        session.execute.return_value = make_scalar_one_or_none_result(assignment_mock)

        repo = AssessmentAssignmentRepository(session)
        result = await repo.get_status(trainee_id=10, attestation_id=30, company_id=1)

        assert result == "\u2705"


# ==========================================================================
# cleanup_duplicates()
# ==========================================================================


class TestCleanupDuplicates:
    """Очистка дублирующих назначений аттестаций."""

    @pytest.mark.asyncio
    async def test_cleanup_duplicates(self):
        """cleanup_duplicates() деактивирует старые дубликаты, сохраняя новейший."""
        session = AsyncMock()

        # Создаем 3 мок-назначения для одной аттестации:
        # newest, middle, oldest
        newest = MagicMock()
        newest.id = 3
        newest.attestation_id = 30
        newest.assigned_date = datetime(2025, 8, 3)
        newest.is_active = True

        middle = MagicMock()
        middle.id = 2
        middle.attestation_id = 30
        middle.assigned_date = datetime(2025, 8, 2)
        middle.is_active = True

        oldest = MagicMock()
        oldest.id = 1
        oldest.attestation_id = 30
        oldest.assigned_date = datetime(2025, 8, 1)
        oldest.is_active = True

        session.execute.return_value = make_scalars_result([newest, middle, oldest])

        repo = AssessmentAssignmentRepository(session)
        result = await repo.cleanup_duplicates(user_id=10)

        assert result == 2
        # Newest остается активным
        assert newest.is_active is True
        # Старые деактивированы
        assert middle.is_active is False
        assert oldest.is_active is False
        session.flush.assert_awaited_once()


# ==========================================================================
# get_users_for_exam_assignment()
# ==========================================================================


def make_scalars_unique_result(items: list) -> MagicMock:
    """Создать мок результата session.execute() с scalars().unique().all()."""
    unique_mock = MagicMock()
    unique_mock.all.return_value = items
    scalars_mock = MagicMock()
    scalars_mock.unique.return_value = unique_mock
    result = MagicMock()
    result.scalars.return_value = scalars_mock
    return result


class TestGetUsersForExamAssignment:
    """Получение пользователей для назначения экзамена (исключая стажёров)."""

    @pytest.mark.asyncio
    async def test_returns_users(self):
        """get_users_for_exam_assignment() возвращает список пользователей."""
        session = AsyncMock()

        user1 = MagicMock(id=1, full_name="Рекрутеров Тест")
        user2 = MagicMock(id=2, full_name="Наставников Тест")

        session.execute.return_value = make_scalars_unique_result([user1, user2])

        repo = AssessmentAssignmentRepository(session)
        result = await repo.get_users_for_exam_assignment(company_id=1)

        assert len(result) == 2
        assert user1 in result
        assert user2 in result
        session.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_empty_result(self):
        """get_users_for_exam_assignment() возвращает пустой список, если нет пользователей."""
        session = AsyncMock()
        session.execute.return_value = make_scalars_unique_result([])

        repo = AssessmentAssignmentRepository(session)
        result = await repo.get_users_for_exam_assignment(company_id=1)

        assert result == []

    @pytest.mark.asyncio
    async def test_filter_by_group(self):
        """get_users_for_exam_assignment() с filter_type='group' выполняет запрос."""
        session = AsyncMock()

        user1 = MagicMock(id=1)
        session.execute.return_value = make_scalars_unique_result([user1])

        repo = AssessmentAssignmentRepository(session)
        result = await repo.get_users_for_exam_assignment(company_id=1, filter_type="group", filter_id=5)

        assert len(result) == 1
        session.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_filter_by_object(self):
        """get_users_for_exam_assignment() с filter_type='object' выполняет запрос."""
        session = AsyncMock()

        user1 = MagicMock(id=1)
        session.execute.return_value = make_scalars_unique_result([user1])

        repo = AssessmentAssignmentRepository(session)
        result = await repo.get_users_for_exam_assignment(company_id=1, filter_type="object", filter_id=3)

        assert len(result) == 1
        session.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_filter_by_search(self):
        """get_users_for_exam_assignment() с filter_type='search' выполняет запрос."""
        session = AsyncMock()

        user1 = MagicMock(id=1, full_name="Наставников Тест")
        session.execute.return_value = make_scalars_unique_result([user1])

        repo = AssessmentAssignmentRepository(session)
        result = await repo.get_users_for_exam_assignment(
            company_id=1, filter_type="search", search_query="Наставников"
        )

        assert len(result) == 1
        assert result[0].full_name == "Наставников Тест"

    @pytest.mark.asyncio
    async def test_error_returns_empty_list(self):
        """get_users_for_exam_assignment() возвращает [] при ошибке."""
        session = AsyncMock()
        session.execute.side_effect = Exception("DB error")

        repo = AssessmentAssignmentRepository(session)
        result = await repo.get_users_for_exam_assignment(company_id=1)

        assert result == []


# ==========================================================================
# get_by_id() — проверка загрузки internship_object
# ==========================================================================


class TestGetByIdInternshipObject:
    """Проверка что get_by_id корректно возвращает объект с trainee.internship_object."""

    @pytest.mark.asyncio
    async def test_get_by_id_returns_trainee_with_internship_object(self):
        """get_by_id() возвращает назначение, у которого trainee имеет internship_object."""
        session = AsyncMock()

        internship_obj = MagicMock()
        internship_obj.name = "Кафе Центр"

        trainee = MagicMock()
        trainee.full_name = "Наставников Тест"
        trainee.work_object = MagicMock(name="Кафе Юг")
        trainee.internship_object = internship_obj

        assignment_mock = MagicMock()
        assignment_mock.id = 42
        assignment_mock.trainee = trainee

        session.execute.return_value = make_scalar_one_or_none_result(assignment_mock)

        repo = AssessmentAssignmentRepository(session)
        result = await repo.get_by_id(assignment_id=42, company_id=1)

        assert result is assignment_mock
        assert result.trainee.internship_object.name == "Кафе Центр"

    @pytest.mark.asyncio
    async def test_get_by_id_trainee_without_internship_object(self):
        """get_by_id() корректно работает, когда internship_object = None."""
        session = AsyncMock()

        trainee = MagicMock()
        trainee.full_name = "Наставников Тест"
        trainee.work_object = MagicMock(name="Кафе Юг")
        trainee.internship_object = None

        assignment_mock = MagicMock()
        assignment_mock.id = 42
        assignment_mock.trainee = trainee

        session.execute.return_value = make_scalar_one_or_none_result(assignment_mock)

        repo = AssessmentAssignmentRepository(session)
        result = await repo.get_by_id(assignment_id=42, company_id=1)

        assert result is assignment_mock
        assert result.trainee.internship_object is None


# ==========================================================================
# get_exam_assignments_for_examiner()
# ==========================================================================


class TestGetExamAssignmentsForExaminer:
    """Получение назначенных экзаменов для экзаменатора."""

    @pytest.mark.asyncio
    async def test_returns_assignments(self):
        """get_exam_assignments_for_examiner() возвращает список назначений."""
        session = AsyncMock()

        att1 = MagicMock(id=1, status="assigned")
        att2 = MagicMock(id=2, status="in_progress")

        session.execute.return_value = make_scalars_result([att1, att2])

        repo = AssessmentAssignmentRepository(session)
        result = await repo.get_exam_assignments_for_examiner(examiner_id=20, company_id=1)

        assert len(result) == 2
        assert att1 in result
        assert att2 in result
        session.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_empty_result(self):
        """get_exam_assignments_for_examiner() возвращает [] если нет экзаменов."""
        session = AsyncMock()
        session.execute.return_value = make_scalars_result([])

        repo = AssessmentAssignmentRepository(session)
        result = await repo.get_exam_assignments_for_examiner(examiner_id=20, company_id=1)

        assert result == []

    @pytest.mark.asyncio
    async def test_returns_trainee_with_internship_object(self):
        """Назначение содержит trainee с загруженным internship_object."""
        session = AsyncMock()

        internship_obj = MagicMock()
        internship_obj.name = "Кафе Центр"

        work_obj = MagicMock()
        work_obj.name = "Кафе Юг"

        trainee = MagicMock()
        trainee.full_name = "Тестовый Сдающий"
        trainee.internship_object = internship_obj
        trainee.work_object = work_obj

        att = MagicMock(id=1, status="assigned")
        att.trainee = trainee

        session.execute.return_value = make_scalars_result([att])

        repo = AssessmentAssignmentRepository(session)
        result = await repo.get_exam_assignments_for_examiner(examiner_id=20, company_id=1)

        assert len(result) == 1
        assert result[0].trainee.internship_object.name == "Кафе Центр"
        assert result[0].trainee.work_object.name == "Кафе Юг"

    @pytest.mark.asyncio
    async def test_error_returns_empty_list(self):
        """get_exam_assignments_for_examiner() возвращает [] при ошибке."""
        session = AsyncMock()
        session.execute.side_effect = Exception("DB error")

        repo = AssessmentAssignmentRepository(session)
        result = await repo.get_exam_assignments_for_examiner(examiner_id=20, company_id=1)

        assert result == []


# ==========================================================================
# get_examiners()
# ==========================================================================


class TestGetExaminers:
    """Получение списка экзаменаторов."""

    @pytest.mark.asyncio
    async def test_returns_examiners(self):
        """get_examiners() возвращает список экзаменаторов."""
        session = AsyncMock()

        user1 = MagicMock(id=1, full_name="Руководитель Тест")
        user2 = MagicMock(id=2, full_name="Рекрутер Тест")

        session.execute.return_value = make_scalars_unique_result([user1, user2])

        repo = AssessmentAssignmentRepository(session)
        result = await repo.get_examiners(company_id=1)

        assert len(result) == 2
        session.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_empty_result(self):
        """get_examiners() возвращает [] если нет экзаменаторов."""
        session = AsyncMock()
        session.execute.return_value = make_scalars_unique_result([])

        repo = AssessmentAssignmentRepository(session)
        result = await repo.get_examiners(company_id=1)

        assert result == []

    @pytest.mark.asyncio
    async def test_error_returns_empty_list(self):
        """get_examiners() возвращает [] при ошибке."""
        session = AsyncMock()
        session.execute.side_effect = Exception("DB error")

        repo = AssessmentAssignmentRepository(session)
        result = await repo.get_examiners(company_id=1)

        assert result == []


# ==========================================================================
# get_for_examinee()
# ==========================================================================


class TestGetForExaminee:
    """Получение назначенных экзаменов для сдающего."""

    @pytest.mark.asyncio
    async def test_returns_assignments(self):
        """get_for_examinee() возвращает список назначений экзаменов."""
        session = AsyncMock()

        att1 = MagicMock(id=1, status="assigned")

        session.execute.return_value = make_scalars_result([att1])

        repo = AssessmentAssignmentRepository(session)
        result = await repo.get_for_examinee(examinee_id=10, company_id=1)

        assert len(result) == 1
        session.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_empty_result(self):
        """get_for_examinee() возвращает [] если нет назначений."""
        session = AsyncMock()
        session.execute.return_value = make_scalars_result([])

        repo = AssessmentAssignmentRepository(session)
        result = await repo.get_for_examinee(examinee_id=10, company_id=1)

        assert result == []

    @pytest.mark.asyncio
    async def test_error_returns_empty_list(self):
        """get_for_examinee() возвращает [] при ошибке."""
        session = AsyncMock()
        session.execute.side_effect = Exception("DB error")

        repo = AssessmentAssignmentRepository(session)
        result = await repo.get_for_examinee(examinee_id=10, company_id=1)

        assert result == []


# ==========================================================================
# get_users_for_exam_assignment() filter_type="role"
# ==========================================================================


class TestGetUsersForExamAssignmentByRole:
    """Фильтрация сдающих по ролям (новая опция из ТЗ)."""

    @pytest.mark.asyncio
    async def test_filter_by_role(self):
        """filter_type='role' выполняет запрос и возвращает пользователей роли."""
        session = AsyncMock()
        user1 = MagicMock(id=1, full_name="Руководитель Иванов")
        session.execute.return_value = make_scalars_unique_result([user1])

        repo = AssessmentAssignmentRepository(session)
        result = await repo.get_users_for_exam_assignment(company_id=1, filter_type="role", filter_id=2)

        assert len(result) == 1
        session.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_filter_by_role_without_id_falls_back(self):
        """Если filter_id=None, фильтр по роли не применяется (возвращаем всех без стажёров)."""
        session = AsyncMock()
        session.execute.return_value = make_scalars_unique_result([])

        repo = AssessmentAssignmentRepository(session)
        result = await repo.get_users_for_exam_assignment(company_id=1, filter_type="role", filter_id=None)

        assert result == []
        session.execute.assert_awaited_once()


# ==========================================================================
# get_examiners_for_assignment() — экзаменаторы с фильтрами
# ==========================================================================


class TestGetExaminersForAssignment:
    """Фильтрация экзаменаторов (whitelist ролей: Руководитель, Сотрудник, Рекрутер)."""

    @pytest.mark.asyncio
    async def test_returns_all_examiners(self):
        """Без фильтра возвращает всех экзаменаторов."""
        session = AsyncMock()
        user1 = MagicMock(id=1, full_name="Руководитель Тест")
        user2 = MagicMock(id=2, full_name="Сотрудник Тест")
        user3 = MagicMock(id=3, full_name="Рекрутер Тест")
        session.execute.return_value = make_scalars_unique_result([user1, user2, user3])

        repo = AssessmentAssignmentRepository(session)
        result = await repo.get_examiners_for_assignment(company_id=1)

        assert len(result) == 3
        session.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_filter_by_group(self):
        session = AsyncMock()
        session.execute.return_value = make_scalars_unique_result([MagicMock(id=1)])

        repo = AssessmentAssignmentRepository(session)
        result = await repo.get_examiners_for_assignment(company_id=1, filter_type="group", filter_id=5)

        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_filter_by_object(self):
        session = AsyncMock()
        session.execute.return_value = make_scalars_unique_result([MagicMock(id=1)])

        repo = AssessmentAssignmentRepository(session)
        result = await repo.get_examiners_for_assignment(company_id=1, filter_type="object", filter_id=3)

        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_filter_by_role(self):
        session = AsyncMock()
        session.execute.return_value = make_scalars_unique_result([MagicMock(id=1)])

        repo = AssessmentAssignmentRepository(session)
        result = await repo.get_examiners_for_assignment(company_id=1, filter_type="role", filter_id=2)

        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_filter_by_search(self):
        session = AsyncMock()
        user = MagicMock(id=1, full_name="Рекрутеров Тест")
        session.execute.return_value = make_scalars_unique_result([user])

        repo = AssessmentAssignmentRepository(session)
        result = await repo.get_examiners_for_assignment(company_id=1, filter_type="search", search_query="Рекрутеров")

        assert len(result) == 1
        assert result[0].full_name == "Рекрутеров Тест"

    @pytest.mark.asyncio
    async def test_error_returns_empty_list(self):
        session = AsyncMock()
        session.execute.side_effect = Exception("DB error")

        repo = AssessmentAssignmentRepository(session)
        result = await repo.get_examiners_for_assignment(company_id=1)

        assert result == []

    @pytest.mark.asyncio
    async def test_legacy_get_examiners_delegates_to_for_assignment(self):
        """get_examiners() — тонкая обёртка над get_examiners_for_assignment()."""
        session = AsyncMock()
        session.execute.return_value = make_scalars_unique_result([MagicMock(id=1), MagicMock(id=2)])

        repo = AssessmentAssignmentRepository(session)
        result = await repo.get_examiners(company_id=1)

        assert len(result) == 2
        session.execute.assert_awaited_once()
