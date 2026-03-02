"""
E2E Сценарий 7: Назначение даты и времени аттестации руководителем.

Руководитель назначает дату/время через "📅 Изменить дату".
Проверяет, что данные корректно сохраняются в БД и отображаются в UI.

Зависит от test_attestation_display.py (order=6).
"""

import re

import asyncpg
import pytest

from tests.e2e.helpers.bot_client import BotClient
from tests.e2e.helpers.waiters import wait_between_actions


pytestmark = [
    pytest.mark.order(7),
    pytest.mark.timeout(300),
    pytest.mark.asyncio(loop_scope="session"),
]


def extract_date_time_fields(text: str) -> tuple[str, str]:
    """
    Извлечь значения полей Дата: и Время: из сообщения бота.

    Returns:
        (date_value, time_value) — строки после "Дата:" и "Время:"
        Пустая строка если поле отсутствует или не заполнено.
    """
    date_match = re.search(r"Дата:(?:</b>|\*{0,2})\s*(.+?)(?:\n|$)", text)
    time_match = re.search(r"Время:(?:</b>|\*{0,2})\s*(.+?)(?:\n|$)", text)

    date_val = date_match.group(1).strip() if date_match else ""
    time_val = time_match.group(1).strip() if time_match else ""

    return date_val, time_val


