"""
Регрессия: наставник видел у стажёра проваленный тест, который тот уже пересдал.

get_user_test_results() отдаёт попытки от новых к старым, а генераторы прогресса
строили словарь `{test_id: result}` перезаписью — в нём оставалась самая старая
попытка. Стажёр (get_user_test_result — новейшая попытка) видел ✅ и «Этап завершен!»,
наставник — ⏳ и «Пройдено: N/M».
"""

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

from bot.handlers.training import mentorship
from bot.utils.formatters import trajectory
from bot.utils.formatters.test_progress import latest_results_by_test


def _result(test_id, is_passed, created_date):
    return SimpleNamespace(
        test_id=test_id, is_passed=is_passed, created_date=created_date, score=10, max_possible_score=10
    )


# Порядок как у get_user_test_results: created_date DESC
RETAKEN_RESULTS = [
    _result(1, True, datetime(2026, 9, 10, 12, 0)),
    _result(1, False, datetime(2026, 9, 10, 11, 0)),
]


def _trainee_path():
    test = SimpleNamespace(id=1, name="Скидки")
    learning_session = SimpleNamespace(id=1, name="День 3. Отчетность", order_number=1, tests=[test])
    stage = SimpleNamespace(id=1, name="Практика", order_number=1)
    stage_progress = SimpleNamespace(
        stage=stage,
        is_opened=True,
        is_completed=False,
        session_progress=[SimpleNamespace(session=learning_session)],
    )
    trainee_path = SimpleNamespace(trainee_id=42, learning_path=SimpleNamespace(name="Бариста", attestation=None))
    return trainee_path, [stage_progress]


class TestLatestResultsByTest:
    def test_newest_attempt_wins_desc_order(self):
        assert latest_results_by_test(RETAKEN_RESULTS)[1].is_passed is True

    def test_newest_attempt_wins_asc_order(self):
        assert latest_results_by_test(list(reversed(RETAKEN_RESULTS)))[1].is_passed is True

    def test_empty(self):
        assert latest_results_by_test(None) == {}
        assert latest_results_by_test([]) == {}


class TestMentorTrajectoryShowsRetakenTest:
    async def test_mentorship_generator(self):
        trainee_path, stages_progress = _trainee_path()

        text = await mentorship.generate_trajectory_progress_with_attestation_status(
            MagicMock(), trainee_path, stages_progress, RETAKEN_RESULTS
        )

        assert "✅ Тест: Скидки" in text
        assert "Этап завершен!" in text

    async def test_formatters_generator(self):
        trainee_path, stages_progress = _trainee_path()

        text = await trajectory.generate_trajectory_progress_with_attestation_status(
            MagicMock(), trainee_path, stages_progress, RETAKEN_RESULTS
        )

        assert "❌" not in text
        assert "⏳" not in text
