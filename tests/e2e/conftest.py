"""
E2E Test Fixtures — session-scoped Telethon clients и BotClient обёртки.

Все фикстуры session-scoped: клиенты создаются один раз и переиспользуются
во всех тестовых файлах (которые запускаются в заданном порядке через pytest-ordering).
"""

import asyncio
import os
from pathlib import Path

import asyncpg
import pytest
import pytest_asyncio
from dotenv import load_dotenv
from telethon import TelegramClient

from tests.e2e.helpers.bot_client import BotClient

# Загружаем .env.e2e
ENV_PATH = Path(__file__).parent / ".env.e2e"
load_dotenv(ENV_PATH, override=True)

SESSIONS_DIR = Path(__file__).parent / "sessions"


# --------------------------------------------------------------------------
# Event loop: единый loop для всей сессии
# --------------------------------------------------------------------------

@pytest.fixture(scope="session")
def event_loop():
    """Единый event loop для всей сессии тестов."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# --------------------------------------------------------------------------
# Конфигурация из .env.e2e
# --------------------------------------------------------------------------

@pytest.fixture(scope="session")
def e2e_config() -> dict:
    """Конфигурация E2E из переменных окружения."""
    return {
        "api_id": int(os.environ["E2E_API_ID"]),
        "api_hash": os.environ["E2E_API_HASH"],
        "bot_token": os.environ["E2E_BOT_TOKEN"],
        "bot_username": os.environ["E2E_BOT_USERNAME"],
        "phone_recruiter": os.environ["E2E_PHONE_RECRUITER"],
        "phone_mentor": os.environ["E2E_PHONE_MENTOR"],
        "phone_manager": os.environ["E2E_PHONE_MANAGER"],
        "phone_trainee1": os.environ["E2E_PHONE_TRAINEE_1"],
        "phone_trainee2": os.environ["E2E_PHONE_TRAINEE_2"],
        "db_host": os.getenv("E2E_POSTGRES_HOST", "localhost"),
        "db_port": int(os.getenv("E2E_POSTGRES_PORT", "5433")),
        "db_name": os.getenv("E2E_POSTGRES_DB", "hrd_e2e_test"),
        "db_user": os.getenv("E2E_POSTGRES_USER", "hrd_test"),
        "db_password": os.getenv("E2E_POSTGRES_PASSWORD", "hrd_test_password"),
    }


# --------------------------------------------------------------------------
# Shared state — dict для передачи данных между ordered test files
# --------------------------------------------------------------------------

@pytest.fixture(scope="session")
def shared_state() -> dict:
    """
    Общее состояние для передачи данных между тестовыми файлами.

    Ключи заполняются в test_setup.py и используются в остальных тестах:
    - invite_code: код приглашения компании
    - test_ids: [id1, id2, id3] — ID созданных тестов
    - test_names: [name1, name2, name3] — названия тестов
    - trajectory_name: название траектории
    - stage_names: [stage1, stage2] — названия этапов
    - session_names: [session1, session2] — названия сессий
    - group_name: название созданной группы
    - object_name: название созданного объекта
    """
    return {}


# --------------------------------------------------------------------------
# Raw Telethon clients (session-scoped)
# --------------------------------------------------------------------------

async def _create_client(
    api_id: int, api_hash: str, session_name: str
) -> TelegramClient:
    """Создать и подключить TelegramClient из сохранённой сессии."""
    session_path = str(SESSIONS_DIR / session_name)
    client = TelegramClient(session_path, api_id, api_hash)
    await client.connect()

    if not await client.is_user_authorized():
        raise RuntimeError(
            f"Session '{session_name}' not authorized. "
            f"Run: python tests/e2e/auth_sessions.py"
        )

    return client


@pytest_asyncio.fixture(scope="session")
async def recruiter_client(e2e_config) -> TelegramClient:
    client = await _create_client(
        e2e_config["api_id"], e2e_config["api_hash"], "recruiter"
    )
    yield client
    await client.disconnect()


@pytest_asyncio.fixture(scope="session")
async def mentor_client(e2e_config) -> TelegramClient:
    client = await _create_client(
        e2e_config["api_id"], e2e_config["api_hash"], "mentor"
    )
    yield client
    await client.disconnect()


@pytest_asyncio.fixture(scope="session")
async def manager_client(e2e_config) -> TelegramClient:
    client = await _create_client(
        e2e_config["api_id"], e2e_config["api_hash"], "manager"
    )
    yield client
    await client.disconnect()


@pytest_asyncio.fixture(scope="session")
async def trainee1_client(e2e_config) -> TelegramClient:
    client = await _create_client(
        e2e_config["api_id"], e2e_config["api_hash"], "trainee1"
    )
    yield client
    await client.disconnect()


@pytest_asyncio.fixture(scope="session")
async def trainee2_client(e2e_config) -> TelegramClient:
    client = await _create_client(
        e2e_config["api_id"], e2e_config["api_hash"], "trainee2"
    )
    yield client
    await client.disconnect()


# --------------------------------------------------------------------------
# Helper: resolve bot entity per client
# --------------------------------------------------------------------------

async def _resolve_bot(client: TelegramClient, config: dict):
    """Resolve бот по username для конкретного клиента."""
    username = config["bot_username"]
    if not username.startswith("@"):
        username = f"@{username}"
    return await client.get_entity(username)


# --------------------------------------------------------------------------
# BotClient wrappers (session-scoped, each resolves bot independently)
# --------------------------------------------------------------------------

@pytest_asyncio.fixture(scope="session")
async def recruiter(recruiter_client, e2e_config) -> BotClient:
    entity = await _resolve_bot(recruiter_client, e2e_config)
    return BotClient(recruiter_client, entity, name="recruiter")


@pytest_asyncio.fixture(scope="session")
async def mentor(mentor_client, e2e_config) -> BotClient:
    entity = await _resolve_bot(mentor_client, e2e_config)
    return BotClient(mentor_client, entity, name="mentor")


@pytest_asyncio.fixture(scope="session")
async def manager(manager_client, e2e_config) -> BotClient:
    entity = await _resolve_bot(manager_client, e2e_config)
    return BotClient(manager_client, entity, name="manager")


@pytest_asyncio.fixture(scope="session")
async def trainee1(trainee1_client, e2e_config) -> BotClient:
    entity = await _resolve_bot(trainee1_client, e2e_config)
    return BotClient(trainee1_client, entity, name="trainee1")


@pytest_asyncio.fixture(scope="session")
async def trainee2(trainee2_client, e2e_config) -> BotClient:
    entity = await _resolve_bot(trainee2_client, e2e_config)
    return BotClient(trainee2_client, entity, name="trainee2")


# --------------------------------------------------------------------------
# Database reset
# --------------------------------------------------------------------------

async def _reset_database(config: dict) -> None:
    """TRUNCATE CASCADE всех таблиц в тестовой БД, сохраняя seed-данные."""
    # Таблицы с начальными данными (роли, права) — не трогаем
    SEED_TABLES = {"roles", "permissions", "role_permissions"}

    conn = await asyncpg.connect(
        host=config["db_host"],
        port=config["db_port"],
        database=config["db_name"],
        user=config["db_user"],
        password=config["db_password"],
    )
    try:
        tables = await conn.fetch("""
            SELECT tablename FROM pg_tables
            WHERE schemaname = 'public'
            AND tablename NOT LIKE 'alembic%'
        """)

        to_truncate = [
            t["tablename"] for t in tables
            if t["tablename"] not in SEED_TABLES
        ]

        if to_truncate:
            table_names = ", ".join(f'"{t}"' for t in to_truncate)
            await conn.execute(f"TRUNCATE {table_names} CASCADE")
            print(f"[DB] Truncated {len(to_truncate)} tables (preserved {len(SEED_TABLES)} seed tables)")
        else:
            print("[DB] No tables to truncate")
    finally:
        await conn.close()


@pytest_asyncio.fixture(scope="session", autouse=True)
async def clean_db_before_session(e2e_config):
    """Очистка БД перед запуском всей сессии тестов."""
    await _reset_database(e2e_config)
    yield


# --------------------------------------------------------------------------
# Direct DB access for SQL manipulation in tests
# --------------------------------------------------------------------------

@pytest_asyncio.fixture(scope="session")
async def e2e_db(e2e_config):
    """Direct asyncpg connection for SQL manipulation in E2E tests.

    Used to simulate production edge cases:
    - Missing TraineeTestAccess records (post-reassignment state)
    - Tests with creator_id = NULL (legacy data)
    """
    conn = await asyncpg.connect(
        host=e2e_config["db_host"],
        port=e2e_config["db_port"],
        database=e2e_config["db_name"],
        user=e2e_config["db_user"],
        password=e2e_config["db_password"],
    )
    yield conn
    await conn.close()
