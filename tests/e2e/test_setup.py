"""
E2E Setup — создание окружения перед сценариями.

Выполняется первым (order=1). Создаёт компанию, пользователей, группу, объект,
тесты, траекторию и назначает наставника. Результаты сохраняются в shared_state.
"""

import pytest

from tests.e2e.helpers.bot_client import BotClient
from tests.e2e.helpers.waiters import (
    extract_invite_code,
    wait_between_actions,
)


pytestmark = [
    pytest.mark.order(1),
    pytest.mark.timeout(300),
    pytest.mark.asyncio(loop_scope="session"),
]


# =========================================================================
# 1. Создание компании рекрутером
# =========================================================================


class TestCompanySetup:
    """Рекрутер создаёт компанию и получает инвайт-код."""

    async def test_recruiter_start(self, recruiter: BotClient, shared_state: dict):
        """Рекрутер отправляет /start и видит выбор: создать/присоединиться."""
        resp = await recruiter.send_and_wait("/start")
        # Бот предлагает создать или присоединиться к компании
        buttons = recruiter.get_button_texts(resp)
        assert any("Создать" in b for b in buttons), f"No 'Создать' button. Buttons: {buttons}"

    async def test_recruiter_creates_company(self, recruiter: BotClient, shared_state: dict):
        """Рекрутер нажимает 'Создать компанию' и проходит FSM."""
        # Получаем последнее сообщение с кнопками
        msg = await recruiter.get_last_message()

        # Нажимаем "Создать компанию"
        resp = await recruiter.click_and_wait(
            msg, data=b"company:create", wait_contains="название"
        )

        # Вводим название компании
        resp = await recruiter.send_and_wait(
            "E2E Test Company", contains="описание"
        )

        # Пропускаем описание (inline-кнопка, не текст)
        resp = await recruiter.click_and_wait(
            resp, data=b"company:skip_description",
            wait_pattern="код приглашения|инвайт|Создание кода"
        )

        # Вводим инвайт-код
        resp = await recruiter.send_and_wait(
            "E2ETESTCODE", pattern="фамилию|имя|ФИО"
        )

        # Вводим ФИО рекрутера
        resp = await recruiter.send_and_wait(
            "Рекрутеров Тест", pattern="телефон|контакт|номер"
        )

        # Вводим телефон
        phone = "+79001000001"
        resp = await recruiter.send_and_wait(
            phone, pattern="успешно|создана|зарегистрирован|Добро пожаловать|Главное меню"
        )

        # Сохраняем инвайт-код
        shared_state["invite_code"] = "E2ETESTCODE"
        shared_state["company_name"] = "E2E Test Company"


# =========================================================================
# 2. Создание группы и объекта (нужны для активации пользователей)
# =========================================================================


class TestPrerequisites:
    """Рекрутер создаёт группу и объект."""

    async def test_create_group(self, recruiter: BotClient, shared_state: dict):
        """Рекрутер создаёт группу 'Бариста'."""
        await wait_between_actions()

        # Нажимаем "Группы 🗂️"
        resp = await recruiter.send_and_wait(
            "Группы 🗂️", pattern="УПРАВЛЕНИЕ ГРУППАМИ|группами"
        )

        # Нажимаем "Создать группу"
        resp = await recruiter.click_and_wait(
            resp, data=b"create_group", wait_contains="название"
        )

        # Вводим название группы
        resp = await recruiter.send_and_wait(
            "Бариста", pattern="создана|успешно|Группа"
        )

        shared_state["group_name"] = "Бариста"

    async def test_create_object(self, recruiter: BotClient, shared_state: dict):
        """Рекрутер создаёт объект 'Кафе Центр'."""
        await wait_between_actions()

        # Нажимаем "Объекты 📍"
        resp = await recruiter.send_and_wait(
            "Объекты 📍", pattern="УПРАВЛЕНИЕ ОБЪЕКТАМИ|объектами"
        )

        # Нажимаем "Создать объект"
        resp = await recruiter.click_and_wait(
            resp, data=b"create_object", wait_contains="название"
        )

        # Вводим название объекта
        resp = await recruiter.send_and_wait(
            "Кафе Центр", pattern="создан|успешно|Объект"
        )

        shared_state["object_name"] = "Кафе Центр"


