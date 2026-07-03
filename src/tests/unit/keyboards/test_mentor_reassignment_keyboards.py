from types import SimpleNamespace

from bot.keyboards.training_keyboards import (
    INLINE_BUTTON_TEXT_MAX_LENGTH,
    MENTOR_REASSIGNMENT_PAGE_SIZE,
    get_reassign_mentor_keyboard,
)


def _mentor(user_id: int, full_name: str, object_name: str):
    return SimpleNamespace(
        id=user_id,
        full_name=full_name,
        work_object=SimpleNamespace(name=object_name),
    )


def _btn_texts(markup):
    return [[btn.text for btn in row] for row in markup.inline_keyboard]


def _btn_callbacks(markup):
    return [[btn.callback_data for btn in row] for row in markup.inline_keyboard]


def test_reassign_mentor_keyboard_is_paginated_and_truncates_long_company_data():
    mentors = [
        _mentor(
            user_id=i,
            full_name=f"Наставник с очень длинным ФИО номер {i}",
            object_name="Объект с чрезмерно длинным названием, которое компания записала в карточку пользователя",
        )
        for i in range(1, 19)
    ]

    markup = get_reassign_mentor_keyboard(mentors, trainee_id=1066, page=0)

    texts = _btn_texts(markup)
    callbacks = _btn_callbacks(markup)

    assert len(texts) == MENTOR_REASSIGNMENT_PAGE_SIZE + 2
    assert all(len(row[0]) <= INLINE_BUTTON_TEXT_MAX_LENGTH for row in texts[:MENTOR_REASSIGNMENT_PAGE_SIZE])
    assert callbacks[0] == ["reassign_to_mentor:1066:1"]
    assert callbacks[MENTOR_REASSIGNMENT_PAGE_SIZE] == ["noop", "reassign_mentors_page:1066:1"]
    assert callbacks[-1] == ["reassign_mentor"]
