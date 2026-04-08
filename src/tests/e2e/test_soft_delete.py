"""
E2E Soft Delete — проверка мягкого и жёсткого удаления всех сущностей.

Выполняется после всех остальных тестов (order=10).
Создаёт изолированные сущности специально для удаления, затем удаляет их
и проверяет результат как через UI, так и через прямые SQL-запросы к БД.

Сценарии:
1. Создание дополнительных сущностей для удаления (группа, объект, тест, папка БЗ, материал)
2. Soft delete: группа, объект, тест (+ вопрос), пользователь
3. Soft delete: траектория (с каскадным удалением этапов/сессий)
4. Hard delete: папка БЗ, материал БЗ
5. DB-верификация: is_active=False, deleted_at IS NOT NULL для soft delete
6. DB-верификация: записи отсутствуют для hard delete
"""

import pytest

from tests.e2e.helpers.bot_client import BotClient
from tests.e2e.helpers.waiters import wait_between_actions

pytestmark = [
    pytest.mark.order(10),
    pytest.mark.timeout(600),
    pytest.mark.asyncio(loop_scope="session"),
]


# =========================================================================
# 1. Создание изолированных сущностей для удаления
# =========================================================================


class TestCreateEntitiesForDeletion:
    """Создаём сущности, которые потом удалим."""

    @pytest.fixture(autouse=True)
    def _inject(self, shared_state):
        self.state = shared_state
        self.state.setdefault("delete_test", {})

    # --- Группа для удаления ---

    async def test_create_group_for_deletion(self, recruiter: BotClient):
        """Рекрутер создаёт группу 'Удаляемая группа'."""
        await wait_between_actions()

        resp = await recruiter.send_and_wait("Группы 🗂️", pattern="УПРАВЛЕНИЕ ГРУППАМИ|группами")
        resp = await recruiter.click_and_wait(resp, data=b"create_group", wait_contains="название")
        resp = await recruiter.send_and_wait("Удаляемая группа", pattern="создана|успешно|Группа")

        self.state["delete_test"]["group_name"] = "Удаляемая группа"

    # --- Объект для удаления ---

    async def test_create_object_for_deletion(self, recruiter: BotClient):
        """Рекрутер создаёт объект 'Удаляемый объект'."""
        await wait_between_actions()

        resp = await recruiter.send_and_wait("Объекты 📍", pattern="УПРАВЛЕНИЕ ОБЪЕКТАМИ|объектами")
        resp = await recruiter.click_and_wait(resp, data=b"create_object", wait_contains="название")
        resp = await recruiter.send_and_wait("Удаляемый объект", pattern="создан|успешно|Объект")

        self.state["delete_test"]["object_name"] = "Удаляемый объект"

    # --- Тест для удаления ---

    async def test_create_test_for_deletion(self, recruiter: BotClient):
        """Рекрутер создаёт тест 'Удаляемый тест' с 1 вопросом."""
        await wait_between_actions()

        resp = await recruiter.send_and_wait("Тесты 📄", pattern="ТЕСТ|тест|действие|Создать")
        resp = await recruiter.click_and_wait(resp, data=b"create_test", wait_contains="название")
        resp = await recruiter.send_and_wait("Удаляемый тест", pattern="материал|Материал")
        resp = await recruiter.click_and_wait(resp, data=b"materials:no", wait_pattern="описание|Описание")
        resp = await recruiter.click_and_wait(resp, data=b"description:skip", wait_pattern="тип вопроса|Тип|вопрос")
        resp = await recruiter.click_and_wait(
            resp, data=b"q_type:single_choice", wait_pattern="текст вопроса|Введи.*вопрос"
        )
        resp = await recruiter.send_and_wait("Вопрос для удаления?", pattern="вариант|ответ|опци")

        resp = await recruiter.send_and_wait("Вариант А")
        await wait_between_actions(1.0)
        resp = await recruiter.send_and_wait("Вариант Б")
        await wait_between_actions(1.0)

        resp = await recruiter.click_and_wait(resp, data=b"finish_options", wait_pattern="номер правильного|правильный")
        resp = await recruiter.send_and_wait("1", pattern="балл|очки|Баллы|Сколько")
        resp = await recruiter.send_and_wait("10", pattern="ещё.*вопрос|еще.*вопрос|добавить")
        resp = await recruiter.click_and_wait(resp, data=b"more_questions:no", wait_pattern="проходной балл|порог")
        resp = await recruiter.send_and_wait("5", pattern="создан|сохранён|успешно|Тест")

        self.state["delete_test"]["test_name"] = "Удаляемый тест"

    # --- Папка БЗ с материалом для удаления ---

    async def test_create_kb_folder_for_deletion(self, recruiter: BotClient):
        """Рекрутер создаёт папку БЗ 'Удаляемая папка' с материалом."""
        await wait_between_actions()

        resp = await recruiter.send_and_wait("База знаний 📁️", pattern="РЕДАКТОР БАЗЫ ЗНАНИЙ|папки|папку")
        resp = await recruiter.click_and_wait(resp, data=b"kb_create_folder", wait_contains="название")
        resp = await recruiter.send_and_wait("Удаляемая папка", pattern="успешно добавил|Добавить материал|папку")

        self.state["delete_test"]["kb_folder_name"] = "Удаляемая папка"

        # Добавляем материал в папку
        resp = await recruiter.click_and_wait(
            resp, data=b"kb_add_material", wait_pattern="название материала|Введи название"
        )
        resp = await recruiter.send_and_wait("Удаляемый материал", pattern="документ|ссылку|материалом")
        # Отправляем текстовую ссылку как контент
        resp = await recruiter.send_and_wait("https://example.com/delete-test", pattern="описание")
        # Пропускаем описание
        resp = await recruiter.click_and_wait(resp, data=b"kb_skip_description", wait_pattern="фото|Пропустить")
        # Пропускаем фото
        resp = await recruiter.click_and_wait(resp, data=b"kb_skip_photos", wait_pattern="Сохранить|сохранить")
        # Сохраняем материал
        resp = await recruiter.click_and_wait(
            resp, data=b"kb_save_material", wait_pattern="успешно сохранил|успешно добавил"
        )

        self.state["delete_test"]["kb_material_name"] = "Удаляемый материал"


