"""
E2E Setup — создание окружения перед сценариями.

Выполняется первым (order=1). Использует 2 аккаунта:
- admin: регистрируется как Рекрутер (создаёт компанию), затем SQL upgrade до ADMIN
- trainee: регистрируется по инвайт-коду

Результаты сохраняются в shared_state для остальных тестов.
"""

import asyncpg
import pytest
from telethon import TelegramClient

from tests.e2e.helpers.bot_client import BotClient
from tests.e2e.helpers.waiters import (
    wait_between_actions,
)

pytestmark = [
    pytest.mark.order(1),
    pytest.mark.timeout(300),
    pytest.mark.asyncio(loop_scope="session"),
]


# =========================================================================
# 1. Создание компании (admin регистрируется как Рекрутер)
# =========================================================================


class TestCompanySetup:
    """Admin создаёт компанию через стандартный flow регистрации."""

    async def test_admin_start(self, admin: BotClient, shared_state: dict):
        """Admin отправляет /start — видит выбор: создать/присоединиться."""
        resp = await admin.send_and_wait("/start")
        buttons = admin.get_button_texts(resp)
        assert any("Создать" in b for b in buttons), f"No 'Создать' button. Buttons: {buttons}"

    async def test_admin_creates_company(self, admin: BotClient, shared_state: dict):
        """Admin создаёт компанию — стандартный FSM flow."""
        msg = await admin.get_last_message()

        # Нажимаем "Создать компанию"
        resp = await admin.click_and_wait(msg, data=b"company:create", wait_contains="название")

        # Вводим название компании
        resp = await admin.send_and_wait("E2E Test Company", contains="описание")

        # Пропускаем описание
        resp = await admin.click_and_wait(
            resp, data=b"company:skip_description", wait_pattern="код приглашения|инвайт|Создание кода"
        )

        # Вводим инвайт-код
        resp = await admin.send_and_wait("E2ETESTCODE", pattern="фамилию|имя|ФИО")

        # Вводим ФИО
        resp = await admin.send_and_wait("Рекрутеров Тест", pattern="телефон|контакт|номер")

        # Вводим телефон
        resp = await admin.send_and_wait(
            "+79001000001", pattern="успешно|создана|зарегистрирован|Добро пожаловать|Главное меню"
        )

        shared_state["invite_code"] = "E2ETESTCODE"
        shared_state["company_name"] = "E2E Test Company"


# =========================================================================
# 2. Создание группы и объекта
# =========================================================================


class TestPrerequisites:
    """Admin (Рекрутер) создаёт группу и объект."""

    async def test_create_group(self, admin: BotClient, shared_state: dict):
        """Создание группы 'Бариста'."""
        await wait_between_actions()

        resp = await admin.send_and_wait("Группы 🗂️", pattern="УПРАВЛЕНИЕ ГРУППАМИ|группами")

        resp = await admin.click_and_wait(resp, data=b"create_group", wait_contains="название")

        resp = await admin.send_and_wait("Бариста", pattern="создана|успешно|Группа")

        shared_state["group_name"] = "Бариста"

    async def test_create_object(self, admin: BotClient, shared_state: dict):
        """Создание объекта 'Кафе Центр'."""
        await wait_between_actions()

        resp = await admin.send_and_wait("Объекты 📍", pattern="УПРАВЛЕНИЕ ОБЪЕКТАМИ|объектами")

        resp = await admin.click_and_wait(resp, data=b"create_object", wait_contains="название")

        resp = await admin.send_and_wait("Кафе Центр", pattern="создан|успешно|Объект")

        shared_state["object_name"] = "Кафе Центр"


# =========================================================================
# 3. Регистрация trainee
# =========================================================================


