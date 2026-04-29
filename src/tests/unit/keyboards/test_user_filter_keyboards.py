"""Тесты для класса UserFilterKeyboards — унифицированные клавиатуры фильтрации пользователей."""

from dataclasses import dataclass, field


@dataclass
class MockRole:
    name: str
    id: int = 0


@dataclass
class MockGroup:
    id: int
    name: str


@dataclass
class MockObject:
    id: int
    name: str


@dataclass
class MockUser:
    id: int
    full_name: str
    roles: list = field(default_factory=list)


def make_groups(n: int) -> list[MockGroup]:
    return [MockGroup(id=i + 1, name=f"Группа {i + 1}") for i in range(n)]


def make_objects(n: int) -> list[MockObject]:
    return [MockObject(id=i + 1, name=f"Объект {i + 1}") for i in range(n)]


def make_roles(n: int) -> list[MockRole]:
    return [MockRole(id=i + 1, name=f"Роль {i + 1}") for i in range(n)]


def make_users(n: int, with_roles: bool = False) -> list[MockUser]:
    roles = [MockRole(name="Стажёр")] if with_roles else []
    return [MockUser(id=i + 1, full_name=f"Иванов {i + 1}", roles=list(roles)) for i in range(n)]


def _all_buttons(keyboard):
    """Все кнопки из клавиатуры плоским списком."""
    return [btn for row in keyboard.inline_keyboard for btn in row]


def _all_callbacks(keyboard):
    """Все callback_data из клавиатуры."""
    return [btn.callback_data for btn in _all_buttons(keyboard)]


# ===================== Callback data helpers =====================


class TestCallbackDataProperties:
    """Тесты для свойств и методов генерации callback_data."""

    def test_cb_all_uses_prefix(self):
        from bot.keyboards.user_filters import UserFilterKeyboards

        kb = UserFilterKeyboards(prefix="ef")
        assert kb.cb_all == "ef_all"

    def test_cb_groups_uses_prefix(self):
        from bot.keyboards.user_filters import UserFilterKeyboards

        kb = UserFilterKeyboards(prefix="uf")
        assert kb.cb_groups == "uf_groups"

    def test_cb_objects_uses_prefix(self):
        from bot.keyboards.user_filters import UserFilterKeyboards

        kb = UserFilterKeyboards(prefix="ef")
        assert kb.cb_objects == "ef_objects"

    def test_cb_search_uses_prefix(self):
        from bot.keyboards.user_filters import UserFilterKeyboards

        kb = UserFilterKeyboards(prefix="uf")
        assert kb.cb_search == "uf_search"

    def test_cb_back_uses_prefix(self):
        from bot.keyboards.user_filters import UserFilterKeyboards

        kb = UserFilterKeyboards(prefix="ef")
        assert kb.cb_back == "ef_back"

    def test_cb_group_with_id(self):
        from bot.keyboards.user_filters import UserFilterKeyboards

        kb = UserFilterKeyboards(prefix="ef")
        assert kb.cb_group(42) == "ef_group:42"

    def test_cb_object_with_id(self):
        from bot.keyboards.user_filters import UserFilterKeyboards

        kb = UserFilterKeyboards(prefix="uf")
        assert kb.cb_object(7) == "uf_object:7"

    def test_cb_user_with_id(self):
        from bot.keyboards.user_filters import UserFilterKeyboards

        kb = UserFilterKeyboards(prefix="ef")
        assert kb.cb_user(99) == "ef_user:99"

    def test_cb_upage(self):
        from bot.keyboards.user_filters import UserFilterKeyboards

        kb = UserFilterKeyboards(prefix="uf")
        assert kb.cb_upage(3) == "uf_upage:3"

    def test_cb_gpage(self):
        from bot.keyboards.user_filters import UserFilterKeyboards

        kb = UserFilterKeyboards(prefix="ef")
        assert kb.cb_gpage(1) == "ef_gpage:1"

    def test_cb_opage(self):
        from bot.keyboards.user_filters import UserFilterKeyboards

        kb = UserFilterKeyboards(prefix="uf")
        assert kb.cb_opage(0) == "uf_opage:0"


