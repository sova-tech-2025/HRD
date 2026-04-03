"""
E2E Сценарий 9: Полные flow экзаменов по ролям.

Покрывает:
- Класс 1: Рекрутер создаёт экзамен (название, вопросы, проходной балл)
- Класс 2: Меню рекрутера — полный набор кнопок + карточка с удалением/назначением
- Класс 3: Меню наставника — список экзаменов, назначение, без создания/проведения
- Класс 4: Меню руководителя — проведение/сдача, без создания/списка
- Класс 5: Меню сотрудника — проведение/сдача, без создания/списка
- Класс 6: Стажёр заблокирован
- Класс 7: Рекрутер назначает экзамен (экзаменатор=руководитель, сдающий=наставник)
- Класс 8: Руководитель проводит экзамен (вопросы, баллы, результат)
- Класс 9: Наставник видит завершённый экзамен в «Сдать экзамен»

Зависит от test_attestation_flows.py (order=8).
"""

import pytest

from tests.e2e.helpers.bot_client import BotClient
from tests.e2e.helpers.waiters import wait_between_actions

pytestmark = [
    pytest.mark.order(9),
    pytest.mark.timeout(600),
    pytest.mark.asyncio(loop_scope="session"),
]


# =========================================================================
# Класс 1: Рекрутер создаёт экзамен
# =========================================================================


class TestExamCreation:
    """Рекрутер создаёт экзамен: название → вопросы → проходной балл."""

    async def test_step1_recruiter_opens_exam_menu(self, recruiter: BotClient):
        """Рекрутер открывает меню экзаменов."""
        resp = await recruiter.send_and_wait("Экзамены 📝", pattern="РЕДАКТОР Экзаменов|действие")
        buttons = recruiter.get_button_texts(resp)
        assert any("Создать экзамен" in b for b in buttons), f"No 'Создать' button. Buttons: {buttons}"
        assert any("Провести экзамен" in b for b in buttons), f"No 'Провести' button. Buttons: {buttons}"
        assert any("Сдать экзамен" in b for b in buttons), f"No 'Сдать' button. Buttons: {buttons}"

    async def test_step2_recruiter_creates_exam(self, recruiter: BotClient, shared_state: dict):
        """Рекрутер создаёт экзамен с 2 вопросами и проходным баллом 10."""
        await wait_between_actions()

        # Открываем меню и нажимаем «Создать»
        resp = await recruiter.send_and_wait("Экзамены 📝", pattern="РЕДАКТОР Экзаменов")
        resp = await recruiter.click_and_wait(resp, data=b"exam_create", wait_pattern="название|Название")

        # Вводим название
        resp = await recruiter.send_and_wait("E2E Экзамен Кофе", pattern="Вопрос 1")

        # Вопрос 1
        resp = await recruiter.send_and_wait(
            "Правильно ли приготовлен эспрессо?",
            pattern="Вопрос 2|Сохранить",
        )

        # Вопрос 2
        resp = await recruiter.send_and_wait(
            "Проверка темперовки",
            pattern="Вопрос 3|сохрани",
        )

        # Сохраняем вопросы
        resp = await recruiter.click_and_wait(
            resp, data=b"exam_save_questions", wait_pattern="проходной балл|Проходной"
        )

        # Вводим проходной балл
        resp = await recruiter.send_and_wait("10", pattern="успешно создан")

        resp_text = resp.text or ""
        assert "E2E Экзамен Кофе" in resp_text, f"Exam name not in response: {resp_text[:300]}"
        shared_state["exam_name"] = "E2E Экзамен Кофе"

    async def test_step3_exam_appears_in_list(self, recruiter: BotClient, shared_state: dict):
        """Созданный экзамен появляется в списке меню рекрутера."""
        await wait_between_actions()

        resp = await recruiter.send_and_wait("Экзамены 📝", pattern="РЕДАКТОР")
        exam_btn = recruiter.find_button_data(resp, text_contains="E2E Экзамен Кофе", data_prefix="exam_view:")
        assert exam_btn, f"Exam not in list. Buttons: {recruiter.get_button_texts(resp)}"


# =========================================================================
# Класс 2: Меню рекрутера — полный набор кнопок
# =========================================================================