class TestUserRegistration:
    """Trainee присоединяется к компании по инвайт-коду."""

    @pytest.fixture(autouse=True)
    def _inject_state(self, shared_state):
        self.state = shared_state

    async def _register_user(self, client: BotClient, name: str, phone: str, invite_code: str):
        """Общий flow регистрации: /start -> инвайт -> имя -> телефон."""
        resp = await client.send_and_wait("/start")

        msg = await client.get_last_message()
        resp = await client.click_and_wait(msg, data=b"company:join", wait_contains="код приглашения")

        resp = await client.send_and_wait(invite_code, pattern="Зарегистрироваться|регистрац")

        resp = await client.click_and_wait(resp, data=b"register:normal", wait_pattern="фамилию|имя|ФИО")

        resp = await client.send_and_wait(name, pattern="телефон|контакт|номер")

        resp = await client.send_and_wait(phone, pattern="завершена|отправлен|рекрутер|ожидайте|Данные")

        return resp

    async def test_register_trainee(self, trainee: BotClient):
        await self._register_user(trainee, "Стажёров Тест", "+79001000002", self.state["invite_code"])


# =========================================================================
# 4. Активация trainee
# =========================================================================


class TestUserActivation:
    """Admin (Рекрутер) активирует trainee как Стажер."""

    async def _activate_user(self, client: BotClient, user_name: str, role: str):
        """Общий flow активации: Новые пользователи -> роль -> группа -> объект -> подтверждение."""
        await wait_between_actions()

        resp = await client.send_and_wait("Новые пользователи ➕", pattern="новых пользовател|Новые пользовател|Выбери")

        btn_data = client.find_button_data(resp, text_contains=user_name, data_prefix="activate_user:")
        if not btn_data:
            all_btns = client.find_all_buttons_data(resp, data_prefix="activate_user:")
            for btn_text, btn_d in all_btns:
                if user_name.split()[0] in btn_text:
                    btn_data = btn_d
                    break

        assert btn_data, f"User '{user_name}' not found in new users list"

        resp = await client.click_and_wait(resp, data=btn_data, wait_pattern="роль|Роль|Выбери роль")

        role_data = f"select_role:{role}".encode()
        resp = await client.click_and_wait(resp, data=role_data, wait_pattern="группу|Группу|Выбери группу")

        group_btn = client.find_button_data(resp, data_prefix="select_group:")
        assert group_btn, "No group buttons found"
        resp = await client.click_and_wait(resp, data=group_btn, wait_pattern="объект|Объект")

        if role == "Стажер":
            obj_btn = client.find_button_data(resp, data_prefix="select_internship_object:")
            assert obj_btn, "No internship object buttons found"
            resp = await client.click_and_wait(resp, data=obj_btn, wait_pattern="рабочий объект|объект|Объект")

            obj_btn = client.find_button_data(resp, data_prefix="select_work_object:")
            assert obj_btn, "No work object buttons found"
            resp = await client.click_and_wait(resp, data=obj_btn, wait_pattern="Добавить|подтвер|активир")
        else:
            obj_btn = client.find_button_data(resp, data_prefix="select_work_object:") or client.find_button_data(
                resp, data_prefix="select_internship_object:"
            )
            assert obj_btn, "No object buttons found"
            resp = await client.click_and_wait(resp, data=obj_btn, wait_pattern="Добавить|подтвер|активир")

        resp = await client.click_and_wait(
            resp, data=b"confirm_activation", wait_pattern="открыл доступ|активирован|добавлен|успешно"
        )

        return resp

    async def test_activate_trainee(self, admin: BotClient):
        await self._activate_user(admin, "Стажёров", "Стажер")


# =========================================================================
# 5. SQL: Upgrade admin до ADMIN + Наставник + Руководитель + Сотрудник
# =========================================================================