# ===================== filter_menu =====================


class TestFilterMenu:
    """Тесты для метода filter_menu — меню фильтров."""

    def test_always_has_all_button(self):
        from bot.keyboards.user_filters import UserFilterKeyboards

        kb = UserFilterKeyboards(prefix="ef")
        keyboard = kb.filter_menu([], [])
        callbacks = _all_callbacks(keyboard)
        assert "ef_all" in callbacks

    def test_always_has_search_button(self):
        from bot.keyboards.user_filters import UserFilterKeyboards

        kb = UserFilterKeyboards(prefix="uf")
        keyboard = kb.filter_menu([], [])
        callbacks = _all_callbacks(keyboard)
        assert "uf_search" in callbacks

    def test_always_has_main_menu_button(self):
        from bot.keyboards.user_filters import UserFilterKeyboards

        kb = UserFilterKeyboards(prefix="ef")
        keyboard = kb.filter_menu([], [])
        callbacks = _all_callbacks(keyboard)
        assert "main_menu" in callbacks

    def test_groups_button_shown_when_groups_exist(self):
        from bot.keyboards.user_filters import UserFilterKeyboards

        kb = UserFilterKeyboards(prefix="ef")
        groups = make_groups(2)
        keyboard = kb.filter_menu(groups, [])
        callbacks = _all_callbacks(keyboard)
        assert "ef_groups" in callbacks

    def test_groups_button_hidden_when_no_groups(self):
        from bot.keyboards.user_filters import UserFilterKeyboards

        kb = UserFilterKeyboards(prefix="ef")
        keyboard = kb.filter_menu([], make_objects(1))
        callbacks = _all_callbacks(keyboard)
        assert "ef_groups" not in callbacks

    def test_objects_button_shown_when_objects_exist(self):
        from bot.keyboards.user_filters import UserFilterKeyboards

        kb = UserFilterKeyboards(prefix="uf")
        objects = make_objects(3)
        keyboard = kb.filter_menu([], objects)
        callbacks = _all_callbacks(keyboard)
        assert "uf_objects" in callbacks

    def test_objects_button_hidden_when_no_objects(self):
        from bot.keyboards.user_filters import UserFilterKeyboards

        kb = UserFilterKeyboards(prefix="uf")
        keyboard = kb.filter_menu(make_groups(1), [])
        callbacks = _all_callbacks(keyboard)
        assert "uf_objects" not in callbacks

    def test_emojis_used_in_button_text(self):
        from bot.keyboards.user_filters import UserFilterKeyboards

        emojis = {"all": "👥", "groups": "🟢", "objects": "🔴", "search": "🟣"}
        kb = UserFilterKeyboards(prefix="ef", emojis=emojis)
        keyboard = kb.filter_menu(make_groups(1), make_objects(1))
        buttons = _all_buttons(keyboard)
        texts = [b.text for b in buttons]
        # Кнопка "Все" должна содержать эмодзи "👥"
        all_btn = next(b for b in buttons if b.callback_data == "ef_all")
        assert "👥" in all_btn.text
        # Кнопка "По группам" — "🟢"
        groups_btn = next(b for b in buttons if b.callback_data == "ef_groups")
        assert "🟢" in groups_btn.text
        # Кнопка "По объектам" — "🔴"
        objects_btn = next(b for b in buttons if b.callback_data == "ef_objects")
        assert "🔴" in objects_btn.text
        # Кнопка "Поиск" — "🟣"
        search_btn = next(b for b in buttons if b.callback_data == "ef_search")
        assert "🟣" in search_btn.text

    def test_default_emojis(self):
        from bot.keyboards.user_filters import UserFilterKeyboards

        kb = UserFilterKeyboards(prefix="uf")
        keyboard = kb.filter_menu(make_groups(1), make_objects(1))
        buttons = _all_buttons(keyboard)
        groups_btn = next(b for b in buttons if b.callback_data == "uf_groups")
        assert "🗂️" in groups_btn.text
        objects_btn = next(b for b in buttons if b.callback_data == "uf_objects")
        assert "📍" in objects_btn.text
        search_btn = next(b for b in buttons if b.callback_data == "uf_search")
        assert "🔍" in search_btn.text


