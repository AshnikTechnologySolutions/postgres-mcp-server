import os
import asyncpg

def _get_database_url(role: str) -> str:
    target = os.getenv("DEFAULT_DB", "local")

    if role == "read":
        return os.getenv(
            "LOCAL_READ_DATABASE_URL"
            if target == "local"
            else "REMOTE_READ_DATABASE_URL"
        )

    if role == "write":
        return os.getenv(
            "LOCAL_WRITE_DATABASE_URL"
            if target == "local"
            else "REMOTE_WRITE_DATABASE_URL"
        )

    raise ValueError(f"Invalid database role: {role}")


async def get_pool(role: str = "read"):
    database_url = _get_database_url(role)

    pool = await asyncpg.create_pool(
        database_url,
        min_size=1,
        max_size=5,
        timeout=5,
    )

    async with pool.acquire() as conn:
        await conn.execute("""
            SET statement_timeout = '5s';
            SET idle_in_transaction_session_timeout = '10s';
            SET search_path = public;
        """)

    return pool