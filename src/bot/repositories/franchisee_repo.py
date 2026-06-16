from __future__ import annotations

from sqlalchemy import delete, insert, select

from bot.database.models import Object, user_work_objects
from bot.repositories.base import BaseRepository


class FranchiseeRepository(BaseRepository):
    """Управление набором объектов работы роли «Франчайзи» (M2M user_work_objects)."""

    async def get_object_ids(self, user_id: int) -> set[int]:
        result = await self.session.execute(
            select(user_work_objects.c.object_id).where(user_work_objects.c.user_id == user_id)
        )
        return {row[0] for row in result.all()}

    async def get_objects(self, user_id: int) -> list[Object]:
        result = await self.session.execute(
            select(Object)
            .join(user_work_objects, Object.id == user_work_objects.c.object_id)
            .where(user_work_objects.c.user_id == user_id)
            .order_by(Object.name)
        )
        return list(result.scalars().all())

    async def set_objects(self, user_id: int, object_ids: list[int]) -> None:
        """Полностью переустанавливает набор объектов Франчайзи."""
        await self.session.execute(delete(user_work_objects).where(user_work_objects.c.user_id == user_id))
        for object_id in dict.fromkeys(object_ids):
            await self.session.execute(insert(user_work_objects).values(user_id=user_id, object_id=object_id))
        await self.session.commit()

    async def clear_objects(self, user_id: int) -> None:
        await self.session.execute(delete(user_work_objects).where(user_work_objects.c.user_id == user_id))
        await self.session.commit()
