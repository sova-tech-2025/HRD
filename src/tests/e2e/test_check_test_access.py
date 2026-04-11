"""
E2E Сценарий 1: Проверка check_test_access.

Стажёр без TraineeTestAccess получает доступ через fallback
(структура траектории с открытым этапом).

Сценарий 2 (Employee access) вынесен в test_employee_access.py (order=8),
т.к. требует перехода trainee в Сотрудника (после attestation_flows).

Зависит от test_setup.py (order=1).
"""

import asyncpg
import pytest

from tests.e2e.helpers.bot_client import BotClient
from tests.e2e.helpers.waiters import (
    contains_access_denied,
    wait_between_actions,
)

pytestmark = [
    pytest.mark.order(2),
    pytest.mark.timeout(300),
    pytest.mark.asyncio(loop_scope="session"),
]


# =========================================================================
# Вспомогательные функции (используются другими тестами через import)
# =========================================================================


async def take_test_via_trajectory(
    trainee: BotClient,
    stage_name: str,
    test_name: str,
    correct_answer_index: int = 1,
    test_index: int = 0,
) -> str:
    """
    Стажёр проходит тест через траекторию обучения.

    Args:
        stage_name: подстрока названия этапа для поиска кнопки
        test_name: название теста (для поиска в тексте траектории)
        correct_answer_index: индекс правильного ответа в списке
        test_index: индекс теста в списке кнопок (0-based), если по имени не найти

    Returns:
        Текст финального сообщения с результатом.
    """
    # Открываем траекторию
    resp = await trainee.send_and_wait("Траектория обучения 📖", pattern="[Тт]раектори|этап|Этап")

    # Ищем нужный этап
    stage_btn = trainee.find_button_data(resp, text_contains=stage_name, data_prefix="select_stage:")
    if not stage_btn:
        # Этап может быть уже открыт в тексте — ищем любую кнопку этапа
        all_stage_btns = trainee.find_all_buttons_data(resp, data_prefix="select_stage:")
        assert all_stage_btns, f"No stage buttons found. Message: {(resp.text or '')[:300]}"
        stage_btn = all_stage_btns[0][1]

    resp = await trainee.click_and_wait(resp, data=stage_btn, wait_pattern="сессия|[Сс]ессия|тест|Тест")

    # Сначала нажимаем на сессию (UI показывает сессии, потом тесты)
    session_btn = trainee.find_button_data(resp, data_prefix="select_session:")
    if session_btn:
        resp = await trainee.click_and_wait(resp, data=session_btn, wait_pattern="тест|Тест")

    # Ищем тест: кнопки показывают "Тест N" (не имя теста)
    # Используем data_prefix и test_index
    test_btn = trainee.find_button_data(resp, text_contains=test_name, data_prefix="take_test:")
    if not test_btn:
        all_test_btns = trainee.find_all_buttons_data(resp, data_prefix="take_test:")
        if all_test_btns and test_index < len(all_test_btns):
            test_btn = all_test_btns[test_index][1]
        elif all_test_btns:
            test_btn = all_test_btns[0][1]

    assert test_btn, f"Test button not found (looking for '{test_name}'). Buttons: {trainee.get_button_texts(resp)}"

    resp = await trainee.click_and_wait(resp, data=test_btn, wait_pattern="[Нн]ачать|[Пп]ройти|тест|вопрос")

    # Нажимаем "Начать тест" если есть карточка теста
    start_btn = trainee.find_button_data(resp, data_prefix="take_test:")
    if not start_btn:
        start_btn = trainee.find_button_data(resp, data_prefix="start_test:")
    if start_btn:
        resp = await trainee.click_and_wait(resp, data=start_btn, wait_pattern="вопрос|Вопрос|\\?")

    # Отвечаем на вопрос (single_choice: нажимаем кнопку с правильным ответом)
    answer_btn = trainee.find_button_data(resp, data_prefix="answer:")
    if answer_btn:
        # Нажимаем правильный ответ
        all_answers = trainee.find_all_buttons_data(resp, data_prefix="answer:")
        if len(all_answers) > correct_answer_index:
            answer_data = all_answers[correct_answer_index][1]
        else:
            answer_data = all_answers[0][1]
        resp = await trainee.click_and_wait(
            resp, data=answer_data, wait_pattern="результат|[Тт]ест.*пройден|балл|Балл|Набрано|Поздравля|завершён"
        )

    return resp.text or ""


async def open_mentor_stage(
    mentor: BotClient,
    trainee_name: str,
    stage_number: int = 1,
):
    """Наставник открывает этап для стажёра."""
    await wait_between_actions()

    resp = await mentor.send_and_wait("Мои стажеры 👥", pattern="стажер|стажёр|Стажёр")

    # Выбираем стажёра
    trainee_btn = mentor.find_button_data(
        resp,
        text_contains=trainee_name,
        data_prefix="select_trainee_for_trajectory:",
    )
    assert trainee_btn, f"Trainee '{trainee_name}' not found in mentor's list"

    resp = await mentor.click_and_wait(resp, data=trainee_btn, wait_pattern="[Тт]раектори|[Ээ]тап|карточка")

    # Переходим в управление этапами
    stages_btn = mentor.find_button_data(resp, data_prefix="manage_stages:")
    if stages_btn:
        resp = await mentor.click_and_wait(resp, data=stages_btn, wait_pattern="[Ээ]тап|[Оо]ткрыть|[Зз]акрыть")

    # Ищем кнопку открытия нужного этапа
    open_btn = mentor.find_button_data(
        resp,
        text_contains=f"Открыть этап {stage_number}",
        data_prefix="toggle_stage:",
    )

    if open_btn:
        resp = await mentor.click_and_wait(resp, data=open_btn, wait_pattern="открыт|Открыт|успешно")
    # Если кнопки нет — этап уже открыт (🔒 Закрыть) или завершён (✅)

    return resp


