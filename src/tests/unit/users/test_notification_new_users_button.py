"""Тесты inline-кнопки 'Новые пользователи' из уведомления о регистрации.

Баг: кнопка в уведомлении о новом пользователе не перекидывает в нужный раздел.
Проверяем полный flow: callback show_new_users → список → выбор пользователя → роль.
"""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from bot.states.states import UserActivationStates


# --- Helpers ---


def make_callback(user_id=453388874, username="Saint_Whirlwind", callback_data="show_new_users"):
    """Мок CallbackQuery."""
    callback = AsyncMock()
    callback.from_user = MagicMock()
    callback.from_user.id = user_id
    callback.from_user.username = username
    callback.data = callback_data
    callback.message = AsyncMock()
    callback.answer = AsyncMock()
    return callback


def make_user(user_id=1, tg_id=453388874, is_active=True, company_id=3, full_name="Recruiter"):
    """Мок пользователя-рекрутера."""
    user = MagicMock()
    user.id = user_id
    user.tg_id = tg_id
    user.is_active = is_active
    user.company_id = company_id
    user.full_name = full_name
    user.phone_number = "+79991234567"
    user.registration_date = datetime(2026, 3, 12, 10, 55)
    return user


def make_unactivated_user(user_id=18, full_name="Daria Daria", phone="+79991991919"):
    """Мок неактивированного пользователя."""
    user = MagicMock()
    user.id = user_id
    user.full_name = full_name
    user.phone_number = phone
    user.registration_date = datetime(2026, 3, 12, 10, 55)
    user.is_activated = False
    user.company_id = 3
    return user


def make_state(initial_state=None, initial_data=None):
    """Мок FSMContext с реальным хранилищем состояния."""
    state = AsyncMock()
    _state_value = initial_state
    _data = initial_data or {}

    async def get_state():
        return _state_value

    async def set_state(new_state):
        nonlocal _state_value
        _state_value = new_state

    async def get_data():
        return _data.copy()

    async def update_data(**kwargs):
        _data.update(kwargs)

    async def clear():
        nonlocal _state_value
        _state_value = None
        _data.clear()

    state.get_state = AsyncMock(side_effect=get_state)
    state.set_state = AsyncMock(side_effect=set_state)
    state.get_data = AsyncMock(side_effect=get_data)
    state.update_data = AsyncMock(side_effect=update_data)
    state.clear = AsyncMock(side_effect=clear)

    return state, _data


def make_role(name="Стажер"):
    """Мок роли."""
    role = MagicMock()
    role.name = name
    return role


# --- Phase 1: callback_show_new_users ---


