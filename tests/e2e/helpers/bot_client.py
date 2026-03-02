"""
BotClient — обёртка над TelegramClient для E2E-тестов.

Предоставляет удобные методы для взаимодействия с ботом:
отправка сообщений, ожидание ответов, нажатие inline-кнопок.
"""

import asyncio
import re
import time
from typing import Optional

from telethon import TelegramClient
from telethon.errors import FloodWaitError
from telethon.tl.custom.message import Message


# Минимальный интервал между API-вызовами (секунды)
MIN_CALL_INTERVAL = 1.5

# Таймауты по умолчанию
DEFAULT_TIMEOUT = 15.0
POLL_INTERVAL = 0.5


class BotClient:
    """Обёртка над TelegramClient для удобного взаимодействия с ботом в тестах."""

    def __init__(self, client: TelegramClient, bot_entity, name: str = "unknown"):
        self.client = client
        self.bot_entity = bot_entity
        self.name = name
        self._last_call_time: float = 0.0
        self._last_sent_message_id: Optional[int] = None

    @staticmethod
    def _clean_text(text: str) -> str:
        """
        Очистка текста от артефактов форматирования для pattern matching.

        Бот иногда использует Markdown-синтаксис (**bold**, __italic__)
        внутри HTML parse_mode, из-за чего ** и __ попадают в raw_text как
        литеральные символы и ломают regex-паттерны.
        """
        # Убираем Markdown bold/italic маркеры
        text = text.replace("**", "").replace("__", "")
        return text

    async def _rate_limit(self) -> None:
        """Ожидание минимального интервала между API-вызовами."""
        elapsed = time.monotonic() - self._last_call_time
        if elapsed < MIN_CALL_INTERVAL:
            await asyncio.sleep(MIN_CALL_INTERVAL - elapsed)
        self._last_call_time = time.monotonic()

    async def _handle_flood(self, func, *args, **kwargs):
        """Обработка FloodWaitError: ожидание и повторный вызов."""
        try:
            return await func(*args, **kwargs)
        except FloodWaitError as e:
            wait_time = e.seconds + 1
            print(f"[{self.name}] FloodWait: sleeping {wait_time}s")
            await asyncio.sleep(wait_time)
            return await func(*args, **kwargs)

    async def send(self, text: str) -> Message:
        """Отправить текстовое сообщение боту."""
        await self._rate_limit()
        msg = await self._handle_flood(self.client.send_message, self.bot_entity, text)
        self._last_sent_message_id = msg.id
        return msg

    async def get_messages(self, limit: int = 5) -> list[Message]:
        """Получить последние сообщения из диалога с ботом."""
        return await self._handle_flood(
            self.client.get_messages, self.bot_entity, limit=limit
        )

    async def get_last_message(self) -> Optional[Message]:
        """Получить последнее сообщение от бота."""
        messages = await self.get_messages(limit=5)
        for msg in messages:
            # Пропускаем собственные сообщения
            if msg.out:
                continue
            return msg
        return None

    async def wait_response(
        self,
        timeout: float = DEFAULT_TIMEOUT,
        contains: Optional[str] = None,
        pattern: Optional[str] = None,
        after_message_id: Optional[int] = None,
    ) -> Message:
        """
        Ожидание ответа от бота с polling get_messages().

        Args:
            timeout: максимальное время ожидания
            contains: подстрока, которая должна содержаться в ответе
            pattern: regex-паттерн для проверки ответа
            after_message_id: ждать сообщение с ID больше указанного

        Returns:
            Message от бота

        Raises:
            TimeoutError: если бот не ответил вовремя
        """
        reference_id = after_message_id or self._last_sent_message_id or 0
        deadline = time.monotonic() + timeout
        last_candidate = None

        while time.monotonic() < deadline:
            messages = await self.get_messages(limit=10)

            for msg in messages:
                # Пропускаем свои сообщения
                if msg.out:
                    continue

                # Ждём сообщение новее отправленного
                if msg.id <= reference_id:
                    continue

                text = msg.raw_text or msg.message or ""
                clean = self._clean_text(text)

                if contains and contains not in clean:
                    last_candidate = msg
                    continue

                if pattern and not re.search(pattern, clean, re.IGNORECASE):
                    last_candidate = msg
                    continue

                return msg

            await asyncio.sleep(POLL_INTERVAL)

        # Если был кандидат без совпадения — покажем его для отладки
        detail = ""
        if last_candidate:
            text = self._clean_text(last_candidate.text or "")[:200]
            detail = f" Last bot message: '{text}'"

        filter_info = ""
        if contains:
            filter_info += f" contains='{contains}'"
        if pattern:
            filter_info += f" pattern='{pattern}'"

        raise TimeoutError(
            f"[{self.name}] Bot did not respond within {timeout}s.{filter_info}{detail}"
        )

    async def send_and_wait(
        self,
        text: str,
        contains: Optional[str] = None,
        pattern: Optional[str] = None,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> Message:
        """Отправить сообщение и дождаться ответа бота."""
        sent = await self.send(text)
        return await self.wait_response(
            timeout=timeout,
            contains=contains,
            pattern=pattern,
            after_message_id=sent.id,
        )

    async def click_button(
        self,
        message: Message,
        text: Optional[str] = None,
        data: Optional[bytes] = None,
    ) -> None:
        """
        Нажать inline-кнопку в сообщении.

        Args:
            message: сообщение с inline-клавиатурой
            text: текст кнопки (поиск по подстроке)
            data: callback_data кнопки (точное совпадение)
        """
        await self._rate_limit()

        if not message.buttons:
            raise ValueError(f"[{self.name}] Message has no inline buttons: {message.text[:100]}")

        for row in message.buttons:
            for button in row:
                if data is not None and hasattr(button, "data") and button.data == data:
                    await self._handle_flood(button.click)
                    self._last_sent_message_id = message.id
                    return
                if text is not None and button.text and text in button.text:
                    await self._handle_flood(button.click)
                    self._last_sent_message_id = message.id
                    return

        # Собираем доступные кнопки для ошибки
        available = self.get_button_texts(message)
        raise ValueError(
            f"[{self.name}] Button not found (text='{text}', data={data}). "
            f"Available: {available}"
        )

    async def click_and_wait(
        self,
        message: Message,
        text: Optional[str] = None,
        data: Optional[bytes] = None,
        wait_contains: Optional[str] = None,
        wait_pattern: Optional[str] = None,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> Message:
        """
        Нажать кнопку и дождаться нового ответа бота.

        Обрабатывает два варианта ответа бота:
        1. Бот отправляет новое сообщение (msg.id > original)
        2. Бот редактирует сообщение с кнопкой (edit_text)
        """
        original_text = message.raw_text or message.message or ""
        original_msg_id = message.id
        await self.click_button(message, text=text, data=data)

        deadline = time.monotonic() + timeout
        last_candidate = None

        while time.monotonic() < deadline:
            messages = await self.get_messages(limit=10)

            for msg in messages:
                if msg.out:
                    continue

                msg_text = msg.raw_text or msg.message or ""
                clean_text = self._clean_text(msg_text)

                # Вариант 1: Бот отправил новое сообщение
                is_new = msg.id > original_msg_id
                # Вариант 2: Бот отредактировал сообщение с кнопкой
                is_edited = (
                    msg.id == original_msg_id and msg_text != original_text
                )

                if not is_new and not is_edited:
                    continue

                if wait_contains and wait_contains not in clean_text:
                    last_candidate = msg
                    continue

                if wait_pattern and not re.search(
                    wait_pattern, clean_text, re.IGNORECASE
                ):
                    last_candidate = msg
                    continue

                return msg

            await asyncio.sleep(POLL_INTERVAL)

        detail = ""
        if last_candidate:
            preview = self._clean_text(last_candidate.text or "")[:200]
            detail = f" Last bot message: '{preview}'"

        filter_info = ""
        if wait_contains:
            filter_info += f" contains='{wait_contains}'"
        if wait_pattern:
            filter_info += f" pattern='{wait_pattern}'"

        raise TimeoutError(
            f"[{self.name}] Bot did not respond within {timeout}s.{filter_info}{detail}"
        )

    @staticmethod
    def get_button_texts(message: Message) -> list[str]:
        """Извлечь тексты всех inline-кнопок из сообщения."""
        if not message.buttons:
            return []
        texts = []
        for row in message.buttons:
            for button in row:
                if button.text:
                    texts.append(button.text)
        return texts

    @staticmethod
    def get_button_data(message: Message) -> list[tuple[str, Optional[bytes]]]:
        """Извлечь пары (текст, callback_data) из inline-кнопок."""
        if not message.buttons:
            return []
        result = []
        for row in message.buttons:
            for button in row:
                cb_data = getattr(button, "data", None)
                result.append((button.text or "", cb_data))
        return result

    @staticmethod
    def find_button_data(
        message: Message,
        text_contains: Optional[str] = None,
        data_prefix: Optional[str] = None,
    ) -> Optional[bytes]:
        """
        Найти callback_data кнопки по тексту и/или префиксу data.

        Когда оба параметра указаны — ищет кнопку, удовлетворяющую ОБОИМ условиям.
        Когда указан только один — фильтрует только по нему.
        """
        if not message.buttons:
            return None
        for row in message.buttons:
            for button in row:
                cb_data = getattr(button, "data", None)
                if cb_data is None:
                    continue
                data_str = cb_data.decode("utf-8") if isinstance(cb_data, bytes) else str(cb_data)

                text_ok = (not text_contains) or (button.text and text_contains in button.text)
                data_ok = (not data_prefix) or data_str.startswith(data_prefix)

                if text_ok and data_ok:
                    return cb_data
        return None

    @staticmethod
    def find_all_buttons_data(
        message: Message,
        data_prefix: Optional[str] = None,
    ) -> list[tuple[str, bytes]]:
        """Найти все кнопки с указанным префиксом callback_data."""
        if not message.buttons:
            return []
        result = []
        for row in message.buttons:
            for button in row:
                cb_data = getattr(button, "data", None)
                if cb_data is None:
                    continue
                data_str = cb_data.decode("utf-8") if isinstance(cb_data, bytes) else str(cb_data)
                if data_prefix and data_str.startswith(data_prefix):
                    result.append((button.text or "", cb_data))
        return result