async def close_mentor_stage(
    mentor: BotClient,
    trainee_name: str,
    stage_number: int = 1,
):
    """Наставник закрывает этап для стажёра."""
    await wait_between_actions()

    resp = await mentor.send_and_wait("Мои стажеры 👥", pattern="стажер|стажёр|Стажёр")

    # Выбираем стажёра
    trainee_btn = mentor.find_button_data(
        resp,
        text_contains=trainee_name,
        data_prefix="select_trainee_for_trajectory:",
    )
    assert trainee_btn, f"Trainee '{trainee_name}' not found"

    resp = await mentor.click_and_wait(resp, data=trainee_btn, wait_pattern="[Тт]раектори|[Ээ]тап|карточка")

    # Управление этапами
    stages_btn = mentor.find_button_data(resp, data_prefix="manage_stages:")
    if stages_btn:
        resp = await mentor.click_and_wait(resp, data=stages_btn, wait_pattern="[Ээ]тап|[Оо]ткрыть|[Зз]акрыть")

    # Ищем кнопку закрытия этапа
    close_btn = mentor.find_button_data(
        resp,
        text_contains=f"Закрыть этап {stage_number}",
        data_prefix="toggle_stage:",
    )
    if not close_btn:
        # Этап может быть уже завершён (✅) или уже закрыт (🔓 Открыть)
        buttons = mentor.get_button_texts(resp)
        completed = any(f"Этап {stage_number} завершен" in b for b in buttons)
        already_closed = any(f"Открыть этап {stage_number}" in b for b in buttons)
        if completed or already_closed:
            return resp
    assert close_btn, f"Close button for stage {stage_number} not found. Buttons: {mentor.get_button_texts(resp)}"

    resp = await mentor.click_and_wait(resp, data=close_btn, wait_pattern="Название траектории|Какой этап")

    return resp


# =========================================================================
# Сценарий 1: Стажёр с закрытым этапом (fallback access)
# =========================================================================


class TestScenario1_TraineeFallbackAccess:
    """
    Баг check_test_access: стажёр теряет доступ к тесту, если TraineeTestAccess
    отсутствует (например, после переназначения траектории).

    Реальный путь бага на продакшне:
    1. Траектория переназначается -> TraineeTestAccess не пересоздаётся
    2. Старый код: if not access: return False (сразу отказ)
    3. Новый код: fallback -> проверка структуры траектории -> тест в открытом этапе -> True

    Для воспроизведения: удаляем TraineeTestAccess через прямой SQL,
    ЗАТЕМ стажёр проходит тест (а не наоборот — иначе этап станет completed
    и кнопки навигации пропадут).
    """

    async def test_step1_switch_to_mentor(self, admin: BotClient):
        """ADMIN переключается в Наставник."""
        await admin.switch_role("Наставник")

    async def test_step2_mentor_opens_stage1(self, admin: BotClient, shared_state: dict):
        """Наставник открывает этап 1 для trainee."""
        await open_mentor_stage(admin, "Стажёров Тест", stage_number=1)

    async def test_step3_delete_trainee_test_access(self, e2e_db: asyncpg.Connection, shared_state: dict):
        """
        SQL: Удаляем ВСЕ записи TraineeTestAccess для trainee.

        Симулирует состояние после переназначения траектории,
        когда записи TraineeTestAccess не были пересозданы.
        """
        result = await e2e_db.execute("""
            DELETE FROM trainee_test_access
            WHERE trainee_id = (
                SELECT id FROM users WHERE full_name = 'Стажёров Тест'
            )
        """)
        deleted_count = int(result.split()[-1])
        assert deleted_count > 0, (
            "No TraineeTestAccess records found for trainee. Stage opening may not have created them."
        )
        shared_state["trainee_deleted_access_count"] = deleted_count

    async def test_step4_trainee_takes_test_via_fallback(self, trainee: BotClient, shared_state: dict):
        """
        КРИТИЧЕСКАЯ ПРОВЕРКА: Стажёр проходит тест БЕЗ TraineeTestAccess,
        используя fallback на структуру траектории (тест в открытом этапе).

        БЕЗ ФИКСА: check_test_access -> нет TraineeTestAccess -> return False ->
                   "Доступ запрещён" при попытке открыть тест
        С ФИКСОМ:  check_test_access -> нет TraineeTestAccess -> fallback ->
                   тест в открытом этапе -> return True -> тест доступен
        """
        await wait_between_actions()

        result_text = await take_test_via_trajectory(
            trainee,
            stage_name="Базовые",
            test_name="E2E Тест Кофе",
            correct_answer_index=1,
        )

        # КРИТИЧЕСКАЯ ПРОВЕРКА: НЕ должно быть "Доступ запрещен"
        assert not contains_access_denied(result_text), (
            f"BUG REPRODUCED: check_test_access has no trajectory fallback!\n"
            f"TraineeTestAccess was deleted (simulating post-reassignment state), "
            f"but test is in OPEN stage and should be accessible via fallback.\n"
            f"Response: {result_text[:500]}"
        )