# ===================== group_list =====================


class TestGroupList:
    """Тесты для метода group_list — список групп с пагинацией."""

    def test_shows_groups_with_correct_callbacks(self):
        from bot.keyboards.user_filters import UserFilterKeyboards

        kb = UserFilterKeyboards(prefix="ef")
        groups = make_groups(3)
        keyboard = kb.group_list(groups)
        callbacks = _all_callbacks(keyboard)
        assert "ef_group:1" in callbacks
        assert "ef_group:2" in callbacks
        assert "ef_group:3" in callbacks

    def test_back_button_uses_cb_back(self):
        from bot.keyboards.user_filters import UserFilterKeyboards

        kb = UserFilterKeyboards(prefix="uf", back_text="↩️ Назад к фильтрам")
        keyboard = kb.group_list(make_groups(1))
        last_row = keyboard.inline_keyboard[-1]
        assert last_row[0].callback_data == "uf_back"
        assert last_row[0].text == "↩️ Назад к фильтрам"

    def test_no_nav_on_single_page(self):
        from bot.keyboards.user_filters import UserFilterKeyboards

        kb = UserFilterKeyboards(prefix="ef", per_page=5)
        keyboard = kb.group_list(make_groups(3))
        callbacks = _all_callbacks(keyboard)
        assert not any(c.startswith("ef_gpage:") for c in callbacks)

    def test_forward_nav_on_first_page(self):
        from bot.keyboards.user_filters import UserFilterKeyboards

        kb = UserFilterKeyboards(prefix="uf", per_page=2)
        keyboard = kb.group_list(make_groups(5), page=0)
        callbacks = _all_callbacks(keyboard)
        assert "uf_gpage:1" in callbacks
        assert not any(c == "uf_gpage:-1" for c in callbacks)

    def test_backward_nav_on_second_page(self):
        from bot.keyboards.user_filters import UserFilterKeyboards

        kb = UserFilterKeyboards(prefix="uf", per_page=2)
        keyboard = kb.group_list(make_groups(5), page=1)
        callbacks = _all_callbacks(keyboard)
        assert "uf_gpage:0" in callbacks
        assert "uf_gpage:2" in callbacks

    def test_no_forward_on_last_page(self):
        from bot.keyboards.user_filters import UserFilterKeyboards

        kb = UserFilterKeyboards(prefix="ef", per_page=2)
        keyboard = kb.group_list(make_groups(4), page=1)
        callbacks = _all_callbacks(keyboard)
        assert "ef_gpage:0" in callbacks
        assert "ef_gpage:2" not in callbacks

    def test_pagination_slices_correctly(self):
        from bot.keyboards.user_filters import UserFilterKeyboards

        kb = UserFilterKeyboards(prefix="ef", per_page=2)
        groups = make_groups(5)
        keyboard = kb.group_list(groups, page=1)
        # Страница 1: группы 3, 4 (индексы 2, 3)
        group_callbacks = [c for c in _all_callbacks(keyboard) if c.startswith("ef_group:")]
        assert group_callbacks == ["ef_group:3", "ef_group:4"]

    def test_group_button_text_has_emoji(self):
        from bot.keyboards.user_filters import UserFilterKeyboards

        kb = UserFilterKeyboards(prefix="ef")
        groups = [MockGroup(id=1, name="Кухня")]
        keyboard = kb.group_list(groups)
        btn = keyboard.inline_keyboard[0][0]
        assert "🗂️" in btn.text
        assert "Кухня" in btn.text


# ===================== object_list =====================