# =========================================================================
# 3. Регистрация 4 пользователей (наставник, руководитель, 2 стажёра)
# =========================================================================


class TestUserRegistration:
    """4 пользователя присоединяются к компании по инвайт-коду."""

    @pytest.fixture(autouse=True)
    def _inject_state(self, shared_state):
        self.state = shared_state

    async def _register_user(
        self, client: BotClient, name: str, phone: str, invite_code: str
    ):
        """Общий flow регистрации: /start → инвайт → имя → телефон."""
        # /start
        resp = await client.send_and_wait("/start")
        buttons = client.get_button_texts(resp)

        # Нажимаем "Присоединиться к компании"
        msg = await client.get_last_message()
        resp = await client.click_and_wait(
            msg, data=b"company:join", wait_contains="код приглашения"
        )

        # Вводим инвайт-код
        resp = await client.send_and_wait(
            invite_code, pattern="Зарегистрироваться|регистрац"
        )

        # Нажимаем "Зарегистрироваться" (обычная регистрация)
        resp = await client.click_and_wait(
            resp, data=b"register:normal", wait_pattern="фамилию|имя|ФИО"
        )

        # Вводим ФИО
        resp = await client.send_and_wait(
            name, pattern="телефон|контакт|номер"
        )

        # Вводим телефон
        resp = await client.send_and_wait(
            phone, pattern="завершена|отправлен|рекрутер|ожидайте|Данные"
        )

        return resp

    async def test_register_mentor(self, mentor: BotClient):
        await self._register_user(
            mentor, "Наставников Тест", "+79001000002", self.state["invite_code"]
        )

    async def test_register_manager(self, manager: BotClient):
        await self._register_user(
            manager, "Руководителев Тест", "+79001000003", self.state["invite_code"]
        )

    async def test_register_trainee1(self, trainee1: BotClient):
        await self._register_user(
            trainee1, "Стажёров Первый", "+79001000004", self.state["invite_code"]
        )

    async def test_register_trainee2(self, trainee2: BotClient):
        await self._register_user(
            trainee2, "Стажёров Второй", "+79001000005", self.state["invite_code"]
        )


# =========================================================================
# 4. Активация пользователей рекрутером (роль + группа + объект)
# =========================================================================


