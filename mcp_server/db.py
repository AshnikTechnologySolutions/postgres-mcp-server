import asyncpg
import os

_read_pool = None
_write_pool = None

async def get_pool(role="read"):
    global _read_pool, _write_pool

    if role == "read":
        if _read_pool is None:
            read_url = os.getenv("READ_DATABASE_URL") or os.getenv("DATABASE_URL")
            if not read_url:
                raise RuntimeError("READ_DATABASE_URL not configured")

            _read_pool = await asyncpg.create_pool(
                dsn=read_url,
                min_size=1,
                max_size=10,
                command_timeout=30,
            )
        return _read_pool

    elif role == "write":
        if _write_pool is None:
            write_url = os.getenv("WRITE_DATABASE_URL") or os.getenv("DATABASE_URL")
            if not write_url:
                raise RuntimeError("WRITE_DATABASE_URL not configured")

            _write_pool = await asyncpg.create_pool(
                dsn=write_url,
                min_size=1,
                max_size=5,
                command_timeout=30,
            )
        return _write_pool

    else:
        raise ValueError("Invalid pool role")
