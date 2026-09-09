"""Тесты кнопки наставника «Сделать сотрудником».

Ключевое требование: наставник не может перевести стажёра в сотрудники,
пока тот не прошёл все этапы и тесты траектории.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from bot.handlers.training import mentorship

MODULE = "bot.handlers.training.mentorship"


def make_role(name: str) -> MagicMock:
    role = MagicMock()
    role.name = name
    return role


def make_user(user_id: int, roles: list[str], full_name: str = "Иванов Иван", company_id: int = 1) -> MagicMock:
    user = MagicMock()
    user.id = user_id
    user.tg_id = 1000 + user_id
    user.full_name = full_name
    user.company_id = company_id
    user.roles = [make_role(name) for name in roles]
    return user


def make_callback(data: str) -> MagicMock:
    callback = MagicMock()
    callback.data = data
    callback.from_user.id = 555
    callback.from_user.username = "mentor"
    callback.answer = AsyncMock()
    callback.message.edit_text = AsyncMock()
    callback.message.bot.send_message = AsyncMock()
    return callback


def patch_repo(all_stages_completed: bool):
    """Подменяет AssessmentAssignmentRepository.check_all_stages_completed."""
    repo = MagicMock()
    repo.check_all_stages_completed = AsyncMock(return_value=all_stages_completed)
    return patch(f"{MODULE}.AssessmentAssignmentRepository", return_value=repo)


class TestGate:
    @pytest.mark.asyncio
    async def test_incomplete_trajectory_blocks_transition(self):
        """Траектория не пройдена — перевод не выполняется, показана причина."""
        mentor = make_user(1, ["Наставник"], "Петров Пётр")
        trainee = make_user(2, ["Стажер"])
        callback = make_callback("mentor_make_employee:2")

        with (
            patch(f"{MODULE}.get_user_by_tg_id", AsyncMock(return_value=mentor)),
            patch(f"{MODULE}.get_user_by_id", AsyncMock(return_value=trainee)),
            patch(f"{MODULE}.get_trainee_mentor", AsyncMock(return_value=mentor)),
            patch(f"{MODULE}.get_trainee_learning_path", AsyncMock(return_value=MagicMock())),
            patch(f"{MODULE}.change_trainee_to_employee", AsyncMock()) as change_role,
            patch_repo(all_stages_completed=False),
        ):
            await mentorship.callback_mentor_make_employee(callback, AsyncMock())

        change_role.assert_not_called()
        text = callback.message.edit_text.call_args[0][0]
        assert "Перевод недоступен" in text
        assert "Все этапы траектории должны быть пройдены" in text

    @pytest.mark.asyncio
    async def test_without_trajectory_shows_own_reason(self):
        """Без назначенной траектории — отдельное сообщение, не «не завершил этапы»."""
        mentor = make_user(1, ["Наставник"])
        trainee = make_user(2, ["Стажер"])
        callback = make_callback("mentor_make_employee:2")

        with (
            patch(f"{MODULE}.get_user_by_tg_id", AsyncMock(return_value=mentor)),
            patch(f"{MODULE}.get_user_by_id", AsyncMock(return_value=trainee)),
            patch(f"{MODULE}.get_trainee_mentor", AsyncMock(return_value=mentor)),
            patch(f"{MODULE}.get_trainee_learning_path", AsyncMock(return_value=None)),
            patch(f"{MODULE}.change_trainee_to_employee", AsyncMock()) as change_role,
            patch_repo(all_stages_completed=False) as repo_patch,
        ):
            repo = repo_patch.return_value
            await mentorship.callback_mentor_make_employee(callback, AsyncMock())

        change_role.assert_not_called()
        repo.check_all_stages_completed.assert_not_called()
        text = callback.message.edit_text.call_args[0][0]
        assert "нет назначенной траектории" in text

    @pytest.mark.asyncio
    async def test_completed_trajectory_shows_confirmation(self):
        """Траектория пройдена — показываем подтверждение с ФИО, но роль ещё не меняем."""
        mentor = make_user(1, ["Наставник"])
        trainee = make_user(2, ["Стажер"], full_name="Сидорова Мария")
        callback = make_callback("mentor_make_employee:2")

        with (
            patch(f"{MODULE}.get_user_by_tg_id", AsyncMock(return_value=mentor)),
            patch(f"{MODULE}.get_user_by_id", AsyncMock(return_value=trainee)),
            patch(f"{MODULE}.get_trainee_mentor", AsyncMock(return_value=mentor)),
            patch(f"{MODULE}.get_trainee_learning_path", AsyncMock(return_value=MagicMock())),
            patch(f"{MODULE}.change_trainee_to_employee", AsyncMock()) as change_role,
            patch_repo(all_stages_completed=True),
        ):
            await mentorship.callback_mentor_make_employee(callback, AsyncMock())

        change_role.assert_not_called()
        text = callback.message.edit_text.call_args[0][0]
        assert "Вы уверены, что хотите перевести Сидорова Мария в сотрудники?" in text
        keyboard = callback.message.edit_text.call_args.kwargs["reply_markup"]
        assert keyboard.inline_keyboard[0][0].callback_data == "confirm_mentor_make_employee:2"


class TestAccess:
    @pytest.mark.asyncio
    async def test_foreign_trainee_is_rejected(self):
        """Чужой стажёр — отказ, роль не меняется."""
        mentor = make_user(1, ["Наставник"])
        other_mentor = make_user(9, ["Наставник"])
        trainee = make_user(2, ["Стажер"])
        callback = make_callback("confirm_mentor_make_employee:2")

        with (
            patch(f"{MODULE}.get_user_by_tg_id", AsyncMock(return_value=mentor)),
            patch(f"{MODULE}.get_user_by_id", AsyncMock(return_value=trainee)),
            patch(f"{MODULE}.get_trainee_mentor", AsyncMock(return_value=other_mentor)),
            patch(f"{MODULE}.change_trainee_to_employee", AsyncMock()) as change_role,
        ):
            await mentorship.callback_confirm_mentor_make_employee(callback, AsyncMock())

        change_role.assert_not_called()
        callback.answer.assert_any_call("❌ Это не твой стажер", show_alert=True)

    @pytest.mark.asyncio
    async def test_other_company_trainee_is_rejected(self):
        """Стажёр из другой компании недоступен."""
        mentor = make_user(1, ["Наставник"], company_id=1)
        trainee = make_user(2, ["Стажер"], company_id=42)
        callback = make_callback("confirm_mentor_make_employee:2")

        with (
            patch(f"{MODULE}.get_user_by_tg_id", AsyncMock(return_value=mentor)),
            patch(f"{MODULE}.get_user_by_id", AsyncMock(return_value=trainee)),
            patch(f"{MODULE}.change_trainee_to_employee", AsyncMock()) as change_role,
        ):
            await mentorship.callback_confirm_mentor_make_employee(callback, AsyncMock())

        change_role.assert_not_called()
        callback.answer.assert_any_call("❌ Стажер не найден", show_alert=True)

    @pytest.mark.asyncio
    async def test_admin_bypasses_mentor_check(self):
        """ADMIN — тестовая мульти-роль, ему доступны стажёры компании."""
        admin = make_user(1, ["ADMIN"])
        trainee = make_user(2, ["Стажер"])
        callback = make_callback("mentor_make_employee:2")
        get_trainee_mentor = AsyncMock(return_value=None)

        with (
            patch(f"{MODULE}.get_user_by_tg_id", AsyncMock(return_value=admin)),
            patch(f"{MODULE}.get_user_by_id", AsyncMock(return_value=trainee)),
            patch(f"{MODULE}.get_trainee_mentor", get_trainee_mentor),
            patch(f"{MODULE}.get_trainee_learning_path", AsyncMock(return_value=MagicMock())),
            patch_repo(all_stages_completed=True),
        ):
            await mentorship.callback_mentor_make_employee(callback, AsyncMock())

        get_trainee_mentor.assert_not_called()
        assert "Вы уверены" in callback.message.edit_text.call_args[0][0]


class TestConfirmation:
    @pytest.mark.asyncio
    async def test_transition_performed_and_trainee_notified(self):
        """Happy path: роль меняется один раз, стажёр получает уведомление."""
        mentor = make_user(1, ["Наставник"], full_name="Петров Пётр")
        trainee = make_user(2, ["Стажер"], full_name="Сидорова Мария")
        callback = make_callback("confirm_mentor_make_employee:2")
        change_role = AsyncMock(return_value=True)
        session = AsyncMock()

        with (
            patch(f"{MODULE}.get_user_by_tg_id", AsyncMock(return_value=mentor)),
            patch(f"{MODULE}.get_user_by_id", AsyncMock(return_value=trainee)),
            patch(f"{MODULE}.get_trainee_mentor", AsyncMock(return_value=mentor)),
            patch(f"{MODULE}.get_trainee_learning_path", AsyncMock(return_value=MagicMock())),
            patch(f"{MODULE}.change_trainee_to_employee", change_role),
            patch_repo(all_stages_completed=True),
        ):
            await mentorship.callback_confirm_mentor_make_employee(callback, session)

        change_role.assert_awaited_once_with(session, 2, None, company_id=1)
        assert "переведен в сотрудники" in callback.message.edit_text.call_args[0][0]
        notification = callback.message.bot.send_message.call_args.kwargs
        assert notification["chat_id"] == trainee.tg_id
        assert "стал сотрудником" in notification["text"]

    @pytest.mark.asyncio
    async def test_gate_rechecked_on_confirmation(self):
        """Гейт проверяется повторно: устаревшая клавиатура не должна пропускать перевод."""
        mentor = make_user(1, ["Наставник"])
        trainee = make_user(2, ["Стажер"])
        callback = make_callback("confirm_mentor_make_employee:2")

        with (
            patch(f"{MODULE}.get_user_by_tg_id", AsyncMock(return_value=mentor)),
            patch(f"{MODULE}.get_user_by_id", AsyncMock(return_value=trainee)),
            patch(f"{MODULE}.get_trainee_mentor", AsyncMock(return_value=mentor)),
            patch(f"{MODULE}.get_trainee_learning_path", AsyncMock(return_value=MagicMock())),
            patch(f"{MODULE}.change_trainee_to_employee", AsyncMock()) as change_role,
            patch_repo(all_stages_completed=False),
        ):
            await mentorship.callback_confirm_mentor_make_employee(callback, AsyncMock())

        change_role.assert_not_called()

    @pytest.mark.asyncio
    async def test_already_employee_is_rejected(self):
        """Повторное нажатие после перевода не выполняет ничего."""
        mentor = make_user(1, ["Наставник"])
        employee = make_user(2, ["Сотрудник"])
        callback = make_callback("confirm_mentor_make_employee:2")

        with (
            patch(f"{MODULE}.get_user_by_tg_id", AsyncMock(return_value=mentor)),
            patch(f"{MODULE}.get_user_by_id", AsyncMock(return_value=employee)),
            patch(f"{MODULE}.get_trainee_mentor", AsyncMock(return_value=mentor)),
            patch(f"{MODULE}.change_trainee_to_employee", AsyncMock()) as change_role,
        ):
            await mentorship.callback_confirm_mentor_make_employee(callback, AsyncMock())

        change_role.assert_not_called()
        callback.answer.assert_any_call("❌ Пользователь уже не стажер", show_alert=True)

    @pytest.mark.asyncio
    async def test_blocked_trainee_does_not_break_transition(self):
        """Стажёр заблокировал бота — перевод всё равно состоялся."""
        mentor = make_user(1, ["Наставник"])
        trainee = make_user(2, ["Стажер"])
        callback = make_callback("confirm_mentor_make_employee:2")
        callback.message.bot.send_message = AsyncMock(side_effect=Exception("bot blocked"))
        change_role = AsyncMock(return_value=True)

        with (
            patch(f"{MODULE}.get_user_by_tg_id", AsyncMock(return_value=mentor)),
            patch(f"{MODULE}.get_user_by_id", AsyncMock(return_value=trainee)),
            patch(f"{MODULE}.get_trainee_mentor", AsyncMock(return_value=mentor)),
            patch(f"{MODULE}.get_trainee_learning_path", AsyncMock(return_value=MagicMock())),
            patch(f"{MODULE}.change_trainee_to_employee", change_role),
            patch_repo(all_stages_completed=True),
        ):
            await mentorship.callback_confirm_mentor_make_employee(callback, AsyncMock())

        change_role.assert_awaited_once()
        assert "переведен в сотрудники" in callback.message.edit_text.call_args[0][0]