class TestRecruiterExamMenu:
    """Проверяем полный набор кнопок рекрутера и карточку экзамена."""

    async def test_step1_recruiter_sees_full_menu(self, recruiter: BotClient):
        """Рекрутер видит все кнопки: создать, провести, сдать, список экзаменов."""
        resp = await recruiter.send_and_wait("Экзамены 📝", pattern="РЕДАКТОР")
        buttons = recruiter.get_button_texts(resp)

        assert any("Создать экзамен" in b for b in buttons), f"No 'Создать'. Buttons: {buttons}"
        assert any("Провести экзамен" in b for b in buttons), f"No 'Провести'. Buttons: {buttons}"
        assert any("Сдать экзамен" in b for b in buttons), f"No 'Сдать'. Buttons: {buttons}"
        assert any("E2E Экзамен Кофе" in b for b in buttons), f"No exam in list. Buttons: {buttons}"

    async def test_step2_recruiter_sees_exam_card_with_delete_and_assign(self, recruiter: BotClient):
        """Рекрутер видит карточку экзамена с кнопками «Удалить» и «Назначить»."""
        await wait_between_actions()

        resp = await recruiter.send_and_wait("Экзамены 📝", pattern="РЕДАКТОР")
        exam_btn = recruiter.find_button_data(resp, text_contains="E2E Экзамен Кофе", data_prefix="exam_view:")
        assert exam_btn, f"Exam button not found. Buttons: {recruiter.get_button_texts(resp)}"

        resp = await recruiter.click_and_wait(
            resp, data=exam_btn, wait_pattern="Экзамен.*E2E Экзамен Кофе|E2E Экзамен Кофе"
        )

        buttons = recruiter.get_button_texts(resp)
        assert any("Удалить" in b for b in buttons), f"No 'Удалить' button. Buttons: {buttons}"
        assert any("Назначить" in b for b in buttons), f"No 'Назначить' button. Buttons: {buttons}"


# =========================================================================
# Класс 3: Меню наставника
# =========================================================================


class TestMentorExamMenu:
    """Наставник видит список экзаменов и может назначить, но не создать/провести."""

    async def test_step1_mentor_opens_exam_menu(self, mentor: BotClient):
        """Наставник открывает экзамены через reply-кнопку (обходит state.clear в inline меню)."""
        resp = await mentor.send_and_wait("Экзамены 📝", pattern="РЕДАКТОР")

        buttons = mentor.get_button_texts(resp)

        # Наставник ВИДИТ: «Сдать экзамен», экзамен в списке
        assert any("Сдать экзамен" in b for b in buttons), f"No 'Сдать' button. Buttons: {buttons}"
        assert any("E2E Экзамен Кофе" in b for b in buttons), f"No exam in list. Buttons: {buttons}"

        # Наставник НЕ видит: «Создать экзамен»
        assert not any("Создать экзамен" in b for b in buttons), f"'Создать' should NOT be visible. Buttons: {buttons}"
        # Наставник НЕ экзаменатор → НЕ видит «Провести экзамен»
        assert not any("Провести экзамен" in b for b in buttons), (
            f"'Провести' should NOT be visible. Buttons: {buttons}"
        )

    async def test_step2_mentor_sees_assign_button_on_card(self, mentor: BotClient):
        """Наставник видит кнопку «Назначить» на карточке, но не «Удалить»."""
        await wait_between_actions()

        resp = await mentor.send_and_wait("Экзамены 📝", pattern="РЕДАКТОР")

        exam_btn = mentor.find_button_data(resp, text_contains="E2E Экзамен Кофе", data_prefix="exam_view:")
        assert exam_btn, f"Exam button not found. Buttons: {mentor.get_button_texts(resp)}"

        resp = await mentor.click_and_wait(resp, data=exam_btn, wait_pattern="E2E Экзамен Кофе")

        buttons = mentor.get_button_texts(resp)
        assert any("Назначить" in b for b in buttons), f"No 'Назначить' button. Buttons: {buttons}"
        assert not any("Удалить" in b for b in buttons), f"'Удалить' should NOT be visible. Buttons: {buttons}"


# =========================================================================
# Класс 4: Меню руководителя
# =========================================================================


