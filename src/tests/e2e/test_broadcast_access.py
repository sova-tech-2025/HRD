"""
E2E Сценарий 5: Рассылочный тест — доступ сотруднику.

Проверяет, что сотрудник (бывший стажёр) может получить и пройти
рассылочный тест. Доступ через TraineeTestAccess с granted_by_id != None.

Зависит от test_check_test_access.py (Стажёр 2 стал Сотрудником).
"""

import pytest

from tests.e2e.helpers.bot_client import BotClient
from tests.e2e.helpers.waiters import (
    contains_access_denied,
    wait_between_actions,
)

pytestmark = [
    pytest.mark.order(5),
    pytest.mark.timeout(300),
    pytest.mark.asyncio(loop_scope="session"),
]


class TestScenario5_BroadcastTestAccess:
    """
    Рассылочные тесты работают для сотрудников.

    Покрывает: oc.md → check_test_access, путь granted_by_id.
    Лог-доказательство: сотрудник 441 — рассылочные тесты 246, 233, 232
    работали, а тесты 12, 50 (без granted_by_id) — нет.

    Ожидание: сотрудник получает рассылку и может пройти тест.
    """

    async def test_step1_recruiter_creates_broadcast(self, recruiter: BotClient, shared_state: dict):
        """Рекрутер создаёт рассылку с тестом 'E2E Тест Кофе'."""
        await wait_between_actions()

        # Открываем меню рассылок
        resp = await recruiter.send_and_wait("Рассылка ✈️", pattern="[Рр]ассылк|действие|Создать")

        # Нажимаем "Создать рассылку"
        resp = await recruiter.click_and_wait(resp, data=b"create_broadcast", wait_pattern="текст|сообщение|Введи")

        # Вводим текст рассылки
        resp = await recruiter.send_and_wait(
            "E2E тестовая рассылка: проверьте свои знания!", pattern="фото|Фото|изображени|материал"
        )

        # Пропускаем фото → может перейти к материалам или сразу к тестам
        skip_photo_btn = recruiter.find_button_data(resp, data_prefix="broadcast_skip_photos")
        if skip_photo_btn:
            resp = await recruiter.click_and_wait(resp, data=skip_photo_btn, wait_pattern="материал|папк|тест|Выбери")

        # Пропускаем материалы (если есть — иначе уже на шаге теста)
        skip_material_btn = recruiter.find_button_data(resp, data_prefix="broadcast_skip_material")
        if skip_material_btn:
            resp = await recruiter.click_and_wait(resp, data=skip_material_btn, wait_pattern="тест|Выбери тест")

        # Ждём чуть больше — два edit_text подряд могут создать race
        await wait_between_actions(2.0)
        resp = await recruiter.get_last_message()

        # Выбираем тест "E2E Тест Кофе"
        test_btn = recruiter.find_button_data(resp, text_contains="Кофе", data_prefix="broadcast_test:")
        if not test_btn:
            # Может быть другой формат кнопки
            test_btn = recruiter.find_button_data(resp, text_contains="Кофе")
        assert test_btn, (
            f"Test 'E2E Тест Кофе' not found for broadcast. "
            f"Buttons: {recruiter.get_button_texts(resp)}. "
            f"Message: {(resp.text or '')[:300]}"
        )
        resp = await recruiter.click_and_wait(
            resp, data=test_btn, wait_pattern="рол[иеь]|Рол[иеь]|Кому|получател|Выбор рол"
        )

        # Выбираем роли: все
        all_roles_btn = recruiter.find_button_data(resp, data_prefix="broadcast_roles_all")
        if all_roles_btn:
            await recruiter.click_button(resp, data=all_roles_btn)
            await wait_between_actions(1.0)
            resp = await recruiter.get_last_message()

        # Нажимаем "Далее" (к выбору групп)
        next_btn = recruiter.find_button_data(resp, data_prefix="broadcast_roles_next")
        if next_btn:
            resp = await recruiter.click_and_wait(resp, data=next_btn, wait_pattern="групп|Групп")

        # Выбираем группу "Бариста"
        group_btn = recruiter.find_button_data(resp, text_contains="Бариста", data_prefix="broadcast_group:")
        if group_btn:
            await recruiter.click_button(resp, data=group_btn)
            await wait_between_actions(1.0)
            resp = await recruiter.get_last_message()

        # Кнопка "Отправить" на шаге групп открывает шаг выбора объектов (Шаг 7)
        send_btn = recruiter.find_button_data(resp, data_prefix="broadcast_send")
        assert send_btn, f"Send broadcast button not found. Buttons: {recruiter.get_button_texts(resp)}"
        resp = await recruiter.click_and_wait(resp, data=send_btn, wait_pattern="Выбор объектов|объект")

        # Выбираем все объекты
        all_objects_btn = recruiter.find_button_data(resp, data_prefix="broadcast_objects_all")
        if all_objects_btn:
            await recruiter.click_button(resp, data=all_objects_btn)
            await wait_between_actions(1.0)
            resp = await recruiter.get_last_message()

        # Финальная отправка рассылки
        objects_send_btn = recruiter.find_button_data(resp, data_prefix="broadcast_objects_send")
        assert objects_send_btn, f"Objects send button not found. Buttons: {recruiter.get_button_texts(resp)}"
        resp = await recruiter.click_and_wait(
            resp,
            data=objects_send_btn,
            wait_pattern="успешно отправил|Статистика|Уведомлений отправлено",
            timeout=30.0,
        )

        shared_state["broadcast_sent"] = True

    async def test_step2_employee_receives_broadcast(self, trainee2: BotClient, shared_state: dict):
        """
        Сотрудник (Стажёр 2, ставший сотрудником) получает рассылку
        и может открыть тест.
        """
        await wait_between_actions(5.0)

        # Ищем уведомление о рассылке в последних сообщениях
        messages = await trainee2.get_messages(limit=15)
        broadcast_msg = None
        test_btn = None

        for msg in messages:
            if msg.out:
                continue
            text = msg.text or ""
            if "рассылка" in text.lower() or "E2E тестовая" in text:
                btn = trainee2.find_button_data(msg, data_prefix="take_test:")
                if btn:
                    broadcast_msg = msg
                    test_btn = btn
                    break

        if not broadcast_msg:
            # Ищем любое сообщение с кнопкой take_test
            for msg in messages:
                if msg.out:
                    continue
                btn = trainee2.find_button_data(msg, data_prefix="take_test:")
                if btn:
                    broadcast_msg = msg
                    test_btn = btn
                    break

        assert broadcast_msg, "Employee did not receive broadcast notification with test button"

        # Нажимаем "Перейти к тесту"
        resp = await trainee2.click_and_wait(
            broadcast_msg,
            data=test_btn,
            wait_pattern="тест|[Нн]ачать|вопрос|Кофе|доступ",
            timeout=15.0,
        )

        text = resp.text or ""

        # КРИТИЧЕСКАЯ ПРОВЕРКА: НЕ должно быть "Доступ запрещен"
        assert not contains_access_denied(text), (
            f"BUG: Employee denied access to broadcast test! granted_by_id should allow access. Response: {text[:500]}"
        )

    async def test_step3_employee_can_take_broadcast_test(self, trainee2: BotClient, shared_state: dict):
        """
        Сотрудник может пройти рассылочный тест.

        Проверяет, что check_test_access разрешает доступ
        через TraineeTestAccess с granted_by_id != None.
        """
        await wait_between_actions()

        # Открываем "Мои тесты" и ищем рассылочный тест
        resp = await trainee2.send_and_wait("Мои тесты 📋", pattern="тест|Тест|Нет тестов")

        text = resp.text or ""

        # Проверяем, что есть тесты
        assert not contains_access_denied(text), f"Employee access denied to test list! Response: {text[:300]}"

        # Ищем тест "Кофе"
        test_btn = trainee2.find_button_data(resp, text_contains="Кофе", data_prefix="test:")
        if not test_btn:
            test_btn = trainee2.find_button_data(resp, text_contains="Кофе", data_prefix="take_test:")

        if test_btn:
            resp = await trainee2.click_and_wait(
                resp,
                data=test_btn,
                wait_pattern="тест|результат|балл|Кофе|доступ|вопрос",
                timeout=10.0,
            )

            text = resp.text or ""
            assert not contains_access_denied(text), (
                f"BUG: Employee denied access to specific broadcast test! Response: {text[:500]}"
            )


