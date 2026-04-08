from __future__ import annotations

from sqlalchemy import delete, func, select

from bot.database.models import (
    Group,
    KnowledgeFolder,
    LearningPath,
    User,
    folder_group_access,
    user_groups,
)
from bot.repositories.base import BaseRepository
from bot.utils.logger import logger


class GroupRepository(BaseRepository):
    """Репозиторий для удаления групп (soft delete)."""

    async def delete(self, group_id: int, company_id: int) -> bool:
        """Мягкое удаление группы с проверками зависимостей.

        Проверяет: нет активных пользователей, траекторий, папок БЗ.
        При удалении: soft delete группы + hard delete M2M ассоциаций.
        """
        try:
            # Проверяем существование группы
            result = await self.session.execute(
                select(Group).where(
                    Group.id == group_id,
                    Group.is_active == True,  # noqa: E712
                    Group.company_id == company_id,
                )
            )
            group = result.scalar_one_or_none()
            if not group:
                logger.error(f"Группа {group_id} не найдена")
                return False

            # Проверяем: нет активных пользователей в группе
            users_count = await self.session.execute(
                select(func.count())
                .select_from(User)
                .join(user_groups, User.id == user_groups.c.user_id)
                .where(
                    user_groups.c.group_id == group_id,
                    User.is_active == True,  # noqa: E712
                    User.company_id == company_id,
                )
            )
            if users_count.scalar() > 0:
                logger.warning(f"Нельзя удалить группу {group_id}: есть активные пользователи")
                return False

            # Проверяем: нет активных траекторий
            paths_count = await self.session.execute(
                select(func.count())
                .select_from(LearningPath)
                .where(
                    LearningPath.group_id == group_id,
                    LearningPath.is_active == True,  # noqa: E712
                    LearningPath.company_id == company_id,
                )
            )
            if paths_count.scalar() > 0:
                logger.warning(f"Нельзя удалить группу {group_id}: используется в траекториях")
                return False

            # Проверяем: нет папок БЗ привязанных к группе
            folders_count = await self.session.execute(
                select(func.count())
                .select_from(KnowledgeFolder)
                .join(folder_group_access, KnowledgeFolder.id == folder_group_access.c.folder_id)
                .where(
                    folder_group_access.c.group_id == group_id,
                    KnowledgeFolder.is_active == True,  # noqa: E712
                    KnowledgeFolder.company_id == company_id,
                )
            )
            if folders_count.scalar() > 0:
                logger.warning(f"Нельзя удалить группу {group_id}: используется в базе знаний")
                return False

            # Soft delete группы
            if not await self._soft_delete(Group, group_id, company_id):
                return False

            # Hard delete M2M ассоциаций
            await self.session.execute(delete(user_groups).where(user_groups.c.group_id == group_id))
            await self.session.execute(delete(folder_group_access).where(folder_group_access.c.group_id == group_id))

            await self.session.commit()
            logger.info(f"Группа {group_id} '{group.name}' мягко удалена")
            return True

        except Exception as e:
            logger.error(f"Ошибка удаления группы {group_id}: {e}")
            await self.session.rollback()
            return False
