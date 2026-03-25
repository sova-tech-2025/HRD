"""
Unit-тесты для handlers/exams/exam_conducting.py.

Проверяют корректное отображение internship_object и work_object
в карточке проведения экзамена и в результатах.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# --- Фабрики моков ---


def make_callback(user_id=123, data="exam_conduct"):
    """Создаёт мок CallbackQuery."""
    callback = AsyncMock()
    callback.from_user = MagicMock()
    callback.from_user.id = user_id
    callback.data = data
    callback.message = AsyncMock()
    callback.message.edit_text = AsyncMock()
    callback.answer = AsyncMock()
    return callback


def make_state(data=None):
    """Создаёт мок FSMContext."""
    state = AsyncMock()
    state.get_data = AsyncMock(return_value=data or {"company_id": 1})
    state.set_state = AsyncMock()
    state.update_data = AsyncMock()
    state.clear = AsyncMock()
    return state


def make_user(user_id=1, tg_id=123, full_name="Тестовый Пользователь"):
    """Создаёт мок пользователя."""
    user = MagicMock()
    user.id = user_id
    user.tg_id = tg_id
    user.full_name = full_name
    return user


def make_question(question_id=1, text="Вопрос?", max_points=10.0):
    """Создаёт мок вопроса экзамена."""
    q = MagicMock()
    q.id = question_id
    q.question_text = text
    q.max_points = max_points
    return q


def make_exam(name="Тест Экзамен", passing_score=5.0, questions=None):
    """Создаёт мок экзамена."""
    exam = MagicMock()
    exam.name = name
    exam.passing_score = passing_score
    exam.questions = questions or [make_question()]
    return exam


def make_assignment(
    assignment_id=42,
    examinee_name="Сдающий Тест",
    exam_name="Тест Экзамен",
    internship_object_name=None,
    work_object_name=None,
    manager_name="Экзаменатор Тест",
):
    """Создаёт мок назначения экзамена с trainee, attestation, manager."""
    internship_obj = None
    if internship_object_name:
        internship_obj = MagicMock()
        internship_obj.name = internship_object_name

    work_obj = None
    if work_object_name:
        work_obj = MagicMock()
        work_obj.name = work_object_name

    trainee = MagicMock()
    trainee.full_name = examinee_name
    trainee.tg_id = 456
    trainee.internship_object = internship_obj
    trainee.work_object = work_obj

    exam = make_exam(name=exam_name)

    manager = MagicMock()
    manager.full_name = manager_name

    assignment = MagicMock()
    assignment.id = assignment_id
    assignment.trainee = trainee
    assignment.attestation = exam
    assignment.manager = manager
    assignment.manager_id = 20
    assignment.status = "assigned"

    return assignment


# ==========================================================================
# callback_exam_conduct — список для экзаменатора
# ==========================================================================


class TestCallbackExamConduct:
    """Список назначенных экзаменов для экзаменатора."""

    @pytest.mark.asyncio
    async def test_shows_work_object_in_list(self):
        """В списке сдающих отображается объект работы."""
        from bot.handlers.exams.exam_conducting import callback_exam_conduct

        callback = make_callback()
        state = make_state()
        session = AsyncMock()

        user = make_user()
        assignment = make_assignment(work_object_name="Кафе Юг")

        repo_mock = MagicMock()
        repo_mock.get_exam_assignments_for_examiner = AsyncMock(return_value=[assignment])

        with (
            patch("bot.handlers.exams.exam_conducting.get_user_by_tg_id", return_value=user),
            patch("bot.handlers.exams.exam_conducting.AssessmentAssignmentRepository", return_value=repo_mock),
        ):
            await callback_exam_conduct(callback, state, session)

        text = callback.message.edit_text.call_args[0][0]
        assert "Кафе Юг" in text

    @pytest.mark.asyncio
    async def test_shows_not_specified_when_no_work_object(self):
        """Если work_object=None, показывается 'Не указан'."""
        from bot.handlers.exams.exam_conducting import callback_exam_conduct

        callback = make_callback()
        state = make_state()
        session = AsyncMock()

        user = make_user()
        assignment = make_assignment(work_object_name=None)

        repo_mock = MagicMock()
        repo_mock.get_exam_assignments_for_examiner = AsyncMock(return_value=[assignment])

        with (
            patch("bot.handlers.exams.exam_conducting.get_user_by_tg_id", return_value=user),
            patch("bot.handlers.exams.exam_conducting.AssessmentAssignmentRepository", return_value=repo_mock),
        ):
            await callback_exam_conduct(callback, state, session)

        text = callback.message.edit_text.call_args[0][0]
        assert "Не указан" in text

    @pytest.mark.asyncio
    async def test_empty_assignments(self):
        """Если нет назначенных экзаменов, показывается сообщение."""
        from bot.handlers.exams.exam_conducting import callback_exam_conduct

        callback = make_callback()
        state = make_state()
        session = AsyncMock()

        user = make_user()

        repo_mock = MagicMock()
        repo_mock.get_exam_assignments_for_examiner = AsyncMock(return_value=[])

        with (
            patch("bot.handlers.exams.exam_conducting.get_user_by_tg_id", return_value=user),
            patch("bot.handlers.exams.exam_conducting.AssessmentAssignmentRepository", return_value=repo_mock),
        ):
            await callback_exam_conduct(callback, state, session)

        text = callback.message.edit_text.call_args[0][0]
        assert "Нет назначенных экзаменов" in text


# ==========================================================================
# callback_exam_conduct_select — карточка управления экзаменом
# ==========================================================================


class TestCallbackExamConductSelect:
    """Карточка сдающего при проведении экзамена."""

    @pytest.mark.asyncio
    async def test_shows_both_objects(self):
        """Карточка показывает и объект стажировки, и объект работы."""
        from bot.handlers.exams.exam_conducting import callback_exam_conduct_select

        callback = make_callback(data="exam_conduct_select:42")
        state = make_state()
        session = AsyncMock()

        assignment = make_assignment(
            internship_object_name="Кафе Центр",
            work_object_name="Кафе Юг",
        )

        repo_mock = MagicMock()
        repo_mock.get_by_id = AsyncMock(return_value=assignment)

        with patch(
            "bot.handlers.exams.exam_conducting.AssessmentAssignmentRepository",
            return_value=repo_mock,
        ):
            await callback_exam_conduct_select(callback, state, session)

        text = callback.message.edit_text.call_args[0][0]
        assert "Кафе Центр" in text
        assert "Кафе Юг" in text
        assert "Объект стажировки" in text
        assert "Объект работы" in text

    @pytest.mark.asyncio
    async def test_shows_not_specified_when_internship_object_none(self):
        """Если internship_object=None, показывается 'Не указан'."""
        from bot.handlers.exams.exam_conducting import callback_exam_conduct_select

        callback = make_callback(data="exam_conduct_select:42")
        state = make_state()
        session = AsyncMock()

        assignment = make_assignment(
            internship_object_name=None,
            work_object_name="Кафе Юг",
        )

        repo_mock = MagicMock()
        repo_mock.get_by_id = AsyncMock(return_value=assignment)

        with patch(
            "bot.handlers.exams.exam_conducting.AssessmentAssignmentRepository",
            return_value=repo_mock,
        ):
            await callback_exam_conduct_select(callback, state, session)

        text = callback.message.edit_text.call_args[0][0]
        # "Объект стажировки: Не указан"
        assert "Не указан" in text
        assert "Кафе Юг" in text

    @pytest.mark.asyncio
    async def test_shows_not_specified_when_work_object_none(self):
        """Если work_object=None, показывается 'Не указан'."""
        from bot.handlers.exams.exam_conducting import callback_exam_conduct_select

        callback = make_callback(data="exam_conduct_select:42")
        state = make_state()
        session = AsyncMock()

        assignment = make_assignment(
            internship_object_name="Кафе Центр",
            work_object_name=None,
        )

        repo_mock = MagicMock()
        repo_mock.get_by_id = AsyncMock(return_value=assignment)

        with patch(
            "bot.handlers.exams.exam_conducting.AssessmentAssignmentRepository",
            return_value=repo_mock,
        ):
            await callback_exam_conduct_select(callback, state, session)

        text = callback.message.edit_text.call_args[0][0]
        assert "Кафе Центр" in text
        # work_object: Не указан
        assert "Не указан" in text

    @pytest.mark.asyncio
    async def test_both_objects_none(self):
        """Если оба объекта None, оба показываются как 'Не указан'."""
        from bot.handlers.exams.exam_conducting import callback_exam_conduct_select

        callback = make_callback(data="exam_conduct_select:42")
        state = make_state()
        session = AsyncMock()

        assignment = make_assignment(
            internship_object_name=None,
            work_object_name=None,
        )

        repo_mock = MagicMock()
        repo_mock.get_by_id = AsyncMock(return_value=assignment)

        with patch(
            "bot.handlers.exams.exam_conducting.AssessmentAssignmentRepository",
            return_value=repo_mock,
        ):
            await callback_exam_conduct_select(callback, state, session)

        text = callback.message.edit_text.call_args[0][0]
        # Оба поля "Не указан"
        assert text.count("Не указан") == 2

    @pytest.mark.asyncio
    async def test_assignment_not_found(self):
        """Если назначение не найдено, показывается сообщение об ошибке."""
        from bot.handlers.exams.exam_conducting import callback_exam_conduct_select

        callback = make_callback(data="exam_conduct_select:999")
        state = make_state()
        session = AsyncMock()

        repo_mock = MagicMock()
        repo_mock.get_by_id = AsyncMock(return_value=None)

        with patch(
            "bot.handlers.exams.exam_conducting.AssessmentAssignmentRepository",
            return_value=repo_mock,
        ):
            await callback_exam_conduct_select(callback, state, session)

        text = callback.message.edit_text.call_args[0][0]
        assert "не найден" in text


# ==========================================================================
# _show_exam_results — результаты экзамена
# ==========================================================================


class TestShowExamResults:
    """Отображение результатов экзамена."""

    @pytest.mark.asyncio
    async def test_results_show_both_objects(self):
        """Результаты экзамена показывают и объект стажировки, и объект работы."""
        from bot.handlers.exams.exam_conducting import _show_exam_results

        message = AsyncMock()
        message.answer = AsyncMock()
        message.from_user = MagicMock()
        message.from_user.id = 123
        message.bot = AsyncMock()

        assignment = make_assignment(
            internship_object_name="Кафе Центр",
            work_object_name="Кафе Юг",
        )
        assignment.attestation.passing_score = 5.0

        answers = [{"question_id": 1, "score": 8.0, "max_score": 10.0}]

        state = make_state(
            data={
                "company_id": 1,
                "exam_assignment_id": 42,
                "exam_answers": answers,
            }
        )

        repo_mock = MagicMock()
        repo_mock.get_by_id = AsyncMock(return_value=assignment)
        repo_mock.complete_session = AsyncMock(return_value=True)

        result_mock = MagicMock()
        result_mock.id = 1
        result_repo_mock = MagicMock()
        result_repo_mock.create = AsyncMock(return_value=result_mock)
        result_repo_mock.save_question_result = AsyncMock()

        session = AsyncMock()

        with (
            patch(
                "bot.handlers.exams.exam_conducting.AssessmentAssignmentRepository",
                return_value=repo_mock,
            ),
            patch(
                "bot.handlers.exams.exam_conducting.AssessmentResultRepository",
                return_value=result_repo_mock,
            ),
        ):
            await _show_exam_results(message, state, session)

        text = message.answer.call_args[0][0]
        assert "Кафе Центр" in text
        assert "Кафе Юг" in text
        assert "Объект стажировки" in text
        assert "Объект работы" in text

    @pytest.mark.asyncio
    async def test_results_show_not_specified_when_objects_none(self):
        """Результаты показывают 'Не указан' когда объекты отсутствуют."""
        from bot.handlers.exams.exam_conducting import _show_exam_results

        message = AsyncMock()
        message.answer = AsyncMock()
        message.from_user = MagicMock()
        message.from_user.id = 123
        message.bot = AsyncMock()

        assignment = make_assignment(
            internship_object_name=None,
            work_object_name=None,
        )
        assignment.attestation.passing_score = 5.0

        answers = [{"question_id": 1, "score": 3.0, "max_score": 10.0}]

        state = make_state(
            data={
                "company_id": 1,
                "exam_assignment_id": 42,
                "exam_answers": answers,
            }
        )

        repo_mock = MagicMock()
        repo_mock.get_by_id = AsyncMock(return_value=assignment)
        repo_mock.complete_session = AsyncMock(return_value=True)

        result_mock = MagicMock()
        result_mock.id = 1
        result_repo_mock = MagicMock()
        result_repo_mock.create = AsyncMock(return_value=result_mock)
        result_repo_mock.save_question_result = AsyncMock()

        session = AsyncMock()

        with (
            patch(
                "bot.handlers.exams.exam_conducting.AssessmentAssignmentRepository",
                return_value=repo_mock,
            ),
            patch(
                "bot.handlers.exams.exam_conducting.AssessmentResultRepository",
                return_value=result_repo_mock,
            ),
        ):
            await _show_exam_results(message, state, session)

        text = message.answer.call_args[0][0]
        assert text.count("Не указан") == 2

    @pytest.mark.asyncio
    async def test_passed_exam_result(self):
        """Экзамен пройден — отображается зелёный статус."""
        from bot.handlers.exams.exam_conducting import _show_exam_results

        message = AsyncMock()
        message.answer = AsyncMock()
        message.from_user = MagicMock()
        message.from_user.id = 123
        message.bot = AsyncMock()

        assignment = make_assignment(
            internship_object_name="Кафе Центр",
            work_object_name="Кафе Юг",
        )
        assignment.attestation.passing_score = 5.0

        answers = [{"question_id": 1, "score": 8.0, "max_score": 10.0}]

        state = make_state(
            data={
                "company_id": 1,
                "exam_assignment_id": 42,
                "exam_answers": answers,
            }
        )

        repo_mock = MagicMock()
        repo_mock.get_by_id = AsyncMock(return_value=assignment)
        repo_mock.complete_session = AsyncMock(return_value=True)

        result_mock = MagicMock()
        result_mock.id = 1
        result_repo_mock = MagicMock()
        result_repo_mock.create = AsyncMock(return_value=result_mock)
        result_repo_mock.save_question_result = AsyncMock()

        session = AsyncMock()

        with (
            patch(
                "bot.handlers.exams.exam_conducting.AssessmentAssignmentRepository",
                return_value=repo_mock,
            ),
            patch(
                "bot.handlers.exams.exam_conducting.AssessmentResultRepository",
                return_value=result_repo_mock,
            ),
        ):
            await _show_exam_results(message, state, session)

        text = message.answer.call_args[0][0]
        assert "пройден" in text
        assert "🟢" in text

    @pytest.mark.asyncio
    async def test_failed_exam_result(self):
        """Экзамен не пройден — отображается красный статус."""
        from bot.handlers.exams.exam_conducting import _show_exam_results

        message = AsyncMock()
        message.answer = AsyncMock()
        message.from_user = MagicMock()
        message.from_user.id = 123
        message.bot = AsyncMock()

        assignment = make_assignment(
            internship_object_name="Кафе Центр",
            work_object_name="Кафе Юг",
        )
        assignment.attestation.passing_score = 15.0  # выше чем набрано

        answers = [{"question_id": 1, "score": 3.0, "max_score": 10.0}]

        state = make_state(
            data={
                "company_id": 1,
                "exam_assignment_id": 42,
                "exam_answers": answers,
            }
        )

        repo_mock = MagicMock()
        repo_mock.get_by_id = AsyncMock(return_value=assignment)
        repo_mock.complete_session = AsyncMock(return_value=True)

        result_mock = MagicMock()
        result_mock.id = 1
        result_repo_mock = MagicMock()
        result_repo_mock.create = AsyncMock(return_value=result_mock)
        result_repo_mock.save_question_result = AsyncMock()

        session = AsyncMock()

        with (
            patch(
                "bot.handlers.exams.exam_conducting.AssessmentAssignmentRepository",
                return_value=repo_mock,
            ),
            patch(
                "bot.handlers.exams.exam_conducting.AssessmentResultRepository",
                return_value=result_repo_mock,
            ),
        ):
            await _show_exam_results(message, state, session)

        text = message.answer.call_args[0][0]
        assert "не пройден" in text
        assert "🔴" in text