class TestObjectList:
    """Тесты для метода object_list — список объектов с пагинацией."""

    def test_shows_objects_with_correct_callbacks(self):
        from bot.keyboards.user_filters import UserFilterKeyboards

        kb = UserFilterKeyboards(prefix="uf")
        objects = make_objects(2)
        keyboard = kb.object_list(objects)
        callbacks = _all_callbacks(keyboard)
        assert "uf_object:1" in callbacks
        assert "uf_object:2" in callbacks

    def test_back_button(self):
        from bot.keyboards.user_filters import UserFilterKeyboards

        kb = UserFilterKeyboards(prefix="ef", back_text="🔙 Назад")
        keyboard = kb.object_list(make_objects(1))
        last_row = keyboard.inline_keyboard[-1]
        assert last_row[0].callback_data == "ef_back"
        assert last_row[0].text == "🔙 Назад"

    def test_pagination_callbacks(self):
        from bot.keyboards.user_filters import UserFilterKeyboards

        kb = UserFilterKeyboards(prefix="uf", per_page=2)
        keyboard = kb.object_list(make_objects(5), page=0)
        callbacks = _all_callbacks(keyboard)
        assert "uf_opage:1" in callbacks

    def test_no_nav_on_single_page(self):
        from bot.keyboards.user_filters import UserFilterKeyboards

        kb = UserFilterKeyboards(prefix="ef", per_page=10)
        keyboard = kb.object_list(make_objects(3))
        callbacks = _all_callbacks(keyboard)
        assert not any(c.startswith("ef_opage:") for c in callbacks)

    def test_object_button_text_has_emoji(self):
        from bot.keyboards.user_filters import UserFilterKeyboards

        kb = UserFilterKeyboards(prefix="uf")
        objects = [MockObject(id=1, name="Кафе Пушкин")]
        keyboard = kb.object_list(objects)
        btn = keyboard.inline_keyboard[0][0]
        assert "📍" in btn.text
        assert "Кафе Пушкин" in btn.text

    def test_pagination_slices_correctly(self):
        from bot.keyboards.user_filters import UserFilterKeyboards

        kb = UserFilterKeyboards(prefix="uf", per_page=3)
        objects = make_objects(7)
        keyboard = kb.object_list(objects, page=2)
        # Страница 2: объект 7 (индекс 6)
        obj_callbacks = [c for c in _all_callbacks(keyboard) if c.startswith("uf_object:")]
        assert obj_callbacks == ["uf_object:7"]


# ===================== user_list =====================