class TestUserActivation:
    """Рекрутер активирует 4 пользователей с разными ролями."""

    @pytest.fixture(autouse=True)
    def _inject(self, shared_state):
        self.state = shared_state

    async def _activate_user(
        self, recruiter: BotClient, user_name: str, role: str
    ):
        """
        Общий flow активации:
        Новые пользователи → выбрать пользователя → роль → группа → объект(ы) → подтвердить.
        """
        await wait_between_actions()

        # Открываем список новых пользователей
        resp = await recruiter.send_and_wait(
            "Новые пользователи ➕", pattern="новых пользовател|Новые пользовател|Выбери"
        )

        # Ищем кнопку с нужным пользователем
        btn_data = recruiter.find_button_data(resp, text_contains=user_name, data_prefix="activate_user:")
        if not btn_data:
            # Может быть на другой странице — ищем по частичному имени
            all_btns = recruiter.find_all_buttons_data(resp, data_prefix="activate_user:")
            for btn_text, btn_d in all_btns:
                if user_name.split()[0] in btn_text:
                    btn_data = btn_d
                    break

        assert btn_data, f"User '{user_name}' not found in new users list"

        # Нажимаем на пользователя
        resp = await recruiter.click_and_wait(
            resp, data=btn_data, wait_pattern="роль|Роль|Выбери роль"
        )

        # Выбираем роль
        role_data = f"select_role:{role}".encode()
        resp = await recruiter.click_and_wait(
            resp, data=role_data, wait_pattern="группу|Группу|Выбери группу"
        )

        # Выбираем группу (первую доступную — "Бариста")
        group_btn = recruiter.find_button_data(resp, data_prefix="select_group:")
        assert group_btn, "No group buttons found"
        resp = await recruiter.click_and_wait(
            resp, data=group_btn, wait_pattern="объект|Объект"
        )

        # Для стажёров: выбираем объект стажировки, потом рабочий объект
        # Для других: выбираем один объект
        if role == "Стажер":
            # Объект стажировки
            obj_btn = recruiter.find_button_data(resp, data_prefix="select_internship_object:")
            assert obj_btn, "No internship object buttons found"
            resp = await recruiter.click_and_wait(
                resp, data=obj_btn, wait_pattern="рабочий объект|объект|Объект"
            )

            # Рабочий объект
            obj_btn = recruiter.find_button_data(resp, data_prefix="select_work_object:")
            assert obj_btn, "No work object buttons found"
            resp = await recruiter.click_and_wait(
                resp, data=obj_btn, wait_pattern="Добавить|подтвер|активир"
            )
        else:
            # Для не-стажёров: один объект
            obj_btn = (
                recruiter.find_button_data(resp, data_prefix="select_work_object:")
                or recruiter.find_button_data(resp, data_prefix="select_internship_object:")
            )
            assert obj_btn, "No object buttons found"
            resp = await recruiter.click_and_wait(
                resp, data=obj_btn, wait_pattern="Добавить|подтвер|активир"
            )

        # Подтверждаем активацию
        resp = await recruiter.click_and_wait(
            resp, data=b"confirm_activation",
            wait_pattern="открыл доступ|активирован|добавлен|успешно"
        )

        return resp

    async def test_activate_mentor(self, recruiter: BotClient):
        await self._activate_user(recruiter, "Наставников", "Наставник")

    async def test_activate_manager(self, recruiter: BotClient):
        await self._activate_user(recruiter, "Руководителев", "Руководитель")

    async def test_activate_trainee1(self, recruiter: BotClient):
        await self._activate_user(recruiter, "Стажёров Первый", "Стажер")

    async def test_activate_trainee2(self, recruiter: BotClient):
        await self._activate_user(recruiter, "Стажёров Второй", "Стажер")


# =========================================================================
# 5. Назначение наставника стажёрам
# =========================================================================


class TestMentorAssignment:
    """Рекрутер назначает наставника для обоих стажёров."""

    async def _assign_mentor_to_trainee(self, recruiter: BotClient, trainee_name: str):
        """Назначить наставника одному стажёру через flow рекрутера."""
        await wait_between_actions()

        # 1. Открываем меню наставников
        resp = await recruiter.send_and_wait(
            "Наставники 🦉", pattern="действие|[Нн]аставник"
        )

        # 2. Главное меню → "Назначить наставника" (mentor_assignment_management)
        btn_data = recruiter.find_button_data(
            resp, data_prefix="mentor_assignment_management"
        )
        assert btn_data, "Button 'mentor_assignment_management' not found"
        resp = await recruiter.click_and_wait(
            resp, data=btn_data, wait_pattern="Управление|действие|Назначить"
        )

        # 3. Управление назначениями → "➕ Назначить наставника" (assign_mentor)
        assign_btn = recruiter.find_button_data(resp, data_prefix="assign_mentor")
        assert assign_btn, "Button 'assign_mentor' not found"
        resp = await recruiter.click_and_wait(
            resp, data=assign_btn,
            wait_pattern="стажёр|стажер|Выбери стажера|Назначение наставника"
        )

        # 4. Выбираем стажёра (unassigned_trainee:{id})
        trainee_btn = recruiter.find_button_data(
            resp, text_contains=trainee_name.split()[0],
            data_prefix="unassigned_trainee:"
        )
        assert trainee_btn, (
            f"Trainee '{trainee_name}' not found for mentor assignment. "
            f"Available buttons: {recruiter.get_button_data(resp)}"
        )

        resp = await recruiter.click_and_wait(
            resp, data=trainee_btn,
            wait_pattern="наставник|Выбери наставника"
        )

        # 5. Выбираем наставника (mentor:{id})
        mentor_btn = recruiter.find_button_data(resp, data_prefix="mentor:")
        assert mentor_btn, "No mentor buttons found"

        resp = await recruiter.click_and_wait(
            resp, data=mentor_btn, wait_pattern="Подтвердить|подтверд"
        )

        # 6. Подтверждаем (confirm_assignment:{mentor_id}:{trainee_id})
        confirm_btn = recruiter.find_button_data(resp, data_prefix="confirm_assignment:")
        assert confirm_btn, "Confirm button not found"

        resp = await recruiter.click_and_wait(
            resp, data=confirm_btn,
            wait_pattern="назначен|успешно"
        )

        return resp

    async def test_assign_mentor_to_trainee1(self, recruiter: BotClient):
        await self._assign_mentor_to_trainee(recruiter, "Стажёров Первый")

    async def test_assign_mentor_to_trainee2(self, recruiter: BotClient):
        await self._assign_mentor_to_trainee(recruiter, "Стажёров Второй")


