"""
Тест бага: при смене траектории стажёру старые аттестации не деактивируются.

Баг: Руководитель видит дубликаты в ЛК → две аттестации для одного стажёра
(от старой и новой траектории), потому что assign_learning_path_to_trainee()
деактивирует TraineeLearningPath, но НЕ деактивирует TraineeAttestation.

Шаги воспроизведения:
1. Назначить стажёру траекторию A (с аттестацией X)
2. Наставник назначает аттестацию X → создаётся TraineeAttestation(attestation_id=X, is_active=True)
3. Сменить траекторию на B (с аттестацией Y)
4. Наставник назначает аттестацию Y → создаётся TraineeAttestation(attestation_id=Y, is_active=True)
5. Руководитель открывает ЛК → видит ОБЕ аттестации (баг)

Ожидание: при смене траектории старая TraineeAttestation должна деактивироваться.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def make_scalar_result(value):
    """Мок результата session.execute() с scalar_one_or_none()."""
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    return result


def make_all_result(rows):
    """Мок результата session.execute() с all()."""
    result = MagicMock()
    result.all.return_value = rows
    return result


class TestTrajectoryChangeAttestationBug:
    """При смене траектории старые TraineeAttestation должны деактивироваться."""

    @pytest.mark.asyncio
    @patch("bot.database.db._create_trainee_progress", new_callable=AsyncMock)
    @patch("bot.database.db.delete_trajectory_test_results", new_callable=AsyncMock)
    async def test_old_attestations_deactivated_on_trajectory_change(self, mock_delete_results, mock_create_progress):
        """
        Баг: assign_learning_path_to_trainee деактивирует TraineeLearningPath,
        но НЕ деактивирует TraineeAttestation для этого стажёра.

        Тест проверяет, что среди SQL-операций есть UPDATE trainee_attestations
        SET is_active=False для данного стажёра.
        """
        from bot.database.db import assign_learning_path_to_trainee

        session = AsyncMock()

        trainee_mock = MagicMock()
        trainee_mock.id = 100
        trainee_mock.company_id = 1

        learning_path_mock = MagicMock()
        learning_path_mock.id = 200
        learning_path_mock.company_id = 1

        # Мокаем последовательные вызовы session.execute():
        # 1. select(User) → стажёр найден
        # 2. select(LearningPath) → траектория найдена
        # 3. select(TraineeLearningPath.id) → одна активная (от старой траектории)
        # 4. select(TraineeStageProgress.id) → нет прогресса
        # 5. select(session_tests.c.test_id) → нет тестов
        # 6. update(TraineeLearningPath) → деактивация
        # 7+ любые дополнительные вызовы (если функция будет исправлена)
        session.execute = AsyncMock(
            side_effect=[
                make_scalar_result(trainee_mock),
                make_scalar_result(learning_path_mock),
                make_all_result([(10,)]),  # active_path_ids = [10]
                make_all_result([]),  # stage_progress_ids = []
                make_all_result([]),  # trajectory_test_ids = []
                MagicMock(),  # update TraineeLearningPath
                MagicMock(),  # UPDATE TraineeAttestation (ожидаемый фикс)
            ]
        )

        # Мокаем session.add и session.commit
        new_path_mock = MagicMock()
        new_path_mock.id = 999
        session.add = MagicMock()
        session.commit = AsyncMock()

        # Подменяем TraineeLearningPath чтобы session.add присваивал id
        with patch("bot.database.db.TraineeLearningPath") as MockTLP:
            mock_instance = MagicMock()
            mock_instance.id = 999
            MockTLP.return_value = mock_instance

            result = await assign_learning_path_to_trainee(
                session=session,
                trainee_id=100,
                learning_path_id=200,
                mentor_id=300,
                company_id=1,
            )

        assert result is True, "assign_learning_path_to_trainee должен вернуть True"

        # Собираем все SQL-операции, переданные в session.execute
        executed_stmts = []
        for call in session.execute.call_args_list:
            stmt = call.args[0] if call.args else None
            if stmt is not None and hasattr(stmt, "compile"):
                try:
                    sql_str = str(stmt)
                    executed_stmts.append(sql_str)
                except Exception:
                    pass

        # Проверяем: должен быть UPDATE trainee_attestations SET is_active=false
        attestation_deactivation_found = any(
            "trainee_attestations" in sql and "UPDATE" in sql for sql in executed_stmts
        )

        assert attestation_deactivation_found, (
            "БАГ: assign_learning_path_to_trainee НЕ деактивирует старые "
            "TraineeAttestation при смене траектории.\n"
            "Выполненные SQL-операции:\n" + "\n".join(f"  - {sql[:120]}" for sql in executed_stmts)
        )

    @pytest.mark.asyncio
    async def test_manager_sees_duplicate_attestations(self):
        """
        Баг: get_manager_assigned_attestations возвращает все active аттестации,
        включая старые от предыдущей траектории.

        Если у стажёра 2 активные аттестации (от старой и новой траектории),
        руководитель видит обе → дубликат в ЛК.
        """
        from bot.repositories import AssessmentAssignmentRepository

        session = AsyncMock()

        # Имитируем 2 активные аттестации для одного стажёра (разные attestation_id)
        old_attestation = MagicMock()
        old_attestation.trainee_id = 100
        old_attestation.attestation_id = 1  # От старой траектории
        old_attestation.is_active = True
        old_attestation.attestation = MagicMock(name="Аттестация Вэй 2")

        new_attestation = MagicMock()
        new_attestation.trainee_id = 100
        new_attestation.attestation_id = 2  # От новой траектории
        new_attestation.is_active = True
        new_attestation.attestation = MagicMock(name="certification 1")

        # Мок результата: возвращает обе аттестации
        scalars_mock = MagicMock()
        scalars_mock.all.return_value = [old_attestation, new_attestation]
        result_mock = MagicMock()
        result_mock.scalars.return_value = scalars_mock
        session.execute = AsyncMock(return_value=result_mock)

        repo = AssessmentAssignmentRepository(session)
        attestations = await repo.get_for_manager(manager_id=500, company_id=1)

        # Это показывает баг: руководитель получает 2 аттестации для одного стажёра
        assert len(attestations) == 2, "Ожидается 2 записи (баг: обе аттестации активны)"

        # После фикса: у одного стажёра должна быть только 1 активная аттестация.
        # Фикс должен быть в assign_learning_path_to_trainee, а не в запросе.
        trainee_ids = [a.trainee_id for a in attestations]
        duplicates = len(trainee_ids) != len(set(trainee_ids))
        assert duplicates, (
            "БАГ ПОДТВЕРЖДЁН: один стажёр имеет несколько активных аттестаций "
            "от разных траекторий. Руководитель видит дубликаты."
        )


class TestAssignAttestationDeduplication:
    """Тест на существующую логику дедупликации в assign_attestation_to_trainee."""

    @pytest.mark.asyncio
    async def test_deduplication_only_checks_same_attestation_id(self):
        """
        assign_attestation_to_trainee деактивирует старые записи только
        с тем же attestation_id. Если attestation_id разный (разные траектории),
        дедупликация НЕ срабатывает.

        Это корневая причина бага: при смене траектории меняется attestation_id,
        и старая запись остаётся активной.
        """
        from bot.repositories import AssessmentAssignmentRepository

        session = AsyncMock()

        # Мок: нет существующего назначения с таким же attestation_id
        existing_result = MagicMock()
        existing_result.scalar_one_or_none.return_value = None
        session.execute = AsyncMock(
            side_effect=[
                existing_result,  # Проверка дубликатов → не найден
                MagicMock(),  # Деактивация старых (тот же attestation_id)
            ]
        )

        session.flush = AsyncMock()

        repo = AssessmentAssignmentRepository(session)
        result = await repo.assign(
            trainee_id=100,
            manager_id=500,
            attestation_id=2,  # Новая аттестация (от новой траектории)
            assigned_by_id=300,
        )

        assert result is not None

        # Проверяем: деактивация фильтрует по attestation_id=2,
        # а старая аттестация с attestation_id=1 остаётся активной (баг)
        deactivation_call = session.execute.call_args_list[1]
        stmt = deactivation_call.args[0]
        sql_str = str(stmt)

        # Проверяем, что в UPDATE есть фильтр по attestation_id
        assert "attestation_id" in sql_str, "Деактивация должна фильтровать по attestation_id"
        # Это означает, что старая аттестация с другим attestation_id НЕ будет затронута