class TestUserList:
    """Тесты для метода user_list — список пользователей с пагинацией."""

    def test_shows_users_with_correct_callbacks(self):
        from bot.keyboards.user_filters import UserFilterKeyboards

        kb = UserFilterKeyboards(prefix="ef")
        users = make_users(3)
        keyboard = kb.user_list(users)
        callbacks = _all_callbacks(keyboard)
        assert "ef_user:1" in callbacks
        assert "ef_user:2" in callbacks
        assert "ef_user:3" in callbacks

    def test_show_role_true_includes_role(self):
        from bot.keyboards.user_filters import UserFilterKeyboards

        kb = UserFilterKeyboards(prefix="uf", show_role=True)
        users = [MockUser(id=1, full_name="Иванов", roles=[MockRole(name="Стажёр")])]
        keyboard = kb.user_list(users)
        btn = keyboard.inline_keyboard[0][0]
        assert "Стажёр" in btn.text
        assert "Иванов" in btn.text

    def test_show_role_false_no_role(self):
        from bot.keyboards.user_filters import UserFilterKeyboards

        kb = UserFilterKeyboards(prefix="ef", show_role=False)
        users = [MockUser(id=1, full_name="Иванов", roles=[MockRole(name="Стажёр")])]
        keyboard = kb.user_list(users)
        btn = keyboard.inline_keyboard[0][0]
        assert "Стажёр" not in btn.text
        assert "Иванов" in btn.text

    def test_show_role_true_no_roles(self):
        """Если show_role=True, но у пользователя нет ролей — показываем 'Без роли'."""
        from bot.keyboards.user_filters import UserFilterKeyboards

        kb = UserFilterKeyboards(prefix="uf", show_role=True)
        users = [MockUser(id=1, full_name="Петров", roles=[])]
        keyboard = kb.user_list(users)
        btn = keyboard.inline_keyboard[0][0]
        assert "Без роли" in btn.text

    def test_back_button(self):
        from bot.keyboards.user_filters import UserFilterKeyboards

        kb = UserFilterKeyboards(prefix="ef", back_text="🔙 Назад")
        keyboard = kb.user_list(make_users(1))
        last_row = keyboard.inline_keyboard[-1]
        assert last_row[0].callback_data == "ef_back"

    def test_pagination_forward(self):
        from bot.keyboards.user_filters import UserFilterKeyboards

        kb = UserFilterKeyboards(prefix="uf", per_page=3)
        keyboard = kb.user_list(make_users(7), page=0)
        callbacks = _all_callbacks(keyboard)
        assert "uf_upage:1" in callbacks

    def test_pagination_backward(self):
        from bot.keyboards.user_filters import UserFilterKeyboards

        kb = UserFilterKeyboards(prefix="uf", per_page=3)
        keyboard = kb.user_list(make_users(7), page=1)
        callbacks = _all_callbacks(keyboard)
        assert "uf_upage:0" in callbacks
        assert "uf_upage:2" in callbacks

    def test_no_nav_on_single_page(self):
        from bot.keyboards.user_filters import UserFilterKeyboards

        kb = UserFilterKeyboards(prefix="ef", per_page=10)
        keyboard = kb.user_list(make_users(5))
        callbacks = _all_callbacks(keyboard)
        assert not any(c.startswith("ef_upage:") for c in callbacks)

    def test_pagination_slices_correctly(self):
        from bot.keyboards.user_filters import UserFilterKeyboards

        kb = UserFilterKeyboards(prefix="ef", per_page=2)
        users = make_users(5)
        keyboard = kb.user_list(users, page=2)
        # Страница 2: пользователь 5 (индекс 4)
        user_callbacks = [c for c in _all_callbacks(keyboard) if c.startswith("ef_user:")]
        assert user_callbacks == ["ef_user:5"]

    def test_per_page_respected(self):
        from bot.keyboards.user_filters import UserFilterKeyboards

        kb = UserFilterKeyboards(prefix="ef", per_page=2)
        keyboard = kb.user_list(make_users(10), page=0)
        user_callbacks = [c for c in _all_callbacks(keyboard) if c.startswith("ef_user:")]
        assert len(user_callbacks) == 2


# ===================== Два инстанса =====================


class TestExamFiltersInstance:
    """Тесты для инстанса exam_filters."""

    def test_prefix_is_ef(self):
        from bot.keyboards.user_filters import exam_filters

        assert exam_filters.prefix == "ef"

    def test_per_page_is_8(self):
        from bot.keyboards.user_filters import exam_filters

        assert exam_filters.per_page == 8

    def test_show_role_is_false(self):
        from bot.keyboards.user_filters import exam_filters

        assert exam_filters.show_role is False

    def test_emojis_custom(self):
        from bot.keyboards.user_filters import exam_filters

        assert exam_filters.emojis["groups"] == "🟢"
        assert exam_filters.emojis["objects"] == "🔴"
        assert exam_filters.emojis["search"] == "🟣"

    def test_back_text(self):
        from bot.keyboards.user_filters import exam_filters

        assert exam_filters.back_text == "🔙 Назад"

    def test_filter_menu_callbacks(self):
        from bot.keyboards.user_filters import exam_filters

        keyboard = exam_filters.filter_menu(make_groups(1), make_objects(1))
        callbacks = _all_callbacks(keyboard)
        assert "ef_all" in callbacks
        assert "ef_groups" in callbacks
        assert "ef_objects" in callbacks
        assert "ef_search" in callbacks

    def test_user_list_no_role_in_text(self):
        from bot.keyboards.user_filters import exam_filters

        users = [MockUser(id=1, full_name="Иванов", roles=[MockRole(name="Стажёр")])]
        keyboard = exam_filters.user_list(users)
        btn = keyboard.inline_keyboard[0][0]
        assert "Стажёр" not in btn.text


