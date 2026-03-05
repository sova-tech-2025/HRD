"""Тесты для функций формирования сообщений в handlers/core/common.py"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime


class FakeRole:
    def __init__(self, name):
        self.name = name


class FakeGroup:
    def __init__(self, name):
        self.name = name


class FakeObject:
    def __init__(self, name):
        self.name = name


def make_user(
    full_name="Иванов Иван",
    phone_number="+79001234567",
    username="ivanov",
    user_id=1,
    registration_date=None,
    groups=None,
    internship_object=None,
    work_object=None,
):
    user = MagicMock()
    user.id = user_id
    user.full_name = full_name
    user.phone_number = phone_number
    user.username = username
    user.registration_date = registration_date or datetime(2025, 6, 15, 10, 30)
    user.groups = groups or []
    user.internship_object = internship_object
    user.work_object = work_object
    return user


class TestFormatProfileText:
    """Тесты для format_profile_text"""

    @pytest.mark.asyncio
    async def test_basic_profile_fields(self):
        """Профиль содержит ФИО, телефон, username, номер, дату"""
        from utils.messages.common import format_profile_text

        user = make_user()
        session = AsyncMock()

        with patch("utils.messages.common.get_user_roles", return_value=[FakeRole("Сотрудник")]):
            result = await format_profile_text(user, session)

        assert "Иванов Иван" in result
        assert "+79001234567" in result
        assert "@ivanov" in result
        assert "#1" in result
        assert "15.06.2025 10:30" in result

    @pytest.mark.asyncio
    async def test_username_not_set(self):
        """Если username отсутствует — показывает 'Не указан'"""
        from utils.messages.common import format_profile_text

        user = make_user(username=None)
        session = AsyncMock()

        with patch("utils.messages.common.get_user_roles", return_value=[FakeRole("Сотрудник")]):
            result = await format_profile_text(user, session)

        assert "Не указан" in result

    @pytest.mark.asyncio
    async def test_groups_displayed(self):
        """Группы пользователя отображаются через запятую"""
        from utils.messages.common import format_profile_text

        groups = [FakeGroup("Кухня"), FakeGroup("Бар")]
        user = make_user(groups=groups)
        session = AsyncMock()

        with patch("utils.messages.common.get_user_roles", return_value=[FakeRole("Сотрудник")]):
            result = await format_profile_text(user, session)

        assert "Кухня, Бар" in result
        assert "Группы" in result

    @pytest.mark.asyncio
    async def test_single_group_label(self):
        """Одна группа — подпись 'Группа' в единственном числе"""
        from utils.messages.common import format_profile_text

        user = make_user(groups=[FakeGroup("Кухня")])
        session = AsyncMock()

        with patch("utils.messages.common.get_user_roles", return_value=[FakeRole("Сотрудник")]):
            result = await format_profile_text(user, session)

        assert "Группа:" in result

    @pytest.mark.asyncio
    async def test_no_groups(self):
        """Нет групп — 'Не указана'"""
        from utils.messages.common import format_profile_text

        user = make_user(groups=[])
        session = AsyncMock()

        with patch("utils.messages.common.get_user_roles", return_value=[FakeRole("Сотрудник")]):
            result = await format_profile_text(user, session)

        assert "Не указана" in result

    @pytest.mark.asyncio
    async def test_trainee_shows_internship_object(self):
        """Стажёр видит объект стажировки и работы"""
        from utils.messages.common import format_profile_text

        user = make_user(
            internship_object=FakeObject("Кафе Центральное"),
            work_object=FakeObject("Ресторан Южный"),
        )
        session = AsyncMock()

        with patch("utils.messages.common.get_user_roles", return_value=[FakeRole("Стажер")]):
            result = await format_profile_text(user, session)

        assert "Стажировки:" in result
        assert "Кафе Центральное" in result
        assert "Ресторан Южный" in result

    @pytest.mark.asyncio
    async def test_non_trainee_no_internship_field(self):
        """Не-стажёр не видит поле 'Стажировки'"""
        from utils.messages.common import format_profile_text

        user = make_user(
            internship_object=FakeObject("Кафе"),
            work_object=FakeObject("Ресторан"),
        )
        session = AsyncMock()

        with patch("utils.messages.common.get_user_roles", return_value=[FakeRole("Сотрудник")]):
            result = await format_profile_text(user, session)

        assert "Стажировки:" not in result
        assert "Работы:" in result

    @pytest.mark.asyncio
    async def test_no_objects_shows_defaults(self):
        """Без объектов — 'Не указан'"""
        from utils.messages.common import format_profile_text

        user = make_user(internship_object=None, work_object=None)
        session = AsyncMock()

        with patch("utils.messages.common.get_user_roles", return_value=[FakeRole("Стажер")]):
            result = await format_profile_text(user, session)

        assert "Не указан" in result

    @pytest.mark.asyncio
    async def test_role_displayed(self):
        """Роль пользователя отображается"""
        from utils.messages.common import format_profile_text

        user = make_user()
        session = AsyncMock()

        with patch("utils.messages.common.get_user_roles", return_value=[FakeRole("Наставник")]):
            result = await format_profile_text(user, session)

        assert "Наставник" in result

    @pytest.mark.asyncio
    async def test_multiple_roles_primary_displayed(self):
        """При нескольких ролях отображается приоритетная"""
        from utils.messages.common import format_profile_text

        user = make_user()
        session = AsyncMock()

        roles = [FakeRole("Стажер"), FakeRole("Наставник")]
        with patch("utils.messages.common.get_user_roles", return_value=roles):
            result = await format_profile_text(user, session)

        # Наставник имеет приоритет 3 > Стажер 1
        assert "Наставник" in result

    @pytest.mark.asyncio
    async def test_result_is_html(self):
        """Результат содержит HTML-теги"""
        from utils.messages.common import format_profile_text

        user = make_user()
        session = AsyncMock()

        with patch("utils.messages.common.get_user_roles", return_value=[FakeRole("Сотрудник")]):
            result = await format_profile_text(user, session)

        assert "<b>" in result
