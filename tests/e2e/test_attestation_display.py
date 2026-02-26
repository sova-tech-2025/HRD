"""
E2E Сценарий 6: Отображение аттестации у наставника.

Проверяет, что наставник видит корректный статус аттестации
в прогрессе траектории (не всегда ⛔️).

Баг (коммит 192ed28^): generate_trajectory_progress_for_mentor() — sync,
attestation_status = "⛔️" (hardcoded). Использовалась в 3 callsites:
  - callback_select_trainee_for_trajectory (quick view)
  - callback_open_stage (после открытия этапа)
  - update_stages_management_interface (управление этапами)

Фикс (коммит 192ed28): все callsites используют async-версию
generate_trajectory_progress_with_attestation_status(), которая
запрашивает реальный статус из БД через get_trainee_attestation_status().

Стратегия тестирования:
  1. SQL INSERT: TraineeAttestation с status='assigned' для Стажёра 1
     → get_trainee_attestation_status() вернёт 🟡
  2. Проверяем 3 view наставника:
     - quick view → ожидаем 🟡 (без фикса: ⛔️)
     - manage_stages → ожидаем 🟡 (без фикса: ⛔️)
     - callback_open_stage → ожидаем 🟡 (без фикса: ⛔️)
  3. Позитивная проверка: все views показывают 🟡 (назначена), а не ⛔️
  4. Проверка консистентности: все views показывают одинаковый статус

Зависит от test_broadcast_access.py (order=5).
"""

import re

import asyncpg
import pytest

from tests.e2e.helpers.bot_client import BotClient
from tests.e2e.helpers.waiters import wait_between_actions


pytestmark = [
    pytest.mark.order(6),
    pytest.mark.timeout(300),
    pytest.mark.asyncio(loop_scope="session"),
]


def extract_attestation_icon(text: str) -> str:
    """
    Извлечь иконку статуса аттестации из текста сообщения.

    Формат в сообщении бота:
        🏁Аттестация: <название> <иконка>

    Returns:
        "🟡", "✅", "⛔" или "not_found"
    """
    match = re.search(r"Аттестация.*?(⛔️|⛔|🟡|✅)", text)
    if match:
        icon = match.group(1)
        # Нормализуем: ⛔️ → ⛔ (с variation selector и без)
        if "⛔" in icon:
            return "⛔"
        return icon
    return "not_found"


async def _select_trainee_in_mentor_list(mentor: BotClient) -> "Message":
    """Выбрать Стажёра 1 в списке наставника."""
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
    assert trainee_btn, (
        f"Trainee 'Стажёров Первый' not found in mentor's list. "
        f"Buttons: {mentor.get_button_texts(resp)}"
    )

    resp = await mentor.click_and_wait(
        resp, data=trainee_btn,
        wait_pattern="[Тт]раектори|[Ээ]тап|карточка"
    )
    return resp


