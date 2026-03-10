"""Тесты для handlers/core/registration.py — выживающая функциональность."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

REG = "bot.handlers.core.registration"


def make_message(user_id=123, username="testuser", text="+79991234567"):
    """Создаёт мок Message."""
    msg = AsyncMock()
    msg.from_user = MagicMock()
    msg.from_user.id = user_id
    msg.from_user.username = username
    msg.text = text
    msg.contact = None
    return msg


def make_state(data=None):
    """Создаёт мок FSMContext."""
    state = AsyncMock()
    state.get_data = AsyncMock(return_value=data or {})
    state.update_data = AsyncMock()
    state.set_state = AsyncMock()
    state.clear = AsyncMock()
    return state


def make_callback(user_id=123, username="testuser", data=""):
    """Создаёт мок CallbackQuery."""
    callback = AsyncMock()
    callback.from_user = MagicMock()
    callback.from_user.id = user_id
    callback.from_user.username = username
    callback.data = data
    callback.message = AsyncMock()
    callback.answer = AsyncMock()
    return callback


# --- _clear_state_if_no_company ---


class TestClearStateIfNoCompany:
    @pytest.mark.asyncio
    async def test_clears_when_no_company(self):
        """Без company_id → state.clear() вызывается."""
        from bot.handlers.core.registration import _clear_state_if_no_company

        state = make_state()
        await _clear_state_if_no_company(state, {})
        state.clear.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_preserves_when_company_present(self):
        """С company_id → state.clear() НЕ вызывается."""
        from bot.handlers.core.registration import _clear_state_if_no_company

        state = make_state()
        await _clear_state_if_no_company(state, {"company_id": 42})
        state.clear.assert_not_awaited()


# --- _complete_phone_registration ---


class TestCompletePhoneRegistration:
    @pytest.mark.asyncio
    async def test_creates_user_and_sends_success(self):
        """Вызывает create_user_without_role, отправляет 'Регистрация завершена', state.clear()."""
        from bot.handlers.core.registration import _complete_phone_registration

        msg = make_message()
        state = make_state(data={"full_name": "Иванов Иван", "phone_number": "+79991234567"})
        session = AsyncMock()
        bot = AsyncMock()

        with patch(f"{REG}.create_user_without_role", new_callable=AsyncMock) as mock_create:
            await _complete_phone_registration(msg, state, session, bot)

        mock_create.assert_awaited_once_with(session, state.get_data.return_value, bot)
        assert any("Регистрация завершена" in str(c) for c in msg.answer.call_args_list)
        state.clear.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_sets_tg_id_and_username(self):
        """user_data получает tg_id и username из message.from_user."""
        from bot.handlers.core.registration import _complete_phone_registration

        msg = make_message(user_id=999, username="myuser")
        captured_data = {"full_name": "Тест Тестов", "phone_number": "+79990000000"}
        state = make_state(data=captured_data)
        session = AsyncMock()
        bot = AsyncMock()

        with patch(f"{REG}.create_user_without_role", new_callable=AsyncMock):
            await _complete_phone_registration(msg, state, session, bot)

        assert captured_data["tg_id"] == 999
        assert captured_data["username"] == "myuser"

    @pytest.mark.asyncio
    async def test_error_clears_state_without_company(self):
        """Исключение + нет company_id → state.clear()."""
        from bot.handlers.core.registration import _complete_phone_registration

        msg = make_message()
        state = make_state(data={"full_name": "Тест", "phone_number": "+79990000000"})
        session = AsyncMock()
        bot = AsyncMock()

        with patch(f"{REG}.create_user_without_role", side_effect=Exception("db error")):
            await _complete_phone_registration(msg, state, session, bot)

        state.clear.assert_awaited_once()
        assert any("ошибка" in str(c).lower() or "Ошибка" in str(c) for c in msg.answer.call_args_list)

    @pytest.mark.asyncio
    async def test_error_preserves_state_with_company(self):
        """Исключение + есть company_id → state НЕ очищается."""
        from bot.handlers.core.registration import _complete_phone_registration

        msg = make_message()
        state = make_state(data={"full_name": "Тест", "phone_number": "+79990000000", "company_id": 5})
        session = AsyncMock()
        bot = AsyncMock()

        with patch(f"{REG}.create_user_without_role", side_effect=Exception("db error")):
            await _complete_phone_registration(msg, state, session, bot)

        state.clear.assert_not_awaited()


# --- process_full_name ---


class TestProcessFullName:
    @pytest.mark.asyncio
    async def test_valid_name_transitions_to_phone(self):
        """Валидное имя → update_data + set_state(waiting_for_phone)."""
        from bot.handlers.core.registration import process_full_name

        msg = make_message(text="Иванов Иван")
        state = make_state()

        with patch(f"{REG}.validate_full_name", return_value=(True, "Иванов Иван")):
            await process_full_name(msg, state)

        state.update_data.assert_awaited_once_with(full_name="Иванов Иван")
        state.set_state.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_invalid_name_shows_error(self):
        """Невалидное имя → ошибка, state не меняется."""
        from bot.handlers.core.registration import process_full_name

        msg = make_message(text="123")
        state = make_state()

        with patch(f"{REG}.validate_full_name", return_value=(False, None)):
            await process_full_name(msg, state)

        msg.answer.assert_awaited_once()
        assert "Некорректный" in msg.answer.call_args[0][0]
        state.update_data.assert_not_awaited()
        state.set_state.assert_not_awaited()


# --- process_contact ---


class TestProcessContact:
    @pytest.mark.asyncio
    async def test_valid_contact_completes(self):
        """Нормализует телефон, вызывает _complete_phone_registration."""
        from bot.handlers.core.registration import process_contact

        msg = make_message()
        msg.contact = MagicMock()
        msg.contact.phone_number = "89991234567"
        state = make_state()
        session = AsyncMock()
        bot = AsyncMock()

        with (
            patch(f"{REG}.validate_phone_number", return_value=(True, "+79991234567")),
            patch(f"{REG}.check_phone_exists", return_value=False),
            patch(f"{REG}._complete_phone_registration", new_callable=AsyncMock) as mock_complete,
        ):
            await process_contact(msg, state, session, bot)

        state.update_data.assert_awaited_once_with(phone_number="+79991234567")
        mock_complete.assert_awaited_once_with(msg, state, session, bot)

    @pytest.mark.asyncio
    async def test_invalid_phone_shows_error(self):
        """Невалидный телефон → показывает ошибку."""
        from bot.handlers.core.registration import process_contact

        msg = make_message()
        msg.contact = MagicMock()
        msg.contact.phone_number = "123"
        state = make_state()
        session = AsyncMock()
        bot = AsyncMock()

        with patch(f"{REG}.validate_phone_number", return_value=(False, None)):
            await process_contact(msg, state, session, bot)

        msg.answer.assert_awaited_once()
        assert "Некорректный" in msg.answer.call_args[0][0]

    @pytest.mark.asyncio
    async def test_existing_phone_blocks(self):
        """Дубликат телефона → ошибка + _clear_state_if_no_company."""
        from bot.handlers.core.registration import process_contact

        msg = make_message()
        msg.contact = MagicMock()
        msg.contact.phone_number = "+79991234567"
        state = make_state(data={})
        session = AsyncMock()
        bot = AsyncMock()

        with (
            patch(f"{REG}.validate_phone_number", return_value=(True, "+79991234567")),
            patch(f"{REG}.check_phone_exists", return_value=True),
            patch(f"{REG}._clear_state_if_no_company", new_callable=AsyncMock) as mock_clear,
        ):
            await process_contact(msg, state, session, bot)

        assert any("уже зарегистрирован" in str(c) for c in msg.answer.call_args_list)
        mock_clear.assert_awaited_once()


# --- process_phone_manually ---


class TestProcessPhoneManually:
    @pytest.mark.asyncio
    async def test_valid_phone_completes(self):
        """Валидный телефон → вызывает _complete_phone_registration."""
        from bot.handlers.core.registration import process_phone_manually

        msg = make_message(text="+79991234567")
        state = make_state()
        session = AsyncMock()
        bot = AsyncMock()

        with (
            patch(f"{REG}.validate_phone_number", return_value=(True, "+79991234567")),
            patch(f"{REG}.check_phone_exists", return_value=False),
            patch(f"{REG}._complete_phone_registration", new_callable=AsyncMock) as mock_complete,
        ):
            await process_phone_manually(msg, state, session, bot)

        state.update_data.assert_awaited_once_with(phone_number="+79991234567")
        mock_complete.assert_awaited_once_with(msg, state, session, bot)

    @pytest.mark.asyncio
    async def test_invalid_phone_shows_error(self):
        """Невалидный телефон → ошибка."""
        from bot.handlers.core.registration import process_phone_manually

        msg = make_message(text="abc")
        state = make_state()
        session = AsyncMock()
        bot = AsyncMock()

        with patch(f"{REG}.validate_phone_number", return_value=(False, None)):
            await process_phone_manually(msg, state, session, bot)

        msg.answer.assert_awaited_once()
        assert "Некорректный" in msg.answer.call_args[0][0]

    @pytest.mark.asyncio
    async def test_existing_phone_blocks(self):
        """Дубликат телефона → ошибка + _clear_state_if_no_company."""
        from bot.handlers.core.registration import process_phone_manually

        msg = make_message(text="+79991234567")
        state = make_state(data={})
        session = AsyncMock()
        bot = AsyncMock()

        with (
            patch(f"{REG}.validate_phone_number", return_value=(True, "+79991234567")),
            patch(f"{REG}.check_phone_exists", return_value=True),
            patch(f"{REG}._clear_state_if_no_company", new_callable=AsyncMock) as mock_clear,
        ):
            await process_phone_manually(msg, state, session, bot)

        assert any("уже зарегистрирован" in str(c) for c in msg.answer.call_args_list)
        mock_clear.assert_awaited_once()


# --- role_selection_error ---


class TestRoleSelectionError:
    @pytest.mark.asyncio
    async def test_shows_fallback_message(self):
        """Отправляет 'Пожалуйста, выберите роль из предложенного списка.'"""
        from bot.handlers.core.registration import role_selection_error

        msg = make_message(text="random text")

        await role_selection_error(msg)

        msg.answer.assert_awaited_once_with("Пожалуйста, выберите роль из предложенного списка.")
