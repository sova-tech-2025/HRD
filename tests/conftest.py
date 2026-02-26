"""Конфигурация тестов: устанавливает env-переменные до импорта модулей проекта."""
import os

# Устанавливаем обязательные переменные окружения ДО импорта config.py
os.environ.setdefault("BOT_TOKEN", "test-token")
os.environ.setdefault("POSTGRES_USER", "test")
os.environ.setdefault("POSTGRES_PASSWORD", "test")
os.environ.setdefault("POSTGRES_DB", "test_db")
os.environ.setdefault("POSTGRES_HOST", "localhost")
os.environ.setdefault("POSTGRES_PORT", "5432")
