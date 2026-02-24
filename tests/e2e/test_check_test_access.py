"""
E2E Сценарии 1-2: Проверка check_test_access.

Сценарий 1: Стажёр без TraineeTestAccess получает доступ через fallback
            (структура траектории с открытым этапом).
Сценарий 2: Сотрудник (бывший стажёр) сохраняет доступ к тестам
            с creator_id = NULL (legacy-данные из продакшна).

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
# Вспомогательные функции
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
    resp = await trainee.send_and_wait(
        "Траектория обучения 📖", pattern="[Тт]раектори|этап|Этап"
    )

    # Ищем нужный этап
    stage_btn = trainee.find_button_data(
        resp, text_contains=stage_name, data_prefix="select_stage:"
    )
    if not stage_btn:
        # Этап может быть уже открыт в тексте — ищем любую кнопку этапа
        all_stage_btns = trainee.find_all_buttons_data(resp, data_prefix="select_stage:")
        assert all_stage_btns, f"No stage buttons found. Message: {(resp.text or '')[:300]}"
        stage_btn = all_stage_btns[0][1]

    resp = await trainee.click_and_wait(
        resp, data=stage_btn, wait_pattern="сессия|[Сс]ессия|тест|Тест"
    )

    # Сначала нажимаем на сессию (UI показывает сессии, потом тесты)
    session_btn = trainee.find_button_data(resp, data_prefix="select_session:")
    if session_btn:
        resp = await trainee.click_and_wait(
            resp, data=session_btn, wait_pattern="тест|Тест"
        )

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

    resp = await trainee.click_and_wait(
        resp, data=test_btn, wait_pattern="[Нн]ачать|[Пп]ройти|тест|вопрос"
    )

    # Нажимаем "Начать тест" если есть карточка теста
    start_btn = trainee.find_button_data(resp, data_prefix="take_test:")
    if not start_btn:
        start_btn = trainee.find_button_data(resp, data_prefix="start_test:")
    if start_btn:
        resp = await trainee.click_and_wait(
            resp, data=start_btn, wait_pattern="вопрос|Вопрос|\\?"
        )

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
            resp, data=answer_data,
            wait_pattern="результат|[Тт]ест.*пройден|балл|Балл|Набрано|Поздравля|завершён"
        )

    return resp.text or ""


async def open_mentor_stage(
    mentor: BotClient,
    trainee_name: str,
    stage_number: int = 1,
):
    """Наставник открывает этап для стажёра."""
    await wait_between_actions()

    resp = await mentor.send_and_wait(
        "Мои стажеры 👥", pattern="стажер|стажёр|Стажёр"
    )

    # Выбираем стажёра
    trainee_btn = mentor.find_button_data(
        resp,
        text_contains=trainee_name,
        data_prefix="select_trainee_for_trajectory:",
    )
    assert trainee_btn, f"Trainee '{trainee_name}' not found in mentor's list"

    resp = await mentor.click_and_wait(
        resp, data=trainee_btn, wait_pattern="[Тт]раектори|[Ээ]тап|карточка"
    )

    # Переходим в управление этапами
    stages_btn = mentor.find_button_data(resp, data_prefix="manage_stages:")
    if stages_btn:
        resp = await mentor.click_and_wait(
            resp, data=stages_btn, wait_pattern="[Ээ]тап|[Оо]ткрыть|[Зз]акрыть"
        )

    # Ищем кнопку открытия нужного этапа
    open_btn = mentor.find_button_data(
        resp,
        text_contains=f"Открыть этап {stage_number}",
        data_prefix="toggle_stage:",
    )
    if not open_btn:
        open_btn = mentor.find_button_data(
            resp,
            text_contains=f"Этап {stage_number}",
            data_prefix="open_stage:",
        )
    if not open_btn:
        # Этап может уже быть открыт
        open_btn = mentor.find_button_data(
            resp,
            text_contains=f"этап {stage_number}",
            data_prefix="toggle_stage:",
        )

    if open_btn:
        resp = await mentor.click_and_wait(
            resp, data=open_btn, wait_pattern="открыт|Открыт|успешно"
        )

    return resp


async def close_mentor_stage(
    mentor: BotClient,
    trainee_name: str,
    stage_number: int = 1,
):
    """Наставник закрывает этап для стажёра."""
    await wait_between_actions()

    resp = await mentor.send_and_wait(
        "Мои стажеры 👥", pattern="стажер|стажёр|Стажёр"
    )

    # Выбираем стажёра
    trainee_btn = mentor.find_button_data(
        resp,
        text_contains=trainee_name,
        data_prefix="select_trainee_for_trajectory:",
    )
    assert trainee_btn, f"Trainee '{trainee_name}' not found"

    resp = await mentor.click_and_wait(
        resp, data=trainee_btn, wait_pattern="[Тт]раектори|[Ээ]тап|карточка"
    )

    # Управление этапами
    stages_btn = mentor.find_button_data(resp, data_prefix="manage_stages:")
    if stages_btn:
        resp = await mentor.click_and_wait(
            resp, data=stages_btn, wait_pattern="[Ээ]тап|[Оо]ткрыть|[Зз]акрыть"
        )

    # Ищем кнопку закрытия этапа
    close_btn = mentor.find_button_data(
        resp,
        text_contains=f"Закрыть этап {stage_number}",
        data_prefix="toggle_stage:",
    )
    if not close_btn:
        # Этап может быть уже завершён (✅) — пропускаем
        buttons = mentor.get_button_texts(resp)
        completed = any(f"Этап {stage_number} завершен" in b for b in buttons)
        if completed:
            return resp
    assert close_btn, (
        f"Close button for stage {stage_number} not found. "
        f"Buttons: {mentor.get_button_texts(resp)}"
    )

    resp = await mentor.click_and_wait(
        resp, data=close_btn, wait_pattern="закрыт|Закрыт|успешно"
    )

    return resp


# =========================================================================
# Сценарий 1: Стажёр с закрытым этапом
# =========================================================================


class TestScenario1_TraineeFallbackAccess:
    """
    Баг check_test_access: стажёр теряет доступ к тесту, если TraineeTestAccess
    отсутствует (например, после переназначения траектории).

    Реальный путь бага на продакшне:
    1. Траектория переназначается → TraineeTestAccess не пересоздаётся
    2. Старый код: if not access: return False (сразу отказ)
    3. Новый код: fallback → проверка структуры траектории → тест в открытом этапе → True

    Для воспроизведения: удаляем TraineeTestAccess через прямой SQL,
    ЗАТЕМ стажёр проходит тест (а не наоборот — иначе этап станет completed
    и кнопки навигации пропадут).
    """

    async def test_step1_mentor_opens_stage1(
        self, mentor: BotClient, shared_state: dict
    ):
        """Наставник открывает этап 1 для Стажёра 1."""
        await open_mentor_stage(mentor, "Стажёров Первый", stage_number=1)

    async def test_step2_delete_trainee_test_access(
        self, e2e_db: asyncpg.Connection, shared_state: dict
    ):
        """
        SQL: Удаляем ВСЕ записи TraineeTestAccess для Стажёра 1.

        Симулирует состояние после переназначения траектории,
        когда записи TraineeTestAccess не были пересозданы.
        На продакшне это затронуло 45 стажёров.

        ВАЖНО: делаем ДО прохождения теста, иначе этап станет is_completed=True
        и кнопки select_stage: пропадут из UI (available_stages фильтрует их).
        """
        result = await e2e_db.execute("""
            DELETE FROM trainee_test_access
            WHERE trainee_id = (
                SELECT id FROM users WHERE full_name = 'Стажёров Первый'
            )
        """)
        deleted_count = int(result.split()[-1])
        assert deleted_count > 0, (
            "No TraineeTestAccess records found for trainee1. "
            "Stage opening may not have created them."
        )
        shared_state["trainee1_deleted_access_count"] = deleted_count

    async def test_step3_trainee1_takes_test_via_fallback(
        self, trainee1: BotClient, shared_state: dict
    ):
        """
        КРИТИЧЕСКАЯ ПРОВЕРКА: Стажёр 1 проходит тест БЕЗ TraineeTestAccess,
        используя fallback на структуру траектории (тест в открытом этапе).

        БЕЗ ФИКСА: check_test_access → нет TraineeTestAccess → return False →
                   "Доступ запрещён" при попытке открыть тест
        С ФИКСОМ:  check_test_access → нет TraineeTestAccess → fallback →
                   тест в открытом этапе → return True → тест доступен

        Одновременно создаёт TestResult (нужен для последующих E2E сценариев).
        """
        await wait_between_actions()

        result_text = await take_test_via_trajectory(
            trainee1,
            stage_name="Базовые",
            test_name="E2E Тест Кофе",
            correct_answer_index=1,
        )

        # КРИТИЧЕСКАЯ ПРОВЕРКА: НЕ должно быть "Доступ запрещен"
        assert not contains_access_denied(result_text), (
            f"BUG REPRODUCED: check_test_access has no trajectory fallback!\n"
            f"TraineeTestAccess was deleted (simulating post-reassignment state), "
            f"but test is in OPEN stage and should be accessible via fallback.\n"
            f"Old code: no TraineeTestAccess → immediate return False\n"
            f"Expected: fallback to trajectory structure → test in open stage → True\n"
            f"Response: {result_text[:500]}"
        )


# =========================================================================
# Сценарий 2: Сотрудник (бывший стажёр) сохраняет доступ к тестам
# =========================================================================


class TestScenario2_EmployeeAccess:
    """
    Баг check_test_access: сотрудник теряет доступ к тестам с creator_id = NULL.

    Реальный путь бага на продакшне:
    1. 49 из 89 тестов имеют creator_id = NULL (legacy-данные октября 2025)
    2. Старый код: get_user_by_id(NULL) → None → crash → return False
    3. Новый код: проверяет TraineeTestAccess → exists → return True

    Для воспроизведения: устанавливаем creator_id = NULL через SQL.
    """

    async def test_step1_mentor_opens_all_stages_for_trainee2(
        self, mentor: BotClient, shared_state: dict
    ):
        """Наставник открывает все этапы для Стажёра 2."""
        await open_mentor_stage(mentor, "Стажёров Второй", stage_number=1)
        await wait_between_actions()
        await open_mentor_stage(mentor, "Стажёров Второй", stage_number=2)

    async def test_step2_trainee2_passes_all_tests(
        self, trainee2: BotClient, shared_state: dict
    ):
        """Стажёр 2 проходит все тесты во всех этапах."""
        await wait_between_actions()

        # Тест 1: E2E Тест Кофе (этап 1)
        result = await take_test_via_trajectory(
            trainee2, stage_name="Базовые", test_name="E2E Тест Кофе",
            correct_answer_index=1,
        )
        assert not contains_access_denied(result)

        await wait_between_actions(3.0)

        # Тест 2: E2E Тест Сервис (этап 2, тест 1 в сессии)
        result = await take_test_via_trajectory(
            trainee2, stage_name="Продвинутые", test_name="E2E Тест Сервис",
            correct_answer_index=1, test_index=0,
        )
        assert not contains_access_denied(result)

        await wait_between_actions(3.0)

        # Тест 3: E2E Тест Гигиена (этап 2, тест 2 в сессии)
        result = await take_test_via_trajectory(
            trainee2, stage_name="Продвинутые", test_name="E2E Тест Гигиена",
            correct_answer_index=1, test_index=1,
        )
        assert not contains_access_denied(result)

    async def test_step3_mentor_assigns_attestation(
        self, mentor: BotClient, shared_state: dict
    ):
        """Наставник назначает аттестацию для Стажёра 2."""
        await wait_between_actions()

        resp = await mentor.send_and_wait(
            "Мои стажеры 👥", pattern="стажер|стажёр"
        )

        # Выбираем стажёра 2
        trainee_btn = mentor.find_button_data(
            resp, text_contains="Стажёров Второй", data_prefix="select_trainee_for_trajectory:"
        )
        if not trainee_btn:
            trainee_btn = mentor.find_button_data(
                resp, text_contains="Второй", data_prefix="select_trainee_for_trajectory:"
            )
        assert trainee_btn, "Trainee 2 not found"

        resp = await mentor.click_and_wait(
            resp, data=trainee_btn, wait_pattern="[Тт]раектори|[Ээ]тап|карточка|Аттестация"
        )

        # Нажимаем "Аттестация"
        att_btn = mentor.find_button_data(
            resp, text_contains="Аттестация", data_prefix="view_trainee_attestation:"
        )
        assert att_btn, f"Attestation button not found. Buttons: {mentor.get_button_texts(resp)}"

        resp = await mentor.click_and_wait(
            resp, data=att_btn,
            wait_pattern="руководител|[Рр]уководител|[Вв]ыбери|менеджер|назначить"
        )

        # Выбираем руководителя
        manager_btn = mentor.find_button_data(
            resp, data_prefix="select_manager_for_attestation:"
        )
        assert manager_btn, "Manager button not found for attestation"

        resp = await mentor.click_and_wait(
            resp, data=manager_btn,
            wait_pattern="Подтвердить|подтверд|назначить"
        )

        # Подтверждаем назначение
        resp = await mentor.click_and_wait(
            resp, data=b"confirm_attestation_assignment",
            wait_pattern="назначена|успешно|аттестация"
        )

    async def test_step4_manager_conducts_attestation(
        self, manager: BotClient, shared_state: dict
    ):
        """Руководитель проводит аттестацию: отвечает на все вопросы максимальным баллом."""
        await wait_between_actions()

        # Открываем меню аттестаций
        resp = await manager.send_and_wait(
            "Аттестация ✔️", pattern="[Аа]ттестац|стажер"
        )

        # Выбираем стажёра для аттестации
        att_btn = (
            manager.find_button_data(resp, text_contains="Второй", data_prefix="select_trainee_attestation:")
            or manager.find_button_data(resp, text_contains="Второй", data_prefix="manage_attestation:")
        )
        if not att_btn:
            # Берём первую аттестацию
            att_btn = (
                manager.find_button_data(resp, data_prefix="select_trainee_attestation:")
                or manager.find_button_data(resp, data_prefix="manage_attestation:")
            )
        assert att_btn, "Attestation assignment not found"

        resp = await manager.click_and_wait(
            resp, data=att_btn, wait_pattern="[Нн]ачать|аттестац"
        )

        # Начинаем аттестацию
        start_btn = manager.find_button_data(resp, data_prefix="start_attestation:")
        assert start_btn, "Start attestation button not found"

        resp = await manager.click_and_wait(
            resp, data=start_btn, wait_pattern="[Дд]а|[Пп]одтверд|[Нн]ачать"
        )

        # Подтверждаем начало
        resp = await manager.click_and_wait(
            resp, data=b"confirm_start_attestation",
            wait_pattern="вопрос|Вопрос|балл|оцен"
        )

        # Отвечаем на все вопросы максимальным баллом
        # Аттестация использует текстовый ввод баллов
        max_attempts = 10
        for i in range(max_attempts):
            text = resp.text or ""
            # Проверяем, не закончились ли вопросы
            if "пройдена" in text.lower() or "результат" in text.lower() or "завершена" in text.lower():
                break

            # Вводим максимальный балл (10)
            resp = await manager.send_and_wait(
                "10",
                pattern="вопрос|Вопрос|балл|пройдена|результат|завершена|Набрано",
                timeout=10.0,
            )

        # Проверяем успешность аттестации
        final_text = resp.text or ""
        assert "пройдена" in final_text.lower() or "✅" in final_text, (
            f"Attestation not marked as passed: {final_text[:300]}"
        )

    async def test_step5_trainee2_becomes_employee(
        self, trainee2: BotClient, shared_state: dict
    ):
        """Стажёр 2 нажимает 'Стать сотрудником'."""
        await wait_between_actions(3.0)

        # Ищем уведомление с кнопкой "Стать сотрудником"
        messages = await trainee2.get_messages(limit=10)
        become_btn = None
        target_msg = None

        for msg in messages:
            if msg.out:
                continue
            btn = trainee2.find_button_data(msg, data_prefix="become_employee")
            if btn:
                become_btn = btn
                target_msg = msg
                break

        if target_msg and become_btn:
            resp = await trainee2.click_and_wait(
                target_msg, data=become_btn,
                wait_pattern="сотрудник|Сотрудник|Поздравля|обновить"
            )
        else:
            # Может уже быть сотрудником или уведомление было раньше
            # Пробуем /start чтобы обновить меню
            resp = await trainee2.send_and_wait(
                "/start", pattern="меню|[Мм]ой профиль|Сотрудник"
            )

    async def test_step6_set_null_creator_id(
        self, e2e_db: asyncpg.Connection, shared_state: dict
    ):
        """
        SQL: Устанавливаем creator_id = NULL для теста "E2E Тест Кофе".

        Симулирует legacy-данные из продакшна:
        49 из 89 тестов (все из октября 2025) имеют creator_id = NULL.
        На продакшне test_id: 12, 16, 19, 50 — все без создателя.
        """
        result = await e2e_db.execute("""
            UPDATE tests SET creator_id = NULL
            WHERE name = 'E2E Тест Кофе'
        """)
        assert "UPDATE 1" in result, (
            f"Failed to nullify creator_id on 'E2E Тест Кофе': {result}"
        )

    async def test_step7_employee_can_access_test_with_null_creator(
        self, trainee2: BotClient, shared_state: dict
    ):
        """
        КРИТИЧЕСКАЯ ПРОВЕРКА: Сотрудник может открыть тест с creator_id = NULL
        через "Мои тесты 📋".

        БЕЗ ФИКСА: get_user_by_id(NULL) → None → None.id → AttributeError →
                    except → return False → "Доступ запрещен"
        С ФИКСОМ:  проверка TraineeTestAccess → запись существует → return True
        """
        await wait_between_actions()

        resp = await trainee2.send_and_wait(
            "Мои тесты 📋", pattern="тест|Тест|Нет тестов|пусто"
        )

        text = resp.text or ""

        # Проверяем, что есть тесты и нет отказа в доступе
        assert not contains_access_denied(text), (
            f"BUG REPRODUCED: Employee lost access to tests! Response: {text[:500]}"
        )

        # Пробуем открыть конкретный тест с creator_id = NULL
        test_btn = trainee2.find_button_data(
            resp, text_contains="Кофе", data_prefix="test:"
        )
        if not test_btn:
            # Попробуем другие варианты кнопок
            test_btn = trainee2.find_button_data(
                resp, text_contains="Кофе", data_prefix="take_test:"
            )

        if test_btn:
            resp = await trainee2.click_and_wait(
                resp, data=test_btn,
                wait_pattern="тест|результат|балл|Кофе|доступ|пройден",
                timeout=10.0,
            )

            text = resp.text or ""
            assert not contains_access_denied(text), (
                f"BUG REPRODUCED: Employee denied access to test with creator_id=NULL!\n"
                f"Old code: get_user_by_id(NULL) → None → crash → return False\n"
                f"Expected: check TraineeTestAccess → exists → return True\n"
                f"Response: {text[:500]}"
            )