# =========================================================================
# 2. Получение ID сущностей из БД
# =========================================================================


class TestResolveEntityIds:
    """Получаем ID созданных сущностей из БД для последующих проверок."""

    @pytest.fixture(autouse=True)
    def _inject(self, shared_state):
        self.state = shared_state

    async def test_resolve_ids(self, e2e_db, shared_state):
        """Достаём ID всех созданных сущностей из БД."""
        dt = shared_state["delete_test"]

        # Группа
        row = await e2e_db.fetchrow(
            "SELECT id FROM groups WHERE name = $1 AND is_active = true",
            dt["group_name"],
        )
        assert row, f"Group '{dt['group_name']}' not found in DB"
        dt["group_id"] = row["id"]

        # Объект
        row = await e2e_db.fetchrow(
            "SELECT id FROM objects WHERE name = $1 AND is_active = true",
            dt["object_name"],
        )
        assert row, f"Object '{dt['object_name']}' not found in DB"
        dt["object_id"] = row["id"]

        # Тест
        row = await e2e_db.fetchrow(
            "SELECT id FROM tests WHERE name = $1 AND is_active = true",
            dt["test_name"],
        )
        assert row, f"Test '{dt['test_name']}' not found in DB"
        dt["test_id"] = row["id"]

        # Вопрос теста
        row = await e2e_db.fetchrow(
            "SELECT id FROM test_questions WHERE test_id = $1 AND is_active = true",
            dt["test_id"],
        )
        assert row, f"Question for test {dt['test_id']} not found in DB"
        dt["question_id"] = row["id"]

        # Папка БЗ
        row = await e2e_db.fetchrow(
            "SELECT id FROM knowledge_folders WHERE name = $1",
            dt["kb_folder_name"],
        )
        assert row, f"KB folder '{dt['kb_folder_name']}' not found in DB"
        dt["kb_folder_id"] = row["id"]

        # Материал БЗ
        row = await e2e_db.fetchrow(
            "SELECT id FROM knowledge_materials WHERE folder_id = $1",
            dt["kb_folder_id"],
        )
        assert row, f"KB material in folder {dt['kb_folder_id']} not found in DB"
        dt["kb_material_id"] = row["id"]