class TestAdminRoleSetup:
    """SQL: добавить роли ADMIN, Наставник, Руководитель, Сотрудник к admin-пользователю."""

    async def test_add_admin_roles(self, e2e_db: asyncpg.Connection, admin_client: TelegramClient, shared_state: dict):
        """Добавляем все необходимые роли admin-пользователю."""
        me = await admin_client.get_me()

        user_id = await e2e_db.fetchval("SELECT id FROM users WHERE tg_id = $1", me.id)
        assert user_id, f"Admin user not found in DB (tg_id={me.id})"

        # Создаём роль ADMIN если её нет в seed-данных
        admin_role_exists = await e2e_db.fetchval("SELECT id FROM roles WHERE name = 'ADMIN'")
        if not admin_role_exists:
            await e2e_db.execute("INSERT INTO roles (name) VALUES ('ADMIN')")

        roles_to_add = ["ADMIN", "Наставник", "Руководитель", "Сотрудник"]
        roles = await e2e_db.fetch("SELECT id, name FROM roles WHERE name = ANY($1)", roles_to_add)
        assert len(roles) == len(roles_to_add), (
            f"Not all roles found in DB. Expected: {roles_to_add}, got: {[r['name'] for r in roles]}"
        )

        for role in roles:
            exists = await e2e_db.fetchval(
                "SELECT 1 FROM user_roles WHERE user_id = $1 AND role_id = $2",
                user_id,
                role["id"],
            )
            if not exists:
                await e2e_db.execute(
                    "INSERT INTO user_roles (user_id, role_id) VALUES ($1, $2)",
                    user_id,
                    role["id"],
                )

        # Привязываем admin к группе и объектам (нужно для get_available_learning_paths_for_mentor)
        group_id = await e2e_db.fetchval(
            "SELECT id FROM groups WHERE company_id = (SELECT company_id FROM users WHERE id = $1) LIMIT 1", user_id
        )
        if group_id:
            exists = await e2e_db.fetchval(
                "SELECT 1 FROM user_groups WHERE user_id = $1 AND group_id = $2", user_id, group_id
            )
            if not exists:
                await e2e_db.execute("INSERT INTO user_groups (user_id, group_id) VALUES ($1, $2)", user_id, group_id)

        obj_id = await e2e_db.fetchval(
            "SELECT id FROM objects WHERE company_id = (SELECT company_id FROM users WHERE id = $1) LIMIT 1", user_id
        )
        if obj_id:
            exists = await e2e_db.fetchval(
                "SELECT 1 FROM user_objects WHERE user_id = $1 AND object_id = $2", user_id, obj_id
            )
            if not exists:
                await e2e_db.execute("INSERT INTO user_objects (user_id, object_id) VALUES ($1, $2)", user_id, obj_id)

        shared_state["admin_user_id"] = user_id
        shared_state["admin_tg_id"] = me.id

    async def test_verify_admin_picker(self, admin: BotClient):
        """Проверяем, что ADMIN видит меню выбора ЛК после upgrade."""
        resp = await admin.send_and_wait("/start", contains="Выберите ЛК")
        buttons = admin.get_button_texts(resp)
        assert "Рекрутер" in buttons, f"No 'Рекрутер' in admin picker. Buttons: {buttons}"


# =========================================================================
# 6. Создание 3 тестов (ADMIN как Рекрутер)
# =========================================================================


class TestTestCreation:
    """Admin (Рекрутер) создаёт 3 минимальных теста (по 1 вопросу)."""

    @pytest.fixture(autouse=True)
    def _inject(self, shared_state):
        self.state = shared_state
        self.state.setdefault("test_names", [])
        self.state.setdefault("test_ids", [])

    async def _create_test(
        self,
        client: BotClient,
        test_name: str,
        question_text: str,
        options: list[str],
        correct_index: int,
        points: int = 10,
        threshold: int = 5,
    ):
        """Создать один тест с одним вопросом single_choice."""
        await wait_between_actions()

        resp = await client.send_and_wait("Тесты 📄", pattern="ТЕСТ|тест|действие|Создать")

        resp = await client.click_and_wait(resp, data=b"create_test", wait_contains="название")

        resp = await client.send_and_wait(test_name, pattern="материал|Материал")

        resp = await client.click_and_wait(resp, data=b"materials:no", wait_pattern="описание|Описание")

        resp = await client.click_and_wait(resp, data=b"description:skip", wait_pattern="тип вопроса|Тип|вопрос")

        resp = await client.click_and_wait(
            resp, data=b"q_type:single_choice", wait_pattern="текст вопроса|Введи.*вопрос"
        )

        resp = await client.send_and_wait(question_text, pattern="вариант|ответ|опци")

        for opt in options:
            resp = await client.send_and_wait(opt)
            await wait_between_actions(1.0)

        resp = await client.click_and_wait(resp, data=b"finish_options", wait_pattern="номер правильного|правильный")

        resp = await client.send_and_wait(str(correct_index + 1), pattern="балл|очки|Баллы|Сколько")

        resp = await client.send_and_wait(str(points), pattern="ещё.*вопрос|еще.*вопрос|добавить")

        resp = await client.click_and_wait(resp, data=b"more_questions:no", wait_pattern="проходной балл|порог")

        resp = await client.send_and_wait(str(threshold), pattern="создан|сохранён|успешно|Тест")

        self.state["test_names"].append(test_name)

        return resp

    async def test_switch_to_recruiter(self, admin: BotClient):
        """Переключение в Рекрутер перед созданием тестов."""
        await admin.switch_role("Рекрутер")

    async def test_create_test_1(self, admin: BotClient):
        await self._create_test(
            admin,
            test_name="E2E Тест Кофе",
            question_text="Какая температура идеальна для эспрессо?",
            options=["85°C", "93°C", "100°C"],
            correct_index=1,
            points=10,
            threshold=5,
        )

    async def test_create_test_2(self, admin: BotClient):
        await self._create_test(
            admin,
            test_name="E2E Тест Сервис",
            question_text="Что делать при жалобе гостя?",
            options=["Игнорировать", "Извиниться и решить", "Позвать менеджера"],
            correct_index=1,
            points=10,
            threshold=5,
        )

    async def test_create_test_3(self, admin: BotClient):
        await self._create_test(
            admin,
            test_name="E2E Тест Гигиена",
            question_text="Как часто нужно мыть руки?",
            options=["Раз в час", "Перед каждым действием", "Раз в смену"],
            correct_index=1,
            points=10,
            threshold=5,
        )


