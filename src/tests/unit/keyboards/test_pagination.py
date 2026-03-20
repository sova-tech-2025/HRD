"""Тесты для PaginatedKeyboard."""

import pytest
from types import SimpleNamespace
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.keyboards.pagination import PaginatedKeyboard


def _items(n: int) -> list:
    """Создаёт n элементов с атрибутами id и name."""
    return [SimpleNamespace(id=i, name=f"Item {i}") for i in range(1, n + 1)]


def _btn_texts(markup: InlineKeyboardMarkup) -> list[list[str]]:
    """Извлекает тексты кнопок из клавиатуры."""
    return [[btn.text for btn in row] for row in markup.inline_keyboard]


def _btn_callbacks(markup: InlineKeyboardMarkup) -> list[list[str | None]]:
    """Извлекает callback_data из клавиатуры."""
    return [[btn.callback_data for btn in row] for row in markup.inline_keyboard]


# ── Базовые тесты ──


class TestPaginatedKeyboardBasic:
    def test_empty_list(self):
        kb = PaginatedKeyboard([], page_callback="p").build()
        assert kb.inline_keyboard == []

    def test_single_page_no_nav(self):
        items = _items(3)
        kb = (
            PaginatedKeyboard(items, per_page=5, page_callback="p")
            .add_items(lambda x: (x.name, f"cb:{x.id}"))
            .build()
        )
        texts = _btn_texts(kb)
        assert texts == [["Item 1"], ["Item 2"], ["Item 3"]]

    def test_single_page_with_footer(self):
        items = _items(2)
        kb = (
            PaginatedKeyboard(items, per_page=5, page_callback="p")
            .add_items(lambda x: (x.name, f"cb:{x.id}"))
            .add_footer([[InlineKeyboardButton(text="Menu", callback_data="menu")]])
            .build()
        )
        texts = _btn_texts(kb)
        assert texts == [["Item 1"], ["Item 2"], ["Menu"]]


# ── Пагинация ──


class TestPaginatedKeyboardPagination:
    def test_first_page_has_forward_only(self):
        items = _items(8)
        kb = (
            PaginatedKeyboard(items, page=0, per_page=3, page_callback="pg")
            .add_items(lambda x: (x.name, f"cb:{x.id}"))
            .build()
        )
        texts = _btn_texts(kb)
        # 3 items + nav row
        assert len(texts) == 4
        assert texts[0:3] == [["Item 1"], ["Item 2"], ["Item 3"]]
        nav = texts[3]
        assert nav == ["1/3", "➡️"]

    def test_middle_page_has_both_arrows(self):
        items = _items(15)
        kb = (
            PaginatedKeyboard(items, page=1, per_page=5, page_callback="pg")
            .add_items(lambda x: (x.name, f"cb:{x.id}"))
            .build()
        )
        texts = _btn_texts(kb)
        assert texts[0:5] == [["Item 6"], ["Item 7"], ["Item 8"], ["Item 9"], ["Item 10"]]
        nav = texts[5]
        assert nav == ["⬅️", "2/3", "➡️"]

    def test_last_page_has_back_only(self):
        items = _items(8)
        kb = (
            PaginatedKeyboard(items, page=2, per_page=3, page_callback="pg")
            .add_items(lambda x: (x.name, f"cb:{x.id}"))
            .build()
        )
        texts = _btn_texts(kb)
        # Last page has 2 items + nav
        assert texts[0:2] == [["Item 7"], ["Item 8"]]
        nav = texts[2]
        assert nav == ["⬅️", "3/3"]

    def test_nav_callbacks(self):
        items = _items(15)
        kb = (
            PaginatedKeyboard(items, page=1, per_page=5, page_callback="my_prefix")
            .add_items(lambda x: (x.name, f"cb:{x.id}"))
            .build()
        )
        cbs = _btn_callbacks(kb)
        nav_cbs = cbs[5]
        assert nav_cbs == ["my_prefix:0", "noop", "my_prefix:2"]


# ── Граничные случаи ──


class TestPaginatedKeyboardEdgeCases:
    def test_page_clamped_below_zero(self):
        items = _items(3)
        pk = PaginatedKeyboard(items, page=-5, per_page=5, page_callback="p")
        assert pk.page == 0

    def test_page_clamped_above_max(self):
        items = _items(3)
        pk = PaginatedKeyboard(items, page=999, per_page=5, page_callback="p")
        assert pk.page == 0  # 3 items, per_page=5 → 1 page → max page is 0

    def test_page_items_property(self):
        items = _items(12)
        pk = PaginatedKeyboard(items, page=1, per_page=5, page_callback="p")
        page_items = pk.page_items
        assert len(page_items) == 5
        assert [x.id for x in page_items] == [6, 7, 8, 9, 10]

    def test_total_pages(self):
        assert PaginatedKeyboard(_items(0), per_page=5).total_pages == 1
        assert PaginatedKeyboard(_items(1), per_page=5).total_pages == 1
        assert PaginatedKeyboard(_items(5), per_page=5).total_pages == 1
        assert PaginatedKeyboard(_items(6), per_page=5).total_pages == 2
        assert PaginatedKeyboard(_items(11), per_page=5).total_pages == 3

    def test_exact_page_boundary(self):
        items = _items(10)
        kb = (
            PaginatedKeyboard(items, page=1, per_page=5, page_callback="pg")
            .add_items(lambda x: (x.name, f"cb:{x.id}"))
            .build()
        )
        texts = _btn_texts(kb)
        assert texts[0:5] == [["Item 6"], ["Item 7"], ["Item 8"], ["Item 9"], ["Item 10"]]
        nav = texts[5]
        assert nav == ["⬅️", "2/2"]


