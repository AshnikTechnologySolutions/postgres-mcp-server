from __future__ import annotations

import json
import re
from typing import Any

import asyncpg

from mcp_server.config import MAX_RESULT_ROWS
from mcp_server.db import get_pool
from mcp_server.otel import get_tracer

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

# Matches single-quoted string literals including escaped quotes ('').
_STRING_LITERAL_RE = re.compile(r"'(?:''|[^'])*'")


class QueryValidationError(ValueError):
    pass


def coerce_limit(limit: int, *, default: int, maximum: int = 200) -> int:
    value = int(limit if limit is not None else default)
    if value < 1 or value > maximum:
        raise QueryValidationError(f"limit must be between 1 and {maximum}")
    return value


def _db_tracer():
    return get_tracer("postgres-mcp.db")


def _statement_preview(query: str) -> str:
    return " ".join(query.split())[:160]


def _span_attrs(query: str, role: str, operation: str) -> dict[str, str]:
    return {
        "db.system": "postgresql",
        "db.operation": operation,
        "db.role": role,
        "db.statement.preview": _statement_preview(query),
    }


def normalize_query(query: str, *, empty_message: str = "Missing SQL query") -> str:
    if not query or not query.strip():
        raise QueryValidationError(empty_message)

    sql = query.strip()
    body = sql.rstrip(";").strip()

    # Strip string literals before checking for semicolons to avoid false positives
    # on queries like SELECT 'a;b' which contain a semicolon inside a literal.
    body_without_literals = _STRING_LITERAL_RE.sub("''", body)
    if ";" in body_without_literals:
        raise QueryValidationError("Only a single SQL statement is allowed")

    return body


def is_likely_write_sql(query: str) -> bool:
    lowered = query.lstrip().lower()
    return lowered.startswith(WRITE_PREFIXES)


def is_fetch_sql(query: str) -> bool:
    lowered = query.lstrip().lower()
    return lowered.startswith(FETCH_PREFIXES)


async def fetch_rows(query: str, *, role: str = "read", read_only: bool = False) -> list[dict[str, Any]]:
    tracer = _db_tracer()
    if tracer is None:
        pool = await get_pool(role=role)
        async with pool.acquire() as conn:
            if read_only:
                async with conn.transaction():
                    await conn.execute("SET TRANSACTION READ ONLY")
                    rows = await conn.fetch(query)
            else:
                rows = await conn.fetch(query)
        return [dict(row) for row in rows[:MAX_RESULT_ROWS]]

    with tracer.start_as_current_span("db.fetch_rows") as span:
        for key, value in _span_attrs(query, role, "fetch").items():
            span.set_attribute(key, value)
        span.set_attribute("db.read_only", read_only)

        pool = await get_pool(role=role)
        async with pool.acquire() as conn:
            if read_only:
                async with conn.transaction():
                    await conn.execute("SET TRANSACTION READ ONLY")
                    rows = await conn.fetch(query)
            else:
                rows = await conn.fetch(query)
        rows = rows[:MAX_RESULT_ROWS]
        span.set_attribute("db.row_count", len(rows))
        return [dict(row) for row in rows]


async def execute_sql(query: str, *, role: str = "write") -> str:
    tracer = _db_tracer()
    if tracer is None:
        pool = await get_pool(role=role)
        async with pool.acquire() as conn:
            return await conn.execute(query)

    with tracer.start_as_current_span("db.execute_sql") as span:
        for key, value in _span_attrs(query, role, "execute").items():
            span.set_attribute(key, value)
        pool = await get_pool(role=role)
        async with pool.acquire() as conn:
            command = await conn.execute(query)
        span.set_attribute("db.command_tag", command)
        return command


async def explain_sql(query: str) -> Any:
    stmt = f"EXPLAIN (FORMAT JSON, ANALYZE false, BUFFERS false) {query}"
    rows = await fetch_rows(stmt, role="read", read_only=True)
    if not rows:
        raise QueryValidationError("No explain output")
    plan = rows[0]["QUERY PLAN"]
    # asyncpg returns EXPLAIN FORMAT JSON as a raw string; parse it here
    # so callers always receive a Python list/dict, never a string.
    if isinstance(plan, str):
        plan = json.loads(plan)
    return plan


async def detect_pg_stat_statements_columns() -> tuple[str, str]:
    tracer = _db_tracer()
    if tracer is None:
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
    else:
        with tracer.start_as_current_span("db.detect_pg_stat_statements_columns") as span:
            span.set_attribute("db.system", "postgresql")
            span.set_attribute("db.role", "read")
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
