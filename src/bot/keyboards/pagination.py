from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


class PaginatedKeyboard:
    """Единый класс для построения инлайн-клавиатур с пагинацией.

    Использование::

        kb = (
            PaginatedKeyboard(items, page=0, per_page=5, page_callback="trainees_page")
            .add_items(lambda t: (t.full_name, f"view_trainee:{t.id}"))
            .add_footer([[InlineKeyboardButton(text="≡ Главное меню", callback_data="main_menu")]])
            .build()
        )
    """

    def __init__(
        self,
        items: list,
        page: int = 0,
        per_page: int = 5,
        page_callback: str = "page",
    ) -> None:
        self.items = items
        self.per_page = per_page
        self.total_pages = max(1, (len(items) + per_page - 1) // per_page)
        self.page = max(0, min(page, self.total_pages - 1))
        self.page_callback = page_callback
        self._rows: list[list[InlineKeyboardButton]] = []
        self._footer: list[list[InlineKeyboardButton]] = []

    @property
    def page_items(self) -> list:
        start = self.page * self.per_page
        return self.items[start : start + self.per_page]

    def add_items(self, render_fn) -> PaginatedKeyboard:
        """Добавить элементы текущей страницы.

        ``render_fn(item)`` должна вернуть:
        - ``(text, callback_data)`` — будет создана одна кнопка в строке
        - ``list[InlineKeyboardButton]`` — строка кнопок как есть
        - ``InlineKeyboardButton`` — одна кнопка в строке
        """
        for item in self.page_items:
            result = render_fn(item)
            if isinstance(result, tuple):
                text, cb = result
                self._rows.append([InlineKeyboardButton(text=text, callback_data=cb)])
            elif isinstance(result, list):
                self._rows.append(result)
            else:
                self._rows.append([result])
        return self

    def add_footer(self, rows: list[list[InlineKeyboardButton]]) -> PaginatedKeyboard:
        """Добавить строки после навигации (кнопки «Назад», «Главное меню» и т.д.)."""
        self._footer = rows
        return self

    def _nav_row(self) -> list[InlineKeyboardButton] | None:
        if self.total_pages <= 1:
            return None
        nav: list[InlineKeyboardButton] = []
        if self.page > 0:
            nav.append(
                InlineKeyboardButton(
                    text="⬅️",
                    callback_data=f"{self.page_callback}:{self.page - 1}",
                )
            )
        nav.append(
            InlineKeyboardButton(
                text=f"{self.page + 1}/{self.total_pages}",
                callback_data="noop",
            )
        )
        if self.page < self.total_pages - 1:
            nav.append(
                InlineKeyboardButton(
                    text="➡️",
                    callback_data=f"{self.page_callback}:{self.page + 1}",
                )
            )
        return nav

    def build(self) -> InlineKeyboardMarkup:
        keyboard = list(self._rows)
        nav = self._nav_row()
        if nav:
            keyboard.append(nav)
        keyboard.extend(self._footer)
        return InlineKeyboardMarkup(inline_keyboard=keyboard)
