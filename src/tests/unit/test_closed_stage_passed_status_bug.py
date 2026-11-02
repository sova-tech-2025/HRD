"""
Регрессия: пройденный этап, который наставник закрыл, выглядел непройденным.

Текст траектории считал статусы только по `is_opened`: у закрытого этапа все
тесты рисовались ❌, а сам этап — «Доступ: закрыт ❌», хотя стажёр их сдал и
`TraineeStageProgress.is_completed` стоял True. Кнопки управления этапами в том
же сообщении строятся по `is_completed` и показывали «✅ Этап N завершен» —
на одном экране получалось противоречие.
"""

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from bot.handlers.training import mentorship, trainee_trajectory
from bot.utils.formatters import trajectory
from bot.utils.formatters.test_progress import get_test_status_icon

PASSED_RESULTS = [
    SimpleNamespace(
        test_id=1, is_passed=True, created_date=datetime(2026, 9, 10, 12, 0), score=10, max_possible_score=10
    )
]


def _closed_completed_stage():
    """Этап пройден (is_completed=True), но закрыт наставником."""
    test = SimpleNamespace(id=1, name="Скидки")
    learning_session = SimpleNamespace(id=1, name="День 3. Отчетность", order_number=1, tests=[test])
    stage = SimpleNamespace(id=1, name="Практика в пекарне", order_number=1)
    stage_progress = SimpleNamespace(
        id=1,
        stage=stage,
        stage_id=1,
        is_opened=False,
        is_completed=True,
        session_progress=[SimpleNamespace(session=learning_session)],
    )
    trainee_path = SimpleNamespace(id=7, trainee_id=42, learning_path=SimpleNamespace(name="Бариста", attestation=None))
    return trainee_path, [stage_progress]


class TestGetTestStatusIcon:
    def test_passed_test_stays_passed_in_closed_stage(self):
        """Прохождение теста — факт, закрытие этапа его не отменяет."""
        assert get_test_status_icon(is_passed=True, is_stage_opened=False) == "✅"

    def test_not_passed_in_closed_stage_is_closed(self):
        assert get_test_status_icon(is_passed=False, is_stage_opened=False) == "❌"

    def test_not_passed_in_opened_stage_is_available(self):
        assert get_test_status_icon(is_passed=False, is_stage_opened=True) == "⏳"


class TestMentorSeesClosedStageAsPassed:
    async def test_mentorship_generator(self):
        trainee_path, stages_progress = _closed_completed_stage()

        text = await mentorship.generate_trajectory_progress_with_attestation_status(
            MagicMock(), trainee_path, stages_progress, PASSED_RESULTS
        )

        assert "этап пройден ✅" in text
        assert "закрыт ❌" not in text
        assert "✅ Тест: Скидки" in text

    async def test_formatters_generator(self):
        trainee_path, stages_progress = _closed_completed_stage()

        text = await trajectory.generate_trajectory_progress_with_attestation_status(
            MagicMock(), trainee_path, stages_progress, PASSED_RESULTS
        )

        assert "✅<b>Этап 1:</b> Практика в пекарне" in text
        assert "✅<b>Тест 1:</b> Скидки" in text


class TestTraineeSeesClosedStageAsPassed:
    async def test_build_trajectory_text(self):
        trainee_path, stages_progress = _closed_completed_stage()
        user = SimpleNamespace(id=42, company_id=1)

        with (
            patch.object(trainee_trajectory, "get_trainee_stage_progress", AsyncMock(return_value=stages_progress)),
            patch.object(
                trainee_trajectory,
                "get_stage_session_progress",
                AsyncMock(return_value=stages_progress[0].session_progress),
            ),
            patch.object(trainee_trajectory, "get_user_test_result", AsyncMock(return_value=PASSED_RESULTS[0])),
            patch.object(trainee_trajectory, "format_attestation_status", AsyncMock(return_value="")),
        ):
            text, _ = await trainee_trajectory.build_trajectory_text(MagicMock(), user, trainee_path, company_id=1)

        assert "этап пройден ✅" in text
        assert "закрыт ❌" not in text
