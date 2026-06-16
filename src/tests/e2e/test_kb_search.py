"""
E2E: поиск материалов в Базе Знаний.

Сценарий:
1. Рекрутер создаёт папку БЗ и материал-ссылку
2. Рекрутер открывает поиск, вводит короткий запрос (валидация)
3. Рекрутер ищет материал по части названия и открывает его
4. Поиск по несуществующему названию возвращает «ничего не найдено»
"""

import pytest

from tests.e2e.helpers.bot_client import BotClient
from tests.e2e.helpers.waiters import wait_between_actions

pytestmark = [
    pytest.mark.order(11),
    pytest.mark.timeout(300),
    pytest.mark.asyncio(loop_scope="session"),
]

FOLDER_NAME = "Папка для поиска"
MATERIAL_NAME = "Уникальный материал поиска"


class TestKnowledgeBaseSearch:
    """Поиск по Базе Знаний из редактора рекрутера."""

    async def test_switch_to_recruiter(self, recruiter: BotClient):
        """ADMIN переключается в Рекрутер."""
        await recruiter.switch_role("Рекрутер")

    async def test_create_folder_and_material(self, recruiter: BotClient):
        """Рекрутер создаёт папку и материал-ссылку для поиска."""
        await wait_between_actions()

        resp = await recruiter.send_and_wait("База знаний 📁️", pattern="РЕДАКТОР БАЗЫ ЗНАНИЙ")
        resp = await recruiter.click_and_wait(resp, data=b"kb_create_folder", wait_contains="название")
        resp = await recruiter.send_and_wait(FOLDER_NAME, pattern="успешно добавил")
        resp = await recruiter.click_and_wait(
            resp, data=b"kb_add_material", wait_pattern="название материала|Введи название"
        )
        resp = await recruiter.send_and_wait(MATERIAL_NAME, pattern="документ|ссылку|материалом")
        resp = await recruiter.send_and_wait("https://example.com/search-test", pattern="описание")
        resp = await recruiter.click_and_wait(resp, data=b"kb_skip_description", wait_pattern="фото|Пропустить")
        resp = await recruiter.click_and_wait(resp, data=b"kb_skip_photos", wait_pattern="Сохранить|сохранить")
        resp = await recruiter.click_and_wait(
            resp, data=b"kb_save_material", wait_pattern="успешно сохранил|успешно добавил"
        )

    async def test_search_short_query_rejected(self, recruiter: BotClient):
        """Запрос из 1 символа отклоняется с подсказкой."""
        await wait_between_actions()

        resp = await recruiter.send_and_wait("База знаний 📁️", pattern="РЕДАКТОР БАЗЫ ЗНАНИЙ")
        resp = await recruiter.click_and_wait(resp, data=b"kb_search", wait_contains="Поиск материалов")
        resp = await recruiter.send_and_wait("У", pattern="слишком короткий")

    async def test_search_finds_material_and_opens_it(self, recruiter: BotClient):
        """Поиск по части названия находит материал, нажатие открывает вложения."""
        await wait_between_actions()

        resp = await recruiter.send_and_wait("Уникальный", pattern="Результаты поиска")

        material_btn = recruiter.find_button_data(resp, data_prefix="kb_search_result:")
        assert material_btn, f"Кнопка результата поиска не найдена: {recruiter.get_button_texts(resp)}"

        resp = await recruiter.click_and_wait(resp, data=material_btn, wait_contains="Навигация по результатам поиска")

    async def test_search_no_results(self, recruiter: BotClient):
        """Поиск по несуществующему названию возвращает пустой результат."""
        await wait_between_actions()

        resp = await recruiter.send_and_wait("База знаний 📁️", pattern="РЕДАКТОР БАЗЫ ЗНАНИЙ")
        resp = await recruiter.click_and_wait(resp, data=b"kb_search", wait_contains="Поиск материалов")
        resp = await recruiter.send_and_wait("НесуществующийМатериалXYZ", pattern="ничего не найдено")
