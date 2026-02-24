#!/usr/bin/env python3
"""
Интерактивный скрипт для первичной авторизации Telethon-сессий.

Запускается один раз перед E2E-тестами для создания .session файлов.
Каждый аккаунт проходит авторизацию: отправка кода → ввод кода → (опционально 2FA).

Использование:
    python tests/e2e/auth_sessions.py
"""

import asyncio
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from telethon import TelegramClient


# Загружаем .env.e2e
ENV_PATH = Path(__file__).parent / ".env.e2e"
load_dotenv(ENV_PATH)

SESSIONS_DIR = Path(__file__).parent / "sessions"

# Аккаунты для авторизации
ACCOUNTS = [
    ("recruiter", os.getenv("E2E_PHONE_RECRUITER")),
    ("mentor", os.getenv("E2E_PHONE_MENTOR")),
    ("manager", os.getenv("E2E_PHONE_MANAGER")),
    ("trainee1", os.getenv("E2E_PHONE_TRAINEE_1")),
    ("trainee2", os.getenv("E2E_PHONE_TRAINEE_2")),
]


async def auth_account(api_id: int, api_hash: str, name: str, phone: str) -> bool:
    """Авторизация одного аккаунта."""
    session_path = str(SESSIONS_DIR / name)
    client = TelegramClient(session_path, api_id, api_hash)

    await client.connect()

    if await client.is_user_authorized():
        me = await client.get_me()
        print(f"  [{name}] Уже авторизован: {me.first_name} ({phone})")
        await client.disconnect()
        return True

    print(f"\n  [{name}] Авторизация {phone}...")

    try:
        await client.send_code_request(phone)
    except Exception as e:
        print(f"  [{name}] Ошибка отправки кода: {e}")
        await client.disconnect()
        return False

    code = input(f"  [{name}] Введи код из Telegram для {phone}: ").strip()

    try:
        await client.sign_in(phone, code)
    except Exception as e:
        if "Two-steps verification" in str(e) or "2FA" in str(e):
            password = input(f"  [{name}] Введи пароль 2FA: ").strip()
            try:
                await client.sign_in(password=password)
            except Exception as e2:
                print(f"  [{name}] Ошибка 2FA: {e2}")
                await client.disconnect()
                return False
        else:
            print(f"  [{name}] Ошибка авторизации: {e}")
            await client.disconnect()
            return False

    me = await client.get_me()
    print(f"  [{name}] Авторизован: {me.first_name} ({phone})")
    await client.disconnect()
    return True


async def main():
    api_id = os.getenv("E2E_API_ID")
    api_hash = os.getenv("E2E_API_HASH")

    if not api_id or not api_hash:
        print("Ошибка: E2E_API_ID и E2E_API_HASH не заданы в .env.e2e")
        sys.exit(1)

    api_id = int(api_id)

    # Создаём директорию для сессий
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)

    print("=" * 50)
    print("Авторизация Telethon-сессий для E2E-тестов")
    print(f"Сессии сохраняются в: {SESSIONS_DIR}")
    print("=" * 50)

    success_count = 0
    for name, phone in ACCOUNTS:
        if not phone:
            print(f"\n  [{name}] ПРОПУЩЕН: телефон не задан в .env.e2e")
            continue

        ok = await auth_account(api_id, api_hash, name, phone)
        if ok:
            success_count += 1

    print(f"\n{'=' * 50}")
    print(f"Авторизовано: {success_count}/{len(ACCOUNTS)}")

    if success_count == len(ACCOUNTS):
        print("Все аккаунты готовы к E2E-тестам!")
    else:
        print("Некоторые аккаунты не авторизованы. Запусти скрипт снова.")


if __name__ == "__main__":
    asyncio.run(main())
