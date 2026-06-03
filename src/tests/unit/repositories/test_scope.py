"""Unit-тесты scope-слоя роли «Франчайзи»: разрешение области и edit-guard."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from bot.repositories.scope import (
    RoleBasedScopeResolver,
    apply_object_scope,
    get_scope_object_ids,
    in_scope,
    is_franchisee,
)
from bot.repositories.scoped_user_repo import ScopedUserRepository


def make_user(role_names: list[str], user_id: int = 1):
    return SimpleNamespace(id=user_id, roles=[SimpleNamespace(name=n) for n in role_names])


def make_object_ids_result(object_ids: list[int]) -> MagicMock:
    result = MagicMock()
    result.all.return_value = [(oid,) for oid in object_ids]
    return result


class TestGetScopeObjectIds:
    @pytest.mark.asyncio
    async def test_recruiter_unrestricted(self):
        session = AsyncMock()
        assert await get_scope_object_ids(session, make_user(["Рекрутер"])) is None
        session.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_admin_unrestricted(self):
        session = AsyncMock()
        assert await get_scope_object_ids(session, make_user(["ADMIN"])) is None

    @pytest.mark.asyncio
    async def test_franchisee_returns_object_set(self):
        session = AsyncMock()
        session.execute.return_value = make_object_ids_result([3, 7, 9])
        scope = await get_scope_object_ids(session, make_user(["Франчайзи"], user_id=42))
        assert scope == {3, 7, 9}

    @pytest.mark.asyncio
    async def test_franchisee_without_objects_empty_set(self):
        session = AsyncMock()
        session.execute.return_value = make_object_ids_result([])
        scope = await get_scope_object_ids(session, make_user(["Франчайзи"]))
        assert scope == set()

    @pytest.mark.asyncio
    async def test_other_roles_unrestricted(self):
        session = AsyncMock()
        assert await get_scope_object_ids(session, make_user(["Сотрудник"])) is None

    @pytest.mark.asyncio
    async def test_resolver_is_protocol_impl(self):
        from bot.repositories.scope import ObjectScopeResolver

        assert isinstance(RoleBasedScopeResolver(), ObjectScopeResolver)


class TestApplyObjectScope:
    def test_none_is_noop(self):
        query = MagicMock()
        assert apply_object_scope(query, None) is query
        query.where.assert_not_called()

    def test_set_applies_where(self):
        query = MagicMock()
        apply_object_scope(query, {1, 2})
        query.where.assert_called_once()


class TestInScopeAndFranchisee:
    def test_in_scope_none_always_true(self):
        assert in_scope(None, 5) is True
        assert in_scope(None, None) is True

    def test_in_scope_membership(self):
        assert in_scope({1, 2}, 2) is True
        assert in_scope({1, 2}, 9) is False

    def test_is_franchisee(self):
        assert is_franchisee(make_user(["Франчайзи"])) is True
        assert is_franchisee(make_user(["Рекрутер"])) is False


class TestCanEdit:
    def test_unrestricted_scope_allows_any(self):
        target = SimpleNamespace(work_object_id=5, internship_object_id=None)
        assert ScopedUserRepository.can_edit(target, None) is True

    def test_matching_work_object_allowed(self):
        target = SimpleNamespace(work_object_id=5, internship_object_id=None)
        assert ScopedUserRepository.can_edit(target, {5, 6}) is True

    def test_matching_internship_object_allowed(self):
        target = SimpleNamespace(work_object_id=None, internship_object_id=6)
        assert ScopedUserRepository.can_edit(target, {5, 6}) is True

    def test_foreign_objects_denied(self):
        target = SimpleNamespace(work_object_id=9, internship_object_id=8)
        assert ScopedUserRepository.can_edit(target, {5, 6}) is False

    def test_null_objects_denied_when_scoped(self):
        target = SimpleNamespace(work_object_id=None, internship_object_id=None)
        assert ScopedUserRepository.can_edit(target, {5}) is False