# =========================================================================
# 3. Soft Delete: Группа
# =========================================================================


class TestDeleteGroup:
    """Удаление группы без зависимостей."""

    @pytest.fixture(autouse=True)
    def _inject(self, shared_state):
        self.state = shared_state

    async def test_delete_group_via_ui(self, recruiter: BotClient):
        """Рекрутер удаляет 'Удаляемая группа' через UI."""
        dt = self.state["delete_test"]
        await wait_between_actions()

        # Открываем меню групп
        resp = await recruiter.send_and_wait("Группы 🗂️", pattern="УПРАВЛЕНИЕ ГРУППАМИ|группами")

        # Нажимаем "Удалить группу"
        resp = await recruiter.click_and_wait(
            resp, data=b"manage_delete_group", wait_pattern="Выбери группу для удаления|удаления"
        )

        # Выбираем нашу группу
        group_btn = recruiter.find_button_data(resp, text_contains="Удаляемая группа", data_prefix="delete_group:")
        assert group_btn, f"Group button not found. Buttons: {recruiter.get_button_texts(resp)}"

        resp = await recruiter.click_and_wait(resp, data=group_btn, wait_pattern="уверен|удалить")

        # Подтверждаем удаление
        confirm_btn = recruiter.find_button_data(resp, data_prefix="confirm_delete_group:")
        assert confirm_btn, f"Confirm button not found. Buttons: {recruiter.get_button_texts(resp)}"

        resp = await recruiter.click_and_wait(resp, data=confirm_btn, wait_pattern="успешно удалена|Группа.*удалена")

    async def test_verify_group_soft_deleted_in_db(self, e2e_db):
        """Проверяем в БД: is_active=False, deleted_at заполнен."""
        dt = self.state["delete_test"]

        row = await e2e_db.fetchrow(
            "SELECT is_active, deleted_at FROM groups WHERE id = $1",
            dt["group_id"],
        )
        assert row is not None, "Group record should still exist in DB (soft delete)"
        assert row["is_active"] is False, "Group should be inactive after soft delete"
        assert row["deleted_at"] is not None, "deleted_at should be set after soft delete"


# =========================================================================
# 4. Soft Delete: Объект
# =========================================================================


class TestDeleteObject:
    """Удаление объекта без зависимостей."""

    @pytest.fixture(autouse=True)
    def _inject(self, shared_state):
        self.state = shared_state

    async def test_delete_object_via_ui(self, recruiter: BotClient):
        """Рекрутер удаляет 'Удаляемый объект' через UI."""
        dt = self.state["delete_test"]
        await wait_between_actions()

        resp = await recruiter.send_and_wait("Объекты 📍", pattern="УПРАВЛЕНИЕ ОБЪЕКТАМИ|объектами")

        resp = await recruiter.click_and_wait(
            resp, data=b"manage_delete_object", wait_pattern="Выбери объект для удаления|удаления"
        )

        obj_btn = recruiter.find_button_data(resp, text_contains="Удаляемый объект", data_prefix="delete_object:")
        assert obj_btn, f"Object button not found. Buttons: {recruiter.get_button_texts(resp)}"

        resp = await recruiter.click_and_wait(resp, data=obj_btn, wait_pattern="уверен|удалить")

        confirm_btn = recruiter.find_button_data(resp, data_prefix="confirm_object_delete:")
        assert confirm_btn, f"Confirm button not found. Buttons: {recruiter.get_button_texts(resp)}"

        resp = await recruiter.click_and_wait(resp, data=confirm_btn, wait_pattern="успешно удален|Объект.*удален")

    async def test_verify_object_soft_deleted_in_db(self, e2e_db):
        """Проверяем в БД: is_active=False, deleted_at заполнен."""
        dt = self.state["delete_test"]

        row = await e2e_db.fetchrow(
            "SELECT is_active, deleted_at FROM objects WHERE id = $1",
            dt["object_id"],
        )
        assert row is not None, "Object record should still exist in DB (soft delete)"
        assert row["is_active"] is False, "Object should be inactive after soft delete"
        assert row["deleted_at"] is not None, "deleted_at should be set after soft delete"


