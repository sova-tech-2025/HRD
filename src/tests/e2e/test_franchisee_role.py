"""
E2E-тесты роли «Франчайзи».

Проверяют (через ADMIN-ЛК): меню Франчайзи соответствует ТЗ §6/§10.2 —
есть scoped-администрирование, нет управления контентом (Группы/Объекты/Компания).
Требует выполненного test_setup (регистрация admin + роль ADMIN).
"""

import pytest

pytestmark = [
    pytest.mark.order(95),
    pytest.mark.timeout(180),
    pytest.mark.asyncio(loop_scope="session"),
]

EXPECTED_BUTTONS = [
    "Все пользователи",
    "Новые пользователи",
    "Стажеры",
    "Наставники",
    "Рассылка",
    "Тесты",
    "Мои тесты",
    "Аттестация",
    "Экзамены",
]
FORBIDDEN_BUTTONS = ["Группы", "Объекты", "Компания"]


class TestFranchiseeMenu:
    async def test_franchisee_lk_menu(self, admin):
        """ADMIN → ЛК Франчайзи: меню содержит scoped-администрирование и не содержит управление контентом."""
        resp = await admin.switch_role("Франчайзи")
        texts = admin.get_button_texts(resp)
        assert texts, "Меню Франчайзи пустое"

        for expected in EXPECTED_BUTTONS:
            assert any(expected in t for t in texts), f"Нет кнопки '{expected}'. Кнопки: {texts}"

        for forbidden in FORBIDDEN_BUTTONS:
            assert not any(forbidden in t for t in texts), f"Лишняя кнопка '{forbidden}'. Кнопки: {texts}"

    async def test_franchisee_can_open_knowledge_base(self, admin):
        """ADMIN → ЛК Франчайзи: кнопка «База знаний» открывает раздел, а не выдаёт отказ.

        Регрессия: cmd_knowledge_base_universal раньше брал роль только из БД (ADMIN)
        и не учитывал активную FSM-роль, из-за чего Франчайзи получал
        «❌ База знаний доступна только для авторизованных пользователей».
        """
        await admin.switch_role("Франчайзи")
        resp = await admin.send_and_wait(
            "База знаний 📁️",
            pattern="Выбери раздел|нет доступных материалов|РЕДАКТОР БАЗЫ ЗНАНИЙ",
        )
        text = resp.raw_text or ""
        assert "доступна только для авторизованных" not in text, f"Франчайзи получил отказ в БЗ: {text!r}"
        assert "нет прав для просмотра" not in text, f"Франчайзи получил отказ по правам: {text!r}"

    async def test_franchisee_test_card_can_assign_not_delete(self, admin):
        """ADMIN → ЛК Франчайзи: «Тесты» открывают просмотр (не управление),
        карточка теста разрешает назначение доступа, но не редактирование/удаление."""
        await admin.switch_role("Франчайзи")

        resp = await admin.send_and_wait("Тесты 📄", pattern="Список доступных тестов|нет созданных тестов")
        text = resp.raw_text or ""
        assert "УПРАВЛЕНИЕ ТЕСТАМИ" not in text, f"Франчайзи не должен видеть меню управления: {text!r}"

        test_btn = admin.find_button_data(resp, data_prefix="test:")
        assert test_btn, f"Нет тестов в списке. Кнопки: {admin.get_button_data(resp)}"

        resp = await admin.click_and_wait(resp, data=test_btn, wait_pattern="Детальная информация о тесте")
        texts = admin.get_button_texts(resp)
        assert any("Предоставить доступ" in t for t in texts), f"Нет кнопки назначения доступа: {texts}"
        assert not any("Удалить" in t for t in texts), f"Франчайзи видит кнопку удаления теста: {texts}"
        assert not any("Редактировать" in t for t in texts), f"Франчайзи видит кнопку редактирования: {texts}"


