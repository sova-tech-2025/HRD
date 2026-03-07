"""Тесты для handlers/core/fallback.py — fallback-обработчики неожиданного ввода."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def make_message(
    text=None,
    photo=None,
    audio=None,
    voice=None,
    video_note=None,
    sticker=None,
    document=None,
    media_group_id=None,
    user_id=123,
    username="testuser",
):
    """Создаёт мок Message с нужными атрибутами."""
    msg = AsyncMock()
    msg.from_user = MagicMock()
    msg.from_user.id = user_id
    msg.from_user.username = username
    msg.text = text
    msg.photo = photo
    msg.audio = audio
    msg.voice = voice
    msg.video_note = video_note
    msg.sticker = sticker
    msg.document = document
    msg.media_group_id = media_group_id
    msg.answer = AsyncMock()
    return msg


def make_state(data=None, state_name=None):
    """Создаёт мок FSMContext."""
    state = AsyncMock()
    state.get_data = AsyncMock(return_value=data or {})
    state.get_state = AsyncMock(return_value=state_name)
    state.clear = AsyncMock()
    state.update_data = AsyncMock()
    return state


# =================================
# send_fallback_message
# =================================


class TestSendFallbackMessage:
    @pytest.mark.asyncio
    async def test_sends_fallback_with_keyboard(self):
        """send_fallback_message отправляет сообщение с клавиатурой"""
        from utils.messages.fallback import send_fallback_message

        msg = make_message()
        state = make_state()

        with patch("utils.messages.fallback.get_fallback_keyboard", return_value="kb_mock"):
            await send_fallback_message(msg, state)

        msg.answer.assert_awaited_once()
        call_kwargs = msg.answer.call_args
        assert "Команда не распознана" in call_kwargs[0][0]
        assert call_kwargs[1]["reply_markup"] == "kb_mock"
        assert call_kwargs[1]["parse_mode"] == "HTML"


# =================================
# send_use_buttons_message
# =================================


class TestSendUseButtonsMessage:
    @pytest.mark.asyncio
    async def test_sends_use_buttons(self):
        """send_use_buttons_message отправляет подсказку про кнопки"""
        from utils.messages.fallback import send_use_buttons_message

        msg = make_message()
        await send_use_buttons_message(msg)

        msg.answer.assert_awaited_once()
        text = msg.answer.call_args[0][0]
        assert "кнопки" in text
        assert "Некорректный выбор" in text


# =================================
# Регистрация: ввод имени
# =================================


class TestUnexpectedNameInput:
    @pytest.mark.asyncio
    async def test_short_name_shows_error(self):
        """Имя < 2 символов — ошибка валидации"""
        from handlers.fallback.registration import handle_unexpected_name_input

        msg = make_message(text="А")
        state = make_state()

        await handle_unexpected_name_input(msg, state)

        text = msg.answer.call_args[0][0]
        assert "Некорректное имя" in text
        assert "минимум 2 символа" in text

    @pytest.mark.asyncio
    async def test_empty_text_shows_error(self):
        """Пустой текст — ошибка валидации"""
        from handlers.fallback.registration import handle_unexpected_name_input

        msg = make_message(text=None)
        state = make_state()

        await handle_unexpected_name_input(msg, state)

        text = msg.answer.call_args[0][0]
        assert "Некорректное имя" in text

    @pytest.mark.asyncio
    async def test_valid_name_gets_fallback(self):
        """Имя >= 2 символов — стандартный fallback"""
        from handlers.fallback.registration import handle_unexpected_name_input

        msg = make_message(text="Иван Петров")
        state = make_state()

        with patch("utils.messages.fallback.get_fallback_keyboard", return_value="kb"):
            await handle_unexpected_name_input(msg, state)

        text = msg.answer.call_args[0][0]
        assert "Команда не распознана" in text


# =================================
# Создание тестов: материалы
# =================================


class TestUnexpectedMaterialsInput:
    @pytest.mark.asyncio
    async def test_photo_rejected(self):
        """Фото — специфическое сообщение об ошибке"""
        from handlers.fallback.tests import handle_unexpected_materials_input

        msg = make_message(photo=[MagicMock()])
        state = make_state()

        await handle_unexpected_materials_input(msg, state)

        text = msg.answer.call_args[0][0]
        assert "Изображения не поддерживаются" in text

    @pytest.mark.asyncio
    async def test_audio_rejected(self):
        """Аудио — специфическое сообщение"""
        from handlers.fallback.tests import handle_unexpected_materials_input

        msg = make_message(audio=MagicMock())
        state = make_state()

        await handle_unexpected_materials_input(msg, state)

        text = msg.answer.call_args[0][0]
        assert "Аудио/голосовые" in text

    @pytest.mark.asyncio
    async def test_voice_rejected(self):
        """Голосовое сообщение — специфическое сообщение"""
        from handlers.fallback.tests import handle_unexpected_materials_input

        msg = make_message(voice=MagicMock())
        state = make_state()

        await handle_unexpected_materials_input(msg, state)

        text = msg.answer.call_args[0][0]
        assert "Аудио/голосовые" in text

    @pytest.mark.asyncio
    async def test_sticker_rejected(self):
        """Стикер — специфическое сообщение"""
        from handlers.fallback.tests import handle_unexpected_materials_input

        msg = make_message(sticker=MagicMock())
        state = make_state()

        await handle_unexpected_materials_input(msg, state)

        text = msg.answer.call_args[0][0]
        assert "Стикеры не поддерживаются" in text

    @pytest.mark.asyncio
    async def test_unknown_input_retry(self):
        """Прочий ввод — просьба повторить"""
        from handlers.fallback.tests import handle_unexpected_materials_input

        msg = make_message()
        state = make_state()

        await handle_unexpected_materials_input(msg, state)

        text = msg.answer.call_args[0][0]
        assert "Повтори ввод" in text


# =================================
# Создание тестов: название теста
# =================================


class TestUnexpectedTestNameInput:
    @pytest.mark.asyncio
    async def test_short_name_error(self):
        """Название < 3 символов — ошибка"""
        from handlers.fallback.tests import handle_unexpected_test_name_input

        msg = make_message(text="АБ")
        state = make_state()

        await handle_unexpected_test_name_input(msg, state)

        text = msg.answer.call_args[0][0]
        assert "Некорректное название" in text
        assert "минимум 3 символа" in text

    @pytest.mark.asyncio
    async def test_empty_name_error(self):
        """Пустое название — ошибка"""
        from handlers.fallback.tests import handle_unexpected_test_name_input

        msg = make_message(text=None)
        state = make_state()

        await handle_unexpected_test_name_input(msg, state)

        text = msg.answer.call_args[0][0]
        assert "Некорректное название" in text

    @pytest.mark.asyncio
    async def test_valid_name_retry(self):
        """Валидное название — просьба повторить"""
        from handlers.fallback.tests import handle_unexpected_test_name_input

        msg = make_message(text="Хороший тест")
        state = make_state()

        await handle_unexpected_test_name_input(msg, state)

        text = msg.answer.call_args[0][0]
        assert "Повтори ввод" in text


# =================================
# Создание тестов: текст вопроса
# =================================


class TestUnexpectedQuestionTextInput:
    @pytest.mark.asyncio
    async def test_short_question_error(self):
        """Вопрос < 5 символов — ошибка"""
        from handlers.fallback.tests import handle_unexpected_question_text_input

        msg = make_message(text="Кто?")
        state = make_state()

        await handle_unexpected_question_text_input(msg, state)

        text = msg.answer.call_args[0][0]
        assert "Слишком короткий вопрос" in text

    @pytest.mark.asyncio
    async def test_valid_question_retry(self):
        """Валидный вопрос — просьба повторить"""
        from handlers.fallback.tests import handle_unexpected_question_text_input

        msg = make_message(text="Какой правильный ответ?")
        state = make_state()

        await handle_unexpected_question_text_input(msg, state)

        text = msg.answer.call_args[0][0]
        assert "Повтори ввод" in text


# =================================
# Создание тестов: правильный ответ (зависит от типа вопроса)
# =================================


class TestUnexpectedAnswerInput:
    @pytest.mark.asyncio
    async def test_single_choice_hint(self):
        """single_choice — подсказка ввести номер"""
        from handlers.fallback.tests import handle_unexpected_answer_input

        msg = make_message()
        state = make_state(data={"current_question_type": "single_choice"})

        await handle_unexpected_answer_input(msg, state)

        text = msg.answer.call_args[0][0]
        assert "номер правильного ответа" in text

    @pytest.mark.asyncio
    async def test_multiple_choice_hint(self):
        """multiple_choice — подсказка ввести номера через запятую"""
        from handlers.fallback.tests import handle_unexpected_answer_input

        msg = make_message()
        state = make_state(data={"current_question_type": "multiple_choice"})

        await handle_unexpected_answer_input(msg, state)

        text = msg.answer.call_args[0][0]
        assert "через запятую" in text

    @pytest.mark.asyncio
    async def test_unknown_type_retry(self):
        """Неизвестный тип — общая просьба повторить"""
        from handlers.fallback.tests import handle_unexpected_answer_input

        msg = make_message()
        state = make_state(data={"current_question_type": "open_text"})

        await handle_unexpected_answer_input(msg, state)

        text = msg.answer.call_args[0][0]
        assert "Повтори ввод" in text


# =================================
# Создание тестов: баллы
# =================================


class TestUnexpectedPointsInput:
    @pytest.mark.asyncio
    async def test_negative_points_error(self):
        """Отрицательные баллы — ошибка"""
        from handlers.fallback.tests import handle_unexpected_points_input

        msg = make_message(text="-5")
        state = make_state()

        await handle_unexpected_points_input(msg, state)

        text = msg.answer.call_args[0][0]
        assert "больше нуля" in text

    @pytest.mark.asyncio
    async def test_zero_points_error(self):
        """Ноль баллов — ошибка"""
        from handlers.fallback.tests import handle_unexpected_points_input

        msg = make_message(text="0")
        state = make_state()

        await handle_unexpected_points_input(msg, state)

        text = msg.answer.call_args[0][0]
        assert "больше нуля" in text

    @pytest.mark.asyncio
    async def test_non_numeric_error(self):
        """Не число — ошибка"""
        from handlers.fallback.tests import handle_unexpected_points_input

        msg = make_message(text="abc")
        state = make_state()

        await handle_unexpected_points_input(msg, state)

        text = msg.answer.call_args[0][0]
        assert "Некорректное количество баллов" in text

    @pytest.mark.asyncio
    async def test_empty_text_error(self):
        """Пустое сообщение — ошибка"""
        from handlers.fallback.tests import handle_unexpected_points_input

        msg = make_message(text=None)
        state = make_state()

        await handle_unexpected_points_input(msg, state)

        text = msg.answer.call_args[0][0]
        assert "Пустое значение" in text

    @pytest.mark.asyncio
    async def test_valid_positive_points(self):
        """Корректные баллы — неожиданная ошибка (повтор)"""
        from handlers.fallback.tests import handle_unexpected_points_input

        msg = make_message(text="5")
        state = make_state()

        await handle_unexpected_points_input(msg, state)

        text = msg.answer.call_args[0][0]
        assert "Повтори ввод" in text or "Неожиданная ошибка" in text

    @pytest.mark.asyncio
    async def test_comma_decimal_parsed(self):
        """Запятая как десятичный разделитель — парсится корректно"""
        from handlers.fallback.tests import handle_unexpected_points_input

        msg = make_message(text="2,5")
        state = make_state()

        await handle_unexpected_points_input(msg, state)

        # 2.5 > 0, поэтому не ошибка "больше нуля"
        text = msg.answer.call_args[0][0]
        assert "больше нуля" not in text


# =================================
# Создание тестов: проходной балл
# =================================


class TestUnexpectedThresholdInput:
    @pytest.mark.asyncio
    async def test_shows_max_score(self):
        """Показывает максимальный балл из вопросов"""
        from handlers.fallback.tests import handle_unexpected_threshold_input

        msg = make_message(text="abc")
        state = make_state(data={"questions": [{"points": 5}, {"points": 10}]})

        await handle_unexpected_threshold_input(msg, state)

        text = msg.answer.call_args[0][0]
        assert "15.0" in text

    @pytest.mark.asyncio
    async def test_empty_questions_default_100(self):
        """Нет вопросов — max_score = 100"""
        from handlers.fallback.tests import handle_unexpected_threshold_input

        msg = make_message(text="abc")
        state = make_state(data={})

        await handle_unexpected_threshold_input(msg, state)

        text = msg.answer.call_args[0][0]
        assert "100.0" in text


# =================================
# Прохождение теста: зависит от типа вопроса
# =================================


class TestUnexpectedTestInput:
    @pytest.mark.asyncio
    async def test_no_questions_clears_state(self):
        """Нет вопросов — ошибка и очистка state"""
        from handlers.fallback.tests import handle_unexpected_test_input

        msg = make_message()
        state = make_state(data={"questions": []})

        await handle_unexpected_test_input(msg, state)

        state.clear.assert_awaited_once()
        text = msg.answer.call_args[0][0]
        assert "Ошибка теста" in text

    @pytest.mark.asyncio
    async def test_index_beyond_questions_completed(self):
        """Индекс >= длины вопросов — тест завершен"""
        from handlers.fallback.tests import handle_unexpected_test_input

        q = MagicMock()
        msg = make_message()
        state = make_state(data={"questions": [q], "current_question_index": 5})

        await handle_unexpected_test_input(msg, state)

        text = msg.answer.call_args[0][0]
        assert "Тест завершен" in text

    @pytest.mark.asyncio
    async def test_text_question_retry(self):
        """Текстовый вопрос — просьба повторить"""
        from handlers.fallback.tests import handle_unexpected_test_input

        q = MagicMock()
        q.question_type = "text"
        msg = make_message()
        state = make_state(data={"questions": [q], "current_question_index": 0})

        await handle_unexpected_test_input(msg, state)

        text = msg.answer.call_args[0][0]
        assert "Повтори ответ" in text

    @pytest.mark.asyncio
    async def test_number_question_error(self):
        """Числовой вопрос — подсказка ввести число"""
        from handlers.fallback.tests import handle_unexpected_test_input

        q = MagicMock()
        q.question_type = "number"
        msg = make_message()
        state = make_state(data={"questions": [q], "current_question_index": 0})

        await handle_unexpected_test_input(msg, state)

        text = msg.answer.call_args[0][0]
        assert "числовой" in text.lower() or "число" in text.lower()

    @pytest.mark.asyncio
    async def test_multiple_choice_question_hint(self):
        """Вопрос multiple_choice — подсказка с форматом"""
        from handlers.fallback.tests import handle_unexpected_test_input

        q = MagicMock()
        q.question_type = "multiple_choice"
        msg = make_message()
        state = make_state(data={"questions": [q], "current_question_index": 0})

        await handle_unexpected_test_input(msg, state)

        text = msg.answer.call_args[0][0]
        assert "через запятую" in text

    @pytest.mark.asyncio
    async def test_unknown_question_type_fallback(self):
        """Неизвестный тип вопроса — стандартный fallback"""
        from handlers.fallback.tests import handle_unexpected_test_input

        q = MagicMock()
        q.question_type = "exotic_type"
        msg = make_message()
        state = make_state(data={"questions": [q], "current_question_index": 0})

        with patch("utils.messages.fallback.get_fallback_keyboard", return_value="kb"):
            await handle_unexpected_test_input(msg, state)

        text = msg.answer.call_args[0][0]
        assert "Команда не распознана" in text


# =================================
# Редактирование вопроса
# =================================


class TestUnexpectedQuestionEdit:
    @pytest.mark.asyncio
    async def test_short_question_error(self):
        """Короткий текст вопроса — ошибка"""
        from handlers.fallback.tests import handle_unexpected_question_edit

        msg = make_message(text="Кто")
        state = make_state()

        await handle_unexpected_question_edit(msg, state)

        text = msg.answer.call_args[0][0]
        assert "Слишком короткий" in text

    @pytest.mark.asyncio
    async def test_valid_question_retry(self):
        """Валидный текст — просьба повторить"""
        from handlers.fallback.tests import handle_unexpected_question_edit

        msg = make_message(text="Какой ответ правильный?")
        state = make_state()

        await handle_unexpected_question_edit(msg, state)

        text = msg.answer.call_args[0][0]
        assert "Повтори ввод" in text


# =================================
# Новый проходной балл
# =================================


class TestUnexpectedNewThreshold:
    @pytest.mark.asyncio
    async def test_zero_threshold_error(self):
        """Ноль — ошибка"""
        from handlers.fallback.tests import handle_unexpected_new_threshold

        msg = make_message(text="0")
        state = make_state()

        await handle_unexpected_new_threshold(msg, state)

        text = msg.answer.call_args[0][0]
        assert "больше нуля" in text

    @pytest.mark.asyncio
    async def test_not_a_number_error(self):
        """Не число — ошибка"""
        from handlers.fallback.tests import handle_unexpected_new_threshold

        msg = make_message(text="abc")
        state = make_state()

        await handle_unexpected_new_threshold(msg, state)

        text = msg.answer.call_args[0][0]
        assert "Некорректный проходной балл" in text

    @pytest.mark.asyncio
    async def test_valid_number_retry(self):
        """Валидное число — повтор"""
        from handlers.fallback.tests import handle_unexpected_new_threshold

        msg = make_message(text="7.5")
        state = make_state()

        await handle_unexpected_new_threshold(msg, state)

        text = msg.answer.call_args[0][0]
        assert "Повтори ввод" in text

    @pytest.mark.asyncio
    async def test_empty_text_error(self):
        """Пустой текст — ошибка"""
        from handlers.fallback.tests import handle_unexpected_new_threshold

        msg = make_message(text=None)
        state = make_state()

        await handle_unexpected_new_threshold(msg, state)

        text = msg.answer.call_args[0][0]
        assert "Пустое значение" in text


# =================================
# База знаний: создание папки
# =================================


class TestKnowledgeBaseFolderName:
    @pytest.mark.asyncio
    async def test_non_text_shows_error(self):
        """Не текст — ошибка формата"""
        from handlers.fallback.knowledge import handle_unexpected_folder_name_input

        msg = make_message(text=None)
        state = make_state()

        await handle_unexpected_folder_name_input(msg, state)

        text = msg.answer.call_args[0][0]
        assert "Неправильный формат" in text
        assert "текстом" in text

    @pytest.mark.asyncio
    async def test_text_input_no_answer(self):
        """Текстовый ввод — обработчик пропускает (обрабатывается основным handler)"""
        from handlers.fallback.knowledge import handle_unexpected_folder_name_input

        msg = make_message(text="Моя папка")
        state = make_state()

        await handle_unexpected_folder_name_input(msg, state)

        msg.answer.assert_not_awaited()


# =================================
# Универсальный fallback: текстовый ввод
# =================================


class TestUnexpectedInputWithState:
    @pytest.mark.asyncio
    async def test_unregistered_user_gets_welcome(self):
        """Незарегистрированный пользователь — приветствие с выбором компании"""
        from handlers.fallback.universal import handle_unexpected_input_with_state

        msg = make_message(text="Привет")
        state = make_state()
        session = AsyncMock()

        with (
            patch("handlers.fallback.universal.get_user_by_tg_id", return_value=None),
            patch("handlers.fallback.universal.log_user_action"),
        ):
            await handle_unexpected_input_with_state(msg, state, session)

        text = msg.answer.call_args[0][0]
        assert "Добро пожаловать" in text

    @pytest.mark.asyncio
    async def test_registered_user_with_state_gets_fallback(self):
        """Зарегистрированный пользователь в FSM-состоянии — fallback"""
        from handlers.fallback.universal import handle_unexpected_input_with_state

        msg = make_message(text="Что-то")
        state = make_state(state_name="SomeStates:some_state")
        session = AsyncMock()
        user = MagicMock()

        with (
            patch("handlers.fallback.universal.get_user_by_tg_id", return_value=user),
            patch("handlers.fallback.universal.get_fallback_keyboard", return_value="kb"),
            patch("handlers.fallback.universal.log_user_action"),
        ):
            await handle_unexpected_input_with_state(msg, state, session)

        text = msg.answer.call_args[0][0]
        assert "Команда не распознана" in text

    @pytest.mark.asyncio
    async def test_registered_user_no_state_gets_fallback(self):
        """Зарегистрированный пользователь без FSM-состояния — стандартный fallback"""
        from handlers.fallback.universal import handle_unexpected_input_with_state

        msg = make_message(text="Что-то")
        state = make_state(state_name=None)
        session = AsyncMock()
        user = MagicMock()

        with (
            patch("handlers.fallback.universal.get_user_by_tg_id", return_value=user),
            patch("utils.messages.fallback.get_fallback_keyboard", return_value="kb"),
        ):
            await handle_unexpected_input_with_state(msg, state, session)

        text = msg.answer.call_args[0][0]
        assert "Команда не распознана" in text


# =================================
# Callback query fallback
# =================================


class TestUnexpectedCallback:
    @pytest.mark.asyncio
    async def test_callback_answered_and_edited(self):
        """Неожиданный callback — edit_text + answer"""
        from handlers.fallback.universal import handle_unexpected_callback

        callback = AsyncMock()
        callback.from_user = MagicMock()
        callback.from_user.id = 123
        callback.from_user.username = "testuser"
        callback.data = "unknown_action"
        callback.message = AsyncMock()
        callback.message.edit_text = AsyncMock()
        callback.answer = AsyncMock()

        state = make_state(state_name="SomeState")

        with (
            patch("handlers.fallback.universal.get_fallback_keyboard", return_value="kb"),
            patch("handlers.fallback.universal.log_user_action"),
        ):
            await handle_unexpected_callback(callback, state)

        callback.message.edit_text.assert_awaited_once()
        edit_text = callback.message.edit_text.call_args[0][0]
        assert "Команда не распознана" in edit_text

        callback.answer.assert_awaited_once()
        assert "Команда не распознана" in callback.answer.call_args[0][0]


# =================================
# Вариант ответа
# =================================


class TestUnexpectedOptionInput:
    @pytest.mark.asyncio
    async def test_empty_option_error(self):
        """Пустой вариант ответа — ошибка"""
        from handlers.fallback.tests import handle_unexpected_option_input

        msg = make_message(text=None)
        state = make_state()

        await handle_unexpected_option_input(msg, state)

        text = msg.answer.call_args[0][0]
        assert "Пустой вариант" in text

    @pytest.mark.asyncio
    async def test_valid_option_retry(self):
        """Валидный вариант — повтор"""
        from handlers.fallback.tests import handle_unexpected_option_input

        msg = make_message(text="Москва")
        state = make_state()

        await handle_unexpected_option_input(msg, state)

        text = msg.answer.call_args[0][0]
        assert "Повтори ввод" in text


# =================================
# Регистрация: ввод телефона
# =================================


class TestUnexpectedPhoneInput:
    @pytest.mark.asyncio
    async def test_shows_phone_format_hint(self):
        """Некорректный телефон — подсказка формата"""
        from handlers.fallback.registration import handle_unexpected_phone_input

        msg = make_message(text="abc")
        state = make_state()

        await handle_unexpected_phone_input(msg, state)

        text = msg.answer.call_args[0][0]
        assert "Некорректный формат телефона" in text


# =================================
# Регистрация: выбор роли
# =================================


class TestUnexpectedRoleInput:
    @pytest.mark.asyncio
    async def test_shows_role_error_with_keyboard(self):
        """Некорректная роль — ошибка + клавиатура"""
        from handlers.fallback.registration import handle_unexpected_role_input

        msg = make_message(text="admin")
        state = make_state()

        with patch("handlers.fallback.registration.get_role_selection_keyboard", return_value="role_kb"):
            await handle_unexpected_role_input(msg, state)

        text = msg.answer.call_args[0][0]
        assert "Некорректный выбор роли" in text
        assert msg.answer.call_args[1]["reply_markup"] == "role_kb"


# =================================
# Тест завершён
# =================================


class TestUnexpectedTestCompleted:
    @pytest.mark.asyncio
    async def test_shows_test_completed(self):
        """Ввод после завершения теста — сообщение о завершении"""
        from handlers.fallback.tests import handle_unexpected_test_completed

        msg = make_message(text="ещё")
        state = make_state()

        await handle_unexpected_test_completed(msg, state)

        text = msg.answer.call_args[0][0]
        assert "Тест уже завершен" in text


# =================================
# Аттестация: дата
# =================================


class TestUnexpectedDateInput:
    @pytest.mark.asyncio
    async def test_shows_date_format_hint(self):
        """Некорректная дата — подсказка формата"""
        from handlers.fallback.training import handle_unexpected_date_input

        msg = make_message(text="завтра")
        state = make_state()

        await handle_unexpected_date_input(msg, state)

        text = msg.answer.call_args[0][0]
        assert "Неправильный формат даты" in text


# =================================
# Аттестация: время
# =================================


class TestUnexpectedTimeInput:
    @pytest.mark.asyncio
    async def test_shows_time_format_hint(self):
        """Некорректное время — подсказка формата"""
        from handlers.fallback.training import handle_unexpected_time_input

        msg = make_message(text="утром")
        state = make_state()

        await handle_unexpected_time_input(msg, state)

        text = msg.answer.call_args[0][0]
        assert "Неправильный формат времени" in text


# =================================
# Аттестация: балл
# =================================


class TestUnexpectedScoreInput:
    @pytest.mark.asyncio
    async def test_shows_score_format_hint(self):
        """Некорректный балл — подсказка формата"""
        from handlers.fallback.training import handle_unexpected_score_input

        msg = make_message(text="отлично")
        state = make_state()

        await handle_unexpected_score_input(msg, state)

        text = msg.answer.call_args[0][0]
        assert "Неправильный формат балла" in text


# =================================
# Компания: редактирование названия
# =================================


class TestUnexpectedCompanyNameEditInput:
    @pytest.mark.asyncio
    async def test_shows_text_expected(self):
        """Некорректный ввод — ожидается текст"""
        from handlers.fallback.company import handle_unexpected_company_name_edit_input

        msg = make_message(text=None)
        state = make_state()

        await handle_unexpected_company_name_edit_input(msg, state)

        text = msg.answer.call_args[0][0]
        assert "Ожидается текстовое сообщение" in text


# =================================
# Компания: редактирование описания
# =================================


class TestUnexpectedCompanyDescriptionEditInput:
    @pytest.mark.asyncio
    async def test_shows_text_expected(self):
        """Некорректный ввод — ожидается текст"""
        from handlers.fallback.company import handle_unexpected_company_description_edit_input

        msg = make_message(text=None)
        state = make_state()

        await handle_unexpected_company_description_edit_input(msg, state)

        text = msg.answer.call_args[0][0]
        assert "Ожидается текстовое сообщение" in text


# =================================
# Подтверждение аттестации
# =================================


class TestUnexpectedAttestationConfirmationInput:
    @pytest.mark.asyncio
    async def test_shows_use_buttons(self):
        """Текстовый ввод вместо кнопки — подсказка"""
        from handlers.fallback.training import handle_unexpected_attestation_confirmation_input

        msg = make_message(text="да")
        state = make_state()

        await handle_unexpected_attestation_confirmation_input(msg, state)

        text = msg.answer.call_args[0][0]
        assert "используй кнопки" in text


# =================================
# Новые материалы теста
# =================================


class TestUnexpectedNewMaterials:
    @pytest.mark.asyncio
    async def test_shows_retry(self):
        """Некорректный ввод — просьба повторить"""
        from handlers.fallback.tests import handle_unexpected_new_materials

        msg = make_message()
        state = make_state()

        await handle_unexpected_new_materials(msg, state)

        text = msg.answer.call_args[0][0]
        assert "Повтори ввод" in text


# =================================
# Вопрос аттестации
# =================================


class TestUnexpectedAttestationQuestionInput:
    @pytest.mark.asyncio
    async def test_shows_format_hint(self):
        """Некорректный вопрос — подсказка формата"""
        from handlers.fallback.training import handle_unexpected_attestation_question_input

        msg = make_message(text="?")
        state = make_state()

        await handle_unexpected_attestation_question_input(msg, state)

        text = msg.answer.call_args[0][0]
        assert "Некорректный вопрос аттестации" in text


# =================================
# Материалы теста в траектории
# =================================


class TestUnexpectedTestMaterialsInput:
    @pytest.mark.asyncio
    async def test_shows_format_hint(self):
        """Некорректные материалы — подсказка"""
        from handlers.fallback.training import handle_unexpected_test_materials_input

        msg = make_message()
        state = make_state()

        await handle_unexpected_test_materials_input(msg, state)

        text = msg.answer.call_args[0][0]
        assert "Некорректные материалы" in text


# =================================
# БЗ: название материала (ветвление по text)
# =================================


class TestUnexpectedMaterialNameInput:
    @pytest.mark.asyncio
    async def test_non_text_shows_error(self):
        """Не текст — ошибка формата"""
        from handlers.fallback.knowledge import handle_unexpected_material_name_input

        msg = make_message(text=None)
        state = make_state()

        await handle_unexpected_material_name_input(msg, state)

        text = msg.answer.call_args[0][0]
        assert "Неправильный формат" in text

    @pytest.mark.asyncio
    async def test_text_input_no_answer(self):
        """Текстовый ввод — пропускает"""
        from handlers.fallback.knowledge import handle_unexpected_material_name_input

        msg = make_message(text="Инструкция")
        state = make_state()

        await handle_unexpected_material_name_input(msg, state)

        msg.answer.assert_not_awaited()


# =================================
# БЗ: содержимое материала (ветвление по text/document)
# =================================


class TestUnexpectedMaterialContentInput:
    @pytest.mark.asyncio
    async def test_non_text_non_doc_shows_error(self):
        """Не текст и не документ — ошибка"""
        from handlers.fallback.knowledge import handle_unexpected_material_content_input

        msg = make_message(text=None, document=None)
        state = make_state()

        await handle_unexpected_material_content_input(msg, state)

        text = msg.answer.call_args[0][0]
        assert "Неправильный формат" in text

    @pytest.mark.asyncio
    async def test_text_input_no_answer(self):
        """Текстовый ввод — пропускает"""
        from handlers.fallback.knowledge import handle_unexpected_material_content_input

        msg = make_message(text="https://example.com")
        state = make_state()

        await handle_unexpected_material_content_input(msg, state)

        msg.answer.assert_not_awaited()


# =================================
# БЗ: описание материала (ветвление по text)
# =================================


class TestUnexpectedMaterialDescriptionInput:
    @pytest.mark.asyncio
    async def test_non_text_shows_error(self):
        """Не текст — ошибка"""
        from handlers.fallback.knowledge import handle_unexpected_material_description_input

        msg = make_message(text=None)
        state = make_state()

        await handle_unexpected_material_description_input(msg, state)

        text = msg.answer.call_args[0][0]
        assert "Неправильный формат" in text

    @pytest.mark.asyncio
    async def test_text_input_no_answer(self):
        """Текстовый ввод — пропускает"""
        from handlers.fallback.knowledge import handle_unexpected_material_description_input

        msg = make_message(text="Описание материала")
        state = make_state()

        await handle_unexpected_material_description_input(msg, state)

        msg.answer.assert_not_awaited()


# =================================
# БЗ: фото материала (ветвление по photo)
# =================================


class TestUnexpectedMaterialPhotosInput:
    @pytest.mark.asyncio
    async def test_non_photo_shows_error(self):
        """Не фото — ошибка"""
        from handlers.fallback.knowledge import handle_unexpected_material_photos_input

        msg = make_message(text="текст", photo=None, media_group_id=None)
        state = make_state()

        await handle_unexpected_material_photos_input(msg, state)

        text = msg.answer.call_args[0][0]
        assert "Неправильный формат" in text

    @pytest.mark.asyncio
    async def test_photo_input_no_answer(self):
        """Фото — пропускает"""
        from handlers.fallback.knowledge import handle_unexpected_material_photos_input

        msg = make_message(photo=[MagicMock()])
        state = make_state()

        await handle_unexpected_material_photos_input(msg, state)

        msg.answer.assert_not_awaited()


# =================================
# Новое название теста (ветвление по длине)
# =================================


class TestUnexpectedNewTestName:
    @pytest.mark.asyncio
    async def test_short_name_error(self):
        """Название < 3 символов — ошибка"""
        from handlers.fallback.tests import handle_unexpected_new_test_name

        msg = make_message(text="АБ")
        state = make_state()

        await handle_unexpected_new_test_name(msg, state)

        text = msg.answer.call_args[0][0]
        assert "Некорректное название" in text

    @pytest.mark.asyncio
    async def test_valid_name_retry(self):
        """Валидное название — просьба повторить"""
        from handlers.fallback.tests import handle_unexpected_new_test_name

        msg = make_message(text="Новый тест")
        state = make_state()

        await handle_unexpected_new_test_name(msg, state)

        text = msg.answer.call_args[0][0]
        assert "Повтори ввод" in text


# =================================
# Групповые обработчики: кнопки
# =================================


class TestUseButtonsStates:
    @pytest.mark.asyncio
    async def test_sends_use_buttons(self):
        """Текстовый ввод — подсказка про кнопки"""
        from handlers.fallback.grouped import handle_use_buttons_states

        msg = make_message(text="текст")
        state = make_state()

        await handle_use_buttons_states(msg, state)

        text = msg.answer.call_args[0][0]
        assert "кнопки" in text


# =================================
# Групповые обработчики: повтор текста
# =================================


class TestTextRetryStates:
    @pytest.mark.asyncio
    async def test_sends_retry(self):
        """Ввод текста — просьба повторить"""
        from handlers.fallback.grouped import handle_text_retry_states

        msg = make_message(text="текст")
        state = make_state()

        await handle_text_retry_states(msg, state)

        text = msg.answer.call_args[0][0]
        assert "Повтори ввод" in text


# =================================
# Групповые: название группы
# =================================


class TestUnexpectedGroupNameInput:
    @pytest.mark.asyncio
    async def test_shows_error(self):
        """Некорректное название группы"""
        from handlers.fallback.grouped import handle_unexpected_group_name_input

        msg = make_message(text=None)
        state = make_state()

        await handle_unexpected_group_name_input(msg, state)

        text = msg.answer.call_args[0][0]
        assert "Некорректное название группы" in text


# =================================
# Групповые: название объекта
# =================================


class TestUnexpectedObjectNameInput:
    @pytest.mark.asyncio
    async def test_shows_error(self):
        """Некорректное название объекта"""
        from handlers.fallback.grouped import handle_unexpected_object_name_input

        msg = make_message(text=None)
        state = make_state()

        await handle_unexpected_object_name_input(msg, state)

        text = msg.answer.call_args[0][0]
        assert "Некорректное название объекта" in text


# =================================
# Групповые: названия сущностей
# =================================


class TestUnexpectedNameInputs:
    @pytest.mark.asyncio
    async def test_shows_error(self):
        """Некорректное название сущности"""
        from handlers.fallback.grouped import handle_unexpected_name_inputs

        msg = make_message(text=None)
        state = make_state()

        await handle_unexpected_name_inputs(msg, state)

        text = msg.answer.call_args[0][0]
        assert "Некорректное название" in text


# =================================
# Групповые: числовой ввод
# =================================


class TestUnexpectedNumericInputs:
    @pytest.mark.asyncio
    async def test_shows_error(self):
        """Некорректное число"""
        from handlers.fallback.grouped import handle_unexpected_numeric_inputs

        msg = make_message(text="abc")
        state = make_state()

        await handle_unexpected_numeric_inputs(msg, state)

        text = msg.answer.call_args[0][0]
        assert "Некорректное число" in text


# =================================
# Групповые: текст теста в траектории
# =================================


class TestUnexpectedLpTestTextInputs:
    @pytest.mark.asyncio
    async def test_shows_error(self):
        """Некорректный текстовый ввод"""
        from handlers.fallback.grouped import handle_unexpected_lp_test_text_inputs

        msg = make_message(text=None)
        state = make_state()

        await handle_unexpected_lp_test_text_inputs(msg, state)

        text = msg.answer.call_args[0][0]
        assert "Некорректный ввод" in text


# =================================
# Групповые: generic fallback
# =================================


class TestGenericFallbackStates:
    @pytest.mark.asyncio
    async def test_sends_fallback(self):
        """Стандартный fallback"""
        from handlers.fallback.grouped import handle_generic_fallback_states

        msg = make_message(text="что-то")
        state = make_state()

        with patch("utils.messages.fallback.get_fallback_keyboard", return_value="kb"):
            await handle_generic_fallback_states(msg, state)

        text = msg.answer.call_args[0][0]
        assert "Команда не распознана" in text
