from __future__ import annotations

from typing import Any

import asyncpg

from mcp_server.db import get_pool

READ_ONLY_PREFIXES = ("select", "with", "show", "values")
FETCH_PREFIXES = READ_ONLY_PREFIXES + ("explain",)
WRITE_PREFIXES = (
    "insert",
    "update",
    "delete",
    "drop",
    "alter",
    "truncate",
    "create",
    "grant",
    "revoke",
    "comment",
    "refresh",
    "vacuum",
    "reindex",
    "copy",
)


class QueryValidationError(ValueError):
    pass


def normalize_query(query: str, *, empty_message: str = "Missing SQL query") -> str:
    if not query or not query.strip():
        raise QueryValidationError(empty_message)

    sql = query.strip()
    body = sql.rstrip(";").strip()
    if ";" in body:
        raise QueryValidationError("Only a single SQL statement is allowed")

    return body


def is_likely_write_sql(query: str) -> bool:
    lowered = query.lstrip().lower()
    return lowered.startswith(WRITE_PREFIXES)


def is_fetch_sql(query: str) -> bool:
    lowered = query.lstrip().lower()
    return lowered.startswith(FETCH_PREFIXES)


async def fetch_rows(query: str, *, role: str = "read", read_only: bool = False) -> list[dict[str, Any]]:
    pool = await get_pool(role=role)
    async with pool.acquire() as conn:
        if read_only:
            async with conn.transaction():
                await conn.execute("SET TRANSACTION READ ONLY")
                rows = await conn.fetch(query)
        else:
            rows = await conn.fetch(query)
    return [dict(row) for row in rows]


async def execute_sql(query: str, *, role: str = "write") -> str:
    pool = await get_pool(role=role)
    async with pool.acquire() as conn:
        return await conn.execute(query)


async def explain_sql(query: str) -> Any:
    stmt = f"EXPLAIN (FORMAT JSON, ANALYZE false, BUFFERS false) {query}"
    rows = await fetch_rows(stmt, role="read", read_only=True)
    if not rows:
        raise QueryValidationError("No explain output")
    return rows[0]["QUERY PLAN"]


async def detect_pg_stat_statements_columns() -> tuple[str, str]:
    pool = await get_pool(role="read")
    async with pool.acquire() as conn:
        try:
            rows = await conn.fetch(
                """
                SELECT attname
                FROM pg_attribute
                WHERE attrelid = 'pg_stat_statements'::regclass
                  AND attnum > 0
                  AND NOT attisdropped;
                """
            )
        except asyncpg.UndefinedTableError as exc:
            raise QueryValidationError(
                "pg_stat_statements extension not enabled. Enable it with: CREATE EXTENSION pg_stat_statements;"
            ) from exc

    names = {row["attname"] for row in rows}
    if {"total_exec_time", "mean_exec_time"} <= names:
        return "total_exec_time", "mean_exec_time"
    if {"total_time", "mean_time"} <= names:
        return "total_time", "mean_time"

    raise QueryValidationError("pg_stat_statements is available, but timing columns could not be detected")
