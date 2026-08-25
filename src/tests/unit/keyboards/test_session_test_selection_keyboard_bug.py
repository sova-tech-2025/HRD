"""Регрессия: «➕ Добавить тест» падал с Bad Request: reply markup is too long.

Клавиатура выбора теста строила кнопку на каждый тест компании без пагинации
и без обрезки названий. В сессии, где тестов ещё нет (например, новая сессия
большой траектории), в разметку уходил весь каталог тестов, Telegram отбивал
сообщение, и пользователь видел, что «ничего не происходит».
"""

import json
from types import SimpleNamespace

from bot.keyboards.training_keyboards import (
    INLINE_BUTTON_TEXT_MAX_LENGTH,
    SESSION_TEST_SELECTION_PAGE_SIZE,
    get_test_selection_for_session_keyboard,
)

# Эмпирический бюджет разметки: Telegram отвечает "reply markup is too long"
# на слишком большой JSON reply_markup. Кириллица экранируется в \uXXXX,
# то есть каждый русский символ названия стоит 6 байт.
TELEGRAM_REPLY_MARKUP_LIMIT_BYTES = 10240


def _test_item(test_id: int, name: str):
    return SimpleNamespace(id=test_id, name=name)


def _markup_size_bytes(markup) -> int:
    return len(json.dumps(markup.model_dump(exclude_none=True), ensure_ascii=True).encode("utf-8"))


def _btn_texts(markup):
    return [[btn.text for btn in row] for row in markup.inline_keyboard]


def _btn_callbacks(markup):
    return [[btn.callback_data for btn in row] for row in markup.inline_keyboard]


def _catalog(count: int) -> list:
    return [
        _test_item(
            i,
            f"Тест №{i} по стандартам обслуживания гостей и приготовлению напитков в баре",
        )
        for i in range(1, count + 1)
    ]


def test_selection_keyboard_fits_telegram_reply_markup_limit():
    markup = get_test_selection_for_session_keyboard(_catalog(100), session_id=1210)

    assert _markup_size_bytes(markup) <= TELEGRAM_REPLY_MARKUP_LIMIT_BYTES


def test_selection_keyboard_is_paginated_and_truncates_long_names():
    markup = get_test_selection_for_session_keyboard(_catalog(100), session_id=1210)

    texts = _btn_texts(markup)
    callbacks = _btn_callbacks(markup)

    # страница тестов + строка навигации + «Назад»
    assert len(texts) == SESSION_TEST_SELECTION_PAGE_SIZE + 2
    assert all(len(row[0]) <= INLINE_BUTTON_TEXT_MAX_LENGTH for row in texts[:SESSION_TEST_SELECTION_PAGE_SIZE])
    assert callbacks[0] == ["select_test_for_session:1210:1"]
    assert callbacks[SESSION_TEST_SELECTION_PAGE_SIZE] == ["noop", "select_test_page:1210:1"]
    assert callbacks[-1] == ["edit_session_view:1210"]


def test_selection_keyboard_shows_requested_page():
    markup = get_test_selection_for_session_keyboard(_catalog(100), session_id=1210, page=3)

    callbacks = _btn_callbacks(markup)
    first_on_page = SESSION_TEST_SELECTION_PAGE_SIZE * 3 + 1

    assert callbacks[0] == [f"select_test_for_session:1210:{first_on_page}"]
    assert callbacks[SESSION_TEST_SELECTION_PAGE_SIZE] == [
        "select_test_page:1210:2",
        "noop",
        "select_test_page:1210:4",
    ]


def test_selection_keyboard_hides_tests_already_in_session():
    markup = get_test_selection_for_session_keyboard(_catalog(6), session_id=1210, existing_test_ids=[1, 2, 3])

    callbacks = _btn_callbacks(markup)

    assert callbacks[0] == ["select_test_for_session:1210:4"]
    assert all("select_test_for_session:1210:1" not in row for row in callbacks)


def test_selection_keyboard_without_pagination_for_short_catalog():
    markup = get_test_selection_for_session_keyboard(_catalog(3), session_id=1210)

    callbacks = _btn_callbacks(markup)

    assert len(callbacks) == 4  # 3 теста + «Назад», строки навигации нет
    assert callbacks[-1] == ["edit_session_view:1210"]