class TestManagerExamMenu:
    """Руководитель: провести/сдать, без создания и списка экзаменов."""

    async def test_step1_manager_sees_limited_menu(self, manager: BotClient):
        """Руководитель видит «Провести» и «Сдать», но не «Создать» и не список."""
        resp = await manager.send_and_wait("Экзамены 📝", pattern="РЕДАКТОР")
        buttons = manager.get_button_texts(resp)

        assert any("Провести экзамен" in b for b in buttons), f"No 'Провести'. Buttons: {buttons}"
        assert any("Сдать экзамен" in b for b in buttons), f"No 'Сдать'. Buttons: {buttons}"

        # Руководитель НЕ видит
        assert not any("Создать экзамен" in b for b in buttons), f"'Создать' should NOT be visible. Buttons: {buttons}"
        assert not any("E2E Экзамен Кофе" in b for b in buttons), f"Exam list should NOT be visible. Buttons: {buttons}"


# =========================================================================
# Класс 5: Меню сотрудника
# =========================================================================


class TestEmployeeExamMenu:
    """Сотрудник (trainee2 стал сотрудником в order=2): провести/сдать, без создания/списка."""

    async def test_step1_employee_sees_limited_menu(self, trainee2: BotClient):
        """Сотрудник видит «Провести» и «Сдать», но не «Создать» и не список."""
        resp = await trainee2.send_and_wait("Экзамены 📝", pattern="РЕДАКТОР")
        buttons = trainee2.get_button_texts(resp)

        assert any("Провести экзамен" in b for b in buttons), f"No 'Провести'. Buttons: {buttons}"
        assert any("Сдать экзамен" in b for b in buttons), f"No 'Сдать'. Buttons: {buttons}"

        # Сотрудник НЕ видит
        assert not any("Создать экзамен" in b for b in buttons), f"'Создать' should NOT be visible. Buttons: {buttons}"
        assert not any("E2E Экзамен Кофе" in b for b in buttons), f"Exam list should NOT be visible. Buttons: {buttons}"


# =========================================================================
# Класс 6: Стажёр заблокирован
# =========================================================================


class TestTraineeExamBlocked:
    """Стажёр не может открыть экзамены."""

    async def test_step1_trainee_cannot_access_exams(self, trainee1: BotClient):
        """Стажёр получает отказ при попытке открыть экзамены."""
        resp = await trainee1.send_and_wait("Экзамены 📝", pattern="не доступны|стажёр|Стажёр|не найден")
        resp_text = resp.text or ""
        assert "не доступны" in resp_text.lower() or "стажёр" in resp_text.lower(), (
            f"Expected access denied for trainee. Response: {resp_text[:300]}"
        )


# =========================================================================
# Класс 7: Стажёр не попадает в список сдающих при назначении экзамена
# =========================================================================


class TestTraineeExcludedFromExamAssignment:
    """По ТЗ стажёр не может быть назначен сдающим экзамена."""

    async def test_step1_trainee_not_in_examinee_list(self, recruiter: BotClient, shared_state: dict):
        """Рекрутер открывает список сдающих — стажёр отсутствует."""
        await wait_between_actions()

        # Открываем меню экзаменов
        resp = await recruiter.send_and_wait("Экзамены 📝", pattern="РЕДАКТОР")

        # Находим экзамен и открываем карточку
        exam_btn = recruiter.find_button_data(resp, text_contains="E2E Экзамен Кофе", data_prefix="exam_view:")
        assert exam_btn, f"Exam not found. Buttons: {recruiter.get_button_texts(resp)}"
        resp = await recruiter.click_and_wait(resp, data=exam_btn, wait_pattern="E2E Экзамен Кофе")

        # Нажимаем «Назначить»
        assign_btn = recruiter.find_button_data(resp, data_prefix="exam_assign:")
        assert assign_btn, f"Assign button not found. Buttons: {recruiter.get_button_texts(resp)}"
        resp = await recruiter.click_and_wait(resp, data=assign_btn, wait_pattern="Экзаменатор|экзаменатор")

        # Выбираем экзаменатора (руководителя)
        examiner_btn = recruiter.find_button_data(resp, text_contains="Руководителев", data_prefix="exam_examiner:")
        assert examiner_btn, f"Examiner not found. Buttons: {recruiter.get_button_texts(resp)}"
        resp = await recruiter.click_and_wait(resp, data=examiner_btn, wait_pattern="Сдающий|способ поиска")

        # Нажимаем «Все пользователи»
        all_btn = recruiter.find_button_data(resp, data_prefix="ef_all")
        assert all_btn, f"'All users' button not found. Buttons: {recruiter.get_button_texts(resp)}"
        resp = await recruiter.click_and_wait(resp, data=all_btn, wait_pattern="Найдено|Выбери")

        # Получаем список имён
        button_texts = recruiter.get_button_texts(resp)

        # Стажёр (trainee1 = "Стажёров Первый") НЕ должен быть в списке сдающих
        assert not any("Стажёров Первый" in b for b in button_texts), (
            f"Trainee 'Стажёров Первый' should NOT be in examinee list. Buttons: {button_texts}"
        )

        # Сотрудник (trainee2 = "Стажёров Второй", перешёл в роль Сотрудник) ДОЛЖЕН быть
        assert any("Стажёров Второй" in b for b in button_texts), (
            f"Employee 'Стажёров Второй' should be in examinee list. Buttons: {button_texts}"
        )

        # Наставник тоже ДОЛЖЕН быть
        assert any("Наставников" in b for b in button_texts), (
            f"Mentor 'Наставников' should be in examinee list. Buttons: {button_texts}"
        )


