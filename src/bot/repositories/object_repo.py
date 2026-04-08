from __future__ import annotations

from sqlalchemy import delete, func, select

from bot.database.models import Object, User, user_objects
from bot.repositories.base import BaseRepository
from bot.utils.logger import logger


class ObjectRepository(BaseRepository):
    """Репозиторий для удаления объектов (soft delete)."""

    async def delete(self, object_id: int, company_id: int) -> bool:
        """Мягкое удаление объекта с проверкой зависимостей.

        Проверяет: нет активных пользователей привязанных к объекту.
        При удалении: soft delete объекта + hard delete M2M ассоциаций.
        """
        try:
            # Проверяем существование объекта
            result = await self.session.execute(
                select(Object).where(
                    Object.id == object_id,
                    Object.is_active == True,  # noqa: E712
                    Object.company_id == company_id,
                )
            )
            obj = result.scalar_one_or_none()
            if not obj:
                logger.error(f"Объект {object_id} не найден")
                return False

            # Проверяем: нет активных пользователей
            users_count = await self.session.execute(
                select(func.count())
                .select_from(User)
                .join(user_objects, User.id == user_objects.c.user_id)
                .where(
                    user_objects.c.object_id == object_id,
                    User.is_active == True,  # noqa: E712
                    User.company_id == company_id,
                )
            )
            if users_count.scalar() > 0:
                logger.warning(f"Нельзя удалить объект {object_id}: есть активные пользователи")
                return False

            # Soft delete объекта
            if not await self._soft_delete(Object, object_id, company_id):
                return False

            # Hard delete M2M ассоциаций
            await self.session.execute(delete(user_objects).where(user_objects.c.object_id == object_id))

            await self.session.commit()
            logger.info(f"Объект {object_id} '{obj.name}' мягко удален")
            return True

        except Exception as e:
            logger.error(f"Ошибка удаления объекта {object_id}: {e}")
            await self.session.rollback()
            return False
