from __future__ import annotations

from typing import Protocol, runtime_checkable

from sqlalchemy import or_
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import User

UNRESTRICTED_ROLES = {"ADMIN", "Рекрутер"}

# Роли, которые Франчайзи (scoped-актор) вправе назначать другим пользователям.
FRANCHISEE_ASSIGNABLE_ROLES = {"Сотрудник", "Стажер", "Наставник"}


def can_assign_role(scope: set[int] | None, role_name: str) -> bool:
    """Может ли актор с данной областью назначать роль role_name.

    scope=None (Рекрутер/ADMIN) — любую; Франчайзи — только из белого списка.
    """
    if scope is None:
        return True
    return role_name in FRANCHISEE_ASSIGNABLE_ROLES


@runtime_checkable
class ObjectScopeResolver(Protocol):
    """Интерфейс разрешения области видимости пользователя по объектам.

    Возвращает None — без ограничений; set[int] — допустимые id объектов.
    """

    async def resolve(self, session: AsyncSession, user) -> set[int] | None: ...


def role_names(user) -> set[str]:
    return {r.name if hasattr(r, "name") else r for r in (getattr(user, "roles", None) or [])}


def is_franchisee(user) -> bool:
    return "Франчайзи" in role_names(user)


class RoleBasedScopeResolver:
    """Разрешение области по ролям пользователя.

    Рекрутер/ADMIN — без ограничений (None); Франчайзи — его объекты; иначе — None.
    """

    async def resolve(self, session: AsyncSession, user) -> set[int] | None:
        names = role_names(user)
        if names & UNRESTRICTED_ROLES:
            return None
        if "Франчайзи" in names:
            from bot.repositories.franchisee_repo import FranchiseeRepository

            return await FranchiseeRepository(session).get_object_ids(user.id)
        return None


_default_resolver: ObjectScopeResolver = RoleBasedScopeResolver()


async def get_scope_object_ids(
    session: AsyncSession, user, resolver: ObjectScopeResolver | None = None
) -> set[int] | None:
    return await (resolver or _default_resolver).resolve(session, user)


def apply_object_scope(query, scope: set[int] | None, column=None):
    """Добавляет фильтр column IN scope, если область ограничена (не None)."""
    if scope is None:
        return query
    if column is None:
        column = User.work_object_id
    return query.where(column.in_(scope))


def apply_object_scope_any(query, scope: set[int] | None, columns):
    """Фильтр: хотя бы одна из колонок IN scope (None => без ограничений).

    Используется для смешанных списков: стажёры скоупятся по объекту стажировки,
    остальные — по объекту работы.
    """
    if scope is None:
        return query
    return query.where(or_(*[column.in_(scope) for column in columns]))


def in_scope(scope: set[int] | None, object_id: int | None) -> bool:
    """Попадает ли объект в область видимости (None => без ограничений)."""
    if scope is None:
        return True
    return object_id in scope


def user_in_scope(scope: set[int] | None, user) -> bool:
    """Пользователь в области: объект работы ИЛИ объект стажировки попадает в scope."""
    if scope is None:
        return True
    return user.work_object_id in scope or user.internship_object_id in scope