# =========================================================================
# 7. Создание аттестации (ADMIN как Рекрутер)
# =========================================================================


class TestAttestationCreation:
    """Admin (Рекрутер) создаёт аттестацию (требуется для траектории)."""

    @pytest.fixture(autouse=True)
    def _inject(self, shared_state):
        self.state = shared_state

    async def test_create_attestation(self, admin: BotClient):
        """
        Flow: Траектория 📖 -> Управление аттестациями -> Создать ->
              Далее -> название -> вопрос -> сохранить -> проходной балл.
        """
        await wait_between_actions()

        resp = await admin.send_and_wait("Траектория 📖", pattern="[Тт]раектори|Создать")

        resp = await admin.click_and_wait(
            resp, data=b"manage_attestations", wait_pattern="АТТЕСТАЦ|аттестац|Выбери|Создай"
        )

        resp = await admin.click_and_wait(resp, data=b"create_attestation", wait_pattern="ИНСТРУКЦИЯ|Аттестация|Далее")

        resp = await admin.click_and_wait(
            resp, data=b"start_attestation_creation", wait_pattern="[Нн]азвание|отправь название"
        )

        attestation_name = "E2E Аттестация Бариста"
        resp = await admin.send_and_wait(attestation_name, pattern="[Вв]опрос|введи текст|критери")

        question = (
            "Расскажи основные правила приготовления эспрессо.\n\n"
            "Правильный ответ: Стажер должен назвать температуру, давление, время.\n\n"
            "Назвал все - 10\nНазвал половину - 5\nНичего не назвал - 0"
        )
        resp = await admin.send_and_wait(question, pattern="[Сс]охранить|[Вв]опрос.*2|Добавлено")

        resp = await admin.click_and_wait(resp, data=b"save_attestation_questions", wait_pattern="проходной балл|балл")

        resp = await admin.send_and_wait("5", pattern="сохранена|создана|успешно|АТТЕСТАЦ")

        self.state["attestation_name"] = attestation_name


# =========================================================================
# 8. Создание траектории с 2 этапами (ADMIN как Рекрутер)
# =========================================================================


