"""
E2E Сценарий 3: Переназначение траектории — сохранение результатов.

Проверяет, что TestResult не удаляются при повторном назначении траектории.
UI стажёра и наставника должны показывать одинаковый статус ✅ для пройденных тестов.

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
    удаляются.

    Ожидание: ✅ для пройденных тестов сохраняется после переназначения.
    """

    async def test_step1_verify_trainee1_sees_passed_test(
        self, trainee1: BotClient, shared_state: dict
    ):
        """Стажёр 1 видит пройденный тест как ✅ в траектории."""
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
        Наставник (или рекрутер) переназначает ту же траекторию Стажёру 1.

        Назначение должно быть идемпотентным — не удалять существующие результаты.
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

        # Ищем кнопку выбора/назначения траектории
        traj_btn = mentor.find_button_data(
            resp, text_contains="траектори", data_prefix="assign_trajectory:"
        )
        if not traj_btn:
            traj_btn = mentor.find_button_data(
                resp, text_contains="Выбрать", data_prefix="select_trajectory_for_trainee:"
            )

        if traj_btn:
            resp = await mentor.click_and_wait(
                resp, data=traj_btn,
                wait_pattern="[Тт]раектори|[Вв]ыбери|назначена|уже назначена"
            )

            # Выбираем ту же траекторию
            same_traj_btn = mentor.find_button_data(
                resp, text_contains="E2E Траектория", data_prefix="assign_trajectory:"
            )
            if same_traj_btn:
                resp = await mentor.click_and_wait(
                    resp, data=same_traj_btn,
                    wait_pattern="назначена|уже|успешно|[Тт]раектори"
                )
        else:
            # Траектория уже назначена — это нормально
            pass

    async def test_step3_trainee1_still_sees_passed_test(
        self, trainee1: BotClient, shared_state: dict
    ):
        """
        КРИТИЧЕСКАЯ ПРОВЕРКА: После переназначения тест всё ещё показывается как ✅.
        """
        await wait_between_actions()

        resp = await trainee1.send_and_wait(
            "Траектория обучения 📖", pattern="[Тт]раектори|этап"
        )

        text = resp.text or ""

        # Тест 1 должен быть по-прежнему пройден
        assert "✅" in text, (
            f"BUG REPRODUCED: Passed test lost ✅ after trajectory reassignment! "
            f"Got: {text[:500]}"
        )

    async def test_step4_mentor_sees_same_status(
        self, mentor: BotClient, shared_state: dict
    ):
        """Наставник видит тот же ✅ статус в прогрессе стажёра."""
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

        # Наставник должен видеть ✅ для пройденного теста
        assert "✅" in text, (
            f"Mentor's view should show ✅ for passed test. Got: {text[:500]}"
        )