# =========================================================================
# 6. Создание 3 тестов рекрутером
# =========================================================================


class TestTestCreation:
    """Рекрутер создаёт 3 минимальных теста (по 1-2 вопроса)."""

    @pytest.fixture(autouse=True)
    def _inject(self, shared_state):
        self.state = shared_state
        self.state.setdefault("test_names", [])
        self.state.setdefault("test_ids", [])

    async def _create_test(
        self,
        recruiter: BotClient,
        test_name: str,
        question_text: str,
        options: list[str],
        correct_index: int,
        points: int = 10,
        threshold: int = 5,
    ):
        """
        Создать один тест с одним вопросом single_choice.

        Flow: Тесты 📄 → Создать новый → название → пропустить материалы →
              пропустить описание → single_choice → вопрос → варианты →
              правильный ответ → баллы → нет больше вопросов → порог.
        """
        await wait_between_actions()

        # Открываем меню тестов
        resp = await recruiter.send_and_wait(
            "Тесты 📄", pattern="ТЕСТ|тест|действие|Создать"
        )

        # Нажимаем "Создать новый"
        resp = await recruiter.click_and_wait(
            resp, data=b"create_test", wait_contains="название"
        )

        # Вводим название теста
        resp = await recruiter.send_and_wait(
            test_name, pattern="материал|Материал"
        )

        # Пропускаем материалы (Нет)
        resp = await recruiter.click_and_wait(
            resp, data=b"materials:no", wait_pattern="описание|Описание"
        )

        # Пропускаем описание
        resp = await recruiter.click_and_wait(
            resp, data=b"description:skip", wait_pattern="тип вопроса|Тип|вопрос"
        )

        # Выбираем single_choice
        resp = await recruiter.click_and_wait(
            resp, data=b"q_type:single_choice", wait_pattern="текст вопроса|Введи.*вопрос"
        )

        # Вводим текст вопроса
        resp = await recruiter.send_and_wait(
            question_text, pattern="вариант|ответ|опци"
        )

        # Вводим варианты ответов
        for opt in options:
            resp = await recruiter.send_and_wait(opt)
            await wait_between_actions(1.0)

        # Завершаем ввод вариантов
        resp = await recruiter.click_and_wait(
            resp, data=b"finish_options", wait_pattern="номер правильного|правильный"
        )

        # Указываем номер правильного ответа (1-based)
        resp = await recruiter.send_and_wait(
            str(correct_index + 1), pattern="балл|очки|Баллы|Сколько"
        )

        # Вводим баллы
        resp = await recruiter.send_and_wait(
            str(points), pattern="ещё.*вопрос|еще.*вопрос|добавить"
        )

        # Не добавляем больше вопросов
        resp = await recruiter.click_and_wait(
            resp, data=b"more_questions:no", wait_pattern="проходной балл|порог"
        )

        # Вводим проходной балл
        resp = await recruiter.send_and_wait(
            str(threshold), pattern="создан|сохранён|успешно|Тест"
        )

        self.state["test_names"].append(test_name)

        return resp

    async def test_create_test_1(self, recruiter: BotClient):
        await self._create_test(
            recruiter,
            test_name="E2E Тест Кофе",
            question_text="Какая температура идеальна для эспрессо?",
            options=["85°C", "93°C", "100°C"],
            correct_index=1,
            points=10,
            threshold=5,
        )

    async def test_create_test_2(self, recruiter: BotClient):
        await self._create_test(
            recruiter,
            test_name="E2E Тест Сервис",
            question_text="Что делать при жалобе гостя?",
            options=["Игнорировать", "Извиниться и решить", "Позвать менеджера"],
            correct_index=1,
            points=10,
            threshold=5,
        )

    async def test_create_test_3(self, recruiter: BotClient):
        await self._create_test(
            recruiter,
            test_name="E2E Тест Гигиена",
            question_text="Как часто нужно мыть руки?",
            options=["Раз в час", "Перед каждым действием", "Раз в смену"],
            correct_index=1,
            points=10,
            threshold=5,
        )