# ── Render function ──


class TestRenderFunction:
    def test_render_tuple(self):
        items = _items(2)
        kb = (
            PaginatedKeyboard(items, page_callback="p")
            .add_items(lambda x: (f"T:{x.name}", f"cb:{x.id}"))
            .build()
        )
        assert _btn_texts(kb) == [["T:Item 1"], ["T:Item 2"]]
        assert _btn_callbacks(kb) == [["cb:1"], ["cb:2"]]

    def test_render_single_button(self):
        items = _items(1)
        kb = (
            PaginatedKeyboard(items, page_callback="p")
            .add_items(lambda x: InlineKeyboardButton(text=x.name, callback_data=f"cb:{x.id}"))
            .build()
        )
        assert _btn_texts(kb) == [["Item 1"]]

    def test_render_button_list(self):
        items = _items(1)
        kb = (
            PaginatedKeyboard(items, page_callback="p")
            .add_items(lambda x: [
                InlineKeyboardButton(text=x.name, callback_data=f"a:{x.id}"),
                InlineKeyboardButton(text="X", callback_data=f"b:{x.id}"),
            ])
            .build()
        )
        assert _btn_texts(kb) == [["Item 1", "X"]]


# ── Footer ──


class TestFooter:
    def test_footer_after_nav(self):
        items = _items(8)
        kb = (
            PaginatedKeyboard(items, page=0, per_page=3, page_callback="pg")
            .add_items(lambda x: (x.name, f"cb:{x.id}"))
            .add_footer([
                [InlineKeyboardButton(text="Back", callback_data="back")],
                [InlineKeyboardButton(text="Menu", callback_data="menu")],
            ])
            .build()
        )
        texts = _btn_texts(kb)
        # 3 items + nav + 2 footer rows
        assert len(texts) == 6
        assert texts[4] == ["Back"]
        assert texts[5] == ["Menu"]

    def test_footer_no_nav(self):
        items = _items(2)
        kb = (
            PaginatedKeyboard(items, per_page=5, page_callback="p")
            .add_items(lambda x: (x.name, f"cb:{x.id}"))
            .add_footer([[InlineKeyboardButton(text="Menu", callback_data="menu")]])
            .build()
        )
        texts = _btn_texts(kb)
        assert texts == [["Item 1"], ["Item 2"], ["Menu"]]


# ── No items (nav-only keyboard) ──


class TestNoItems:
    def test_nav_only_keyboard(self):
        """Клавиатура с пагинацией, но без кнопок элементов (как get_test_results_keyboard)."""
        items = _items(12)
        kb = (
            PaginatedKeyboard(items, page=1, per_page=5, page_callback="scores_page")
            .add_footer([[InlineKeyboardButton(text="Menu", callback_data="menu")]])
            .build()
        )
        texts = _btn_texts(kb)
        # nav + footer only
        assert len(texts) == 2
        assert texts[0] == ["⬅️", "2/3", "➡️"]
        assert texts[1] == ["Menu"]

    def test_nav_only_single_page(self):
        items = _items(3)
        kb = (
            PaginatedKeyboard(items, per_page=5, page_callback="p")
            .add_footer([[InlineKeyboardButton(text="Menu", callback_data="menu")]])
            .build()
        )
        texts = _btn_texts(kb)
        assert texts == [["Menu"]]


# ── Compound page_callback ──


class TestCompoundCallback:
    def test_compound_page_callback(self):
        """page_callback с дополнительными данными (как tests_list_page:filter_type)."""
        items = _items(12)
        kb = (
            PaginatedKeyboard(items, page=0, per_page=5, page_callback="tests_list_page:all")
            .add_items(lambda x: (x.name, f"cb:{x.id}"))
            .build()
        )
        cbs = _btn_callbacks(kb)
        nav_cbs = cbs[5]
        assert nav_cbs == ["noop", "tests_list_page:all:1"]

    def test_compound_page_callback_last_page(self):
        items = _items(12)
        kb = (
            PaginatedKeyboard(items, page=2, per_page=5, page_callback="tests_list_page:my")
            .add_items(lambda x: (x.name, f"cb:{x.id}"))
            .build()
        )
        cbs = _btn_callbacks(kb)
        nav_cbs = cbs[2]  # 2 items on last page + nav
        assert nav_cbs == ["tests_list_page:my:1", "noop"]


# ── Chaining ──


class TestChaining:
    def test_method_chaining_returns_self(self):
        pk = PaginatedKeyboard(_items(3), page_callback="p")
        assert pk.add_items(lambda x: (x.name, f"cb:{x.id}")) is pk
        assert pk.add_footer([]) is pk
