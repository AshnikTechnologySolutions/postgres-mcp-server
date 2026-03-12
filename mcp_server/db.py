import asyncio
import os

import asyncpg

_POOLS: dict[str, asyncpg.Pool] = {}
_POOL_LOCK = asyncio.Lock()


def _require_database_url(role: str) -> str:
    target = os.getenv("DEFAULT_DB", "local").strip().lower()

    if target not in {"local", "remote"}:
        raise ValueError("DEFAULT_DB must be either 'local' or 'remote'")

    env_name = {
        ("local", "read"): "LOCAL_READ_DATABASE_URL",
        ("local", "write"): "LOCAL_WRITE_DATABASE_URL",
        ("remote", "read"): "REMOTE_READ_DATABASE_URL",
        ("remote", "write"): "REMOTE_WRITE_DATABASE_URL",
    }.get((target, role))

    if not env_name:
        raise ValueError(f"Invalid database role: {role}")

    database_url = os.getenv(env_name)
    if not database_url:
        raise RuntimeError(f"Missing required environment variable: {env_name}")

    return database_url


async def _setup_connection(conn: asyncpg.Connection) -> None:
    await conn.execute("SET statement_timeout = '5s'")
    await conn.execute("SET idle_in_transaction_session_timeout = '10s'")
    await conn.execute("SET search_path = public")


async def get_pool(role: str = "read") -> asyncpg.Pool:
    if role in _POOLS:
        return _POOLS[role]

    async with _POOL_LOCK:
        if role not in _POOLS:
            _POOLS[role] = await asyncpg.create_pool(
                dsn=_require_database_url(role),
                min_size=int(os.getenv("DB_POOL_MIN_SIZE", "2")),
                max_size=int(os.getenv("DB_POOL_MAX_SIZE", "20")),
                timeout=float(os.getenv("DB_CONNECT_TIMEOUT_SECONDS", "5")),
                setup=_setup_connection,
            )

    return _POOLS[role]
