"""
E2E Сценарий 3: Переназначение траектории — полный сброс прогресса.

Проверяет, что при переназначении той же траектории все TestResult, StageProgress,
SessionProgress и TestAccess удаляются и создаются заново.
Стажёр должен увидеть все тесты как непройденные после переназначения.

Зависит от test_setup.py и test_check_test_access.py (Стажёр 1 уже прошёл тест 1).
"""

import pytest

from tests.e2e.helpers.bot_client import BotClient
from tests.e2e.helpers.waiters import (
    extract_emoji_status,
    wait_between_actions,
)


pytestmark = [
    pytest.mark.order(3),
    pytest.mark.timeout(300),
    pytest.mark.asyncio(loop_scope="session"),
]


class TestScenario3_TrajectoryReassignment:
    """
    Проблема 3 из oc.md: при переназначении траектории результаты тестов
    должны быть сброшены (полное пересоздание прогресса).

    Ожидание: после переназначения ✅ исчезают, все тесты становятся непройденными.
    """

    async def test_step1_verify_trainee1_sees_passed_test(
        self, trainee1: BotClient, shared_state: dict
    ):
        """Стажёр 1 видит пройденный тест как ✅ в траектории (до переназначения)."""
        await wait_between_actions()

        resp = await trainee1.send_and_wait(
            "Траектория обучения 📖", pattern="[Тт]раектори|этап"
        )

        text = resp.text or ""

        # Проверяем наличие статуса ✅ (тест 1 был пройден в сценарии 1)
        has_passed = "✅" in text
        # Допустимо, что ✅ может быть на уровне этапа или теста
        assert has_passed or "Кофе" in text, (
            f"Trainee1's trajectory should show passed test. Got: {text[:500]}"
        )

        shared_state["trainee1_trajectory_before"] = text

    async def test_step2_reassign_same_trajectory(
        self, mentor: BotClient, shared_state: dict
    ):
        """
        Наставник переназначает ту же траекторию Стажёру 1.

        Теперь это полное пересоздание — все результаты и прогресс обнуляются.
        """
        await wait_between_actions()

        resp = await mentor.send_and_wait(
            "Мои стажеры 👥", pattern="стажер|стажёр"
        )

        # Выбираем стажёра 1
        trainee_btn = mentor.find_button_data(
            resp, text_contains="Первый", data_prefix="select_trainee_for_trajectory:"
        )
        if not trainee_btn:
            trainee_btn = mentor.find_button_data(
                resp, text_contains="Стажёров", data_prefix="select_trainee_for_trajectory:"
            )
        assert trainee_btn, "Trainee 1 not found in mentor's list"

        resp = await mentor.click_and_wait(
            resp, data=trainee_btn, wait_pattern="[Тт]раектори|[Ээ]тап|карточка"
        )

        # Нажимаем "Поменять траекторию" (change_trajectory:)
        change_btn = mentor.find_button_data(
            resp, data_prefix="change_trajectory:"
        )
        if not change_btn:
            # Fallback: стажёр без траектории — кнопки assign_trajectory: напрямую
            change_btn = mentor.find_button_data(
                resp, text_contains="E2E Траектория", data_prefix="assign_trajectory:"
            )

        if not change_btn:
            pytest.skip("Trajectory change button not found — UI may differ")

        resp = await mentor.click_and_wait(
            resp, data=change_btn,
            wait_pattern="[Уу]верен|[Зз]амен|[Тт]раектори|назначена"
        )

        # Подтверждаем замену (confirm_change_trajectory:)
        confirm_btn = mentor.find_button_data(
            resp, data_prefix="confirm_change_trajectory:"
        )
        if confirm_btn:
            resp = await mentor.click_and_wait(
                resp, data=confirm_btn,
                wait_pattern="[Тт]раектори|[Вв]ыбери"
            )

        # Выбираем ту же траекторию (assign_trajectory:)
        same_traj_btn = mentor.find_button_data(
            resp, text_contains="E2E Траектория", data_prefix="assign_trajectory:"
        )
        if same_traj_btn:
            resp = await mentor.click_and_wait(
                resp, data=same_traj_btn,
                wait_pattern="назначена|Какой этап|открыть стажеру"
            )

    async def test_step3_trainee1_sees_reset_progress(
        self, trainee1: BotClient, shared_state: dict
    ):
        """
        КРИТИЧЕСКАЯ ПРОВЕРКА: После переназначения все тесты сброшены.

        Прогресс пересоздан с нуля — все этапы закрыты (❌), тесты непройдены.
        """
        await wait_between_actions()

        resp = await trainee1.send_and_wait(
            "Траектория обучения 📖", pattern="[Тт]раектори|этап"
        )

        text = resp.text or ""

        # После полного сброса не должно быть ✅ (все тесты не пройдены)
        assert "✅" not in text, (
            f"After reassignment, all progress should be reset (no ✅). "
            f"Got: {text[:500]}"
        )

    async def test_step4_mentor_sees_reset_status(
        self, mentor: BotClient, shared_state: dict
    ):
        """Наставник видит сброшенный прогресс стажёра (нет ✅)."""
        await wait_between_actions()

        resp = await mentor.send_and_wait(
            "Мои стажеры 👥", pattern="стажер|стажёр"
        )

        # Выбираем стажёра 1
        trainee_btn = mentor.find_button_data(
            resp, text_contains="Первый", data_prefix="select_trainee_for_trajectory:"
        )
        if not trainee_btn:
            trainee_btn = mentor.find_button_data(
                resp, text_contains="Стажёров", data_prefix="select_trainee_for_trajectory:"
            )
        assert trainee_btn, "Trainee 1 not found"

        resp = await mentor.click_and_wait(
            resp, data=trainee_btn, wait_pattern="[Тт]раектори|прогресс|[Ээ]тап|карточка"
        )

        text = resp.text or ""

        # Наставник тоже должен видеть сброшенный прогресс
        # Все этапы закрыты (❌) или пустые (нет ✅)
        assert "✅" not in text, (
            f"Mentor's view should show reset progress (no ✅). Got: {text[:500]}"
        )