class TestScenario6_AttestationDisplay:
    """
    Баг 2 из oc.md: аттестация всегда показывается как ⛔️
    в нескольких views наставника.

    Корневая причина: sync-функция generate_trajectory_progress_for_mentor()
    содержала hardcoded attestation_status = "⛔️" с комментарием
    "нужна async версия для точного статуса".

    Фикс: заменена на async generate_trajectory_progress_with_attestation_status()
    во всех 4 callsites (3 в mentorship.py + 1 в db.py).

    Тест ГАРАНТИРОВАННО ловит баг:
    - Создаём TraineeAttestation с status='assigned' через SQL
    - get_trainee_attestation_status() вернёт 🟡
    - Без фикса: sync-функция возвращает ⛔️ → assert fails
    - С фиксом: async-функция запрашивает БД → 🟡 → assert passes
    """

    async def test_step0_insert_trainee_attestation_via_sql(
        self, e2e_db: asyncpg.Connection, shared_state: dict
    ):
        """
        SQL: Создаём TraineeAttestation с status='assigned' для Стажёра 1.

        Это ключевой setup, который делает тест детерминированным:
        - Без этой записи: get_trainee_attestation_status() → ⛔️ (not assigned)
        - С этой записью: get_trainee_attestation_status() → 🟡 (assigned)
        - Sync-функция (баг): игнорирует запись → ⛔️ (hardcoded)
        - Async-функция (фикс): запрашивает БД → 🟡
        """
        # Получаем ID сущностей (параметризованные запросы)
        trainee_id = await e2e_db.fetchval(
            "SELECT id FROM users WHERE full_name = $1", "Стажёров Первый"
        )
        manager_id = await e2e_db.fetchval(
            "SELECT id FROM users WHERE full_name = $1", "Руководителев Тест"
        )
        mentor_id = await e2e_db.fetchval(
            "SELECT id FROM users WHERE full_name = $1", "Наставников Тест"
        )
        attestation_id = await e2e_db.fetchval(
            "SELECT id FROM attestations WHERE name = $1", "E2E Аттестация Бариста"
        )

        assert trainee_id, "Trainee 'Стажёров Первый' not found in DB"
        assert manager_id, "Manager 'Руководителев Тест' not found in DB"
        assert mentor_id, "Mentor 'Наставников Тест' not found in DB"
        assert attestation_id, "Attestation 'E2E Аттестация Бариста' not found in DB"

        # Удаляем старые записи (если есть от предыдущих прогонов)
        await e2e_db.execute(
            "DELETE FROM trainee_attestations WHERE trainee_id = $1",
            trainee_id,
        )

        # Вставляем назначение аттестации со статусом 'assigned'
        # assigned_date указан явно, т.к. SQLAlchemy defaults не работают через asyncpg
        await e2e_db.execute(
            """
            INSERT INTO trainee_attestations
                (trainee_id, manager_id, attestation_id, assigned_by_id, status, is_active, assigned_date)
            VALUES ($1, $2, $3, $4, 'assigned', true, NOW())
            """,
            trainee_id, manager_id, attestation_id, mentor_id,
        )

        # Верификация: запись создана
        status = await e2e_db.fetchval(
            "SELECT status FROM trainee_attestations WHERE trainee_id = $1 AND is_active = true",
            trainee_id,
        )
        assert status == "assigned", f"Expected status='assigned', got '{status}'"

        shared_state["attestation_sql_inserted"] = True
        shared_state["expected_attestation_icon"] = "🟡"

    async def test_step1_quick_view_shows_assigned_status(
        self, mentor: BotClient, shared_state: dict
    ):
        """
        Callsite 1: callback_select_trainee_for_trajectory()

        Наставник выбирает стажёра → видит карточку с прогрессом траектории.

        БЕЗ ФИКСА: generate_trajectory_progress_for_mentor() →
                   attestation_status = "⛔️" (hardcoded) → FAIL
        С ФИКСОМ:  generate_trajectory_progress_with_attestation_status() →
                   get_trainee_attestation_status() → "🟡" → PASS
        """
        await wait_between_actions()

        resp = await _select_trainee_in_mentor_list(mentor)
        text = resp.text or ""

        assert "Аттестация" in text, (
            f"Attestation section not found in quick view. Text: {text[:500]}"
        )

        icon = extract_attestation_icon(text)
        shared_state["quick_view_attestation_icon"] = icon
        shared_state["quick_view_text"] = text

        assert icon == "🟡", (
            f"BUG DETECTED (quick_view): Attestation should show 🟡 (assigned) "
            f"but shows '{icon}'. "
            f"Root cause: sync generate_trajectory_progress_for_mentor() "
            f"hardcodes ⛔️ instead of querying DB.\n"
            f"Attestation line: {text.split('Аттестация')[1][:50] if 'Аттестация' in text else 'N/A'}"
        )

    async def test_step2_manage_stages_shows_assigned_status(
        self, mentor: BotClient, shared_state: dict
    ):
        """
        Callsite 2: update_stages_management_interface()

        Наставник открывает управление этапами → видит прогресс с аттестацией.

        БЕЗ ФИКСА: generate_trajectory_progress_for_mentor() → ⛔️ → FAIL
        С ФИКСОМ:  generate_trajectory_progress_with_attestation_status() → 🟡 → PASS
        """
        await wait_between_actions()

        resp = await _select_trainee_in_mentor_list(mentor)

        stages_btn = mentor.find_button_data(
            resp, data_prefix="manage_stages:"
        )
        assert stages_btn, (
            f"'manage_stages' button not found. "
            f"Buttons: {mentor.get_button_texts(resp)}"
        )

        resp = await mentor.click_and_wait(
            resp, data=stages_btn,
            wait_pattern="[Ээ]тап|[Оо]ткрыть|[Зз]акрыть|Какой этап"
        )

        text = resp.text or ""

        assert "Аттестация" in text, (
            f"Attestation section not found in stages management. Text: {text[:500]}"
        )

        icon = extract_attestation_icon(text)
        shared_state["stages_view_attestation_icon"] = icon
        shared_state["stages_view_text"] = text

        assert icon == "🟡", (
            f"BUG DETECTED (manage_stages): Attestation should show 🟡 (assigned) "
            f"but shows '{icon}'. "
            f"Root cause: sync generate_trajectory_progress_for_mentor() "
            f"hardcodes ⛔️ instead of querying DB.\n"
            f"Attestation line: {text.split('Аттестация')[1][:50] if 'Аттестация' in text else 'N/A'}"
        )

    async def test_step3_open_stage_shows_assigned_status(
        self, mentor: BotClient, shared_state: dict
    ):
        """
        Callsite 3: callback_open_stage()

        Наставник открывает этап → в ответе прогресс траектории с аттестацией.

        БЕЗ ФИКСА: generate_trajectory_progress_for_mentor() → ⛔️ → FAIL
        С ФИКСОМ:  generate_trajectory_progress_with_attestation_status() → 🟡 → PASS
        """
        await wait_between_actions()

        resp = await _select_trainee_in_mentor_list(mentor)

        # Переходим в управление этапами
        stages_btn = mentor.find_button_data(
            resp, data_prefix="manage_stages:"
        )
        if not stages_btn:
            shared_state["open_stage_view_attestation_icon"] = "skipped"
            pytest.skip("manage_stages button not found, cannot test open_stage view")

        resp = await mentor.click_and_wait(
            resp, data=stages_btn,
            wait_pattern="[Ээ]тап|[Оо]ткрыть|[Зз]акрыть|Какой этап"
        )

        # Ищем кнопку открытия этапа (toggle_stage или open_stage)
        open_btn = mentor.find_button_data(
            resp,
            text_contains="Открыть",
            data_prefix="toggle_stage:",
        )
        if not open_btn:
            open_btn = mentor.find_button_data(
                resp, data_prefix="open_stage:"
            )

        if not open_btn:
            # Все этапы уже открыты или завершены — пропускаем
            shared_state["open_stage_view_attestation_icon"] = "skipped"
            pytest.skip(
                "No 'Open stage' button available. "
                f"Buttons: {mentor.get_button_texts(resp)}"
            )

        resp = await mentor.click_and_wait(
            resp, data=open_btn,
            wait_pattern="открыт|Открыт|успешно|Этап|Название траектории"
        )

        text = resp.text or ""

        if "Аттестация" not in text:
            shared_state["open_stage_view_attestation_icon"] = "not_in_response"
            pytest.skip(
                "Attestation section not in open_stage response. "
                f"Text: {text[:300]}"
            )

        icon = extract_attestation_icon(text)
        shared_state["open_stage_view_attestation_icon"] = icon
        shared_state["open_stage_view_text"] = text

        assert icon == "🟡", (
            f"BUG DETECTED (open_stage): Attestation should show 🟡 (assigned) "
            f"but shows '{icon}'. "
            f"Root cause: sync generate_trajectory_progress_for_mentor() "
            f"hardcodes ⛔️ instead of querying DB.\n"
            f"Attestation line: {text.split('Аттестация')[1][:50] if 'Аттестация' in text else 'N/A'}"
        )

    async def test_step4_verify_all_views_consistent(
        self, shared_state: dict
    ):
        """
        Проверка консистентности: все views показывают одинаковый статус.

        Это альтернативный способ обнаружения бага — если sync и async views
        показывают разный статус, баг однозначно воспроизведён.
        """
        icons = {}

        quick = shared_state.get("quick_view_attestation_icon")
        if quick and quick not in ("not_found", "skipped"):
            icons["quick_view"] = quick

        stages = shared_state.get("stages_view_attestation_icon")
        if stages and stages not in ("not_found", "skipped"):
            icons["stages_view"] = stages

        open_stage = shared_state.get("open_stage_view_attestation_icon")
        if open_stage and open_stage not in ("not_found", "skipped", "not_in_response"):
            icons["open_stage_view"] = open_stage

        if len(icons) < 2:
            pytest.skip(
                f"Need at least 2 views with attestation. Got: {icons}"
            )

        unique_icons = set(icons.values())

        assert len(unique_icons) == 1, (
            f"BUG: Attestation status differs across mentor views!\n"
            f"Views: {icons}\n"
            f"Expected: all views show the same status.\n"
            f"This means some views use sync (hardcoded ⛔️) "
            f"while others use async (correct DB query)."
        )

    async def test_step5_no_view_shows_hardcoded_stop(
        self, shared_state: dict
    ):
        """
        Позитивная проверка: ни один view НЕ показывает ⛔️
        для назначенной аттестации (status='assigned').

        Это самая прямая проверка бага:
        - SQL: TraineeAttestation.status = 'assigned'
        - get_trainee_attestation_status() → "🟡"
        - Без фикса: sync-функция hardcodes "⛔️" → FAIL
        - С фиксом: async-функция queries DB → "🟡" → PASS
        """
        expected = shared_state.get("expected_attestation_icon", "🟡")

        for view_name in ["quick_view", "stages_view", "open_stage_view"]:
            icon = shared_state.get(f"{view_name}_attestation_icon")
            if icon in (None, "not_found", "skipped", "not_in_response"):
                continue

            assert icon != "⛔", (
                f"BUG in {view_name}: Attestation is ASSIGNED (status='assigned' in DB) "
                f"but view shows ⛔️ (not assigned). "
                f"Expected: {expected}. Got: {icon}.\n"
                f"This proves sync generate_trajectory_progress_for_mentor() "
                f"ignores DB and hardcodes ⛔️."
            )

            assert icon == expected, (
                f"Unexpected icon in {view_name}: expected {expected}, got {icon}"
            )

    async def test_step6_cleanup_attestation(
        self, e2e_db: asyncpg.Connection
    ):
        """Очистка: удаляем тестовую TraineeAttestation."""
        trainee_id = await e2e_db.fetchval(
            "SELECT id FROM users WHERE full_name = 'Стажёров Первый'"
        )
        if trainee_id:
            await e2e_db.execute(
                "DELETE FROM trainee_attestations WHERE trainee_id = $1",
                trainee_id,
            )