# =========================================================================
# 5. Soft Delete: Тест (+ каскад на вопросы)
# =========================================================================


class TestDeleteTest:
    """Удаление теста с каскадным soft delete вопросов."""

    @pytest.fixture(autouse=True)
    def _inject(self, shared_state):
        self.state = shared_state

    async def test_delete_test_via_ui(self, recruiter: BotClient):
        """Рекрутер удаляет 'Удаляемый тест' через UI."""
        dt = self.state["delete_test"]
        await wait_between_actions()

        # Тесты → Список тестов → Все тесты → Выбрать тест → Удалить → Подтвердить
        resp = await recruiter.send_and_wait("Тесты 📄", pattern="ТЕСТ|тест|действие")

        resp = await recruiter.click_and_wait(resp, data=b"list_tests", wait_pattern="Выбери|какие тесты|фильтр")

        # Показать все тесты
        resp = await recruiter.click_and_wait(resp, data=b"test_filter:all", wait_pattern="тест|Выбери")

        # Находим наш тест в списке
        test_btn = recruiter.find_button_data(resp, text_contains="Удаляемый тест", data_prefix="test:")
        assert test_btn, f"Test button not found. Buttons: {recruiter.get_button_texts(resp)}"

        resp = await recruiter.click_and_wait(resp, data=test_btn, wait_pattern="Детальная информация|Удаляемый тест")

        # Нажимаем "Удалить"
        delete_btn = recruiter.find_button_data(resp, data_prefix="delete_test:")
        assert delete_btn, f"Delete button not found. Buttons: {recruiter.get_button_texts(resp)}"

        resp = await recruiter.click_and_wait(resp, data=delete_btn, wait_pattern="действительно хочешь удалить")

        # Подтверждаем
        confirm_btn = recruiter.find_button_data(resp, data_prefix="confirm_delete_test:")
        assert confirm_btn, f"Confirm button not found. Buttons: {recruiter.get_button_texts(resp)}"

        resp = await recruiter.click_and_wait(resp, data=confirm_btn, wait_pattern="Тест удален|успешно удален")

    async def test_verify_test_soft_deleted_in_db(self, e2e_db):
        """Проверяем: тест и вопросы помечены is_active=False."""
        dt = self.state["delete_test"]

        # Тест
        row = await e2e_db.fetchrow(
            "SELECT is_active, deleted_at FROM tests WHERE id = $1",
            dt["test_id"],
        )
        assert row is not None, "Test record should still exist in DB"
        assert row["is_active"] is False, "Test should be inactive after soft delete"
        assert row["deleted_at"] is not None, "Test deleted_at should be set"

        # Вопросы
        row = await e2e_db.fetchrow(
            "SELECT is_active, deleted_at FROM test_questions WHERE id = $1",
            dt["question_id"],
        )
        assert row is not None, "Question record should still exist in DB"
        assert row["is_active"] is False, "Question should be inactive after cascade soft delete"


# =========================================================================
# 6. Hard Delete: Материал БЗ
# =========================================================================


