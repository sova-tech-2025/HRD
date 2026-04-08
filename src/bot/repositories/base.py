from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from bot.utils.timezone import moscow_now


class BaseRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def _soft_delete(self, model_class, entity_id: int, company_id: int = None) -> bool:
        """Мягкое удаление: is_active=False, deleted_at=now()"""
        query = (
            update(model_class)
            .where(model_class.id == entity_id, model_class.is_active == True)  # noqa: E712
            .values(is_active=False, deleted_at=moscow_now())
        )
        if company_id is not None and hasattr(model_class, "company_id"):
            query = query.where(model_class.company_id == company_id)
        result = await self.session.execute(query)
        return result.rowcount > 0

    async def _bulk_soft_delete(self, model_class, *conditions) -> int:
        """Массовое мягкое удаление по условиям. Возвращает количество затронутых строк."""
        query = (
            update(model_class)
            .where(model_class.is_active == True, *conditions)  # noqa: E712
            .values(is_active=False, deleted_at=moscow_now())
        )
        result = await self.session.execute(query)
        return result.rowcount