class TestScenario7A_ManagerSchedulesDateTime:
    """
    Подсценарий A: руководитель назначает дату/время через "📅 Изменить дату".

    Флоу: Аттестация → выбрать стажёра → 📅 Изменить дату →
          ввести дату → ввести время → ✅ Да → проверяем сохранение.

    Также проверяем что scheduled_date/time записались в БД.
    """

    async def test_step0_setup_attestation_for_scheduling(
        self, e2e_db: asyncpg.Connection, shared_state: dict
    ):
        """SQL: назначаем аттестацию стажёру 1 (без даты/времени)."""
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

        assert trainee_id, "Trainee not found"
        assert manager_id, "Manager not found"
        assert mentor_id, "Mentor not found"
        assert attestation_id, "Attestation not found"

        # Чистим старые записи
        await e2e_db.execute(
            "DELETE FROM attestation_question_results WHERE attestation_result_id IN "
            "(SELECT id FROM attestation_results WHERE trainee_id = $1)",
            trainee_id,
        )
        await e2e_db.execute(
            "DELETE FROM attestation_results WHERE trainee_id = $1", trainee_id
        )
        await e2e_db.execute(
            "DELETE FROM trainee_attestations WHERE trainee_id = $1", trainee_id
        )

        # Создаём назначение (без scheduled_date/time — как в проде)
        await e2e_db.execute(
            """
            INSERT INTO trainee_attestations
                (trainee_id, manager_id, attestation_id, assigned_by_id,
                 status, is_active, assigned_date)
            VALUES ($1, $2, $3, $4, 'assigned', true, NOW())
            """,
            trainee_id, manager_id, attestation_id, mentor_id,
        )

        assignment_id = await e2e_db.fetchval(
            "SELECT id FROM trainee_attestations WHERE trainee_id = $1 AND is_active = true",
            trainee_id,
        )
        assert assignment_id, "Assignment not created"

        # Проверяем что scheduled_date/time = NULL
        row = await e2e_db.fetchrow(
            "SELECT scheduled_date, scheduled_time FROM trainee_attestations WHERE id = $1",
            assignment_id,
        )
        assert row["scheduled_date"] is None, "scheduled_date should be NULL before scheduling"
        assert row["scheduled_time"] is None, "scheduled_time should be NULL before scheduling"

        shared_state["sched_assignment_id"] = assignment_id
        shared_state["sched_trainee_id"] = trainee_id

    async def test_step1_manager_sets_date_and_time(
        self, manager: BotClient, shared_state: dict
    ):
        """
        Руководитель назначает дату и время:
        Аттестация → стажёр → 📅 Изменить дату → дата → время → ✅ Да.
        """
        await wait_between_actions()

        # 1. Открываем список аттестаций
        resp = await manager.send_and_wait(
            "Аттестация", pattern="[Аа]ттестация|стажер|стажёр|список"
        )

        # 2. Выбираем стажёра
        trainee_btn = manager.find_button_data(
            resp, text_contains="Первый",
            data_prefix="select_trainee_attestation:",
        )
        if not trainee_btn:
            trainee_btn = manager.find_button_data(
                resp, text_contains="Стажёров",
                data_prefix="select_trainee_attestation:",
            )
        assert trainee_btn, (
            f"Trainee button not found. Buttons: {manager.get_button_texts(resp)}"
        )

        resp = await manager.click_and_wait(
            resp, data=trainee_btn,
            wait_pattern="Начать аттестацию|Управление|Изменить дату"
        )

        # 3. Нажимаем "📅 Изменить дату"
        date_btn = manager.find_button_data(
            resp, text_contains="Изменить дату",
            data_prefix="change_attestation_date:",
        )
        assert date_btn, (
            f"'Изменить дату' button not found. Buttons: {manager.get_button_texts(resp)}"
        )

        resp = await manager.click_and_wait(
            resp, data=date_btn,
            wait_pattern="[Уу]кажите.*дату|новую дату"
        )

        # 4. Вводим дату
        test_date = "28.02.2026"
        resp = await manager.send_and_wait(
            test_date, pattern="[Уу]кажите.*время|новое время"
        )

        # Проверяем что дата отобразилась в ответе
        resp_text = resp.text or ""
        assert test_date in resp_text, (
            f"Entered date '{test_date}' not shown in response. Text: {resp_text[:300]}"
        )

        # 5. Вводим время
        test_time = "14:30"
        resp = await manager.send_and_wait(
            test_time, pattern="[Сс]охранить|Да"
        )

        # Проверяем что дата и время отобразились в подтверждении
        resp_text = resp.text or ""
        assert test_date in resp_text, f"Date not in confirmation. Text: {resp_text[:300]}"
        assert test_time in resp_text, f"Time not in confirmation. Text: {resp_text[:300]}"

        # 6. Подтверждаем — нажимаем "✅ Да"
        resp = await manager.click_and_wait(
            resp, data=b"save_new_schedule",
            wait_pattern="успешно|изменен|сохранен|Начать аттестацию"
        )

        shared_state["sched_test_date"] = test_date
        shared_state["sched_test_time"] = test_time
        shared_state["sched_save_response"] = resp.text or ""

    async def test_step2_date_time_saved_in_db(
        self, e2e_db: asyncpg.Connection, shared_state: dict
    ):
        """Проверяем: scheduled_date и scheduled_time записались в БД."""
        assignment_id = shared_state.get("sched_assignment_id")
        assert assignment_id, "No assignment_id in shared_state"

        row = await e2e_db.fetchrow(
            "SELECT scheduled_date, scheduled_time FROM trainee_attestations WHERE id = $1",
            assignment_id,
        )

        assert row is not None, f"Assignment {assignment_id} not found in DB"

        test_date = shared_state["sched_test_date"]
        test_time = shared_state["sched_test_time"]

        assert row["scheduled_date"] == test_date, (
            f"scheduled_date mismatch. Expected '{test_date}', "
            f"got '{row['scheduled_date']}'"
        )
        assert row["scheduled_time"] == test_time, (
            f"scheduled_time mismatch. Expected '{test_time}', "
            f"got '{row['scheduled_time']}'"
        )

    async def test_step3_date_time_shown_in_management_view(
        self, manager: BotClient, shared_state: dict
    ):
        """Проверяем: дата и время отображаются в экране управления стажёром."""
        await wait_between_actions()

        # Заново открываем аттестации → стажёр
        resp = await manager.send_and_wait(
            "Аттестация", pattern="[Аа]ттестация|стажер|стажёр|список"
        )

        trainee_btn = manager.find_button_data(
            resp, text_contains="Первый",
            data_prefix="select_trainee_attestation:",
        )
        if not trainee_btn:
            trainee_btn = manager.find_button_data(
                resp, text_contains="Стажёров",
                data_prefix="select_trainee_attestation:",
            )
        assert trainee_btn, f"Trainee button not found. Buttons: {manager.get_button_texts(resp)}"

        resp = await manager.click_and_wait(
            resp, data=trainee_btn,
            wait_pattern="Начать аттестацию|Управление"
        )

        mgmt_text = resp.text or ""
        test_date = shared_state["sched_test_date"]
        test_time = shared_state["sched_test_time"]

        date_val, time_val = extract_date_time_fields(mgmt_text)

        assert date_val == test_date, (
            f"Date not shown in management view. Expected '{test_date}', "
            f"got '{date_val}'. Text: {mgmt_text[:300]}"
        )
        assert time_val == test_time, (
            f"Time not shown in management view. Expected '{test_time}', "
            f"got '{time_val}'. Text: {mgmt_text[:300]}"
        )

    async def test_step4_cleanup_scheduling(
        self, e2e_db: asyncpg.Connection, shared_state: dict
    ):
        """Очистка: удаляем тестовое назначение."""
        trainee_id = shared_state.get("sched_trainee_id")
        if not trainee_id:
            return

        await e2e_db.execute(
            "DELETE FROM trainee_attestations WHERE trainee_id = $1", trainee_id
        )