# =========================================================================
# 7. Создание аттестации (необходима для траектории)
# =========================================================================


class TestAttestationCreation:
    """Рекрутер создаёт аттестацию (требуется для сохранения траектории)."""

    @pytest.fixture(autouse=True)
    def _inject(self, shared_state):
        self.state = shared_state

    async def test_create_attestation(self, recruiter: BotClient):
        """
        Flow: Траектория 📖 → Управление аттестациями → Создать →
              Далее → название → вопрос → сохранить → проходной балл.
        """
        await wait_between_actions()

        # Открываем меню траекторий
        resp = await recruiter.send_and_wait(
            "Траектория 📖", pattern="[Тт]раектори|Создать"
        )

        # Нажимаем "Управление аттестациями"
        resp = await recruiter.click_and_wait(
            resp, data=b"manage_attestations",
            wait_pattern="АТТЕСТАЦ|аттестац|Выбери|Создай"
        )

        # Нажимаем "Создать аттестацию"
        resp = await recruiter.click_and_wait(
            resp, data=b"create_attestation",
            wait_pattern="ИНСТРУКЦИЯ|Аттестация|Далее"
        )

        # Нажимаем "Далее"
        resp = await recruiter.click_and_wait(
            resp, data=b"start_attestation_creation",
            wait_pattern="[Нн]азвание|отправь название"
        )

        # Вводим название аттестации
        attestation_name = "E2E Аттестация Бариста"
        resp = await recruiter.send_and_wait(
            attestation_name, pattern="[Вв]опрос|введи текст|критери"
        )

        # Вводим вопрос аттестации (текстовый блок с вопросом и критериями)
        question = (
            "Расскажи основные правила приготовления эспрессо.\n\n"
            "Правильный ответ: Стажер должен назвать температуру, давление, время.\n\n"
            "Назвал все - 10\nНазвал половину - 5\nНичего не назвал - 0"
        )
        resp = await recruiter.send_and_wait(
            question, pattern="[Сс]охранить|[Вв]опрос.*2|Добавлено"
        )

        # Сохраняем вопросы
        resp = await recruiter.click_and_wait(
            resp, data=b"save_attestation_questions",
            wait_pattern="проходной балл|балл"
        )

        # Вводим проходной балл
        resp = await recruiter.send_and_wait(
            "5", pattern="сохранена|создана|успешно|АТТЕСТАЦ"
        )

        self.state["attestation_name"] = attestation_name


# =========================================================================
# 8. Создание траектории с 2 этапами
# =========================================================================


