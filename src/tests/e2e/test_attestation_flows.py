"""
E2E Сценарий 8: Полные flow аттестации.

Покрывает:
- Класс 1: Подготовка trainee1 (прохождение всех тестов для unlock аттестации)
- Класс 2: Полное проведение аттестации наставником → руководителем (passed)
- Класс 3: Назначение аттестации рекрутером (bypass этапов)
- Класс 4: Провал аттестации (failed flow)

Зависит от test_attestation_completion.py (order=7).
"""

import asyncpg
import pytest

from tests.e2e.helpers.bot_client import BotClient
from tests.e2e.helpers.waiters import wait_between_actions
from tests.e2e.test_check_test_access import open_mentor_stage, take_test_via_trajectory

pytestmark = [
    pytest.mark.order(8),
    pytest.mark.timeout(600),
    pytest.mark.asyncio(loop_scope="session"),
]


# =========================================================================
# Класс 1: Подготовка — trainee1 проходит все тесты
# =========================================================================


class TestAttestationFlowSetup:
    """
    Подготовка trainee1: открытие этапов и прохождение всех тестов.

    Наставник должен видеть check_all_stages_completed = True,
    чтобы кнопка "Аттестация" стала доступна.
    """

    async def test_step0_open_stage1_for_trainee1(self, mentor: BotClient):
        """Наставник открывает этап 1 для Стажёра 1."""
        await open_mentor_stage(mentor, "Стажёров Первый", stage_number=1)

    async def test_step1_trainee1_passes_stage1_test(self, trainee1: BotClient):
        """Стажёр 1 проходит тест «Кофе» в этапе 1."""
        await wait_between_actions()

        result = await take_test_via_trajectory(
            trainee1,
            stage_name="Базовые",
            test_name="E2E Тест Кофе",
            correct_answer_index=1,
        )
        assert "пройден" in result.lower() or "✅" in result or "балл" in result.lower(), (
            f"Test not passed. Result: {result[:300]}"
        )

    async def test_step2_open_stage2(self, mentor: BotClient):
        """Наставник открывает этап 2 для Стажёра 1."""
        await wait_between_actions()
        await open_mentor_stage(mentor, "Стажёров Первый", stage_number=2)

    async def test_step3_trainee1_passes_stage2_tests(self, trainee1: BotClient):
        """Стажёр 1 проходит тесты «Сервис» и «Гигиена» в этапе 2."""
        await wait_between_actions(3.0)

        # Тест Сервис (первый в сессии)
        result = await take_test_via_trajectory(
            trainee1,
            stage_name="Продвинутые",
            test_name="E2E Тест Сервис",
            correct_answer_index=1,
            test_index=0,
        )
        assert "пройден" in result.lower() or "✅" in result or "балл" in result.lower(), (
            f"Test Сервис not passed. Result: {result[:300]}"
        )

        await wait_between_actions(3.0)

        # Тест Гигиена (второй в сессии)
        result = await take_test_via_trajectory(
            trainee1,
            stage_name="Продвинутые",
            test_name="E2E Тест Гигиена",
            correct_answer_index=1,
            test_index=1,
        )
        assert "пройден" in result.lower() or "✅" in result or "балл" in result.lower(), (
            f"Test Гигиена not passed. Result: {result[:300]}"
        )


# =========================================================================
# Класс 2: Полное проведение аттестации (наставник назначает → руководитель проводит)
# =========================================================================


