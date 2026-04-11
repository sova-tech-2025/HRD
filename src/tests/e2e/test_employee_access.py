"""
E2E Сценарий: Сотрудник (бывший стажёр) сохраняет доступ к тестам.

Тестирует check_test_access для сотрудника с тестами, у которых creator_id = NULL
(legacy-данные из продакшна).

Запускается ПОСЛЕ test_attestation_flows.py (order=7), где trainee становится Сотрудником.

Зависит от: test_setup.py, test_attestation_flows.py (trainee уже Employee).
"""

import asyncpg
import pytest

from tests.e2e.helpers.bot_client import BotClient
from tests.e2e.helpers.waiters import (
    contains_access_denied,
    wait_between_actions,
)

pytestmark = [
    pytest.mark.order(8),
    pytest.mark.timeout(300),
    pytest.mark.asyncio(loop_scope="session"),
]


class TestEmployeeTestAccess:
    """
    Баг check_test_access: сотрудник теряет доступ к тестам с creator_id = NULL.

    Реальный путь бага на продакшне:
    1. 49 из 89 тестов имеют creator_id = NULL (legacy-данные октября 2025)
    2. Старый код: get_user_by_id(NULL) -> None -> crash -> return False
    3. Новый код: проверяет TraineeTestAccess -> exists -> return True

    Для воспроизведения: устанавливаем creator_id = NULL через SQL.
    """

    async def test_step1_set_null_creator_id(self, e2e_db: asyncpg.Connection, shared_state: dict):
        """
        SQL: Устанавливаем creator_id = NULL для теста "E2E Тест Кофе".

        Симулирует legacy-данные из продакшна:
        49 из 89 тестов (все из октября 2025) имеют creator_id = NULL.
        """
        result = await e2e_db.execute("""
            UPDATE tests SET creator_id = NULL
            WHERE name = 'E2E Тест Кофе'
        """)
        assert "UPDATE 1" in result, f"Failed to nullify creator_id on 'E2E Тест Кофе': {result}"

    async def test_step2_employee_can_access_test_with_null_creator(self, trainee: BotClient, shared_state: dict):
        """
        КРИТИЧЕСКАЯ ПРОВЕРКА: Сотрудник может открыть тест с creator_id = NULL
        через "Мои тесты 📋".

        БЕЗ ФИКСА: get_user_by_id(NULL) -> None -> None.id -> AttributeError ->
                    except -> return False -> "Доступ запрещен"
        С ФИКСОМ:  проверка TraineeTestAccess -> запись существует -> return True
        """
        await wait_between_actions()

        resp = await trainee.send_and_wait("Мои тесты 📋", pattern="тест|Тест|Нет тестов|пусто")

        text = resp.text or ""

        # Проверяем, что есть тесты и нет отказа в доступе
        assert not contains_access_denied(text), (
            f"BUG REPRODUCED: Employee lost access to tests! Response: {text[:500]}"
        )

        # Пробуем открыть конкретный тест с creator_id = NULL
        test_btn = trainee.find_button_data(resp, text_contains="Кофе", data_prefix="test:")
        if not test_btn:
            test_btn = trainee.find_button_data(resp, text_contains="Кофе", data_prefix="take_test:")

        if test_btn:
            resp = await trainee.click_and_wait(
                resp,
                data=test_btn,
                wait_pattern="тест|результат|балл|Кофе|доступ|пройден",
                timeout=10.0,
            )

            text = resp.text or ""
            assert not contains_access_denied(text), (
                f"BUG REPRODUCED: Employee denied access to test with creator_id=NULL!\n"
                f"Old code: get_user_by_id(NULL) -> None -> crash -> return False\n"
                f"Expected: check TraineeTestAccess -> exists -> return True\n"
                f"Response: {text[:500]}"
            )