class TestTrajectoryCreation:
    """Admin (Рекрутер) создаёт траекторию с 2 этапами, по 1 сессии, тестами."""

    @pytest.fixture(autouse=True)
    def _inject(self, shared_state):
        self.state = shared_state

    async def test_create_trajectory(self, admin: BotClient):
        """
        Flow: Траектория 📖 -> Создать -> название -> этап 1 -> сессия 1 -> тесты ->
              сохранить -> этап 2 -> сессия 2 -> тесты -> сохранить -> выбрать аттестацию ->
              выбрать группу -> финальное сохранение.
        """
        await wait_between_actions()

        resp = await admin.send_and_wait("Траектория 📖", pattern="[Тт]раектори|Создать")

        resp = await admin.click_and_wait(resp, data=b"create_trajectory", wait_pattern="[Нн]ачать|инструкци|создани")

        resp = await admin.click_and_wait(
            resp, data=b"start_trajectory_creation", wait_pattern="название.*траектори|Введи название"
        )

        trajectory_name = "E2E Траектория Бариста"
        resp = await admin.send_and_wait(trajectory_name, pattern="название.*[Ээ]тап|Введи.*этап")
        self.state["trajectory_name"] = trajectory_name

        # --- Этап 1 ---
        stage1_name = "Базовые навыки"
        resp = await admin.send_and_wait(stage1_name, pattern="название.*[Сс]ессии|Введи.*сессии")

        session1_name = "Основы кофе"
        resp = await admin.send_and_wait(session1_name, pattern="тест|Выбери тест")

        test1_btn = admin.find_button_data(resp, text_contains="E2E Тест Кофе", data_prefix="select_test:")
        if test1_btn:
            await admin.click_button(resp, data=test1_btn)
            await wait_between_actions(1.5)
            resp = await admin.get_last_message()

        resp = await admin.click_and_wait(
            resp, data=b"save_session", wait_pattern="[Дд]обавить.*сессию|[Дд]обавить.*этап|[Сс]охранить"
        )

        resp = await admin.click_and_wait(resp, data=b"add_stage", wait_pattern="название.*[Ээ]тап|Введи.*этап")

        # --- Этап 2 ---
        stage2_name = "Продвинутые навыки"
        resp = await admin.send_and_wait(stage2_name, pattern="название.*[Сс]ессии|Введи.*сессии")

        session2_name = "Сервис и гигиена"
        resp = await admin.send_and_wait(session2_name, pattern="тест|Выбери тест")

        test2_btn = admin.find_button_data(resp, text_contains="E2E Тест Сервис", data_prefix="select_test:")
        if test2_btn:
            await admin.click_button(resp, data=test2_btn)
            await wait_between_actions(1.5)
            resp = await admin.get_last_message()

        test3_btn = admin.find_button_data(resp, text_contains="E2E Тест Гигиена", data_prefix="select_test:")
        if test3_btn:
            await admin.click_button(resp, data=test3_btn)
            await wait_between_actions(1.5)
            resp = await admin.get_last_message()

        resp = await admin.click_and_wait(resp, data=b"save_session", wait_pattern="[Дд]обавить|[Сс]охранить")

        resp = await admin.click_and_wait(
            resp, data=b"save_trajectory", wait_pattern="[Сс]охранить.*траекторию|созданн"
        )

        resp = await admin.click_and_wait(resp, data=b"confirm_trajectory_save", wait_pattern="[Аа]ттестац|выбери тест")

        att_btn = admin.find_button_data(resp, text_contains="E2E Аттестация", data_prefix="select_attestation:")
        if not att_btn:
            att_btn = admin.find_button_data(resp, data_prefix="select_attestation:")
        assert att_btn, f"No attestation buttons found. Buttons: {admin.get_button_texts(resp)}"

        resp = await admin.click_and_wait(resp, data=att_btn, wait_pattern="[Сс]охранить.*[Аа]ттестац|Да")

        resp = await admin.click_and_wait(
            resp, data=b"confirm_attestation_and_proceed", wait_pattern="групп|Выбери группу"
        )

        group_btn = admin.find_button_data(resp, data_prefix="select_group:")
        assert group_btn, f"No group buttons found. Buttons: {admin.get_button_texts(resp)}"
        resp = await admin.click_and_wait(resp, data=group_btn, wait_pattern="[Сс]охранить.*траекторию|подтверд|итог")

        resp = await admin.click_and_wait(
            resp, data=b"final_confirm_save", wait_pattern="сохранена|создана|успешно|[Тт]раектори"
        )

        self.state["stage_names"] = [stage1_name, stage2_name]
        self.state["session_names"] = [session1_name, session2_name]
        self.state["test_assignments"] = {
            stage1_name: ["E2E Тест Кофе"],
            stage2_name: ["E2E Тест Сервис", "E2E Тест Гигиена"],
        }