class TestFullAttestationConducting:
    """
    Полный flow: наставник назначает аттестацию → руководитель проводит
    (вопрос за вопросом, баллы, результат passed).
    """

    async def test_step0_mentor_assigns_attestation(self, mentor: BotClient, shared_state: dict):
        """Наставник назначает аттестацию для Стажёра 1."""
        await wait_between_actions()

        resp = await mentor.send_and_wait("Мои стажеры 👥", pattern="стажер|стажёр")

        # Выбираем стажёра 1
        trainee_btn = mentor.find_button_data(
            resp, text_contains="Первый", data_prefix="select_trainee_for_trajectory:"
        )
        if not trainee_btn:
            trainee_btn = mentor.find_button_data(
                resp, text_contains="Стажёров", data_prefix="select_trainee_for_trajectory:"
            )
        assert trainee_btn, f"Trainee 1 not found. Buttons: {mentor.get_button_texts(resp)}"

        resp = await mentor.click_and_wait(
            resp, data=trainee_btn, wait_pattern="[Тт]раектори|[Ээ]тап|карточка|Аттестация"
        )

        # Нажимаем "Аттестация"
        att_btn = mentor.find_button_data(resp, data_prefix="view_trainee_attestation:")
        assert att_btn, f"Attestation button not found. Buttons: {mentor.get_button_texts(resp)}"

        resp = await mentor.click_and_wait(
            resp, data=att_btn, wait_pattern="руководител|[Рр]уководител|[Вв]ыбери|назначить"
        )

        # Выбираем руководителя
        manager_btn = mentor.find_button_data(resp, data_prefix="select_manager_for_attestation:")
        assert manager_btn, f"Manager button not found. Buttons: {mentor.get_button_texts(resp)}"

        resp = await mentor.click_and_wait(resp, data=manager_btn, wait_pattern="[Пп]одтвердить|подтверд|Да")

        # Подтверждаем
        resp = await mentor.click_and_wait(
            resp, data=b"confirm_attestation_assignment", wait_pattern="назначена|успешно|аттестация"
        )

        resp_text = resp.text or ""
        assert "назначена" in resp_text.lower() or "успешно" in resp_text.lower(), (
            f"Assignment not confirmed. Response: {resp_text[:300]}"
        )
        shared_state["att_flow_mentor_assigned"] = True

    async def test_step1_verify_assignment_in_db(self, e2e_db: asyncpg.Connection, shared_state: dict):
        """Проверяем назначение аттестации в БД."""
        trainee_id = await e2e_db.fetchval("SELECT id FROM users WHERE full_name = $1", "Стажёров Первый")
        assert trainee_id, "Trainee not found in DB"

        row = await e2e_db.fetchrow(
            "SELECT id, status, manager_id, attestation_id, is_active "
            "FROM trainee_attestations WHERE trainee_id = $1 AND is_active = true",
            trainee_id,
        )
        assert row, "No active trainee_attestation found in DB"
        assert row["status"] == "assigned", f"Expected status='assigned', got '{row['status']}'"

        shared_state["att_flow_assignment_id"] = row["id"]
        shared_state["att_flow_trainee_id"] = trainee_id

    async def test_step2_manager_sees_trainee_in_list(self, manager: BotClient):
        """Руководитель видит Стажёра 1 в списке аттестаций."""
        await wait_between_actions()

        resp = await manager.send_and_wait("Аттестация", pattern="[Аа]ттестац|стажер|стажёр")

        trainee_btn = manager.find_button_data(resp, text_contains="Первый", data_prefix="select_trainee_attestation:")
        if not trainee_btn:
            trainee_btn = manager.find_button_data(
                resp, text_contains="Стажёров", data_prefix="select_trainee_attestation:"
            )
        assert trainee_btn, f"Trainee not in manager's attestation list. Buttons: {manager.get_button_texts(resp)}"

    async def test_step3_manager_starts_attestation(self, manager: BotClient, shared_state: dict):
        """Руководитель начинает аттестацию: выбирает стажёра → Начать → Подтвердить."""
        await wait_between_actions()

        resp = await manager.send_and_wait("Аттестация", pattern="[Аа]ттестац|стажер|стажёр")

        # Выбираем стажёра
        trainee_btn = manager.find_button_data(resp, text_contains="Первый", data_prefix="select_trainee_attestation:")
        if not trainee_btn:
            trainee_btn = manager.find_button_data(
                resp, text_contains="Стажёров", data_prefix="select_trainee_attestation:"
            )
        assert trainee_btn, f"Trainee button not found. Buttons: {manager.get_button_texts(resp)}"

        resp = await manager.click_and_wait(
            resp, data=trainee_btn, wait_pattern="Начать аттестацию|Управление|Изменить дату"
        )

        # Нажимаем "Начать аттестацию"
        start_btn = manager.find_button_data(resp, data_prefix="start_attestation:")
        assert start_btn, f"Start button not found. Buttons: {manager.get_button_texts(resp)}"

        resp = await manager.click_and_wait(resp, data=start_btn, wait_pattern="[Дд]а|[Пп]одтверд|[Нн]ачать")

        # Подтверждаем начало
        resp = await manager.click_and_wait(
            resp, data=b"confirm_start_attestation", wait_pattern="[Вв]опрос|балл|оцен|Максимальный"
        )

        resp_text = resp.text or ""
        assert "Вопрос" in resp_text or "вопрос" in resp_text, (
            f"Question not shown after start. Response: {resp_text[:300]}"
        )
        shared_state["att_flow_question_shown"] = True

    async def test_step4_manager_scores_question(self, manager: BotClient, shared_state: dict):
        """Руководитель вводит максимальный балл (10) за вопрос."""
        await wait_between_actions()

        resp = await manager.send_and_wait(
            "10", pattern="принят|Балл|вопрос|пройдена|результат|завершена|Набрано|провалена"
        )

        resp_text = resp.text or ""
        shared_state["att_flow_score_response"] = resp_text

    async def test_step5_verify_passed(self, manager: BotClient, shared_state: dict):
        """Проверяем результат: аттестация успешно пройдена."""
        # После ввода балла бот отправляет подтверждение + результат
        # Ищем результат в последних сообщениях
        await wait_between_actions(2.0)

        messages = await manager.get_messages(limit=5)
        result_found = False

        for msg in messages:
            if msg.out:
                continue
            text = msg.text or ""
            if "пройдена" in text.lower() or "провалена" in text.lower():
                assert "успешно пройдена" in text.lower() or "✅" in text, (
                    f"Attestation not passed with score 10! Text: {text[:300]}"
                )
                result_found = True
                shared_state["att_flow_result_text"] = text
                break

        assert result_found, (
            f"Result message not found in last 5 messages. "
            f"Last score response: {shared_state.get('att_flow_score_response', '')[:200]}"
        )

    async def test_step6_verify_result_in_db(self, e2e_db: asyncpg.Connection, shared_state: dict):
        """Проверяем результат аттестации в БД."""
        trainee_id = shared_state["att_flow_trainee_id"]

        # Проверяем attestation_results
        result = await e2e_db.fetchrow(
            "SELECT id, total_score, is_passed FROM attestation_results "
            "WHERE trainee_id = $1 ORDER BY completed_date DESC LIMIT 1",
            trainee_id,
        )
        assert result, "No attestation_result found in DB"
        assert result["is_passed"] is True, f"Expected is_passed=True, got {result['is_passed']}"
        assert result["total_score"] == 10.0, f"Expected total_score=10.0, got {result['total_score']}"

        # Проверяем attestation_question_results
        q_results = await e2e_db.fetch(
            "SELECT points_awarded FROM attestation_question_results WHERE attestation_result_id = $1",
            result["id"],
        )
        assert len(q_results) == 1, f"Expected 1 question result, got {len(q_results)}"
        assert q_results[0]["points_awarded"] == 10.0, (
            f"Expected question points_awarded=10.0, got {q_results[0]['points_awarded']}"
        )

    async def test_step7_cleanup(self, e2e_db: asyncpg.Connection, shared_state: dict):
        """Очистка: удаляем результаты и назначение."""
        trainee_id = shared_state.get("att_flow_trainee_id")
        if not trainee_id:
            return

        # Порядок: question_results → results → trainee_attestations
        await e2e_db.execute(
            "DELETE FROM attestation_question_results WHERE attestation_result_id IN "
            "(SELECT id FROM attestation_results WHERE trainee_id = $1)",
            trainee_id,
        )
        await e2e_db.execute("DELETE FROM attestation_results WHERE trainee_id = $1", trainee_id)
        await e2e_db.execute("DELETE FROM trainee_attestations WHERE trainee_id = $1", trainee_id)