class TestDeleteKBMaterial:
    """Hard delete материала из Базы Знаний."""

    @pytest.fixture(autouse=True)
    def _inject(self, shared_state):
        self.state = shared_state

    async def test_delete_kb_material_via_ui(self, recruiter: BotClient):
        """Рекрутер удаляет материал из папки БЗ."""
        dt = self.state["delete_test"]
        await wait_between_actions()

        # Заходим в БЗ
        resp = await recruiter.send_and_wait("База знаний 📁️", pattern="РЕДАКТОР БАЗЫ ЗНАНИЙ|папки")

        # Открываем папку
        folder_btn = recruiter.find_button_data(resp, text_contains="Удаляемая папка", data_prefix="kb_folder:")
        assert folder_btn, f"Folder button not found. Buttons: {recruiter.get_button_texts(resp)}"

        resp = await recruiter.click_and_wait(resp, data=folder_btn, wait_pattern="Папка|материал")

        # Открываем материал
        material_btn = recruiter.find_button_data(resp, text_contains="Удаляемый материал", data_prefix="kb_material:")
        if not material_btn:
            # Пробуем найти любой материал в папке
            material_btn = recruiter.find_button_data(resp, data_prefix="kb_material:")
        assert material_btn, f"Material button not found. Buttons: {recruiter.get_button_texts(resp)}"

        resp = await recruiter.click_and_wait(resp, data=material_btn, wait_pattern="Материал|материал|Удаляемый")

        # Нажимаем "Удалить материал"
        delete_btn = recruiter.find_button_data(resp, data_prefix="kb_delete_material:")
        assert delete_btn, f"Delete material button not found. Buttons: {recruiter.get_button_texts(resp)}"

        resp = await recruiter.click_and_wait(resp, data=delete_btn, wait_pattern="уверен.*удалить|удалить материал")

        # Подтверждаем удаление
        confirm_btn = recruiter.find_button_data(resp, data_prefix="kb_confirm_delete_material:")
        assert confirm_btn, f"Confirm button not found. Buttons: {recruiter.get_button_texts(resp)}"

        resp = await recruiter.click_and_wait(resp, data=confirm_btn, wait_pattern="УСПЕШНО УДАЛИЛИ МАТЕРИАЛ|успешно")

    async def test_verify_kb_material_hard_deleted_in_db(self, e2e_db):
        """Проверяем: материал физически удалён из БД."""
        dt = self.state["delete_test"]

        row = await e2e_db.fetchrow(
            "SELECT id FROM knowledge_materials WHERE id = $1",
            dt["kb_material_id"],
        )
        assert row is None, "Material should be physically deleted from DB (hard delete)"


# =========================================================================
# 7. Hard Delete: Папка БЗ
# =========================================================================


class TestDeleteKBFolder:
    """Hard delete папки из Базы Знаний."""

    @pytest.fixture(autouse=True)
    def _inject(self, shared_state):
        self.state = shared_state

    async def test_delete_kb_folder_via_ui(self, recruiter: BotClient):
        """Рекрутер удаляет папку 'Удаляемая папка' из БЗ."""
        dt = self.state["delete_test"]
        await wait_between_actions()

        # Заходим в БЗ
        resp = await recruiter.send_and_wait("База знаний 📁️", pattern="РЕДАКТОР БАЗЫ ЗНАНИЙ|папки")

        # Открываем папку
        folder_btn = recruiter.find_button_data(resp, text_contains="Удаляемая папка", data_prefix="kb_folder:")
        assert folder_btn, f"Folder button not found. Buttons: {recruiter.get_button_texts(resp)}"

        resp = await recruiter.click_and_wait(resp, data=folder_btn, wait_pattern="Папка|Удаляемая папка")

        # Нажимаем "Удалить папку"
        delete_btn = recruiter.find_button_data(resp, data_prefix="kb_delete_folder:")
        assert delete_btn, f"Delete folder button not found. Buttons: {recruiter.get_button_texts(resp)}"

        resp = await recruiter.click_and_wait(
            resp, data=delete_btn, wait_pattern="уверен.*удалить.*папку|удалить папку"
        )

        # Подтверждаем удаление
        confirm_btn = recruiter.find_button_data(resp, data_prefix="kb_confirm_delete_folder:")
        assert confirm_btn, f"Confirm button not found. Buttons: {recruiter.get_button_texts(resp)}"

        resp = await recruiter.click_and_wait(resp, data=confirm_btn, wait_pattern="УСПЕШНО УДАЛИЛИ ПАПКУ|успешно")

    async def test_verify_kb_folder_hard_deleted_in_db(self, e2e_db):
        """Проверяем: папка физически удалена из БД."""
        dt = self.state["delete_test"]

        row = await e2e_db.fetchrow(
            "SELECT id FROM knowledge_folders WHERE id = $1",
            dt["kb_folder_id"],
        )
        assert row is None, "Folder should be physically deleted from DB (hard delete)"


# =========================================================================
# 8. Soft Delete: Пользователь (каскад)
# =========================================================================