class TestUserEditFiltersInstance:
    """Тесты для инстанса user_edit_filters."""

    def test_prefix_is_uf(self):
        from bot.keyboards.user_filters import user_edit_filters

        assert user_edit_filters.prefix == "uf"

    def test_per_page_is_5(self):
        from bot.keyboards.user_filters import user_edit_filters

        assert user_edit_filters.per_page == 5

    def test_show_role_is_true(self):
        from bot.keyboards.user_filters import user_edit_filters

        assert user_edit_filters.show_role is True

    def test_emojis_default_style(self):
        from bot.keyboards.user_filters import user_edit_filters

        assert user_edit_filters.emojis["groups"] == "🗂️"
        assert user_edit_filters.emojis["objects"] == "📍"
        assert user_edit_filters.emojis["search"] == "🔍"

    def test_back_text(self):
        from bot.keyboards.user_filters import user_edit_filters

        assert user_edit_filters.back_text == "↩️ Назад к фильтрам"

    def test_filter_menu_callbacks(self):
        from bot.keyboards.user_filters import user_edit_filters

        keyboard = user_edit_filters.filter_menu(make_groups(1), make_objects(1))
        callbacks = _all_callbacks(keyboard)
        assert "uf_all" in callbacks
        assert "uf_groups" in callbacks
        assert "uf_objects" in callbacks
        assert "uf_search" in callbacks

    def test_user_list_shows_role(self):
        from bot.keyboards.user_filters import user_edit_filters

        users = [MockUser(id=1, full_name="Иванов", roles=[MockRole(name="Стажёр")])]
        keyboard = user_edit_filters.user_list(users)
        btn = keyboard.inline_keyboard[0][0]
        assert "Стажёр" in btn.text


# ===================== Различия между инстансами =====================


class TestInstancesProduceDifferentCallbacks:
    """Проверяем, что два инстанса генерируют разные callback_data."""

    def test_filter_menu_callbacks_differ(self):
        from bot.keyboards.user_filters import exam_filters, user_edit_filters

        groups = make_groups(1)
        objects = make_objects(1)
        ef_callbacks = set(_all_callbacks(exam_filters.filter_menu(groups, objects)))
        uf_callbacks = set(_all_callbacks(user_edit_filters.filter_menu(groups, objects)))
        # Общий — только main_menu
        common = ef_callbacks & uf_callbacks
        assert common == {"main_menu"}

    def test_user_list_callbacks_differ(self):
        from bot.keyboards.user_filters import exam_filters, user_edit_filters

        users = make_users(3)
        ef_callbacks = set(_all_callbacks(exam_filters.user_list(users)))
        uf_callbacks = set(_all_callbacks(user_edit_filters.user_list(users)))
        assert ef_callbacks.isdisjoint(uf_callbacks)

    def test_group_list_callbacks_differ(self):
        from bot.keyboards.user_filters import exam_filters, user_edit_filters

        groups = make_groups(2)
        ef_callbacks = set(_all_callbacks(exam_filters.group_list(groups)))
        uf_callbacks = set(_all_callbacks(user_edit_filters.group_list(groups)))
        assert ef_callbacks.isdisjoint(uf_callbacks)


# ===================== Фильтр по ролям =====================