# =========================================================================
# Класс 3: Назначение аттестации рекрутером (bypass этапов)
# =========================================================================


class TestRecruiterInitiatedAttestation:
    """
    Рекрутер назначает аттестацию через "Стажеры 🐣" → карточка → "Открыть аттестацию".
    Этот flow не требует прохождения этапов (bypass).
    """

    async def test_step0_recruiter_opens_trainees(self, recruiter: BotClient):
        """Рекрутер открывает список стажёров."""
        await wait_between_actions()

        resp = await recruiter.send_and_wait("Стажеры 🐣", pattern="стажер|стажёр|Стажёр|Список")
        resp_text = resp.text or ""
        assert "стажер" in resp_text.lower() or "стажёр" in resp_text.lower() or recruiter.get_button_texts(resp), (
            f"Trainees list not shown. Response: {resp_text[:300]}"
        )

    async def test_step1_recruiter_selects_trainee1(self, recruiter: BotClient, shared_state: dict):
        """Рекрутер выбирает Стажёра 1 → карточка."""
        await wait_between_actions()

        resp = await recruiter.send_and_wait("Стажеры 🐣", pattern="стажер|стажёр|Стажёр|Список")

        trainee_btn = recruiter.find_button_data(resp, text_contains="Первый", data_prefix="view_trainee:")
        if not trainee_btn:
            trainee_btn = recruiter.find_button_data(resp, text_contains="Стажёров", data_prefix="view_trainee:")
        assert trainee_btn, f"Trainee 1 not found in recruiter list. Buttons: {recruiter.get_button_texts(resp)}"

        resp = await recruiter.click_and_wait(
            resp, data=trainee_btn, wait_pattern="Стажёров|Первый|ФИО|карточка|аттестац"
        )
        shared_state["rec_att_trainee_card"] = resp

    async def test_step2_recruiter_clicks_open_attestation(self, recruiter: BotClient, shared_state: dict):
        """Рекрутер нажимает «Открыть аттестацию» → список руководителей."""
        resp = shared_state.get("rec_att_trainee_card")
        if not resp:
            pytest.skip("No trainee card from previous step")

        att_btn = recruiter.find_button_data(resp, data_prefix="recruiter_open_attestation:")
        assert att_btn, f"'Открыть аттестацию' button not found. Buttons: {recruiter.get_button_texts(resp)}"

        resp = await recruiter.click_and_wait(
            resp, data=att_btn, wait_pattern="руководител|[Рр]уководител|[Вв]ыбери|менеджер"
        )

        shared_state["rec_att_manager_selection"] = resp

    async def test_step3_recruiter_selects_manager(self, recruiter: BotClient, shared_state: dict):
        """Рекрутер выбирает руководителя."""
        resp = shared_state.get("rec_att_manager_selection")
        if not resp:
            pytest.skip("No manager selection from previous step")

        manager_btn = recruiter.find_button_data(resp, data_prefix="recruiter_select_manager:")
        assert manager_btn, f"Manager button not found. Buttons: {recruiter.get_button_texts(resp)}"

        resp = await recruiter.click_and_wait(
            resp, data=manager_btn, wait_pattern="[Пп]одтвердить|подтверд|Да.*открыть|открыть"
        )

        shared_state["rec_att_confirmation"] = resp

    async def test_step4_recruiter_confirms(self, recruiter: BotClient, shared_state: dict):
        """Рекрутер подтверждает назначение."""
        resp = shared_state.get("rec_att_confirmation")
        if not resp:
            pytest.skip("No confirmation from previous step")

        resp = await recruiter.click_and_wait(
            resp,
            data=b"recruiter_confirm_attestation",
            wait_pattern="открыта|назначена|успешно|аттестация",
        )

        resp_text = resp.text or ""
        assert "открыта" in resp_text.lower() or "назначена" in resp_text.lower() or "успешно" in resp_text.lower(), (
            f"Attestation not confirmed. Response: {resp_text[:300]}"
        )
        shared_state["rec_att_confirmed"] = True

    async def test_step5_verify_in_db(self, e2e_db: asyncpg.Connection, shared_state: dict):
        """Проверяем назначение в БД: assigned_by_id = recruiter."""
        trainee_id = await e2e_db.fetchval("SELECT id FROM users WHERE full_name = $1", "Стажёров Первый")
        recruiter_id = await e2e_db.fetchval("SELECT id FROM users WHERE full_name = $1", "Рекрутеров Тест")

        row = await e2e_db.fetchrow(
            "SELECT id, assigned_by_id, status FROM trainee_attestations WHERE trainee_id = $1 AND is_active = true",
            trainee_id,
        )
        assert row, "No active trainee_attestation in DB"
        assert row["status"] == "assigned", f"Expected status='assigned', got '{row['status']}'"
        assert row["assigned_by_id"] == recruiter_id, (
            f"Expected assigned_by_id={recruiter_id} (recruiter), got {row['assigned_by_id']}"
        )

        shared_state["rec_att_assignment_id"] = row["id"]
        shared_state["rec_att_trainee_id"] = trainee_id

    async def test_step6_manager_sees_assignment(self, manager: BotClient):
        """Руководитель видит назначение в своём списке аттестаций."""
        await wait_between_actions()

        resp = await manager.send_and_wait("Аттестация", pattern="[Аа]ттестац|стажер|стажёр")

        trainee_btn = manager.find_button_data(resp, text_contains="Первый", data_prefix="select_trainee_attestation:")
        if not trainee_btn:
            trainee_btn = manager.find_button_data(
                resp, text_contains="Стажёров", data_prefix="select_trainee_attestation:"
            )
        assert trainee_btn, (
            f"Trainee not in manager's list after recruiter assignment. Buttons: {manager.get_button_texts(resp)}"
        )

    async def test_step7_cleanup(self, e2e_db: asyncpg.Connection, shared_state: dict):
        """Очистка: удаляем назначение."""
        trainee_id = shared_state.get("rec_att_trainee_id")
        if not trainee_id:
            return

        await e2e_db.execute("DELETE FROM trainee_attestations WHERE trainee_id = $1", trainee_id)