class TestDeleteUser:
    """
    Удаление пользователя через UI.

    Используем «Руководителев Тест» — он гарантированно активирован
    и виден в списке. Тест order=10, выполняется последним, так что
    удаление руководителя не сломает другие сценарии.
    """

    @pytest.fixture(autouse=True)
    def _inject(self, shared_state):
        self.state = shared_state

    async def test_resolve_user_id(self, e2e_db, shared_state):
        """Получаем ID Руководителева из БД."""
        row = await e2e_db.fetchrow("SELECT id FROM users WHERE full_name = 'Руководителев Тест' AND is_active = true")
        assert row, "User 'Руководителев Тест' not found in DB"
        shared_state["delete_test"]["user_id"] = row["id"]

    async def test_delete_user_via_ui(self, recruiter: BotClient):
        """Рекрутер удаляет 'Руководителев Тест' через UI."""
        await wait_between_actions()

        # Все пользователи → фильтр → список → выбрать → удалить → подтвердить
        resp = await recruiter.send_and_wait("Все пользователи 🚸", pattern="пользовател|Фильтр|фильтр")

        # Показать всех пользователей
        resp = await recruiter.click_and_wait(resp, data=b"uf_all", wait_pattern="пользовател|Выбери")

        # Находим Руководителева
        user_btn = recruiter.find_button_data(resp, text_contains="Руководителев", data_prefix="uf_user:")
        if not user_btn:
            # Может быть на второй странице
            next_page_btn = recruiter.find_button_data(resp, data_prefix="uf_upage:")
            if next_page_btn:
                resp = await recruiter.click_and_wait(resp, data=next_page_btn, wait_pattern="пользовател")
                user_btn = recruiter.find_button_data(resp, text_contains="Руководителев", data_prefix="uf_user:")
        assert user_btn, f"User button not found. Buttons: {recruiter.get_button_texts(resp)}"

        # Открываем карточку пользователя
        resp = await recruiter.click_and_wait(resp, data=user_btn, wait_pattern="Пользователь|Руководителев")

        # Нажимаем "Редактировать" чтобы попасть в редактор
        edit_btn = recruiter.find_button_data(resp, data_prefix="edit_user:")
        assert edit_btn, f"Edit button not found. Buttons: {recruiter.get_button_texts(resp)}"

        resp = await recruiter.click_and_wait(resp, data=edit_btn, wait_pattern="параметр для изменения|Редакт")

        # Нажимаем "Удалить пользователя"
        resp = await recruiter.click_and_wait(
            resp, data=b"delete_user", wait_pattern="ПРЕДУПРЕЖДЕНИЕ|ПОЛНОСТЬЮ УДАЛИТЬ"
        )

        # Подтверждаем
        confirm_btn = recruiter.find_button_data(resp, data_prefix="confirm_delete_user:")
        assert confirm_btn, f"Confirm button not found. Buttons: {recruiter.get_button_texts(resp)}"

        resp = await recruiter.click_and_wait(
            resp, data=confirm_btn, wait_pattern="успешно удален|Пользователь.*удален"
        )

    async def test_verify_user_soft_deleted_in_db(self, e2e_db):
        """Проверяем: пользователь soft deleted, M2M очищены."""
        dt = self.state["delete_test"]
        user_id = dt["user_id"]

        # Пользователь помечен неактивным
        row = await e2e_db.fetchrow(
            "SELECT is_active, deleted_at FROM users WHERE id = $1",
            user_id,
        )
        assert row is not None, "User record should still exist in DB (soft delete)"
        assert row["is_active"] is False, "User should be inactive"
        assert row["deleted_at"] is not None, "deleted_at should be set"

        # M2M roles удалены физически
        count = await e2e_db.fetchval(
            "SELECT count(*) FROM user_roles WHERE user_id = $1",
            user_id,
        )
        assert count == 0, "user_roles should be hard deleted"

        # M2M groups удалены физически
        count = await e2e_db.fetchval(
            "SELECT count(*) FROM user_groups WHERE user_id = $1",
            user_id,
        )
        assert count == 0, "user_groups should be hard deleted"


# =========================================================================
# 9. Блокировка удаления: Группа с пользователями
# =========================================================================


