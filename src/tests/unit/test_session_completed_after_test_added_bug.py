"""
Тест бага: добавление теста в сессию через редактор не сбрасывает is_completed.

Баг: Стажёр видит "Нет открытых сессий для прохождения" хотя этап открыт.

Шаги воспроизведения:
1. Сессия имеет 1 тест (test_A)
2. Стажёр проходит test_A → сессия помечена is_completed=True (1/1 тестов)
3. Рекрутер добавляет test_B в сессию через редактор траекторий
4. is_completed НЕ сбрасывается → сессия всё ещё "завершена"
5. Стажёр кликает на этап → фильтр `not sp.is_completed` убирает сессию
6. Результат: "Нет открытых сессий для прохождения"

Ожидание: add_test_to_session_from_editor должен сбросить is_completed=False
для всех TraineeSessionProgress, ссылающихся на эту сессию.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def make_scalar_result(value):
    """Мок результата session.execute() с scalar_one_or_none()."""
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    return result


def make_scalars_all_result(values):
    """Мок результата session.execute() с scalars().all()."""
    result = MagicMock()
    scalars_mock = MagicMock()
    scalars_mock.all.return_value = values
    result.scalars.return_value = scalars_mock
    return result


def make_first_result(value):
    """Мок результата session.execute() с first()."""
    result = MagicMock()
    result.first.return_value = value
    return result


def make_scalar_value(value):
    """Мок результата session.execute() с scalar()."""
    result = MagicMock()
    result.scalar.return_value = value
    return result


class TestAddTestToSessionResetsCompleted:
    """При добавлении теста в сессию is_completed стажёров должен сбрасываться."""

    @pytest.mark.asyncio
    async def test_add_test_resets_session_completed_flag(self):
        """
        Баг: add_test_to_session_from_editor добавляет тест в session_tests,
        но НЕ сбрасывает TraineeSessionProgress.is_completed и
        TraineeStageProgress.is_completed для стажёров с этой сессией.

        Тест проверяет, что среди SQL-операций есть UPDATE trainee_session_progress
        SET is_completed=false для сессии, в которую добавлен тест.
        """
        from bot.database.db import add_test_to_session_from_editor

        session = AsyncMock()

        # Мокаем данные
        test_mock = MagicMock()
        test_mock.id = 99
        test_mock.name = "Новый тест"
        test_mock.company_id = 1

        learning_session_mock = MagicMock()
        learning_session_mock.id = 340
        learning_session_mock.stage_id = 184

        stage_mock = MagicMock()
        stage_mock.id = 184
        stage_mock.learning_path_id = 122

        learning_path_mock = MagicMock()
        learning_path_mock.id = 122
        learning_path_mock.company_id = 1

        # С patch get_test_by_id и get_learning_path_by_id,
        # session.execute вызывается для:
        # 1. select(LearningSession) → сессия найдена
        # 2. select(LearningStage) → этап найден
        # 3. select(session_tests) → тест ещё не добавлен (existing check)
        # 4. select(func.max(order_number)) → max_order = 1
        # 5. insert(session_tests) → добавление
        # 6+ UPDATE trainee_session_progress (ожидаемый фикс)
        # 7+ UPDATE trainee_stage_progress (ожидаемый фикс)

        execute_results = [
            make_scalar_result(learning_session_mock),  # select LearningSession
            make_scalar_result(stage_mock),             # select LearningStage
            make_first_result(None),                    # existing check → not found
            make_scalar_value(1),                       # max order_number
            MagicMock(),                                # insert session_tests
            MagicMock(),                                # UPDATE trainee_session_progress (фикс)
            MagicMock(),                                # UPDATE trainee_stage_progress (фикс)
        ]

        call_count = 0
        original_results = list(execute_results)

        async def mock_execute(stmt, *args, **kwargs):
            nonlocal call_count
            if call_count < len(original_results):
                result = original_results[call_count]
                call_count += 1
                return result
            call_count += 1
            return MagicMock()

        session.execute = AsyncMock(side_effect=mock_execute)
        session.commit = AsyncMock()

        # Патчим get_test_by_id и get_learning_path_by_id чтобы не усложнять моки
        with patch("bot.database.db.get_test_by_id", new_callable=AsyncMock, return_value=test_mock), \
             patch("bot.database.db.get_learning_path_by_id", new_callable=AsyncMock, return_value=learning_path_mock):

            result = await add_test_to_session_from_editor(
                session=session,
                session_id=340,
                test_id=99,
                company_id=1,
            )

        assert result is True, "add_test_to_session_from_editor должен вернуть True"

        # Собираем все SQL-операции
        executed_stmts = []
        for call in session.execute.call_args_list:
            stmt = call.args[0] if call.args else None
            if stmt is not None and hasattr(stmt, "compile"):
                try:
                    sql_str = str(stmt)
                    executed_stmts.append(sql_str)
                except Exception:
                    pass

        # Проверяем: должен быть UPDATE trainee_session_progress SET is_completed=false
        session_reset_found = any(
            "trainee_session_progress" in sql and "UPDATE" in sql
            for sql in executed_stmts
        )

        assert session_reset_found, (
            "БАГ: add_test_to_session_from_editor НЕ сбрасывает "
            "TraineeSessionProgress.is_completed при добавлении нового теста.\n"
            "Это приводит к тому, что стажёр видит 'Нет открытых сессий'.\n"
            "Выполненные SQL-операции:\n" + "\n".join(f"  - {sql[:150]}" for sql in executed_stmts)
        )

    @pytest.mark.asyncio
    async def test_add_test_resets_stage_completed_flag(self):
        """
        При добавлении теста в сессию, если этап был помечен как завершённый,
        TraineeStageProgress.is_completed тоже должен сбрасываться.
        """
        from bot.database.db import add_test_to_session_from_editor

        session = AsyncMock()

        test_mock = MagicMock()
        test_mock.id = 99
        test_mock.company_id = 1

        learning_session_mock = MagicMock()
        learning_session_mock.id = 340
        learning_session_mock.stage_id = 184

        stage_mock = MagicMock()
        stage_mock.id = 184
        stage_mock.learning_path_id = 122

        learning_path_mock = MagicMock()
        learning_path_mock.id = 122
        learning_path_mock.company_id = 1

        execute_results = [
            make_scalar_result(learning_session_mock),  # select LearningSession
            make_scalar_result(stage_mock),             # select LearningStage
            make_first_result(None),                    # existing check
            make_scalar_value(1),                       # max order
            MagicMock(),                                # insert
            MagicMock(),                                # UPDATE session progress
            MagicMock(),                                # UPDATE stage progress
        ]

        call_count = 0
        original_results = list(execute_results)

        async def mock_execute(stmt, *args, **kwargs):
            nonlocal call_count
            if call_count < len(original_results):
                result = original_results[call_count]
                call_count += 1
                return result
            call_count += 1
            return MagicMock()

        session.execute = AsyncMock(side_effect=mock_execute)
        session.commit = AsyncMock()

        with patch("bot.database.db.get_test_by_id", new_callable=AsyncMock, return_value=test_mock), \
             patch("bot.database.db.get_learning_path_by_id", new_callable=AsyncMock, return_value=learning_path_mock):

            result = await add_test_to_session_from_editor(
                session=session,
                session_id=340,
                test_id=99,
                company_id=1,
            )

        assert result is True

        executed_stmts = []
        for call in session.execute.call_args_list:
            stmt = call.args[0] if call.args else None
            if stmt is not None and hasattr(stmt, "compile"):
                try:
                    sql_str = str(stmt)
                    executed_stmts.append(sql_str)
                except Exception:
                    pass

        # Должен быть UPDATE trainee_stage_progress SET is_completed=false
        stage_reset_found = any(
            "trainee_stage_progress" in sql and "UPDATE" in sql
            for sql in executed_stmts
        )

        assert stage_reset_found, (
            "БАГ: add_test_to_session_from_editor НЕ сбрасывает "
            "TraineeStageProgress.is_completed при добавлении нового теста в сессию.\n"
            "Выполненные SQL-операции:\n" + "\n".join(f"  - {sql[:150]}" for sql in executed_stmts)
        )


class TestTraineeSeesNoOpenSessions:
    """Воспроизведение бага: стажёр видит 'Нет открытых сессий'."""

    @pytest.mark.asyncio
    async def test_completed_session_filtered_out_from_available(self):
        """
        Прямое воспроизведение бага:
        Сессия is_completed=True (была завершена с 1 тестом),
        затем в неё добавлен новый тест.
        Фильтр `sp.is_opened and not sp.is_completed` исключает сессию.
        """
        # Имитируем данные как в БД: сессия завершена но тесты не все пройдены
        session_progress = MagicMock()
        session_progress.is_opened = True
        session_progress.is_completed = True  # Баг: не сброшено после добавления теста

        sessions_progress = [session_progress]

        # Фильтр из trainee_trajectory.py:385
        available_sessions = [
            sp for sp in sessions_progress
            if sp.is_opened and not sp.is_completed
        ]

        # Это показывает баг: сессия отфильтрована, стажёр ничего не видит
        assert len(available_sessions) == 0, (
            "Подтверждение бага: завершённая сессия отфильтровывается, "
            "даже если в неё добавлены новые тесты"
        )

    @pytest.mark.asyncio
    async def test_after_fix_session_available_when_new_test_added(self):
        """
        После фикса: если в сессию добавлен новый тест,
        is_completed должен быть False → сессия доступна стажёру.
        """
        session_progress = MagicMock()
        session_progress.is_opened = True
        session_progress.is_completed = False  # Ожидание после фикса

        sessions_progress = [session_progress]

        available_sessions = [
            sp for sp in sessions_progress
            if sp.is_opened and not sp.is_completed
        ]

        assert len(available_sessions) == 1, (
            "После фикса сессия с новыми непройденными тестами "
            "должна быть доступна стажёру"
        )