@pytest.mark.order(96)
class TestFranchiseeScope:
    """Скоупинг на РЕАЛЬНОМ Франчайзи: видит пользователей только своих объектов."""

    async def _setup(self, e2e_db, shared_state) -> dict:
        company_id = await e2e_db.fetchval("SELECT id FROM companies WHERE name = $1", shared_state["company_name"])
        obj_a = await e2e_db.fetchval(
            "SELECT id FROM objects WHERE name = $1 AND company_id = $2", shared_state["object_name"], company_id
        )
        obj_b = await e2e_db.fetchval(
            """
            INSERT INTO objects (name, created_date, is_active, company_id)
            VALUES ('Кафе Юг', now(), true, $1) RETURNING id
            """,
            company_id,
        )
        employee_role = await e2e_db.fetchval("SELECT id FROM roles WHERE name = 'Сотрудник'")
        franchisee_role = await e2e_db.fetchval("SELECT id FROM roles WHERE name = 'Франчайзи'")

        async def make_employee(tg_id: int, name: str, phone: str, work_object_id: int) -> int:
            uid = await e2e_db.fetchval(
                """
                INSERT INTO users (tg_id, full_name, phone_number, is_active, is_activated,
                                   work_object_id, company_id, registration_date, role_assigned_date)
                VALUES ($1, $2, $3, true, true, $4, $5, now(), now()) RETURNING id
                """,
                tg_id,
                name,
                phone,
                work_object_id,
                company_id,
            )
            await e2e_db.execute("INSERT INTO user_roles (user_id, role_id) VALUES ($1, $2)", uid, employee_role)
            return uid

        await make_employee(990000001, "Альфа Сотрудник", "+79990000001", obj_a)
        await make_employee(990000002, "Бета Сотрудник", "+79990000002", obj_b)

        trainee_id = await e2e_db.fetchval("SELECT id FROM users WHERE phone_number = '+79001000002'")
        await e2e_db.execute("DELETE FROM user_roles WHERE user_id = $1", trainee_id)
        await e2e_db.execute("INSERT INTO user_roles (user_id, role_id) VALUES ($1, $2)", trainee_id, franchisee_role)
        await e2e_db.execute("UPDATE users SET work_object_id = NULL WHERE id = $1", trainee_id)
        await e2e_db.execute(
            "INSERT INTO user_work_objects (user_id, object_id) VALUES ($1, $2) ON CONFLICT DO NOTHING",
            trainee_id,
            obj_a,
        )
        return {"obj_a": obj_a, "obj_b": obj_b}

    async def test_franchisee_sees_only_in_scope_users(self, trainee, e2e_db, shared_state):
        await self._setup(e2e_db, shared_state)

        resp = await trainee.send_and_wait("Все пользователи 🚸", pattern="фильтрац|способ")
        resp = await trainee.click_and_wait(resp, data=b"uf_all", wait_pattern="ПОЛЬЗОВАТЕЛЕЙ|Найдено|пользоват")

        texts = trainee.get_button_texts(resp)
        joined = " ".join(texts)
        assert "Альфа" in joined, f"Франчайзи не видит сотрудника своего объекта. Кнопки: {texts}"
        assert "Бета" not in joined, f"Франчайзи видит сотрудника ЧУЖОГО объекта (утечка scope). Кнопки: {texts}"

    async def test_admin_can_edit_franchisee_objects_via_user_card(self, admin, e2e_db):
        """Через карточку пользователя (редактор) можно добавить Франчайзи объект
        без переназначения роли — сценарий «Франчайзи открыл дополнительный объект»."""
        trainee_id = await e2e_db.fetchval("SELECT id FROM users WHERE phone_number = '+79001000002'")
        before = await e2e_db.fetchval("SELECT count(*) FROM user_work_objects WHERE user_id = $1", trainee_id)
        assert before == 1, f"Предусловие: у Франчайзи должен быть 1 объект, есть {before}"

        await admin.switch_role("Рекрутер")
        resp = await admin.send_and_wait("Все пользователи 🚸", pattern="фильтрац|способ|пользоват")
        resp = await admin.click_and_wait(resp, data=b"uf_all", wait_pattern="ПОЛЬЗОВАТЕЛЕЙ|Найдено|пользоват")

        user_btn = admin.find_button_data(resp, text_contains="Стажёров", data_prefix="uf_user:")
        for _ in range(5):
            if user_btn:
                break
            next_btn = admin.find_button_data(resp, data_prefix="uf_upage:")
            if not next_btn:
                break
            resp = await admin.click_and_wait(resp, data=next_btn, wait_pattern="пользоват")
            user_btn = admin.find_button_data(resp, text_contains="Стажёров", data_prefix="uf_user:")
        assert user_btn, f"Франчайзи не найден в списке. Кнопки: {admin.get_button_texts(resp)}"

        resp = await admin.click_and_wait(resp, data=user_btn, wait_pattern="Пользователь|Стажёров")
        edit_btn = admin.find_button_data(resp, data_prefix="edit_user:")
        assert edit_btn, f"Нет кнопки редактирования. Кнопки: {admin.get_button_texts(resp)}"
        resp = await admin.click_and_wait(resp, data=edit_btn, wait_pattern="параметр для изменения|Редакт")

        # Ключевая проверка: для существующего Франчайзи в редакторе есть кнопка «Объекты Франчайзи»
        fr_btn = admin.find_button_data(resp, data_prefix="franchisee_objects:")
        assert fr_btn, f"Нет кнопки «Объекты Франчайзи» в редакторе. Кнопки: {admin.get_button_texts(resp)}"

        resp = await admin.click_and_wait(resp, data=fr_btn, wait_pattern="Объекты Франчайзи")

        # Выбираем все доступные объекты (добавляем второй) и сохраняем
        all_btn = admin.find_button_data(resp, data_prefix="fr_obj_all")
        assert all_btn, f"Нет кнопки выбора всех объектов. Кнопки: {admin.get_button_texts(resp)}"
        resp = await admin.click_and_wait(resp, data=all_btn, wait_pattern="Выбрано")

        done_btn = admin.find_button_data(resp, data_prefix="fr_obj_done")
        assert done_btn, f"Нет кнопки сохранения. Кнопки: {admin.get_button_texts(resp)}"
        resp = await admin.click_and_wait(resp, data=done_btn, wait_pattern="сохранены")

        after = await e2e_db.fetchval("SELECT count(*) FROM user_work_objects WHERE user_id = $1", trainee_id)
        assert after > before and after >= 2, f"Объект Франчайзи не добавился: было {before}, стало {after}"


