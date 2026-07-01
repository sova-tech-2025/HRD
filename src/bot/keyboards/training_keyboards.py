from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.keyboards.pagination import PaginatedKeyboard

INLINE_BUTTON_TEXT_MAX_LENGTH = 64
MENTOR_REASSIGNMENT_PAGE_SIZE = 5


def truncate_inline_button_text(text: str, max_length: int = INLINE_BUTTON_TEXT_MAX_LENGTH) -> str:
    if len(text) <= max_length:
        return text
    return text[: max_length - 1].rstrip() + "…"


def _mentor_work_object_name(mentor) -> str:
    work_object = getattr(mentor, "work_object", None)
    return getattr(work_object, "name", None) or "Не указан"


def format_reassign_mentor_button_text(mentor) -> str:
    full_name = getattr(mentor, "full_name", None) or "Без имени"
    work_object = _mentor_work_object_name(mentor)
    return truncate_inline_button_text(f"👨‍🏫 {full_name} ({work_object})")


def get_reassign_mentor_keyboard(
    mentors: list,
    trainee_id: int,
    page: int = 0,
    per_page: int = MENTOR_REASSIGNMENT_PAGE_SIZE,
) -> InlineKeyboardMarkup:
    """Клавиатура выбора нового наставника при переназначении."""
    return (
        PaginatedKeyboard(
            mentors,
            page=page,
            per_page=per_page,
            page_callback=f"reassign_mentors_page:{trainee_id}",
        )
        .add_items(
            lambda mentor: (
                format_reassign_mentor_button_text(mentor),
                f"reassign_to_mentor:{trainee_id}:{mentor.id}",
            )
        )
        .add_footer([[InlineKeyboardButton(text="← назад", callback_data="reassign_mentor")]])
        .build()
    )
