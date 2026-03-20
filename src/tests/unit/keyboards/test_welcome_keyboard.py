"""Тесты для get_welcome_keyboard() из keyboards/keyboards.py."""

from bot.keyboards.keyboards import get_welcome_keyboard


class TestGetWelcomeKeyboard:
    def test_has_register_normal_button(self):
        """Кнопка 'Зарегистрироваться' с callback_data='register:normal'."""
        kb = get_welcome_keyboard()
        buttons = [btn for row in kb.inline_keyboard for btn in row]
        normal_buttons = [b for b in buttons if b.callback_data == "register:normal"]
        assert len(normal_buttons) == 1
        assert normal_buttons[0].text == "Зарегистрироваться"

    def test_only_one_button(self):
        """Клавиатура содержит ровно 1 кнопку (без 'У меня есть код')."""
        kb = get_welcome_keyboard()
        buttons = [btn for row in kb.inline_keyboard for btn in row]
        assert len(buttons) == 1