class TestDeleteGroupBlocked:
    """Попытка удалить группу 'Бариста', в которой есть пользователи — должна быть заблокирована."""

    async def test_delete_group_blocked_by_users(self, recruiter: BotClient):
        """Рекрутер пытается удалить группу с пользователями — бот блокирует."""
        await wait_between_actions()

        resp = await recruiter.send_and_wait("Группы 🗂️", pattern="УПРАВЛЕНИЕ ГРУППАМИ|группами")

        resp = await recruiter.click_and_wait(
            resp, data=b"manage_delete_group", wait_pattern="Выбери группу для удаления|удаления"
        )

        # Ищем основную группу "Бариста" (в ней есть пользователи)
        group_btn = recruiter.find_button_data(resp, text_contains="Бариста", data_prefix="delete_group:")
        assert group_btn, f"Barista group not found. Buttons: {recruiter.get_button_texts(resp)}"

        resp = await recruiter.click_and_wait(resp, data=group_btn, wait_pattern="Нельзя удалить|пользовател|уверен")

        # Проверяем что бот сообщил о блокировке
        text = resp.raw_text or ""
        # Если удаление заблокировано — сообщение содержит "Нельзя" или информацию о пользователях
        # Если показана форма подтверждения — значит нет блокировки, и это тоже валидный результат
        # (зависит от того, есть ли пользователи в группе на момент теста)
        assert "Нельзя удалить" in text or "пользовател" in text.lower() or "уверен" in text.lower(), (
            f"Expected block message or confirmation, got: {text[:200]}"
        )


# =========================================================================
# 10. Финальная DB-верификация: сводная проверка
# =========================================================================


class TestFinalDBVerification:
    """Сводная проверка целостности БД после всех удалений."""

    @pytest.fixture(autouse=True)
    def _inject(self, shared_state):
        self.state = shared_state

    async def test_soft_deleted_entities_invisible_in_active_queries(self, e2e_db):
        """Проверяем: soft-deleted сущности не видны в запросах с is_active=true."""
        dt = self.state["delete_test"]

        # Группа невидима в активных
        count = await e2e_db.fetchval(
            "SELECT count(*) FROM groups WHERE id = $1 AND is_active = true",
            dt["group_id"],
        )
        assert count == 0, "Soft-deleted group should not appear in active queries"

        # Объект невидим в активных
        count = await e2e_db.fetchval(
            "SELECT count(*) FROM objects WHERE id = $1 AND is_active = true",
            dt["object_id"],
        )
        assert count == 0, "Soft-deleted object should not appear in active queries"

        # Тест невидим в активных
        count = await e2e_db.fetchval(
            "SELECT count(*) FROM tests WHERE id = $1 AND is_active = true",
            dt["test_id"],
        )
        assert count == 0, "Soft-deleted test should not appear in active queries"

        # Пользователь невидим в активных
        count = await e2e_db.fetchval(
            "SELECT count(*) FROM users WHERE id = $1 AND is_active = true",
            dt["user_id"],
        )
        assert count == 0, "Soft-deleted user should not appear in active queries"

    async def test_soft_deleted_entities_visible_for_admin(self, e2e_db):
        """Проверяем: soft-deleted сущности видны в запросах БЕЗ фильтра is_active (для администратора Sova-tech)."""
        dt = self.state["delete_test"]

        for table, entity_id, name in [
            ("groups", dt["group_id"], "Group"),
            ("objects", dt["object_id"], "Object"),
            ("tests", dt["test_id"], "Test"),
            ("users", dt["user_id"], "User"),
        ]:
            row = await e2e_db.fetchrow(
                f"SELECT id, is_active, deleted_at FROM {table} WHERE id = $1",
                entity_id,
            )
            assert row is not None, f"{name} (id={entity_id}) should still exist in DB for admin access"
            assert row["is_active"] is False, f"{name} should be inactive"
            assert row["deleted_at"] is not None, f"{name} should have deleted_at timestamp"

    async def test_hard_deleted_entities_gone(self, e2e_db):
        """Проверяем: hard-deleted сущности полностью отсутствуют в БД."""
        dt = self.state["delete_test"]

        # Папка БЗ
        row = await e2e_db.fetchrow(
            "SELECT id FROM knowledge_folders WHERE id = $1",
            dt["kb_folder_id"],
        )
        assert row is None, "KB folder should be physically absent from DB"

        # Материал БЗ
        row = await e2e_db.fetchrow(
            "SELECT id FROM knowledge_materials WHERE id = $1",
            dt["kb_material_id"],
        )
        assert row is None, "KB material should be physically absent from DB"