class TestTrajectoryCreation:
    """Рекрутер создаёт траекторию с 2 этапами, по 1 сессии, тестами."""

    @pytest.fixture(autouse=True)
    def _inject(self, shared_state):
        self.state = shared_state

    async def test_create_trajectory(self, recruiter: BotClient):
        """
        Flow: Траектория 📖 → Создать → название → этап 1 → сессия 1 → тесты →
              сохранить сессию → добавить этап → этап 2 → сессия 2 → тесты →
              сохранить сессию → сохранить траекторию → подтвердить →
              выбрать аттестацию → выбрать группу → финальное сохранение.
        """
        await wait_between_actions()

        # Открываем меню траекторий
        resp = await recruiter.send_and_wait(
            "Траектория 📖", pattern="[Тт]раектори|Создать"
        )

        # Нажимаем "Создать траекторию"
        resp = await recruiter.click_and_wait(
            resp, data=b"create_trajectory", wait_pattern="[Нн]ачать|инструкци|создани"
        )

        # Нажимаем "Начать создание"
        resp = await recruiter.click_and_wait(
            resp, data=b"start_trajectory_creation",
            wait_pattern="название.*траектори|Введи название"
        )

        # Вводим название траектории
        trajectory_name = "E2E Траектория Бариста"
        resp = await recruiter.send_and_wait(
            trajectory_name, pattern="название.*[Ээ]тап|Введи.*этап"
        )
        self.state["trajectory_name"] = trajectory_name

        # --- Этап 1 ---
        stage1_name = "Базовые навыки"
        resp = await recruiter.send_and_wait(
            stage1_name, pattern="название.*[Сс]ессии|Введи.*сессии"
        )

        session1_name = "Основы кофе"
        resp = await recruiter.send_and_wait(
            session1_name, pattern="тест|Выбери тест"
        )

        # Выбираем тест 1 для сессии 1
        test1_btn = recruiter.find_button_data(
            resp, text_contains="E2E Тест Кофе", data_prefix="select_test:"
        )
        if test1_btn:
            await recruiter.click_button(resp, data=test1_btn)
            await wait_between_actions(1.5)
            resp = await recruiter.get_last_message()

        # Сохраняем сессию 1
        resp = await recruiter.click_and_wait(
            resp, data=b"save_session",
            wait_pattern="[Дд]обавить.*сессию|[Дд]обавить.*этап|[Сс]охранить"
        )

        # Добавляем этап 2
        resp = await recruiter.click_and_wait(
            resp, data=b"add_stage",
            wait_pattern="название.*[Ээ]тап|Введи.*этап"
        )

        # --- Этап 2 ---
        stage2_name = "Продвинутые навыки"
        resp = await recruiter.send_and_wait(
            stage2_name, pattern="название.*[Сс]ессии|Введи.*сессии"
        )

        session2_name = "Сервис и гигиена"
        resp = await recruiter.send_and_wait(
            session2_name, pattern="тест|Выбери тест"
        )

        # Выбираем тест 2 для сессии 2
        test2_btn = recruiter.find_button_data(
            resp, text_contains="E2E Тест Сервис", data_prefix="select_test:"
        )
        if test2_btn:
            await recruiter.click_button(resp, data=test2_btn)
            await wait_between_actions(1.5)
            resp = await recruiter.get_last_message()

        # Выбираем тест 3 тоже для сессии 2
        test3_btn = recruiter.find_button_data(
            resp, text_contains="E2E Тест Гигиена", data_prefix="select_test:"
        )
        if test3_btn:
            await recruiter.click_button(resp, data=test3_btn)
            await wait_between_actions(1.5)
            resp = await recruiter.get_last_message()

        # Сохраняем сессию 2
        resp = await recruiter.click_and_wait(
            resp, data=b"save_session",
            wait_pattern="[Дд]обавить|[Сс]охранить"
        )

        # Сохраняем траекторию → показывает подтверждение
        resp = await recruiter.click_and_wait(
            resp, data=b"save_trajectory",
            wait_pattern="[Сс]охранить.*траекторию|созданн"
        )

        # Подтверждаем → переход к выбору аттестации
        resp = await recruiter.click_and_wait(
            resp, data=b"confirm_trajectory_save",
            wait_pattern="[Аа]ттестац|выбери тест"
        )

        # Выбираем аттестацию
        att_btn = recruiter.find_button_data(
            resp, text_contains="E2E Аттестация", data_prefix="select_attestation:"
        )
        if not att_btn:
            att_btn = recruiter.find_button_data(resp, data_prefix="select_attestation:")
        assert att_btn, f"No attestation buttons found. Buttons: {recruiter.get_button_texts(resp)}"

        resp = await recruiter.click_and_wait(
            resp, data=att_btn,
            wait_pattern="[Сс]охранить.*[Аа]ттестац|Да"
        )

        # Подтверждаем аттестацию → переход к выбору группы
        resp = await recruiter.click_and_wait(
            resp, data=b"confirm_attestation_and_proceed",
            wait_pattern="групп|Выбери группу"
        )

        # Выбираем группу
        group_btn = recruiter.find_button_data(resp, data_prefix="select_group:")
        assert group_btn, f"No group buttons found. Buttons: {recruiter.get_button_texts(resp)}"
        resp = await recruiter.click_and_wait(
            resp, data=group_btn,
            wait_pattern="[Сс]охранить.*траекторию|подтверд|итог"
        )

        # Финальное сохранение
        resp = await recruiter.click_and_wait(
            resp, data=b"final_confirm_save",
            wait_pattern="сохранена|создана|успешно|[Тт]раектори"
        )

        self.state["stage_names"] = [stage1_name, stage2_name]
        self.state["session_names"] = [session1_name, session2_name]
        self.state["test_assignments"] = {
            stage1_name: ["E2E Тест Кофе"],
            stage2_name: ["E2E Тест Сервис", "E2E Тест Гигиена"],
        }


