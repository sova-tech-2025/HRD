from __future__ import annotations

from sqlalchemy import or_, select
from sqlalchemy.orm import selectinload

from bot.database.models import Mentorship, Role, User, user_groups, user_roles
from bot.repositories.base import BaseRepository
from bot.repositories.scope import apply_object_scope, apply_object_scope_any, user_in_scope

_MIXED_SCOPE_COLUMNS = (User.work_object_id, User.internship_object_id)


def _admin_inclusive(role_names: list[str]):
    return or_(Role.name.in_(role_names), Role.name == "ADMIN")


class ScopedUserRepository(BaseRepository):
    """Scoped-чтения для администрирования пользователей.

    scope=None — без ограничений (Рекрутер/ADMIN). Для set[int]:
    стажёры скоупятся по объекту стажировки, остальные — по объекту работы,
    смешанные списки — по любому из двух объектов.
    """

    _DETAILS = (
        selectinload(User.roles),
        selectinload(User.groups),
        selectinload(User.internship_object),
        selectinload(User.work_object),
    )

    async def list_activated(self, company_id: int | None = None, scope: set[int] | None = None) -> list[User]:
        query = (
            select(User).options(*self._DETAILS).where(User.is_activated == True, User.is_active == True)  # noqa: E712
        )
        if company_id is not None:
            query = query.where(User.company_id == company_id)
        query = apply_object_scope_any(query, scope, _MIXED_SCOPE_COLUMNS)
        result = await self.session.execute(query.order_by(User.id))
        return list(result.scalars().all())

    async def list_trainees(self, company_id: int | None = None, scope: set[int] | None = None) -> list[User]:
        query = (
            select(User)
            .options(*self._DETAILS)
            .join(user_roles, User.id == user_roles.c.user_id)
            .join(Role, user_roles.c.role_id == Role.id)
            .where(
                _admin_inclusive(["Стажер"]),
                User.is_activated == True,  # noqa: E712
                User.is_active == True,  # noqa: E712
            )
        )
        if company_id is not None:
            query = query.where(User.company_id == company_id)
        query = apply_object_scope(query, scope, User.internship_object_id)
        result = await self.session.execute(query.order_by(User.registration_date.desc()))
        return list(result.scalars().all())

    async def list_mentors(self, company_id: int | None = None, scope: set[int] | None = None) -> list[User]:
        query = (
            select(User)
            .options(selectinload(User.work_object), selectinload(User.internship_object))
            .join(user_roles, User.id == user_roles.c.user_id)
            .join(Role, user_roles.c.role_id == Role.id)
            .where(_admin_inclusive(["Наставник", "Руководитель"]), User.is_active == True)  # noqa: E712
        )
        if company_id is not None:
            query = query.where(User.company_id == company_id)
        query = apply_object_scope(query, scope, User.work_object_id)
        result = await self.session.execute(query.order_by(User.full_name))
        return list(result.scalars().all())

    async def list_trainees_without_mentor(
        self, company_id: int | None = None, scope: set[int] | None = None
    ) -> list[User]:
        roles_result = await self.session.execute(select(Role).where(Role.name.in_(["Стажер", "ADMIN"])))
        role_ids = [r.id for r in roles_result.scalars().all()]
        if not role_ids:
            return []
        query = (
            select(User)
            .options(*self._DETAILS)
            .where(User.is_active == True, User.is_activated == True)  # noqa: E712
            .join(user_roles)
            .where(user_roles.c.role_id.in_(role_ids))
            .outerjoin(Mentorship, (Mentorship.trainee_id == User.id) & (Mentorship.is_active == True))  # noqa: E712
            .where(Mentorship.id.is_(None))
        )
        if company_id is not None:
            query = query.where(User.company_id == company_id)
        query = apply_object_scope(query, scope, User.internship_object_id)
        result = await self.session.execute(query.order_by(User.full_name))
        return list(result.scalars().all())

    async def list_by_group(
        self, group_id: int, company_id: int | None = None, scope: set[int] | None = None
    ) -> list[User]:
        query = (
            select(User)
            .options(*self._DETAILS)
            .join(user_groups, User.id == user_groups.c.user_id)
            .where(
                user_groups.c.group_id == group_id,
                User.is_activated == True,  # noqa: E712
                User.is_active == True,  # noqa: E712
            )
        )
        if company_id is not None:
            query = query.where(User.company_id == company_id)
        query = apply_object_scope_any(query, scope, _MIXED_SCOPE_COLUMNS)
        result = await self.session.execute(query.order_by(User.full_name))
        return list(result.scalars().all())

    async def list_by_object(
        self, object_id: int, company_id: int | None = None, scope: set[int] | None = None
    ) -> list[User]:
        query = (
            select(User)
            .options(*self._DETAILS)
            .where(
                or_(User.internship_object_id == object_id, User.work_object_id == object_id),
                User.is_activated == True,  # noqa: E712
                User.is_active == True,  # noqa: E712
            )
        )
        if company_id is not None:
            query = query.where(User.company_id == company_id)
        query = apply_object_scope_any(query, scope, _MIXED_SCOPE_COLUMNS)
        result = await self.session.execute(query.order_by(User.full_name))
        return list(result.scalars().all())

    async def search_by_name(
        self, name_query: str, company_id: int | None = None, scope: set[int] | None = None
    ) -> list[User]:
        query = (
            select(User)
            .options(*self._DETAILS)
            .where(
                User.is_activated == True,  # noqa: E712
                User.is_active == True,  # noqa: E712
                User.full_name.ilike(f"%{name_query}%"),
            )
        )
        if company_id is not None:
            query = query.where(User.company_id == company_id)
        query = apply_object_scope_any(query, scope, _MIXED_SCOPE_COLUMNS)
        result = await self.session.execute(query.order_by(User.full_name))
        return list(result.scalars().all())

    @staticmethod
    def can_edit(target_user: User, scope: set[int] | None) -> bool:
        """Edit-guard: Франчайзи правит пользователя при совпадении объекта работы или стажировки."""
        return user_in_scope(scope, target_user)