@pytest.mark.order(97)
class TestFranchiseeAttestation:
    """Франчайзи может проводить аттестацию: право conduct_attestations + кнопка «Аттестация».

    ВАЖНО: проверка идёт на РЕАЛЬНОМ Франчайзи (клиент trainee, конвертированный
    в TestFranchiseeScope), а не через admin.switch_role — у ADMIN
    check_user_permission всегда True (is_admin_user), что замаскировало бы
    отсутствие права у роли Франчайзи.
    """

    FR_PHONE = "+79001000002"
    EXAMINEE_TG = 990000050

    async def _assign_attestation_to_franchisee(self, e2e_db, shared_state) -> dict:
        company_id = await e2e_db.fetchval("SELECT id FROM companies WHERE name = $1", shared_state["company_name"])
        franchisee_id = await e2e_db.fetchval("SELECT id FROM users WHERE phone_number = $1", self.FR_PHONE)
        assert franchisee_id, "Реальный Франчайзи (из TestFranchiseeScope) не найден в БД"

        # Страховка: гарантируем роль «Франчайзи» (на случай изменения порядка тестов)
        franchisee_role = await e2e_db.fetchval("SELECT id FROM roles WHERE name = 'Франчайзи'")
        await e2e_db.execute(
            "INSERT INTO user_roles (user_id, role_id) VALUES ($1, $2) ON CONFLICT DO NOTHING",
            franchisee_id,
            franchisee_role,
        )

        # Стажёр той же компании, которого аттестует Франчайзи (manager_id = franchisee)
        examinee_id = await e2e_db.fetchval(
            """
            INSERT INTO users (tg_id, full_name, phone_number, is_active, is_activated,
                               company_id, registration_date, role_assigned_date)
            VALUES ($1, 'Гамма Аттестуемый', '+79990000050', true, true, $2, now(), now())
            ON CONFLICT (tg_id) DO UPDATE SET company_id = EXCLUDED.company_id
            RETURNING id
            """,
            self.EXAMINEE_TG,
            company_id,
        )

        attestation_id = await e2e_db.fetchval(
            "SELECT id FROM attestations WHERE company_id = $1 ORDER BY id LIMIT 1", company_id
        )
        assert attestation_id, "В компании нет ни одной аттестации для назначения"

        await e2e_db.execute("DELETE FROM trainee_attestations WHERE trainee_id = $1", examinee_id)
        await e2e_db.execute(
            """
            INSERT INTO trainee_attestations
                (trainee_id, manager_id, attestation_id, assigned_by_id, status, is_active, assigned_date)
            VALUES ($1, $2, $3, $2, 'assigned', true, now())
            """,
            examinee_id,
            franchisee_id,
            attestation_id,
        )
        return {"franchisee_id": franchisee_id, "examinee_id": examinee_id}

    async def test_franchisee_attestation_shows_assigned_trainee(self, trainee, e2e_db, shared_state):
        """Реальный Франчайзи жмёт «Аттестация» → видит назначенного стажёра, а не отказ по правам."""
        await self._assign_attestation_to_franchisee(e2e_db, shared_state)

        # /start обновляет FSM реального Франчайзи (role=Франчайзи, company_id)
        await trainee.send_and_wait("/start", pattern="Добро пожаловать|меню|Франчайзи")

        resp = await trainee.send_and_wait(
            "Аттестация ✔️", pattern="[Аа]ттестац|стажер|стажёр|готовы пройти|Недостаточно прав"
        )
        text = resp.raw_text or ""

        assert "Недостаточно прав" not in text, (
            f"Франчайзи получил отказ по правам — право conduct_attestations не выдано роли: {text!r}"
        )

        trainee_btn = trainee.find_button_data(resp, data_prefix="select_trainee_attestation:")
        assert trainee_btn, (
            f"Назначенный стажёр не виден Франчайзи в списке аттестаций. "
            f"Текст: {text[:300]!r}, кнопки: {trainee.get_button_texts(resp)}"
        )

    async def test_cleanup(self, e2e_db):
        """Очистка: удаляем созданного аттестуемого и его назначение."""
        examinee_id = await e2e_db.fetchval("SELECT id FROM users WHERE tg_id = $1", self.EXAMINEE_TG)
        if examinee_id:
            await e2e_db.execute("DELETE FROM trainee_attestations WHERE trainee_id = $1", examinee_id)
            await e2e_db.execute("DELETE FROM user_roles WHERE user_id = $1", examinee_id)
            await e2e_db.execute("DELETE FROM users WHERE id = $1", examinee_id)
