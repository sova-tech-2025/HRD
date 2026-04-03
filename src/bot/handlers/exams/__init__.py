from bot.handlers.exams.exam_assignment import router as exam_assignment_router
from bot.handlers.exams.exam_conducting import router as exam_conducting_router
from bot.handlers.exams.exam_menu import router as exam_menu_router

__all__ = [
    "exam_menu_router",
    "exam_assignment_router",
    "exam_conducting_router",
]