# =========================================================================
# Класс 4: Провал аттестации (failed flow)
# =========================================================================


class TestFailedAttestation:
    """
    Руководитель проводит аттестацию с баллом 0 → провал (0 < passing_score 5).
    """

    async def test_step0_setup_via_sql(self, e2e_db: asyncpg.Connection, shared_state: dict):
        """SQL: создаём назначение аттестации с status='assigned'."""
        trainee_id = await e2e_db.fetchval("SELECT id FROM users WHERE full_name = $1", "Стажёров Первый")
        manager_id = await e2e_db.fetchval("SELECT id FROM users WHERE full_name = $1", "Руководителев Тест")
        mentor_id = await e2e_db.fetchval("SELECT id FROM users WHERE full_name = $1", "Наставников Тест")
        attestation_id = await e2e_db.fetchval("SELECT id FROM attestations WHERE name = $1", "E2E Аттестация Бариста")

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
        await e2e_db.execute("DELETE FROM attestation_results WHERE trainee_id = $1", trainee_id)
        await e2e_db.execute("DELETE FROM trainee_attestations WHERE trainee_id = $1", trainee_id)

        await e2e_db.execute(
            """
            INSERT INTO trainee_attestations
                (trainee_id, manager_id, attestation_id, assigned_by_id,
                 status, is_active, assigned_date)
            VALUES ($1, $2, $3, $4, 'assigned', true, NOW())
            """,
            trainee_id,
            manager_id,
            attestation_id,
            mentor_id,
        )

        assignment_id = await e2e_db.fetchval(
            "SELECT id FROM trainee_attestations WHERE trainee_id = $1 AND is_active = true",
            trainee_id,
        )
        assert assignment_id, "Assignment not created"

        shared_state["failed_att_assignment_id"] = assignment_id
        shared_state["failed_att_trainee_id"] = trainee_id

    async def test_step1_manager_starts(self, manager: BotClient, shared_state: dict):
        """Руководитель начинает аттестацию."""
        await wait_between_actions()

        resp = await manager.send_and_wait("Аттестация", pattern="[Аа]ттестац|стажер|стажёр")

        trainee_btn = manager.find_button_data(resp, text_contains="Первый", data_prefix="select_trainee_attestation:")
        if not trainee_btn:
            trainee_btn = manager.find_button_data(
                resp, text_contains="Стажёров", data_prefix="select_trainee_attestation:"
            )
        assert trainee_btn, f"Trainee not found. Buttons: {manager.get_button_texts(resp)}"

        resp = await manager.click_and_wait(
            resp, data=trainee_btn, wait_pattern="Начать аттестацию|Управление|Изменить дату"
        )

        start_btn = manager.find_button_data(resp, data_prefix="start_attestation:")
        assert start_btn, f"Start button not found. Buttons: {manager.get_button_texts(resp)}"

        resp = await manager.click_and_wait(resp, data=start_btn, wait_pattern="[Дд]а|[Пп]одтверд|[Нн]ачать")

        resp = await manager.click_and_wait(
            resp, data=b"confirm_start_attestation", wait_pattern="[Вв]опрос|балл|оцен|Максимальный"
        )

        resp_text = resp.text or ""
        assert "Вопрос" in resp_text or "вопрос" in resp_text, f"Question not shown. Response: {resp_text[:300]}"

    async def test_step2_manager_gives_zero(self, manager: BotClient, shared_state: dict):
        """Руководитель вводит 0 баллов."""
        await wait_between_actions()

        resp = await manager.send_and_wait(
            "0", pattern="принят|Балл|вопрос|пройдена|провалена|результат|завершена|Набрано"
        )
        shared_state["failed_att_score_response"] = resp.text or ""

    async def test_step3_verify_failed(self, manager: BotClient, shared_state: dict):
        """Проверяем результат: аттестация провалена."""
        await wait_between_actions(2.0)

        messages = await manager.get_messages(limit=5)
        result_found = False

        for msg in messages:
            if msg.out:
                continue
            text = msg.text or ""
            if "пройдена" in text.lower() or "провалена" in text.lower():
                assert "провалена" in text.lower() or "❌" in text, (
                    f"Expected failed attestation with score 0, but got: {text[:300]}"
                )
                result_found = True
                shared_state["failed_att_result_text"] = text
                break

        assert result_found, (
            f"Result message not found. Last score response: {shared_state.get('failed_att_score_response', '')[:200]}"
        )

    async def test_step4_verify_in_db(self, e2e_db: asyncpg.Connection, shared_state: dict):
        """Проверяем результат в БД: is_passed=False, total_score=0."""
        trainee_id = shared_state["failed_att_trainee_id"]

        result = await e2e_db.fetchrow(
            "SELECT id, total_score, is_passed FROM attestation_results "
            "WHERE trainee_id = $1 ORDER BY completed_date DESC LIMIT 1",
            trainee_id,
        )
        assert result, "No attestation_result found in DB"
        assert result["is_passed"] is False, f"Expected is_passed=False, got {result['is_passed']}"
        assert result["total_score"] == 0.0, f"Expected total_score=0.0, got {result['total_score']}"

    async def test_step5_cleanup(self, e2e_db: asyncpg.Connection, shared_state: dict):
        """Очистка: удаляем результаты и назначение."""
        trainee_id = shared_state.get("failed_att_trainee_id")
        if not trainee_id:
            return

        await e2e_db.execute(
            "DELETE FROM attestation_question_results WHERE attestation_result_id IN "
            "(SELECT id FROM attestation_results WHERE trainee_id = $1)",
            trainee_id,
        )
        await e2e_db.execute("DELETE FROM attestation_results WHERE trainee_id = $1", trainee_id)
        await e2e_db.execute("DELETE FROM trainee_attestations WHERE trainee_id = $1", trainee_id)
