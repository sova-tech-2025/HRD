"""Универсальные клавиатуры фильтрации пользователей с пагинацией.

Используются в сценариях выбора пользователя (сдающий, экзаменатор,
редактирование пользователей). Фильтры: все / группы / объекты / роли /
поиск по ФИО. Все callback_data имеют общий префикс, переданный в конструктор,
поэтому один инстанс не конфликтует с другими.
"""

from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


class UserFilterKeyboards:
    """Генератор клавиатур фильтрации пользователей.

    Callback_data: ``{prefix}_all``, ``{prefix}_groups``, ``{prefix}_group:{id}``,
    ``{prefix}_roles``, ``{prefix}_role:{id}`` и т.д.
    """

    def __init__(
        self,
        prefix: str,
        emojis: dict | None = None,
        per_page: int = 5,
        show_role: bool = True,
        back_text: str = "↩️ Назад к фильтрам",
        main_menu_text: str = "≡ Главное меню",
    ) -> None:
        self.prefix = prefix
        self.emojis = emojis or {
            "all": "👥",
            "groups": "🗂️",
            "objects": "📍",
            "roles": "👑",
            "search": "🔍",
        }
        self.per_page = per_page
        self.show_role = show_role
        self.back_text = back_text
        self.main_menu_text = main_menu_text

    # ---------- callback_data helpers ----------

    @property
    def cb_all(self) -> str:
        return f"{self.prefix}_all"

    @property
    def cb_groups(self) -> str:
        return f"{self.prefix}_groups"

    @property
    def cb_objects(self) -> str:
        return f"{self.prefix}_objects"

    @property
    def cb_roles(self) -> str:
        return f"{self.prefix}_roles"

    @property
    def cb_search(self) -> str:
        return f"{self.prefix}_search"

    @property
    def cb_back(self) -> str:
        return f"{self.prefix}_back"

    def cb_group(self, id: int) -> str:
        return f"{self.prefix}_group:{id}"

    def cb_object(self, id: int) -> str:
        return f"{self.prefix}_object:{id}"

    def cb_role(self, id: int) -> str:
        return f"{self.prefix}_role:{id}"

    def cb_user(self, id: int) -> str:
        return f"{self.prefix}_user:{id}"

    def cb_upage(self, page: int) -> str:
        return f"{self.prefix}_upage:{page}"

    def cb_gpage(self, page: int) -> str:
        return f"{self.prefix}_gpage:{page}"

    def cb_opage(self, page: int) -> str:
        return f"{self.prefix}_opage:{page}"

    def cb_rpage(self, page: int) -> str:
        return f"{self.prefix}_rpage:{page}"

    # ---------- keyboards ----------

    def filter_menu(
        self,
        groups: list | None = None,
        objects: list | None = None,
        roles: list | None = None,
    ) -> InlineKeyboardMarkup:
        """Меню выбора типа фильтра. Кнопки групп/объектов/ролей появляются,
        только если соответствующий список не пуст."""
        keyboard: list[list[InlineKeyboardButton]] = [
            [
                InlineKeyboardButton(
                    text=f"{self.emojis['all']} Все пользователи",
                    callback_data=self.cb_all,
                )
            ],
        ]
        if groups:
            keyboard.append(
                [
                    InlineKeyboardButton(
                        text=f"{self.emojis['groups']} Фильтр по группам",
                        callback_data=self.cb_groups,
                    )
                ]
            )
        if objects:
            keyboard.append(
                [
                    InlineKeyboardButton(
                        text=f"{self.emojis['objects']} Фильтр по объектам",
                        callback_data=self.cb_objects,
                    )
                ]
            )
        if roles:
            keyboard.append(
                [
                    InlineKeyboardButton(
                        text=f"{self.emojis['roles']} Фильтр по ролям",
                        callback_data=self.cb_roles,
                    )
                ]
            )
        keyboard.append(
            [
                InlineKeyboardButton(
                    text=f"{self.emojis['search']} Поиск по ФИО",
                    callback_data=self.cb_search,
                )
            ]
        )
        keyboard.append([InlineKeyboardButton(text=self.main_menu_text, callback_data="main_menu")])
        return InlineKeyboardMarkup(inline_keyboard=keyboard)

    def _paginated_list(self, items, page, render_item, page_cb) -> InlineKeyboardMarkup:
        """Общий рендер пагинированного списка с кнопкой «назад»."""
        keyboard: list[list[InlineKeyboardButton]] = []
        total = len(items)
        start = page * self.per_page
        end = start + self.per_page

        for item in items[start:end]:
            keyboard.append([render_item(item)])

        nav: list[InlineKeyboardButton] = []
        if page > 0:
            nav.append(InlineKeyboardButton(text="⬅️", callback_data=page_cb(page - 1)))
        if end < total:
            nav.append(InlineKeyboardButton(text="➡️", callback_data=page_cb(page + 1)))
        if nav:
            keyboard.append(nav)

        keyboard.append([InlineKeyboardButton(text=self.back_text, callback_data=self.cb_back)])
        return InlineKeyboardMarkup(inline_keyboard=keyboard)

    def group_list(self, groups, page: int = 0) -> InlineKeyboardMarkup:
        return self._paginated_list(
            groups,
            page,
            lambda g: InlineKeyboardButton(text=f"🗂️ {g.name}", callback_data=self.cb_group(g.id)),
            self.cb_gpage,
        )

    def object_list(self, objects, page: int = 0) -> InlineKeyboardMarkup:
        return self._paginated_list(
            objects,
            page,
            lambda o: InlineKeyboardButton(text=f"📍 {o.name}", callback_data=self.cb_object(o.id)),
            self.cb_opage,
        )

    def role_list(self, roles, page: int = 0) -> InlineKeyboardMarkup:
        return self._paginated_list(
            roles,
            page,
            lambda r: InlineKeyboardButton(text=f"👑 {r.name}", callback_data=self.cb_role(r.id)),
            self.cb_rpage,
        )

    def user_list(self, users, page: int = 0) -> InlineKeyboardMarkup:
        def render(user):
            if self.show_role:
                role_name = user.roles[0].name if user.roles else "Без роли"
                text = f"👤 {user.full_name} ({role_name})"
            else:
                text = user.full_name
            return InlineKeyboardButton(text=text, callback_data=self.cb_user(user.id))

        return self._paginated_list(users, page, render, self.cb_upage)


# ---------- Предопределённые инстансы ----------

# Фильтры при выборе СДАЮЩЕГО для экзамена.
exam_filters = UserFilterKeyboards(
    prefix="ef",
    emojis={"all": "👥", "groups": "🟢", "objects": "🔴", "roles": "👑", "search": "🟣"},
    per_page=8,
    show_role=False,
    back_text="🔙 Назад",
)

# Фильтры при выборе ЭКЗАМЕНАТОРА для экзамена. show_role=True — полезно
# видеть, какую роль занимает кандидат на проведение.
examiner_filters = UserFilterKeyboards(
    prefix="exf",
    emojis={"all": "👥", "groups": "🟢", "objects": "🔴", "roles": "👑", "search": "🟣"},
    per_page=8,
    show_role=True,
    back_text="🔙 Назад",
)

# Фильтры при редактировании пользователей (раздел «Пользователи» рекрутера).
user_edit_filters = UserFilterKeyboards(
    prefix="uf",
    emojis={"all": "👥", "groups": "🗂️", "objects": "📍", "roles": "👑", "search": "🔍"},
    per_page=5,
    show_role=True,
    back_text="↩️ Назад к фильтрам",
)
