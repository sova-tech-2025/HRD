"""
Unit-тесты для KnowledgeRepository.

Проверяют физическое удаление папок (с материалами и связями)
и отдельных материалов базы знаний.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from bot.repositories.knowledge_repo import KnowledgeRepository


def make_scalar_one_or_none_result(value) -> MagicMock:
    """Создать мок результата session.execute() с scalar_one_or_none()."""
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    return result


# ==========================================================================
# delete_folder()
# ==========================================================================


class TestDeleteFolder:
    """Физическое удаление папки базы знаний."""

    @pytest.mark.asyncio
    async def test_delete_folder_success(self):
        """delete_folder() удаляет папку, материалы и связи → True."""
        session = AsyncMock()

        folder_mock = MagicMock()
        folder_mock.id = 1
        folder_mock.name = "Рецепты"

        # execute вызывается 4 раза:
        # 1. SELECT KnowledgeFolder → scalar_one_or_none
        # 2. DELETE KnowledgeMaterial (материалы папки)
        # 3. DELETE folder_group_access (связи с группами)
        # 4. DELETE KnowledgeFolder (сама папка)
        session.execute = AsyncMock(
            side_effect=[
                make_scalar_one_or_none_result(folder_mock),  # SELECT
                MagicMock(),  # DELETE materials
                MagicMock(),  # DELETE group access
                MagicMock(),  # DELETE folder
            ]
        )

        repo = KnowledgeRepository(session)
        result = await repo.delete_folder(folder_id=1, company_id=10)

        assert result is True
        session.commit.assert_awaited_once()
        session.rollback.assert_not_awaited()
        assert session.execute.await_count == 4

    @pytest.mark.asyncio
    async def test_delete_folder_not_found(self):
        """delete_folder() возвращает False, если папка не найдена."""
        session = AsyncMock()

        session.execute = AsyncMock(
            return_value=make_scalar_one_or_none_result(None),
        )

        repo = KnowledgeRepository(session)
        result = await repo.delete_folder(folder_id=999, company_id=10)

        assert result is False
        session.commit.assert_not_awaited()


# ==========================================================================
# delete_material()
# ==========================================================================


class TestDeleteMaterial:
    """Физическое удаление материала базы знаний."""

    @pytest.mark.asyncio
    async def test_delete_material_success(self):
        """delete_material() удаляет материал → True."""
        session = AsyncMock()

        material_mock = MagicMock()
        material_mock.id = 5
        material_mock.name = "Инструкция по кассе"

        # execute вызывается 2 раза:
        # 1. SELECT KnowledgeMaterial → scalar_one_or_none
        # 2. DELETE KnowledgeMaterial
        session.execute = AsyncMock(
            side_effect=[
                make_scalar_one_or_none_result(material_mock),  # SELECT
                MagicMock(),  # DELETE material
            ]
        )

        repo = KnowledgeRepository(session)
        result = await repo.delete_material(material_id=5)

        assert result is True
        session.commit.assert_awaited_once()
        session.rollback.assert_not_awaited()
        assert session.execute.await_count == 2

    @pytest.mark.asyncio
    async def test_delete_material_not_found(self):
        """delete_material() возвращает False, если материал не найден."""
        session = AsyncMock()

        session.execute = AsyncMock(
            return_value=make_scalar_one_or_none_result(None),
        )

        repo = KnowledgeRepository(session)
        result = await repo.delete_material(material_id=999)

        assert result is False
        session.commit.assert_not_awaited()
