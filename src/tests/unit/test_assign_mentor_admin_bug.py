"""
Тесты для assign_mentor: воспроизведение и проверка фикса бага,
при котором назначение наставника падало для пользователя с ролью ADMIN.

Баг:
- Списки кандидатов в наставники/стажёры включают ADMIN (admin_inclusive_role_filter),
  но валидация ролей в assign_mentor не учитывала ADMIN:
    * наставник проверялся против ["Наставник", "Сотрудник", "Руководитель"]
    * стажёр проверялся строго на "Стажер"
  → при выборе пользователя с одной лишь ролью ADMIN функция возвращала None,
    и в боте показывалось «❌ Ошибка назначения наставника».

Фикс: ADMIN допускается как мульти-роль в обеих проверках.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def make_role(name: str) -> MagicMock:
    role = MagicMock()
    role.name = name
    return role


def make_user(user_id: int, full_name: str = "Тест", company_id: int = 1) -> MagicMock:
    user = MagicMock()
    user.id = user_id
    user.full_name = full_name
    user.company_id = company_id
    user.phone_number = "+70000000000"
    user.username = "test"
    return user


def make_scalar_result(value):
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    return result


def build_session(mentor, trainee, assigner, existing_mentorship=None):
    """session.execute последовательно отдаёт: наставник, стажёр, назначающий, существующее наставничество."""
    session = AsyncMock()
    session.add = MagicMock()
    session.execute.side_effect = [
        make_scalar_result(mentor),
        make_scalar_result(trainee),
        make_scalar_result(assigner),
        make_scalar_result(existing_mentorship),
    ]
    return session


def roles_side_effect(mentor_roles, trainee_roles, mentor_id, trainee_id):
    async def _get_user_roles(session, user_id):
        if user_id == mentor_id:
            return mentor_roles
        if user_id == trainee_id:
            return trainee_roles
        return []

    return _get_user_roles


class TestAssignMentorAdmin:
    @pytest.mark.asyncio
    async def test_admin_only_mentor_is_accepted(self):
        """Наставник с единственной ролью ADMIN должен успешно назначаться (регрессия)."""
        from bot.database.db import assign_mentor

        mentor = make_user(498, "Админ Наставник")
        trainee = make_user(499, "Стажёр")
        assigner = make_user(1, "Рекрутер")
        session = build_session(mentor, trainee, assigner)

        with patch(
            "bot.database.db.get_user_roles",
            side_effect=roles_side_effect([make_role("ADMIN")], [make_role("Стажер")], 498, 499),
        ):
            result = await assign_mentor(session, mentor_id=498, trainee_id=499, assigned_by_id=1, company_id=1)

        assert result is not None, "ADMIN-наставник должен приниматься"
        session.add.assert_called_once()
        session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_admin_only_trainee_is_accepted(self):
        """Стажёр с единственной ролью ADMIN должен успешно назначаться (регрессия)."""
        from bot.database.db import assign_mentor

        mentor = make_user(498, "Наставник")
        trainee = make_user(499, "Админ Стажёр")
        assigner = make_user(1, "Рекрутер")
        session = build_session(mentor, trainee, assigner)

        with patch(
            "bot.database.db.get_user_roles",
            side_effect=roles_side_effect([make_role("Наставник")], [make_role("ADMIN")], 498, 499),
        ):
            result = await assign_mentor(session, mentor_id=498, trainee_id=499, assigned_by_id=1, company_id=1)

        assert result is not None, "ADMIN-стажёр должен приниматься"
        session.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_unsuitable_mentor_role_still_rejected(self):
        """Пользователь без подходящей роли (только «Стажер») не может быть наставником."""
        from bot.database.db import assign_mentor

        mentor = make_user(498, "Стажёр-как-наставник")
        trainee = make_user(499, "Стажёр")
        assigner = make_user(1, "Рекрутер")
        session = build_session(mentor, trainee, assigner)

        with patch(
            "bot.database.db.get_user_roles",
            side_effect=roles_side_effect([make_role("Стажер")], [make_role("Стажер")], 498, 499),
        ):
            result = await assign_mentor(session, mentor_id=498, trainee_id=499, assigned_by_id=1, company_id=1)

        assert result is None, "Наставник с неподходящей ролью должен отклоняться"
        session.add.assert_not_called()