# =========================================================================
# Класс 8: Рекрутер назначает экзамен
# =========================================================================


class TestExamAssignment:
    """Рекрутер назначает экзамен: экзаменатор=Руководителев, сдающий=Наставников."""

    async def test_step1_open_exam_card_and_assign(self, recruiter: BotClient, shared_state: dict):
        """Рекрутер открывает карточку экзамена и нажимает «Назначить»."""
        await wait_between_actions()

        resp = await recruiter.send_and_wait("Экзамены 📝", pattern="РЕДАКТОР")
        exam_btn = recruiter.find_button_data(resp, text_contains="E2E Экзамен Кофе", data_prefix="exam_view:")
        assert exam_btn, f"Exam button not found. Buttons: {recruiter.get_button_texts(resp)}"

        resp = await recruiter.click_and_wait(resp, data=exam_btn, wait_pattern="E2E Экзамен Кофе")

        assign_btn = recruiter.find_button_data(resp, data_prefix="exam_assign:")
        assert assign_btn, f"Assign button not found. Buttons: {recruiter.get_button_texts(resp)}"

        resp = await recruiter.click_and_wait(resp, data=assign_btn, wait_pattern="Экзаменатор|экзаменатор")

        shared_state["exam_assign_resp"] = resp

    async def test_step2_select_examiner(self, recruiter: BotClient, shared_state: dict):
        """Рекрутер выбирает руководителя как экзаменатора."""
        resp = shared_state.get("exam_assign_resp")
        if not resp:
            pytest.skip("No assign response from previous step")

        examiner_btn = recruiter.find_button_data(resp, text_contains="Руководителев", data_prefix="exam_examiner:")
        assert examiner_btn, f"Examiner button not found. Buttons: {recruiter.get_button_texts(resp)}"

        resp = await recruiter.click_and_wait(resp, data=examiner_btn, wait_pattern="Сдающий|способ поиска")

        shared_state["exam_filter_resp"] = resp

    async def test_step3_filter_all_select_examinee(self, recruiter: BotClient, shared_state: dict):
        """Рекрутер выбирает «Все пользователи» и находит наставника."""
        resp = shared_state.get("exam_filter_resp")
        if not resp:
            pytest.skip("No filter response from previous step")

        # Нажимаем «Все пользователи»
        all_btn = recruiter.find_button_data(resp, data_prefix="ef_all")
        assert all_btn, f"'All users' button not found. Buttons: {recruiter.get_button_texts(resp)}"

        resp = await recruiter.click_and_wait(resp, data=all_btn, wait_pattern="Найдено|Выбери")

        # Ищем наставника
        examinee_btn = recruiter.find_button_data(resp, text_contains="Наставников", data_prefix="ef_user:")
        assert examinee_btn, f"Examinee not found. Buttons: {recruiter.get_button_texts(resp)}"

        resp = await recruiter.click_and_wait(
            resp, data=examinee_btn, wait_pattern="Карточка|Назначить экзамен|Назначить"
        )

        shared_state["exam_examinee_card_resp"] = resp

    async def test_step4_confirm_assignment(self, recruiter: BotClient, shared_state: dict):
        """Рекрутер подтверждает назначение экзамена."""
        resp = shared_state.get("exam_examinee_card_resp")
        if not resp:
            pytest.skip("No examinee card from previous step")

        resp = await recruiter.click_and_wait(resp, data=b"exam_confirm_assign", wait_pattern="ЭКЗАМЕН НАЗНАЧЕН")

        resp_text = resp.text or ""
        assert "Руководителев" in resp_text, f"Examiner name not in response: {resp_text[:300]}"
        assert "Наставников" in resp_text, f"Examinee name not in response: {resp_text[:300]}"
        shared_state["exam_assigned"] = True

    async def test_step5_examiner_receives_notification(self, manager: BotClient, shared_state: dict):
        """Руководитель (экзаменатор) получает уведомление о назначении."""
        if not shared_state.get("exam_assigned"):
            pytest.skip("Exam was not assigned — previous steps failed")
        await wait_between_actions(3.0)

        messages = await manager.get_messages(limit=10)
        found = False
        for msg in messages:
            if msg.out:
                continue
            text = msg.text or ""
            if "назначен экзамен для проведения" in text.lower() or "назначен экзамен" in text.lower():
                assert "E2E Экзамен Кофе" in text, f"Exam name not in notification: {text[:300]}"
                assert "Наставников" in text, f"Examinee name not in notification: {text[:300]}"
                found = True
                break

        assert found, (
            f"Examiner notification not found. Last messages: {[m.text[:100] for m in messages if not m.out][:5]}"
        )

    async def test_step6_examinee_receives_notification(self, mentor: BotClient, shared_state: dict):
        """Наставник (сдающий) получает уведомление о назначении."""
        if not shared_state.get("exam_assigned"):
            pytest.skip("Exam was not assigned — previous steps failed")
        messages = await mentor.get_messages(limit=10)
        found = False
        for msg in messages:
            if msg.out:
                continue
            text = msg.text or ""
            if "назначен Экзамен" in text or "назначен экзамен" in text.lower():
                assert "E2E Экзамен Кофе" in text, f"Exam name not in notification: {text[:300]}"
                assert "Руководителев" in text, f"Examiner name not in notification: {text[:300]}"
                found = True
                break

        assert found, (
            f"Examinee notification not found. Last messages: {[m.text[:100] for m in messages if not m.out][:5]}"
        )


