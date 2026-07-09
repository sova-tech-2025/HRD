from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def make_callback(data: str) -> MagicMock:
    callback = MagicMock()
    callback.data = data
    callback.answer = AsyncMock()
    callback.message = MagicMock()
    callback.message.edit_text = AsyncMock()
    callback.from_user.id = 941173405
    return callback


def make_stage_progress(*, is_opened: bool, is_completed: bool = False) -> SimpleNamespace:
    stage = SimpleNamespace(id=186, order_number=3, name="Практика на баре")
    return SimpleNamespace(id=3474, stage_id=186, stage=stage, is_opened=is_opened, is_completed=is_completed)


@pytest.mark.asyncio
async def test_duplicate_open_action_does_not_close_open_stage():
    from bot.handlers.training.mentorship import callback_toggle_stage

    callback = make_callback("toggle_stage:1210:186:open")
    session = AsyncMock()
    session.expire_all = MagicMock()
    trainee = SimpleNamespace(id=1210, company_id=1)
    trainee_path = SimpleNamespace(id=725)
    stage_progress = make_stage_progress(is_opened=True)

    with (
        patch("bot.handlers.training.mentorship.get_user_by_id", AsyncMock(return_value=trainee)),
        patch("bot.handlers.training.mentorship.get_trainee_learning_path", AsyncMock(return_value=trainee_path)),
        patch(
            "bot.handlers.training.mentorship.get_trainee_stage_progress",
            AsyncMock(return_value=[stage_progress]),
        ),
        patch("bot.handlers.training.mentorship.open_stage_for_trainee", new_callable=AsyncMock) as open_stage,
        patch(
            "bot.handlers.training.mentorship.update_stages_management_interface",
            new_callable=AsyncMock,
        ),
        patch("bot.handlers.training.mentorship.log_user_action"),
    ):
        await callback_toggle_stage(callback, MagicMock(), session, MagicMock())

    open_stage.assert_not_awaited()
    session.execute.assert_not_awaited()
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_legacy_duplicate_open_button_does_not_close_open_stage():
    from bot.handlers.training.mentorship import callback_toggle_stage

    callback = make_callback("toggle_stage:1210:186")
    callback.message.reply_markup = SimpleNamespace(
        inline_keyboard=[[SimpleNamespace(text="🔓 Открыть этап 3", callback_data="toggle_stage:1210:186")]]
    )
    session = AsyncMock()
    session.expire_all = MagicMock()
    trainee = SimpleNamespace(id=1210, company_id=1)
    trainee_path = SimpleNamespace(id=725)
    stage_progress = make_stage_progress(is_opened=True)

    with (
        patch("bot.handlers.training.mentorship.get_user_by_id", AsyncMock(return_value=trainee)),
        patch("bot.handlers.training.mentorship.get_trainee_learning_path", AsyncMock(return_value=trainee_path)),
        patch(
            "bot.handlers.training.mentorship.get_trainee_stage_progress",
            AsyncMock(return_value=[stage_progress]),
        ),
        patch("bot.handlers.training.mentorship.open_stage_for_trainee", new_callable=AsyncMock) as open_stage,
        patch(
            "bot.handlers.training.mentorship.update_stages_management_interface",
            new_callable=AsyncMock,
        ),
        patch("bot.handlers.training.mentorship.log_user_action"),
    ):
        await callback_toggle_stage(callback, MagicMock(), session, MagicMock())

    open_stage.assert_not_awaited()
    session.execute.assert_not_awaited()
    session.commit.assert_not_awaited()


async def render_stage_button(stage_progress: SimpleNamespace):
    from bot.handlers.training.mentorship import update_stages_management_interface

    callback = make_callback("manage_stages:1210")
    session = AsyncMock()
    trainee = SimpleNamespace(id=1210, company_id=1)
    trainee_path = SimpleNamespace(id=725)

    with (
        patch("bot.handlers.training.mentorship.get_user_by_id", AsyncMock(return_value=trainee)),
        patch("bot.handlers.training.mentorship.get_trainee_learning_path", AsyncMock(return_value=trainee_path)),
        patch(
            "bot.handlers.training.mentorship.get_trainee_stage_progress",
            AsyncMock(return_value=[stage_progress]),
        ),
        patch("bot.handlers.training.mentorship.get_user_test_results", AsyncMock(return_value=[])),
        patch(
            "bot.handlers.training.mentorship.generate_trajectory_progress_with_attestation_status",
            AsyncMock(return_value="Прогресс"),
        ),
    ):
        await update_stages_management_interface(callback, session, trainee.id)

    return callback.message.edit_text.await_args.kwargs["reply_markup"].inline_keyboard[0][0]


@pytest.mark.asyncio
async def test_closed_stage_button_encodes_open_action():
    button = await render_stage_button(make_stage_progress(is_opened=False))

    assert button.callback_data == "toggle_stage:1210:186:open"


@pytest.mark.asyncio
async def test_open_stage_button_encodes_close_action():
    button = await render_stage_button(make_stage_progress(is_opened=True))

    assert button.callback_data == "toggle_stage:1210:186:close"


@pytest.mark.asyncio
async def test_completed_closed_stage_is_not_rendered_as_openable():
    button = await render_stage_button(make_stage_progress(is_opened=False, is_completed=True))

    assert button.text == "✅ Этап 3 завершен"
    assert button.callback_data == "stage_completed_stub:1210:186"