# =========================================================================
# 9. Назначение наставника (ADMIN назначает себя наставником trainee)
# =========================================================================


class TestMentorAssignment:
    """Admin (Рекрутер) назначает себя наставником для trainee."""

    async def test_assign_admin_as_mentor(self, admin: BotClient):
        """ADMIN как Рекрутер назначает себя наставником trainee."""
        await wait_between_actions()

        # 1. Открываем меню наставников
        resp = await admin.send_and_wait("Наставники 🦉", pattern="действие|[Нн]аставник")

        # 2. Управление назначениями
        btn_data = admin.find_button_data(resp, data_prefix="mentor_assignment_management")
        assert btn_data, "Button 'mentor_assignment_management' not found"
        resp = await admin.click_and_wait(resp, data=btn_data, wait_pattern="Управление|действие|Назначить")

        # 3. Назначить наставника
        assign_btn = admin.find_button_data(resp, data_prefix="assign_mentor")
        assert assign_btn, "Button 'assign_mentor' not found"
        resp = await admin.click_and_wait(
            resp, data=assign_btn, wait_pattern="стажёр|стажер|Выбери стажера|Назначение наставника"
        )

        # 4. Выбираем trainee
        trainee_btn = admin.find_button_data(resp, text_contains="Стажёров", data_prefix="unassigned_trainee:")
        assert trainee_btn, (
            f"Trainee 'Стажёров' not found for mentor assignment. Available buttons: {admin.get_button_data(resp)}"
        )

        resp = await admin.click_and_wait(resp, data=trainee_btn, wait_pattern="наставник|Выбери наставника")

        # 5. Выбираем наставника (ADMIN = "Рекрутеров Тест")
        mentor_btn = admin.find_button_data(resp, data_prefix="mentor:")
        assert mentor_btn, "No mentor buttons found"

        resp = await admin.click_and_wait(resp, data=mentor_btn, wait_pattern="Подтвердить|подтверд")

        # 6. Подтверждаем
        confirm_btn = admin.find_button_data(resp, data_prefix="confirm_assignment:")
        assert confirm_btn, "Confirm button not found"

        resp = await admin.click_and_wait(resp, data=confirm_btn, wait_pattern="назначен|успешно")


# =========================================================================
# 10. Назначение траектории (ADMIN как Наставник)
# =========================================================================


class TestTrajectoryAssignment:
    """Admin (Наставник) назначает траекторию trainee."""

    async def test_switch_to_mentor(self, admin: BotClient):
        """Переключение в Наставник для назначения траектории."""
        await admin.switch_role("Наставник")

    async def test_assign_trajectory_to_trainee(self, admin: BotClient, shared_state: dict):
        """Назначить траекторию trainee."""
        await wait_between_actions()

        resp = await admin.send_and_wait("Мои стажеры 👥", pattern="стажер|стажёр|Стажёр")

        trainee_btn = admin.find_button_data(
            resp,
            text_contains="Стажёров",
            data_prefix="select_trainee_for_trajectory:",
        )
        if not trainee_btn:
            trainee_btn = admin.find_button_data(
                resp,
                text_contains="Тест",
                data_prefix="select_trainee_for_trajectory:",
            )
        assert trainee_btn, f"Trainee not found. Buttons: {admin.get_button_texts(resp)}"

        resp = await admin.click_and_wait(
            resp, data=trainee_btn, wait_pattern="[Тт]раектори|[Ээ]тап|карточка|Выбрать|траектории"
        )

        traj_btn = admin.find_button_data(resp, text_contains="E2E Траектория", data_prefix="assign_trajectory:")
        if not traj_btn:
            traj_btn = admin.find_button_data(resp, data_prefix="assign_trajectory:")
        assert traj_btn, f"Trajectory not found. Buttons: {admin.get_button_texts(resp)}"

        resp = await admin.click_and_wait(resp, data=traj_btn, wait_pattern="назначена|[Ээ]тап|открыть|уже")