class TestRoleFilter:
    """Тесты для фильтра «По ролям» — новая опция (ТЗ от ПМ)."""

    def test_cb_roles_uses_prefix(self):
        from bot.keyboards.user_filters import UserFilterKeyboards

        kb = UserFilterKeyboards(prefix="exf")
        assert kb.cb_roles == "exf_roles"

    def test_cb_role_with_id(self):
        from bot.keyboards.user_filters import UserFilterKeyboards

        kb = UserFilterKeyboards(prefix="ef")
        assert kb.cb_role(7) == "ef_role:7"

    def test_cb_rpage(self):
        from bot.keyboards.user_filters import UserFilterKeyboards

        kb = UserFilterKeyboards(prefix="exf")
        assert kb.cb_rpage(2) == "exf_rpage:2"

    def test_roles_button_shown_when_roles_exist(self):
        from bot.keyboards.user_filters import UserFilterKeyboards

        kb = UserFilterKeyboards(prefix="ef")
        keyboard = kb.filter_menu(groups=[], objects=[], roles=make_roles(2))
        callbacks = _all_callbacks(keyboard)
        assert "ef_roles" in callbacks

    def test_roles_button_hidden_when_no_roles(self):
        from bot.keyboards.user_filters import UserFilterKeyboards

        kb = UserFilterKeyboards(prefix="ef")
        keyboard = kb.filter_menu(groups=make_groups(1), objects=[], roles=None)
        callbacks = _all_callbacks(keyboard)
        assert "ef_roles" not in callbacks

    def test_role_list_callbacks(self):
        from bot.keyboards.user_filters import UserFilterKeyboards

        kb = UserFilterKeyboards(prefix="exf")
        keyboard = kb.role_list(make_roles(3))
        callbacks = _all_callbacks(keyboard)
        assert "exf_role:1" in callbacks
        assert "exf_role:2" in callbacks
        assert "exf_role:3" in callbacks

    def test_role_list_back_button(self):
        from bot.keyboards.user_filters import UserFilterKeyboards

        kb = UserFilterKeyboards(prefix="exf", back_text="🔙 Назад")
        keyboard = kb.role_list(make_roles(1))
        last_row = keyboard.inline_keyboard[-1]
        assert last_row[0].callback_data == "exf_back"

    def test_role_list_pagination(self):
        from bot.keyboards.user_filters import UserFilterKeyboards

        kb = UserFilterKeyboards(prefix="ef", per_page=2)
        keyboard = kb.role_list(make_roles(5), page=1)
        callbacks = _all_callbacks(keyboard)
        assert "ef_rpage:0" in callbacks
        assert "ef_rpage:2" in callbacks
        role_cbs = [c for c in callbacks if c.startswith("ef_role:")]
        assert role_cbs == ["ef_role:3", "ef_role:4"]

    def test_role_button_has_emoji(self):
        from bot.keyboards.user_filters import UserFilterKeyboards

        kb = UserFilterKeyboards(prefix="ef")
        keyboard = kb.role_list([MockRole(id=1, name="Руководитель")])
        btn = keyboard.inline_keyboard[0][0]
        assert "👑" in btn.text
        assert "Руководитель" in btn.text


class TestExaminerFiltersInstance:
    """Тесты для инстанса examiner_filters — выбор экзаменатора с фильтрами."""

    def test_prefix_is_exf(self):
        from bot.keyboards.user_filters import examiner_filters

        assert examiner_filters.prefix == "exf"

    def test_per_page_is_8(self):
        from bot.keyboards.user_filters import examiner_filters

        assert examiner_filters.per_page == 8

    def test_show_role_is_true(self):
        from bot.keyboards.user_filters import examiner_filters

        assert examiner_filters.show_role is True

    def test_filter_menu_has_roles_button_when_roles_given(self):
        from bot.keyboards.user_filters import examiner_filters

        keyboard = examiner_filters.filter_menu(groups=make_groups(1), objects=make_objects(1), roles=make_roles(2))
        callbacks = _all_callbacks(keyboard)
        assert "exf_all" in callbacks
        assert "exf_groups" in callbacks
        assert "exf_objects" in callbacks
        assert "exf_roles" in callbacks
        assert "exf_search" in callbacks

    def test_user_list_shows_role(self):
        from bot.keyboards.user_filters import examiner_filters

        users = [MockUser(id=1, full_name="Петров", roles=[MockRole(name="Руководитель")])]
        keyboard = examiner_filters.user_list(users)
        btn = keyboard.inline_keyboard[0][0]
        assert "Руководитель" in btn.text
        assert "Петров" in btn.text

    def test_examiner_and_exam_callbacks_disjoint(self):
        from bot.keyboards.user_filters import exam_filters, examiner_filters

        users = make_users(3)
        exf_cbs = set(_all_callbacks(examiner_filters.user_list(users)))
        ef_cbs = set(_all_callbacks(exam_filters.user_list(users)))
        assert exf_cbs.isdisjoint(ef_cbs)