class TestCallbackShowNewUsers:
    """Тесты для inline-кнопки 'Новые пользователи' из уведомления."""

    @pytest.mark.asyncio
    async def test_unregistered_user_blocked(self):
        """Незарегистрированный пользователь получает ошибку."""
        from bot.handlers.users.user_activation import callback_show_new_users

        callback = make_callback()
        state, _ = make_state()
        session = AsyncMock()

        with patch("bot.handlers.users.user_activation.get_user_by_tg_id", return_value=None):
            await callback_show_new_users(callback, state, session)

        callback.answer.assert_awaited()
        call_args = callback.answer.call_args
        assert "не зарегистрирован" in call_args.kwargs.get("text", call_args.args[0] if call_args.args else "")

    @pytest.mark.asyncio
    async def test_inactive_user_blocked(self):
        """Деактивированный пользователь получает ошибку."""
        from bot.handlers.users.user_activation import callback_show_new_users

        callback = make_callback()
        state, _ = make_state()
        session = AsyncMock()
        user = make_user(is_active=False)

        with patch("bot.handlers.users.user_activation.get_user_by_tg_id", return_value=user):
            await callback_show_new_users(callback, state, session)

        callback.answer.assert_awaited()
        call_args = callback.answer.call_args
        assert "деактивирован" in call_args.kwargs.get("text", call_args.args[0] if call_args.args else "")

    @pytest.mark.asyncio
    async def test_no_permission_blocked(self):
        """Пользователь без прав manage_groups получает ошибку."""
        from bot.handlers.users.user_activation import callback_show_new_users

        callback = make_callback()
        state, _ = make_state()
        session = AsyncMock()
        user = make_user()

        with (
            patch("bot.handlers.users.user_activation.get_user_by_tg_id", return_value=user),
            patch("bot.handlers.users.user_activation.check_user_permission", return_value=False),
        ):
            await callback_show_new_users(callback, state, session)

        callback.answer.assert_awaited()
        call_args = callback.answer.call_args
        assert "прав" in call_args.kwargs.get("text", call_args.args[0] if call_args.args else "").lower()

    @pytest.mark.asyncio
    async def test_no_company_id_blocked(self):
        """Без company_id — ошибка."""
        from bot.handlers.users.user_activation import callback_show_new_users

        callback = make_callback()
        state, _ = make_state()
        session = AsyncMock()
        user = make_user()

        with (
            patch("bot.handlers.users.user_activation.get_user_by_tg_id", return_value=user),
            patch("bot.handlers.users.user_activation.check_user_permission", return_value=True),
            patch("bot.handlers.users.user_activation.ensure_company_id", return_value=None),
        ):
            await callback_show_new_users(callback, state, session)

        callback.answer.assert_awaited()

    @pytest.mark.asyncio
    async def test_no_unactivated_users_shows_empty(self):
        """Если нет неактивированных пользователей — показываем сообщение."""
        from bot.handlers.users.user_activation import callback_show_new_users

        callback = make_callback()
        state, _ = make_state()
        session = AsyncMock()
        user = make_user()

        with (
            patch("bot.handlers.users.user_activation.get_user_by_tg_id", return_value=user),
            patch("bot.handlers.users.user_activation.check_user_permission", return_value=True),
            patch("bot.handlers.users.user_activation.ensure_company_id", return_value=3),
            patch("bot.handlers.users.user_activation.get_unactivated_users", return_value=[]),
        ):
            await callback_show_new_users(callback, state, session)

        # Должно отредактировать уведомление — "Все пользователи активированы"
        callback.message.edit_text.assert_awaited_once()
        text = callback.message.edit_text.call_args.args[0]
        assert "активирован" in text.lower()
        callback.answer.assert_awaited()

    @pytest.mark.asyncio
    async def test_shows_user_list_and_sets_state(self):
        """Главный тест: кнопка редактирует уведомление, показывая список и устанавливая FSM-состояние."""
        from bot.handlers.users.user_activation import callback_show_new_users

        callback = make_callback()
        state, state_data = make_state()
        session = AsyncMock()
        user = make_user()
        unactivated = [make_unactivated_user(user_id=18, full_name="Daria Daria")]

        with (
            patch("bot.handlers.users.user_activation.get_user_by_tg_id", return_value=user),
            patch("bot.handlers.users.user_activation.check_user_permission", return_value=True),
            patch("bot.handlers.users.user_activation.ensure_company_id", return_value=3),
            patch("bot.handlers.users.user_activation.get_unactivated_users", return_value=unactivated),
            patch("bot.handlers.users.user_activation.get_new_users_list_keyboard") as mock_kb,
        ):
            mock_kb.return_value = MagicMock()
            await callback_show_new_users(callback, state, session)

        # 1. Редактирует уведомление, показывая список (edit_text, не answer)
        callback.message.edit_text.assert_awaited_once()
        text = callback.message.edit_text.call_args.args[0]
        assert "Новые пользователи" in text
        assert "1" in text  # количество пользователей

        # 2. Устанавливает правильное состояние
        state.set_state.assert_awaited()
        set_state_arg = state.set_state.call_args.args[0]
        assert set_state_arg == UserActivationStates.waiting_for_user_selection

        # 3. Сохраняет данные в state
        state.update_data.assert_awaited()
        assert state_data.get("current_new_users") == unactivated
        assert state_data.get("current_page") == 0

        # 4. Отвечает на callback (чтобы убрать loading на кнопке)
        callback.answer.assert_awaited()

        # 5. Передана клавиатура с пользователями
        mock_kb.assert_called_once_with(unactivated, 0, 5)
        call_kwargs = callback.message.edit_text.call_args.kwargs
        assert "reply_markup" in call_kwargs


# --- Phase 2: process_user_selection (после показа списка) ---


class TestProcessUserSelection:
    """Тесты для выбора пользователя из списка (шаг после показа)."""

    @pytest.mark.asyncio
    async def test_user_not_found(self):
        """Если пользователь удалён — ошибка."""
        from bot.handlers.users.user_activation import process_user_selection

        callback = make_callback(callback_data="activate_user:18")
        state, _ = make_state(initial_state=UserActivationStates.waiting_for_user_selection)
        session = AsyncMock()

        with patch("bot.handlers.users.user_activation.get_user_by_id", return_value=None):
            await process_user_selection(callback, state, session)

        callback.message.edit_text.assert_awaited_once()
        text = callback.message.edit_text.call_args.args[0]
        assert "не найден" in text.lower()

    @pytest.mark.asyncio
    async def test_already_activated_user(self):
        """Уже активированный пользователь — ошибка."""
        from bot.handlers.users.user_activation import process_user_selection

        callback = make_callback(callback_data="activate_user:18")
        state, _ = make_state(initial_state=UserActivationStates.waiting_for_user_selection)
        session = AsyncMock()
        user = make_unactivated_user()
        user.is_activated = True

        with patch("bot.handlers.users.user_activation.get_user_by_id", return_value=user):
            await process_user_selection(callback, state, session)

        callback.message.edit_text.assert_awaited_once()
        text = callback.message.edit_text.call_args.args[0]
        assert "уже активирован" in text.lower()

    @pytest.mark.asyncio
    async def test_successful_selection_shows_roles(self):
        """После выбора пользователя — показывает выбор роли."""
        from bot.handlers.users.user_activation import process_user_selection

        callback = make_callback(callback_data="activate_user:18")
        state, state_data = make_state(initial_state=UserActivationStates.waiting_for_user_selection)
        session = AsyncMock()
        user = make_unactivated_user()
        roles = [make_role("Стажер"), make_role("Наставник"), make_role("Руководитель")]

        with (
            patch("bot.handlers.users.user_activation.get_user_by_id", return_value=user),
            patch("bot.handlers.users.user_activation.get_all_roles", return_value=roles),
        ):
            await process_user_selection(callback, state, session)

        # 1. Сохраняет ID выбранного пользователя
        assert state_data.get("selected_user_id") == 18

        # 2. Показывает выбор роли
        callback.message.edit_text.assert_awaited_once()
        text = callback.message.edit_text.call_args.args[0]
        assert "роль" in text.lower()
        assert "Daria Daria" in text

        # 3. Устанавливает состояние ожидания роли
        state.set_state.assert_awaited()
        # Последний вызов set_state должен быть waiting_for_role_selection
        last_set = state.set_state.call_args_list[-1].args[0]
        assert last_set == UserActivationStates.waiting_for_role_selection

        # 4. Отвечает на callback
        callback.answer.assert_awaited()


