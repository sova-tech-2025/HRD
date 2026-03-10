#!/usr/bin/env python3
"""
Генератор токена инициализации для HRD-bot
Запустите этот скрипт для получения безопасного токена администратора
"""

import secrets
import string


def generate_secure_token(length=32):
    """Генерирует безопасный токен"""
    return secrets.token_urlsafe(length)


def generate_readable_token(length=24):
    """Генерирует читаемый токен (только буквы и цифры)"""
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


if __name__ == "__main__":
    import sys

    print("🔐 Генератор токенов инициализации HRD-bot")
    print("=" * 50)

    # Проверяем аргументы командной строки
    num_tokens = 1
    if len(sys.argv) > 1:
        try:
            num_tokens = int(sys.argv[1])
            if num_tokens < 1 or num_tokens > 10:
                print("❌ Количество токенов должно быть от 1 до 10")
                sys.exit(1)
        except ValueError:
            print("❌ Неверный формат количества токенов")
            sys.exit(1)

    print(f"Генерация {num_tokens} токена(ов)...\n")

    # Генерируем токены
    secure_tokens = [generate_secure_token(32) for _ in range(num_tokens)]
    readable_tokens = [generate_readable_token(24) for _ in range(num_tokens)]

    if num_tokens == 1:
        print("Безопасный токен (рекомендуемый):")
        print(f"ADMIN_INIT_TOKEN={secure_tokens[0]}")
        print()

        print("Читаемый токен (альтернатива):")
        print(f"ADMIN_INIT_TOKEN={readable_tokens[0]}")
    else:
        print("Безопасные токены (рекомендуемые):")
        print(f"ADMIN_INIT_TOKENS={','.join(secure_tokens)}")
        print()

        print("Читаемые токены (альтернатива):")
        print(f"ADMIN_INIT_TOKENS={','.join(readable_tokens)}")
        print()

        print("Отдельные токены:")
        for i, token in enumerate(secure_tokens, 1):
            print(f"  Токен {i}: {token}")

    print("\n📝 Инструкции:")
    if num_tokens == 1:
        print("1. Скопируйте один из токенов выше")
        print("2. Добавьте его в файл .env как ADMIN_INIT_TOKEN=...")
    else:
        print("1. Скопируйте строку ADMIN_INIT_TOKENS=... выше")
        print("2. Добавьте её в файл .env")
        print("3. Каждый токен может использоваться одним администратором")

    print("3. Запустите бота")
    print("4. Дайте токены людям, которые должны стать администраторами")
    print("5. Они регистрируются и вводят свои токены")
    print("6. ВАЖНО: После создания всех админов удалите токены из .env!")
    print()
    print(f"⚙️  Настройки: MAX_ADMINS={num_tokens} (максимум администраторов)")
    print("⚠️  НИКОМУ НЕ ПОКАЗЫВАЙТЕ ЭТИ ТОКЕНЫ!")
    print("\n💡 Использование:")
    print("  python generate_token.py       # 1 токен")
    print("  python generate_token.py 3     # 3 токена")
    print("  python generate_token.py 5     # 5 токенов")
