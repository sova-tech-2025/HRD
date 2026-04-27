"""Тесты на регистрацию обработчиков в роутере exam_assignment.

Покрывают два ранее найденных дефекта:

1. Мёртвый обработчик ``callback_exam_back_to_card`` — старая клавиатура
   ``get_exam_examiner_list_keyboard`` с этим callback была удалена,
   поэтому handler больше не должен быть зарегистрирован.

2. Несогласованность state-guard: обработчики пагинации фильтра сдающего
   (``ef_gpage:`` / ``ef_opage:`` / ``ef_rpage:``) должны быть привязаны к
   ``ExamStates.selecting_examinee_filter`` — как у экзаменатора. Без guard
   старая пагинационная кнопка из истории чата может сработать в чужом
   состоянии (``selecting_examinee`` / ``viewing_examinee_card``).
"""

from aiogram.filters import StateFilter
from aiogram.fsm.state import State

from bot.handlers.exams.exam_assignment import router
from bot.states.states import ExamStates


def _find_handler_by_func_name(func_name: str):
    for h in router.callback_query.handlers:
        if h.callback.__name__ == func_name:
            return h
    return None


def _state_filter_states(handler) -> tuple:
    """Возвращает кортеж состояний из state-guard обработчика, или ().

    Aiogram оборачивает state-аргумент декоратора либо в ``StateFilter``,
    либо кладёт сам ``State`` как callback `FilterObject`-а — поддерживаем
    оба варианта.
    """
    states: list = []
    for f in handler.filters:
        cb = f.callback
        if isinstance(cb, StateFilter):
            states.extend(cb.states)
        elif isinstance(cb, State):
            states.append(cb)
    return tuple(states)


# ============================================================
# 1. Мёртвый callback `exam_back_to_card`
# ============================================================


class TestDeadBackToCardHandler:
    """Старый обработчик карточки больше не должен висеть в роутере."""

    def test_callback_exam_back_to_card_handler_removed(self):
        """Функция-обработчик `callback_exam_back_to_card` отсутствует."""
        assert _find_handler_by_func_name("callback_exam_back_to_card") is None

    def test_no_handler_matches_exam_back_to_card_callback(self):
        """Ни один MagicFilter в роутере не ловит data='exam_back_to_card'."""

        class _FakeCQ:
            data = "exam_back_to_card"

        fake = _FakeCQ()

        for h in router.callback_query.handlers:
            for f in h.filters:
                # aiogram кладёт MagicFilter в `f.magic`, а в `f.callback` — bound-метод resolve.
                magic = getattr(f, "magic", None)
                if magic is None:
                    continue
                try:
                    matched = magic.resolve(fake)
                except Exception:
                    matched = False
                assert not matched, f"Handler `{h.callback.__name__}` всё ещё ловит 'exam_back_to_card'"


# ============================================================
# 2. State-guard на пагинации фильтра сдающего
# ============================================================


class TestExamineeFilterPaginationStateGuards:
    """Пагинация групп/объектов/ролей сдающего должна быть привязана к
    ``selecting_examinee_filter`` — иначе устаревшая стрелка из истории
    чата сработает посреди другого состояния и порвёт мастер.
    """

    def test_examinee_group_pagination_has_state_guard(self):
        h = _find_handler_by_func_name("callback_exam_examinee_group_page")
        assert h is not None, "Handler `callback_exam_examinee_group_page` не зарегистрирован"
        states = _state_filter_states(h)
        assert ExamStates.selecting_examinee_filter in states, (
            f"`ef_gpage:*` должен быть гардён `selecting_examinee_filter`, а гарды: {states}"
        )

    def test_examinee_object_pagination_has_state_guard(self):
        h = _find_handler_by_func_name("callback_exam_examinee_object_page")
        assert h is not None, "Handler `callback_exam_examinee_object_page` не зарегистрирован"
        states = _state_filter_states(h)
        assert ExamStates.selecting_examinee_filter in states, (
            f"`ef_opage:*` должен быть гардён `selecting_examinee_filter`, а гарды: {states}"
        )

    def test_examinee_role_pagination_has_state_guard(self):
        h = _find_handler_by_func_name("callback_exam_examinee_role_page")
        assert h is not None, "Handler `callback_exam_examinee_role_page` не зарегистрирован"
        states = _state_filter_states(h)
        assert ExamStates.selecting_examinee_filter in states, (
            f"`ef_rpage:*` должен быть гардён `selecting_examinee_filter`, а гарды: {states}"
        )

    def test_consistent_with_examiner_side(self):
        """Симметричный sanity-check: на стороне экзаменатора те же пагинации
        привязаны к ``selecting_examiner_filter``. Если этот тест когда-нибудь
        упадёт — значит поломали другую сторону симметрии.
        """
        for func_name in (
            "callback_exam_examiner_group_page",
            "callback_exam_examiner_object_page",
            "callback_exam_examiner_role_page",
        ):
            h = _find_handler_by_func_name(func_name)
            assert h is not None, f"Handler `{func_name}` не зарегистрирован"
            assert ExamStates.selecting_examiner_filter in _state_filter_states(h), (
                f"`{func_name}` потерял guard `selecting_examiner_filter`"
            )