# --- Phase 3: full flow от уведомления до выбора роли ---


class TestFullNotificationFlow:
    """Интеграционный тест: полный flow от клика в уведомлении до выбора роли."""

    @pytest.mark.asyncio
    async def test_notification_button_to_role_selection(self):
        """
        Воспроизведение бага: полный flow от клика кнопки в уведомлении.

        1. Клик 'Новые пользователи' в уведомлении → список пользователей
        2. Клик на пользователя из списка → выбор роли
        """
        from bot.handlers.users.user_activation import (
            callback_show_new_users,
            process_user_selection,
        )

        recruiter = make_user(user_id=1, tg_id=453388874)
        new_user = make_unactivated_user(user_id=18, full_name="Daria Daria")
        roles = [make_role("Стажер"), make_role("Наставник")]
        session = AsyncMock()

        # --- Step 1: Клик на кнопку "Новые пользователи" в уведомлении ---
        callback1 = make_callback(callback_data="show_new_users")
        state, state_data = make_state()

        with (
            patch("bot.handlers.users.user_activation.get_user_by_tg_id", return_value=recruiter),
            patch("bot.handlers.users.user_activation.check_user_permission", return_value=True),
            patch("bot.handlers.users.user_activation.ensure_company_id", return_value=3),
            patch("bot.handlers.users.user_activation.get_unactivated_users", return_value=[new_user]),
            patch("bot.handlers.users.user_activation.get_new_users_list_keyboard") as mock_kb,
        ):
            mock_kb.return_value = MagicMock()
            await callback_show_new_users(callback1, state, session)

        # Проверяем: уведомление отредактировано со списком, состояние установлено
        callback1.message.edit_text.assert_awaited_once()
        assert await state.get_state() == UserActivationStates.waiting_for_user_selection
        assert state_data.get("current_new_users") == [new_user]

        # --- Step 2: Клик на пользователя из списка ---
        callback2 = make_callback(callback_data="activate_user:18")

        with (
            patch("bot.handlers.users.user_activation.get_user_by_id", return_value=new_user),
            patch("bot.handlers.users.user_activation.get_all_roles", return_value=roles),
        ):
            await process_user_selection(callback2, state, session)

        # Проверяем: роли показаны, состояние обновлено
        callback2.message.edit_text.assert_awaited_once()
        text = callback2.message.edit_text.call_args.args[0]
        assert "роль" in text.lower()
        assert "Daria Daria" in text

        # Финальное состояние — ожидание выбора роли
        assert await state.get_state() == UserActivationStates.waiting_for_role_selection
        assert state_data.get("selected_user_id") == 18

    @pytest.mark.asyncio
    async def test_notification_button_while_in_other_state(self):
        """
        Кнопка уведомления должна работать даже если рекрутер в другом FSM-состоянии.

        Например, рекрутер создаёт тест и получает уведомление о новом пользователе.
        """
        from bot.handlers.users.user_activation import callback_show_new_users

        recruiter = make_user()
        new_user = make_unactivated_user()
        session = AsyncMock()

        # Рекрутер в каком-то другом состоянии
        callback = make_callback(callback_data="show_new_users")
        state, state_data = make_state(
            initial_state="SomeOtherState:waiting_for_something",
            initial_data={"some_key": "some_value"},
        )

        with (
            patch("bot.handlers.users.user_activation.get_user_by_tg_id", return_value=recruiter),
            patch("bot.handlers.users.user_activation.check_user_permission", return_value=True),
            patch("bot.handlers.users.user_activation.ensure_company_id", return_value=3),
            patch("bot.handlers.users.user_activation.get_unactivated_users", return_value=[new_user]),
            patch("bot.handlers.users.user_activation.get_new_users_list_keyboard") as mock_kb,
        ):
            mock_kb.return_value = MagicMock()
            await callback_show_new_users(callback, state, session)

        # Состояние должно быть перезаписано на waiting_for_user_selection
        assert await state.get_state() == UserActivationStates.waiting_for_user_selection
        callback.message.edit_text.assert_awaited_once()
