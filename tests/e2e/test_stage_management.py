"""
E2E Сценарий 4: Закрытие этапа — согласованность UI и access.

Проверяет, что:
- Открытие этапа → стажёр видит 🟡
- Прохождение теста → стажёр видит ✅
- Закрытие этапа → стажёр видит ⛔️, но данные не потеряны
- Наставник видит тест как пройденный даже в закрытом этапе

Зависит от предыдущих тестов (Стажёр 1: этап 1 закрыт, тест 1 пройден).
"""

import pytest

from tests.e2e.helpers.bot_client import BotClient
from tests.e2e.helpers.waiters import (
    extract_emoji_status,
    wait_between_actions,
)
from tests.e2e.test_check_test_access import open_mentor_stage, close_mentor_stage


pytestmark = [
    pytest.mark.order(4),
    pytest.mark.timeout(300),
    pytest.mark.asyncio(loop_scope="session"),
]


class TestScenario4_StageOpenCloseConsistency:
    """
    Баг 4 из oc.md: закрытие этапа нарушает согласованность UI.

    Проверяем, что данные о прохождении сохраняются при закрытии/открытии.
    """

    async def test_step1_reopen_stage1(
        self, mentor: BotClient, shared_state: dict
    ):
        """Наставник повторно открывает этап 1 для проверки."""
        await open_mentor_stage(mentor, "Стажёров Первый", stage_number=1)

    async def test_step2_trainee_sees_open_stage(
        self, trainee1: BotClient, shared_state: dict
    ):
        """Стажёр 1 видит этап 1 как открытый (🟡 или ✅)."""
        await wait_between_actions()

        resp = await trainee1.send_and_wait(
            "Траектория обучения 📖", pattern="[Тт]раектори|этап"
        )

        text = resp.text or ""

        # Этап 1 должен быть открыт (🟡) или пройден (✅), но НЕ закрыт (⛔️)
        # Тест 1 уже пройден, поэтому может быть ✅
        has_open_or_passed = "🟡" in text or "✅" in text
        assert has_open_or_passed, (
            f"Stage 1 should be open (🟡) or passed (✅) after reopening. Got: {text[:500]}"
        )

        shared_state["stage1_open_text"] = text

    async def test_step3_close_stage1_again(
        self, mentor: BotClient, shared_state: dict
    ):
        """Наставник снова закрывает этап 1."""
        await close_mentor_stage(mentor, "Стажёров Первый", stage_number=1)

    async def test_step4_trainee_sees_closed_stage(
        self, trainee1: BotClient, shared_state: dict
    ):
        """Стажёр 1 видит этап 1 как закрытый (⛔️)."""
        await wait_between_actions()

        resp = await trainee1.send_and_wait(
            "Траектория обучения 📖", pattern="[Тт]раектори|этап"
        )

        text = resp.text or ""

        # Этап 1 должен быть ⛔️ (закрыт) в UI стажёра — это by design
        assert "⛔" in text, (
            f"Stage 1 should show ⛔️ after closing. Got: {text[:500]}"
        )

    async def test_step5_mentor_progress_shows_passed(
        self, mentor: BotClient, shared_state: dict
    ):
        """
        КРИТИЧЕСКАЯ ПРОВЕРКА: Наставник видит тест как пройденный
        в закрытом этапе (данные не потеряны).
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
        assert trainee_btn, "Trainee 1 not found"

        resp = await mentor.click_and_wait(
            resp, data=trainee_btn,
            wait_pattern="[Тт]раектори|прогресс|[Ээ]тап|карточка"
        )

        text = resp.text or ""

        # Наставник должен видеть ✅ для пройденного теста, даже если этап закрыт
        assert "✅" in text, (
            f"BUG: Mentor should see ✅ for passed test in closed stage. "
            f"Got: {text[:500]}"
        )

    async def test_step6_mentor_stage_management_shows_correct_toggle(
        self, mentor: BotClient, shared_state: dict
    ):
        """Управление этапами показывает корректную кнопку для закрытого этапа."""
        await wait_between_actions()

        resp = await mentor.send_and_wait(
            "Мои стажеры 👥", pattern="стажер|стажёр"
        )

        trainee_btn = mentor.find_button_data(
            resp, text_contains="Первый", data_prefix="select_trainee_for_trajectory:"
        )
        if not trainee_btn:
            trainee_btn = mentor.find_button_data(
                resp, text_contains="Стажёров", data_prefix="select_trainee_for_trajectory:"
            )
        assert trainee_btn, "Trainee 1 not found"

        resp = await mentor.click_and_wait(
            resp, data=trainee_btn, wait_pattern="[Тт]раектори|[Ээ]тап|карточка"
        )

        # Управление этапами
        stages_btn = mentor.find_button_data(resp, data_prefix="manage_stages:")
        if stages_btn:
            resp = await mentor.click_and_wait(
                resp, data=stages_btn, wait_pattern="[Ээ]тап|[Оо]ткрыть|[Зз]акрыть"
            )

        buttons = mentor.get_button_texts(resp)

        # Этап 1 может быть закрыт (кнопка "Открыть") или завершён (✅)
        has_open_or_completed = any(
            ("Открыть" in b and "1" in b)
            or ("Этап 1" in b and "завершен" in b.lower())
            for b in buttons
        )
        assert has_open_or_completed, (
            f"Stage 1 should show 'Открыть этап 1' or '✅ Этап 1 завершен'. "
            f"Buttons: {buttons}"
        )
