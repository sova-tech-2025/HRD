from __future__ import annotations

from sqlalchemy import delete, select

from bot.database.models import KnowledgeFolder, KnowledgeMaterial, folder_group_access
from bot.repositories.base import BaseRepository
from bot.utils.logger import logger


class KnowledgeRepository(BaseRepository):
    """Репозиторий для удаления сущностей Базы Знаний (hard delete)."""

    async def delete_folder(self, folder_id: int, company_id: int) -> bool:
        """Физическое удаление папки со всеми материалами и связями."""
        try:
            # Проверяем существование папки
            result = await self.session.execute(
                select(KnowledgeFolder).where(
                    KnowledgeFolder.id == folder_id,
                    KnowledgeFolder.is_active == True,  # noqa: E712
                    KnowledgeFolder.company_id == company_id,
                )
            )
            folder = result.scalar_one_or_none()
            if not folder:
                logger.error(f"Папка {folder_id} не найдена")
                return False

            # Hard delete материалов папки
            await self.session.execute(delete(KnowledgeMaterial).where(KnowledgeMaterial.folder_id == folder_id))

            # Hard delete связей с группами
            await self.session.execute(delete(folder_group_access).where(folder_group_access.c.folder_id == folder_id))

            # Hard delete самой папки
            await self.session.execute(delete(KnowledgeFolder).where(KnowledgeFolder.id == folder_id))

            await self.session.commit()
            logger.info(f"Папка {folder_id} '{folder.name}' физически удалена со всеми материалами")
            return True

        except Exception as e:
            logger.error(f"Ошибка удаления папки {folder_id}: {e}")
            await self.session.rollback()
            return False

    async def delete_material(self, material_id: int) -> bool:
        """Физическое удаление материала."""
        try:
            # Проверяем существование материала
            result = await self.session.execute(
                select(KnowledgeMaterial).where(
                    KnowledgeMaterial.id == material_id,
                    KnowledgeMaterial.is_active == True,  # noqa: E712
                )
            )
            material = result.scalar_one_or_none()
            if not material:
                logger.error(f"Материал {material_id} не найден")
                return False

            # Hard delete материала
            await self.session.execute(delete(KnowledgeMaterial).where(KnowledgeMaterial.id == material_id))

            await self.session.commit()
            logger.info(f"Материал {material_id} '{material.name}' физически удален")
            return True

        except Exception as e:
            logger.error(f"Ошибка удаления материала {material_id}: {e}")
            await self.session.rollback()
            return False