# =========================================================================
# Класс 8: Руководитель проводит экзамен
# =========================================================================


class TestExamConducting:
    """Руководитель проводит экзамен: вопросы, баллы, результат."""

    async def test_step1_examiner_opens_conduct_menu(self, manager: BotClient, shared_state: dict):
        """Руководитель открывает «Провести экзамен» и видит сдающего."""
        if not shared_state.get("exam_assigned"):
            pytest.skip("Exam was not assigned — previous steps failed")
        await wait_between_actions()

        resp = await manager.send_and_wait("Экзамены 📝", pattern="РЕДАКТОР")
        resp = await manager.click_and_wait(
            resp, data=b"exam_conduct", wait_pattern="готовы пройти|сотрудник|Наставников"
        )

        buttons = manager.get_button_texts(resp)
        assert any("Наставников" in b for b in buttons), (
            f"Examinee 'Наставников' not in conduct list. Buttons: {buttons}"
        )
        shared_state["exam_conduct_resp"] = resp

    async def test_step2_select_and_view_details(self, manager: BotClient, shared_state: dict):
        """Руководитель выбирает сдающего и видит карточку экзамена."""
        resp = shared_state.get("exam_conduct_resp")
        if not resp:
            pytest.skip("No conduct response from previous step")

        conduct_btn = manager.find_button_data(resp, text_contains="Наставников", data_prefix="exam_conduct_select:")
        assert conduct_btn, f"Conduct button not found. Buttons: {manager.get_button_texts(resp)}"

        resp = await manager.click_and_wait(resp, data=conduct_btn, wait_pattern="Начать экзамен|Управление")

        buttons = manager.get_button_texts(resp)
        assert any("Начать экзамен" in b for b in buttons), f"'Начать экзамен' button not found. Buttons: {buttons}"
        shared_state["exam_detail_resp"] = resp

    async def test_step3_start_exam(self, manager: BotClient, shared_state: dict):
        """Руководитель начинает экзамен: старт → подтверждение → вопрос 1."""
        resp = shared_state.get("exam_detail_resp")
        if not resp:
            pytest.skip("No detail response from previous step")

        # Нажимаем «Начать экзамен»
        start_btn = manager.find_button_data(resp, data_prefix="exam_start:")
        assert start_btn, f"Start button not found. Buttons: {manager.get_button_texts(resp)}"

        resp = await manager.click_and_wait(resp, data=start_btn, wait_pattern="Начать|Да")

        # Подтверждаем
        resp = await manager.click_and_wait(resp, data=b"exam_confirm_start", wait_pattern="Вопрос 1")

        resp_text = resp.text or ""
        assert "Правильно ли приготовлен эспрессо" in resp_text, (
            f"Question 1 text not found. Response: {resp_text[:300]}"
        )
        shared_state["exam_q1_resp"] = resp

    async def test_step4_score_question_1(self, manager: BotClient, shared_state: dict):
        """Руководитель ставит 8 баллов за вопрос 1."""
        if not shared_state.get("exam_q1_resp"):
            pytest.skip("Exam was not started — previous steps failed")
        resp = await manager.send_and_wait("8", pattern="Вопрос 2|принят")

        resp_text = resp.text or ""
        # Бот отправляет «принят» и потом вопрос 2
        # settling захватит последнее сообщение
        shared_state["exam_q2_shown"] = True

    async def test_step5_score_question_2(self, manager: BotClient, shared_state: dict):
        """Руководитель ставит 7 баллов за вопрос 2 → результат."""
        if not shared_state.get("exam_q2_shown"):
            pytest.skip("Question 2 was not shown — previous steps failed")
        await wait_between_actions()

        resp = await manager.send_and_wait("7", pattern="пройден|результат|Набрано")

        shared_state["exam_result_resp"] = resp

    async def test_step6_verify_result(self, manager: BotClient, shared_state: dict):
        """Проверяем результат: сумма 15, экзамен пройден."""
        if not shared_state.get("exam_result_resp"):
            pytest.skip("Exam result not received — previous steps failed")
        await wait_between_actions(2.0)

        messages = await manager.get_messages(limit=5)
        result_found = False

        for msg in messages:
            if msg.out:
                continue
            text = msg.text or ""
            if "пройден" in text.lower() and "Экзамен" in text:
                assert "15" in text, f"Score 15 not found in result: {text[:300]}"
                assert "не пройден" not in text.lower(), f"Exam should be passed but got: {text[:300]}"
                result_found = True
                shared_state["exam_result_text"] = text
                break

        assert result_found, (
            f"Result message not found. Last messages: {[m.text[:100] for m in messages if not m.out][:5]}"
        )

    async def test_step7_examinee_gets_result_notification(self, mentor: BotClient, shared_state: dict):
        """Наставник (сдающий) получает уведомление о результате экзамена."""
        if not shared_state.get("exam_result_text"):
            pytest.skip("Exam was not completed — previous steps failed")
        await wait_between_actions(2.0)

        messages = await mentor.get_messages(limit=10)
        found = False

        for msg in messages:
            if msg.out:
                continue
            text = msg.text or ""
            if "E2E Экзамен Кофе" in text and "пройден" in text.lower():
                found = True
                break

        assert found, (
            f"Result notification not found for examinee. Last messages: "
            f"{[m.text[:100] for m in messages if not m.out][:5]}"
        )


# =========================================================================
# Класс 9: Наставник видит завершённый экзамен в «Сдать экзамен»
# =========================================================================


class TestExamExamineeView:
    """Наставник (сдающий) видит свой завершённый экзамен."""

    async def test_step1_examinee_sees_completed_exam(self, mentor: BotClient, shared_state: dict):
        """Наставник открывает «Сдать экзамен» и видит E2E Экзамен Кофе со статусом ✅."""
        if not shared_state.get("exam_result_text"):
            pytest.skip("Exam was not completed — previous steps failed")
        await wait_between_actions()

        resp = await mentor.send_and_wait("Экзамены 📝", pattern="РЕДАКТОР")
        resp = await mentor.click_and_wait(resp, data=b"exam_take", wait_pattern="Мои экзамены|экзамен")

        resp_text = resp.text or ""
        assert "E2E Экзамен Кофе" in resp_text, f"Exam not found in examinee's list. Response: {resp_text[:300]}"
        # Статус должен быть «Пройден» (✅)
        assert "✅" in resp_text or "Пройден" in resp_text, f"Expected ✅/Пройден status. Response: {resp_text[:300]}"
