"""Тесты клавиатур поиска по Базе Знаний."""

from types import SimpleNamespace

from bot.keyboards.keyboards import (
    get_employee_knowledge_folders_keyboard,
    get_kb_search_material_view_keyboard,
    get_kb_search_no_results_keyboard,
    get_kb_search_prompt_keyboard,
    get_kb_search_results_keyboard,
    get_knowledge_base_main_keyboard,
    get_knowledge_folders_keyboard,
)


def _all_callbacks(markup) -> list[str]:
    return [btn.callback_data for row in markup.inline_keyboard for btn in row]


def _make_materials(count: int) -> list:
    folder = SimpleNamespace(name="Кухня")
    return [SimpleNamespace(id=i, name=f"Материал {i}", folder=folder) for i in range(1, count + 1)]


class TestSearchButtonInMenus:
    def test_kb_main_keyboard_has_search(self):
        kb = get_knowledge_base_main_keyboard()
        assert "kb_search" in _all_callbacks(kb)

    def test_kb_folders_keyboard_has_search(self):
        folders = [SimpleNamespace(id=1, name="Кухня")]
        kb = get_knowledge_folders_keyboard(folders)
        assert "kb_search" in _all_callbacks(kb)

    def test_employee_folders_keyboard_has_search(self):
        folders = [SimpleNamespace(id=1, name="Кухня", is_active=True)]
        kb = get_employee_knowledge_folders_keyboard(folders)
        assert "kb_search" in _all_callbacks(kb)


class TestSearchResultsKeyboard:
    def test_results_have_material_buttons_and_footer(self):
        kb = get_kb_search_results_keyboard(_make_materials(3), page=0)
        callbacks = _all_callbacks(kb)
        assert "kb_search_result:1" in callbacks
        assert "kb_search_result:3" in callbacks
        assert "kb_search_retry" in callbacks
        assert "kb_search_cancel" in callbacks
        assert "main_menu" in callbacks

    def test_results_button_text_contains_folder_name(self):
        kb = get_kb_search_results_keyboard(_make_materials(1), page=0)
        texts = [btn.text for row in kb.inline_keyboard for btn in row]
        assert any("Кухня" in text for text in texts)

    def test_results_long_names_truncated(self):
        folder = SimpleNamespace(name="Очень длинное название папки базы знаний")
        materials = [SimpleNamespace(id=1, name="Очень длинное название материала базы знаний", folder=folder)]
        kb = get_kb_search_results_keyboard(materials, page=0)
        button_text = kb.inline_keyboard[0][0].text
        assert button_text == "📄 Очень длинное название ма... (📁 Очень длинное назван...)"

    def test_results_paginated_after_five(self):
        kb = get_kb_search_results_keyboard(_make_materials(7), page=0)
        callbacks = _all_callbacks(kb)
        assert "kb_search_page:1" in callbacks
        assert "kb_search_result:6" not in callbacks


class TestSearchServiceKeyboards:
    def test_prompt_keyboard(self):
        callbacks = _all_callbacks(get_kb_search_prompt_keyboard())
        assert callbacks == ["kb_search_cancel", "main_menu"]

    def test_no_results_keyboard(self):
        callbacks = _all_callbacks(get_kb_search_no_results_keyboard())
        assert callbacks == ["kb_search_retry", "kb_search_cancel", "main_menu"]

    def test_material_view_keyboard(self):
        callbacks = _all_callbacks(get_kb_search_material_view_keyboard())
        assert callbacks == ["kb_search_back_to_results", "main_menu"]