# =========================================================================
# 9. Назначение траектории стажёрам
# =========================================================================


async def _assign_trajectory_to_trainee(
    mentor: BotClient, trainee_name: str, trajectory_name: str
):
    """
    Наставник назначает траекторию стажёру.

    Флоу: Мои стажеры → выбрать стажёра → Выбрать траекторию → выбрать → назначено.
    """
    await wait_between_actions()

    # Открываем список стажёров
    resp = await mentor.send_and_wait(
        "Мои стажеры 👥", pattern="стажер|стажёр|Стажёр"
    )

    # Выбираем стажёра (используем фамилию + имя для однозначного совпадения)
    trainee_btn = mentor.find_button_data(
        resp,
        text_contains=trainee_name,
        data_prefix="select_trainee_for_trajectory:",
    )
    if not trainee_btn:
        # Пробуем только фамилию (может быть усечено в кнопке)
        trainee_btn = mentor.find_button_data(
            resp,
            text_contains=trainee_name.split()[-1],
            data_prefix="select_trainee_for_trajectory:",
        )
    assert trainee_btn, (
        f"Trainee '{trainee_name}' not found. "
        f"Buttons: {mentor.get_button_texts(resp)}"
    )

    resp = await mentor.click_and_wait(
        resp, data=trainee_btn,
        wait_pattern="[Тт]раектори|[Ээ]тап|карточка|Выбрать"
    )

    # Нажимаем "Выбрать траекторию"
    select_traj_btn = mentor.find_button_data(
        resp, data_prefix="select_trajectory_for_trainee:"
    )
    assert select_traj_btn, (
        f"'Выбрать траекторию' button not found. "
        f"Buttons: {mentor.get_button_texts(resp)}"
    )

    resp = await mentor.click_and_wait(
        resp, data=select_traj_btn,
        wait_pattern="траекторию|обучения|Выбери"
    )

    # Выбираем траекторию
    traj_btn = mentor.find_button_data(
        resp, text_contains=trajectory_name, data_prefix="assign_trajectory:"
    )
    if not traj_btn:
        # Берём первую доступную
        traj_btn = mentor.find_button_data(resp, data_prefix="assign_trajectory:")
    assert traj_btn, (
        f"Trajectory '{trajectory_name}' not found. "
        f"Buttons: {mentor.get_button_texts(resp)}"
    )

    resp = await mentor.click_and_wait(
        resp, data=traj_btn,
        wait_pattern="назначена|[Ээ]тап|открыть|уже"
    )

    return resp


class TestTrajectoryAssignment:
    """Наставник назначает траекторию обоим стажёрам."""

    async def test_assign_trajectory_to_trainee1(
        self, mentor: BotClient, shared_state: dict
    ):
        """Назначить траекторию Стажёру 1."""
        await _assign_trajectory_to_trainee(
            mentor, "Стажёров Первый", "E2E Траектория"
        )

    async def test_assign_trajectory_to_trainee2(
        self, mentor: BotClient, shared_state: dict
    ):
        """Назначить траекторию Стажёру 2."""
        await _assign_trajectory_to_trainee(
            mentor, "Стажёров Второй", "E2E Траектория"
        )