class TestScenario5b_BroadcastByEmployee:
    """Поимённая рассылка: на шаге 5 рекрутер выбирает конкретного сотрудника
    по ФИО (шаг выбора групп пропускается) и отправляет ему рассылку."""

    BROADCAST_TEXT = "E2E поимённая рассылка выбранному сотруднику"

    async def test_step1_broadcast_to_selected_employee(self, recruiter: BotClient):
        await wait_between_actions()

        resp = await recruiter.send_and_wait("Рассылка ✈️", pattern="[Рр]ассылк|действие|Создать")
        resp = await recruiter.click_and_wait(resp, data=b"create_broadcast", wait_pattern="текст|сообщение|Введи")
        resp = await recruiter.send_and_wait(self.BROADCAST_TEXT, pattern="фото|Фото|изображени|материал")

        skip_photo = recruiter.find_button_data(resp, data_prefix="broadcast_skip_photos")
        if skip_photo:
            resp = await recruiter.click_and_wait(resp, data=skip_photo, wait_pattern="материал|папк|тест|Выбери")
        skip_material = recruiter.find_button_data(resp, data_prefix="broadcast_skip_material")
        if skip_material:
            resp = await recruiter.click_and_wait(resp, data=skip_material, wait_pattern="тест|Выбери тест")

        await wait_between_actions(2.0)
        resp = await recruiter.get_last_message()
        skip_test = recruiter.find_button_data(resp, data_prefix="broadcast_skip_test")
        assert skip_test, f"Нет кнопки пропуска теста. Кнопки: {recruiter.get_button_texts(resp)}"
        resp = await recruiter.click_and_wait(resp, data=skip_test, wait_pattern="Выбор ролей|Шаг 5")

        # Новая кнопка «Выбрать сотрудника»
        emp_btn = recruiter.find_button_data(resp, data_prefix="broadcast_select_employee")
        assert emp_btn, f"Нет кнопки «Выбрать сотрудника». Кнопки: {recruiter.get_button_texts(resp)}"
        resp = await recruiter.click_and_wait(resp, data=emp_btn, wait_pattern="Выбор сотрудников")

        # Поиск по ФИО
        search_btn = recruiter.find_button_data(resp, data_prefix="bc_emp_search")
        assert search_btn, f"Нет кнопки поиска. Кнопки: {recruiter.get_button_texts(resp)}"
        resp = await recruiter.click_and_wait(resp, data=search_btn, wait_pattern="Введи ФИО|Поиск")
        resp = await recruiter.send_and_wait("Стажёров", pattern="Результаты|никого|Выбрано")

        # Отмечаем сотрудника
        toggle_btn = recruiter.find_button_data(resp, text_contains="Стажёров", data_prefix="bc_emp_toggle:")
        assert toggle_btn, f"Сотрудник не найден в результатах. Кнопки: {recruiter.get_button_texts(resp)}"
        resp = await recruiter.click_and_wait(resp, data=toggle_btn, wait_pattern="Выбрано")

        # Далее → сводка выбранных
        next_btn = recruiter.find_button_data(resp, data_prefix="bc_emp_next")
        assert next_btn, f"Нет кнопки «Далее». Кнопки: {recruiter.get_button_texts(resp)}"
        resp = await recruiter.click_and_wait(resp, data=next_btn, wait_pattern="Выбрано сотрудников|Отправить")

        # Отправить
        send_btn = recruiter.find_button_data(resp, data_prefix="bc_emp_send")
        assert send_btn, f"Нет кнопки «Отправить». Кнопки: {recruiter.get_button_texts(resp)}"
        resp = await recruiter.click_and_wait(
            resp, data=send_btn, wait_pattern="отправлена выбранным|Уведомлений отправлено", timeout=30.0
        )

    async def test_step2_selected_employee_receives(self, trainee2: BotClient):
        await wait_between_actions(5.0)
        messages = await trainee2.get_messages(limit=15)
        received = any((not m.out) and self.BROADCAST_TEXT in (m.text or "") for m in messages)
        assert received, "Выбранный поимённо сотрудник не получил рассылку"
