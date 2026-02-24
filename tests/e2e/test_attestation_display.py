"""
E2E Сценарий 6: Отображение аттестации у наставника.

Проверяет, что наставник видит корректный статус аттестации
в прогрессе траектории (не всегда ⛔️).

Баг: generate_trajectory_progress_for_mentor() — синхронная функция,
attestation_status = "⛔️" (hardcoded). Async-версия
generate_trajectory_progress_with_attestation_status() существует,
но используется только в view_trajectory, а НЕ в manage_stages
и select_trainee_for_trajectory.

Зависит от test_check_test_access.py (Стажёр 2: аттестация назначена/пройдена).
"""

import pytest

from tests.e2e.helpers.bot_client import BotClient
from tests.e2e.helpers.waiters import (
    extract_emoji_status,
    wait_between_actions,
)


pytestmark = [
    pytest.mark.order(6),
    pytest.mark.timeout(300),
    pytest.mark.asyncio(loop_scope="session"),
]


class TestScenario6_AttestationDisplay:
    """
    Баг 2 из oc.md: аттестация всегда показывается как ⛔️
    в некоторых views наставника.

    Три view наставника показывают прогресс траектории:
    1. select_trainee_for_trajectory → sync → attestation_status = "⛔️"
    2. view_trajectory → async → КОРРЕКТНЫЙ статус
    3. manage_stages → sync → attestation_status = "⛔️"

    Тест проверяет расхождение между views.
    """

    async def test_step1_mentor_quick_view_attestation_status(
        self, mentor: BotClient, shared_state: dict
    ):
        """
        Наставник выбирает стажёра — видит quick view с прогрессом.

        Этот view использует sync-версию generate_trajectory_progress_for_mentor(),
        где attestation_status hardcoded как "⛔️".

        BUG: Даже если аттестация назначена/пройдена, показывается ⛔️.
        """
        await wait_between_actions()

        resp = await mentor.send_and_wait(
            "Мои стажеры 👥", pattern="стажер|стажёр"
        )

        # Выбираем стажёра 1 (у него траектория с пройденными тестами)
        trainee_btn = mentor.find_button_data(
            resp, text_contains="Первый",
            data_prefix="select_trainee_for_trajectory:",
        )
        if not trainee_btn:
            trainee_btn = mentor.find_button_data(
                resp, text_contains="Стажёров",
                data_prefix="select_trainee_for_trajectory:",
            )
        assert trainee_btn, "Trainee 1 not found in mentor's list"

        resp = await mentor.click_and_wait(
            resp, data=trainee_btn,
            wait_pattern="[Тт]раектори|[Ээ]тап|карточка"
        )

        text = resp.text or ""

        # Записываем текст quick view для сравнения
        shared_state["mentor_quick_view_text"] = text

        # Если траектория имеет аттестацию, проверяем её отображение
        if "Аттестация" in text:
            shared_state["quick_view_has_attestation"] = True
            # В quick view аттестация ВСЕГДА ⛔️ (баг)
            # Это ожидаемое поведение БАГА
            shared_state["quick_view_attestation_icon"] = (
                "⛔" if "⛔" in text.split("Аттестация")[1][:20] else
                "✅" if "✅" in text.split("Аттестация")[1][:20] else
                "🟡" if "🟡" in text.split("Аттестация")[1][:20] else
                "unknown"
            )
        else:
            shared_state["quick_view_has_attestation"] = False

    async def test_step2_mentor_detailed_view_attestation_status(
        self, mentor: BotClient, shared_state: dict
    ):
        """
        Наставник открывает детальный view траектории (view_trajectory).

        Этот view использует async-версию
        generate_trajectory_progress_with_attestation_status(),
        которая корректно запрашивает статус из БД.
        """
        await wait_between_actions()

        resp = await mentor.send_and_wait(
            "Мои стажеры 👥", pattern="стажер|стажёр"
        )

        trainee_btn = mentor.find_button_data(
            resp, text_contains="Первый",
            data_prefix="select_trainee_for_trajectory:",
        )
        if not trainee_btn:
            trainee_btn = mentor.find_button_data(
                resp, text_contains="Стажёров",
                data_prefix="select_trainee_for_trajectory:",
            )
        assert trainee_btn, "Trainee 1 not found"

        resp = await mentor.click_and_wait(
            resp, data=trainee_btn,
            wait_pattern="[Тт]раектори|[Ээ]тап|карточка"
        )

        # Ищем кнопку "Посмотреть траекторию" (view_trajectory)
        view_btn = mentor.find_button_data(
            resp, data_prefix="view_trajectory:"
        )

        if view_btn:
            resp = await mentor.click_and_wait(
                resp, data=view_btn,
                wait_pattern="[Тт]раектори|[Ээ]тап|прогресс|Управление"
            )

            text = resp.text or ""
            shared_state["mentor_detailed_view_text"] = text

            if "Аттестация" in text:
                shared_state["detailed_view_has_attestation"] = True
                shared_state["detailed_view_attestation_icon"] = (
                    "⛔" if "⛔" in text.split("Аттестация")[1][:20] else
                    "✅" if "✅" in text.split("Аттестация")[1][:20] else
                    "🟡" if "🟡" in text.split("Аттестация")[1][:20] else
                    "unknown"
                )
            else:
                shared_state["detailed_view_has_attestation"] = False
        else:
            shared_state["detailed_view_has_attestation"] = False

    async def test_step3_mentor_stages_management_attestation_status(
        self, mentor: BotClient, shared_state: dict
    ):
        """
        Наставник открывает управление этапами (manage_stages).

        Этот view тоже использует sync-версию — attestation_status = "⛔️".
        """
        await wait_between_actions()

        resp = await mentor.send_and_wait(
            "Мои стажеры 👥", pattern="стажер|стажёр"
        )

        trainee_btn = mentor.find_button_data(
            resp, text_contains="Первый",
            data_prefix="select_trainee_for_trajectory:",
        )
        if not trainee_btn:
            trainee_btn = mentor.find_button_data(
                resp, text_contains="Стажёров",
                data_prefix="select_trainee_for_trajectory:",
            )
        assert trainee_btn, "Trainee 1 not found"

        resp = await mentor.click_and_wait(
            resp, data=trainee_btn,
            wait_pattern="[Тт]раектори|[Ээ]тап|карточка"
        )

        # Переходим в управление этапами
        stages_btn = mentor.find_button_data(
            resp, data_prefix="manage_stages:"
        )
        if stages_btn:
            resp = await mentor.click_and_wait(
                resp, data=stages_btn,
                wait_pattern="[Ээ]тап|[Оо]ткрыть|[Зз]акрыть"
            )

            text = resp.text or ""
            shared_state["mentor_stages_view_text"] = text

            if "Аттестация" in text:
                shared_state["stages_view_has_attestation"] = True
                shared_state["stages_view_attestation_icon"] = (
                    "⛔" if "⛔" in text.split("Аттестация")[1][:20] else
                    "✅" if "✅" in text.split("Аттестация")[1][:20] else
                    "🟡" if "🟡" in text.split("Аттестация")[1][:20] else
                    "unknown"
                )
            else:
                shared_state["stages_view_has_attestation"] = False

    async def test_step4_verify_attestation_consistency(
        self, shared_state: dict
    ):
        """
        КРИТИЧЕСКАЯ ПРОВЕРКА: статус аттестации одинаков во всех views.

        Если этот тест FAIL — воспроизводит Баг 2 из oc.md:
        - quick_view и manage_stages всегда показывают ⛔️
        - view_trajectory показывает корректный статус (🟡 или ✅)
        """
        quick = shared_state.get("quick_view_has_attestation", False)
        detailed = shared_state.get("detailed_view_has_attestation", False)
        stages = shared_state.get("stages_view_has_attestation", False)

        # Если ни в одном view нет аттестации — тест не применим
        if not any([quick, detailed, stages]):
            pytest.skip(
                "Trajectory does not have attestation configured. "
                "Bug 2 test not applicable."
            )

        # Если аттестация есть хотя бы в двух views — сравниваем
        icons = {}
        if quick:
            icons["quick_view"] = shared_state.get(
                "quick_view_attestation_icon", "unknown"
            )
        if detailed:
            icons["detailed_view"] = shared_state.get(
                "detailed_view_attestation_icon", "unknown"
            )
        if stages:
            icons["stages_view"] = shared_state.get(
                "stages_view_attestation_icon", "unknown"
            )

        if len(icons) < 2:
            pytest.skip(
                f"Attestation visible in only {len(icons)} view(s): {icons}. "
                f"Need at least 2 views for consistency check."
            )

        unique_icons = set(icons.values())

        # Баг 2: quick_view и stages_view показывают ⛔️,
        # а detailed_view — реальный статус
        if len(unique_icons) > 1:
            pytest.fail(
                f"BUG REPRODUCED (oc.md Bug 2): Attestation status differs "
                f"across mentor views! {icons}. "
                f"Sync views hardcode ⛔️, async view shows correct status. "
                f"Fix: use generate_trajectory_progress_with_attestation_status() "
                f"in all views."
            )
