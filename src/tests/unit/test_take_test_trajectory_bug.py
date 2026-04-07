"""
Тест на баг: "❌ Тест не найден" при клике на тест из траектории.

Баг: когда стажёр находится в FSM-состоянии waiting_for_test_start
(оставшемся от предыдущего просмотра теста) и кликает на тест в траектории,
срабатывает process_back_to_test_details → process_test_selection_for_taking.

process_test_selection_for_taking парсит callback_data.split(":")[1]:
  - "test:15"           → test_id = 15 ✅ (ожидаемый формат)
  - "take_test:341:15"  → test_id = 341 ❌ (session_id вместо test_id!)

Из-за этого ищется тест с id=341 (session_id), которого нет → "Тест не найден".
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def make_callback(callback_data: str, user_id: int = 527628821):
    """Создать мок CallbackQuery."""
    callback = AsyncMock()
    callback.data = callback_data
    callback.from_user = MagicMock()
    callback.from_user.id = user_id
    callback.from_user.username = "test_user"
    callback.message = AsyncMock()
    callback.message.photo = None
    callback.message.chat = MagicMock()
    callback.message.chat.id = user_id
    callback.answer = AsyncMock()
    return callback


def make_user(user_id: int = 739, tg_id: int = 527628821, company_id: int = 1):
    """Создать мок пользователя."""
    user = MagicMock()
    user.id = user_id
    user.tg_id = tg_id
    user.company_id = company_id
    return user


def make_test(test_id: int = 15, name: str = "Задачи и рабочий день бариста", company_id: int = 1):
    """Создать мок теста."""
    test = MagicMock()
    test.id = test_id
    test.name = name
    test.company_id = company_id
    test.description = "Тестовое описание"
    test.threshold_score = 80.0
    test.max_score = 100.0
    test.material_link = None
    test.material_file_path = None
    test.material_type = None
    test.shuffle_questions = False
    test.max_attempts = 0
    return test


class TestTakeTestFromTrajectoryBug:
    """Клик на тест из траектории при остаточном FSM-состоянии waiting_for_test_start."""

    @pytest.mark.asyncio
    async def test_trajectory_callback_extracts_correct_test_id(self):
        """
        Баг: callback_data = "take_test:341:15" (session_id=341, test_id=15).
        process_test_selection_for_taking делает split(":")[1] → получает 341.
        get_test_by_id(session, 341) → None → "❌ Тест не найден."

        Ожидание: должен использоваться test_id=15, а не session_id=341.
        """
        from bot.handlers.tests.test_taking import process_back_to_test_details

        callback = make_callback("take_test:341:15")
        state = AsyncMock()
        state.get_data = AsyncMock(return_value={})
        db_session = AsyncMock()

        user = make_user()
        test = make_test(test_id=15)

        with (
            patch("bot.handlers.tests.test_taking.get_user_by_tg_id", return_value=user) as mock_get_user,
            patch("bot.handlers.tests.test_taking.get_test_by_id", return_value=test) as mock_get_test,
            patch("bot.handlers.tests.test_taking.check_test_access", return_value=True),
            patch("bot.handlers.tests.test_taking.get_user_test_attempts_count", return_value=0),
            patch("bot.handlers.tests.test_taking.get_user_test_result", return_value=None),
            patch("bot.handlers.tests.test_taking.ensure_company_id", return_value=1),
            patch("bot.handlers.tests.test_taking.log_user_action"),
        ):
            await process_back_to_test_details(callback, state, db_session)

            # Ключевая проверка: get_test_by_id должен вызываться с test_id=15, НЕ с 341
            mock_get_test.assert_called()
            actual_test_id = mock_get_test.call_args[0][1]  # второй позиционный аргумент
            assert actual_test_id == 15, (
                f"get_test_by_id вызван с test_id={actual_test_id} (session_id), а должен быть вызван с test_id=15"
            )

    @pytest.mark.asyncio
    async def test_trajectory_callback_does_not_show_test_not_found(self):
        """
        Баг: при callback "take_test:341:15" пользователь видит "❌ Тест не найден."
        Ожидание: тест id=15 существует, ошибка не должна показываться.
        """
        from bot.handlers.tests.test_taking import process_back_to_test_details

        callback = make_callback("take_test:341:15")
        state = AsyncMock()
        state.get_data = AsyncMock(return_value={})
        db_session = AsyncMock()

        user = make_user()
        test = make_test(test_id=15)

        def get_test_side_effect(session, test_id, company_id=None):
            """Возвращает тест только если запрошен правильный id=15."""
            if test_id == 15:
                return test
            return None  # id=341 → не найден (как в продакшене)

        with (
            patch("bot.handlers.tests.test_taking.get_user_by_tg_id", return_value=user),
            patch("bot.handlers.tests.test_taking.get_test_by_id", side_effect=get_test_side_effect),
            patch("bot.handlers.tests.test_taking.check_test_access", return_value=True),
            patch("bot.handlers.tests.test_taking.get_user_test_attempts_count", return_value=0),
            patch("bot.handlers.tests.test_taking.get_user_test_result", return_value=None),
            patch("bot.handlers.tests.test_taking.ensure_company_id", return_value=1),
            patch("bot.handlers.tests.test_taking.log_user_action"),
        ):
            await process_back_to_test_details(callback, state, db_session)

            # Не должно быть сообщения "Тест не найден"
            for call in callback.message.answer.call_args_list:
                args = call[0] if call[0] else ()
                for arg in args:
                    assert "Тест не найден" not in str(arg), (
                        "Пользователь увидел 'Тест не найден' при существующем тесте id=15"
                    )
