# mcp_server/server.py

import asyncpg

from fastmcp import FastMCP

from mcp_server.audit import log_audit_event, read_audit_events
from mcp_server.config import ALLOW_ARBITRARY_SQL
from mcp_server.sql import (
    QueryValidationError,
    detect_pg_stat_statements_columns,
    execute_sql,
    explain_sql,
    fetch_rows,
    is_fetch_sql,
    is_likely_write_sql,
    normalize_query,
)

# Create MCP Server
mcp = FastMCP("postgres-mcp")


def _error(message: str) -> dict[str, object]:
    return {"ok": False, "error": message}


def _coerce_limit(limit: int, *, default: int, maximum: int = 200) -> int:
    value = int(limit if limit is not None else default)
    if value < 1 or value > maximum:
        raise QueryValidationError(f"limit must be between 1 and {maximum}")
    return value


@mcp.tool()
async def sql_query(query: str):
    """Run a single SQL statement when arbitrary SQL is enabled."""

    if not ALLOW_ARBITRARY_SQL:
        await log_audit_event(
            tool_name="sql_query",
            ok=False,
            transport="mcp",
            query=query,
            error="Unsafe SQL disabled. Set ALLOW_ARBITRARY_SQL=true in .env",
        )
        return _error("Unsafe SQL disabled. Set ALLOW_ARBITRARY_SQL=true in .env")

    try:
        sql = normalize_query(query)
        if is_fetch_sql(sql):
            rows = await fetch_rows(sql, role="write")
            await log_audit_event(
                tool_name="sql_query",
                ok=True,
                transport="mcp",
                query=sql,
                details={"mode": "fetch", "row_count": len(rows)},
            )
            return {"ok": True, "rows": rows}

        command = await execute_sql(sql, role="write")
        await log_audit_event(
            tool_name="sql_query",
            ok=True,
            transport="mcp",
            query=sql,
            details={"mode": "execute", "command": command},
        )
        return {"ok": True, "command": command}
    except (QueryValidationError, RuntimeError, ValueError) as exc:
        await log_audit_event(
            tool_name="sql_query",
            ok=False,
            transport="mcp",
            query=query,
            error=str(exc),
        )
        return _error(str(exc))
    except Exception as exc:
        await log_audit_event(
            tool_name="sql_query",
            ok=False,
            transport="mcp",
            query=query,
            error=str(exc),
        )
        return _error(str(exc))


@mcp.tool()
async def sql_safe(query: str):
    """Read-only SQL tool enforced with a database read-only transaction."""

    try:
        sql = normalize_query(query)
        rows = await fetch_rows(sql, role="read", read_only=True)
        await log_audit_event(
            tool_name="sql_safe",
            ok=True,
            transport="mcp",
            query=sql,
            details={"row_count": len(rows)},
        )
        return {"ok": True, "rows": rows}
    except asyncpg.ReadOnlySQLTransactionError:
        await log_audit_event(
            tool_name="sql_safe",
            ok=False,
            transport="mcp",
            query=query,
            error="Read-only mode: write operations are not allowed",
        )
        return _error("Read-only mode: write operations are not allowed")
    except (QueryValidationError, RuntimeError, ValueError) as exc:
        await log_audit_event(
            tool_name="sql_safe",
            ok=False,
            transport="mcp",
            query=query,
            error=str(exc),
        )
        return _error(str(exc))
    except Exception as exc:
        await log_audit_event(
            tool_name="sql_safe",
            ok=False,
            transport="mcp",
            query=query,
            error=str(exc),
        )
        return _error(str(exc))


@mcp.tool()
async def health():
    """Return DB health and PostgreSQL version."""

    try:
        rows = await fetch_rows(
            """
            SELECT
                version() AS postgres_version,
                current_database() AS database_name,
                current_user AS database_user
            """,
            role="read",
            read_only=True,
        )
        await log_audit_event(
            tool_name="health",
            ok=True,
            transport="mcp",
            details={"database_name": rows[0]["database_name"]},
        )
        return {"ok": True, "status": "ok", **rows[0]}
    except Exception as exc:
        await log_audit_event(tool_name="health", ok=False, transport="mcp", error=str(exc))
        return _error(str(exc))


@mcp.tool()
async def uptime():
    """Return PostgreSQL uptime and postmaster start time."""

    try:
        rows = await fetch_rows(
            """
            SELECT
                pg_postmaster_start_time() AS start_time,
                now() - pg_postmaster_start_time() AS uptime
            """,
            role="read",
            read_only=True,
        )
        row = rows[0]
        await log_audit_event(tool_name="uptime", ok=True, transport="mcp")
        return {
            "ok": True,
            "start_time": row["start_time"].isoformat(),
            "uptime": str(row["uptime"]),
        }
    except Exception as exc:
        await log_audit_event(tool_name="uptime", ok=False, transport="mcp", error=str(exc))
        return _error(str(exc))


@mcp.tool()
async def schema():
    """Return public schema table and column metadata."""

    try:
        rows = await fetch_rows(
            """
            SELECT
                table_name,
                column_name,
                data_type,
                is_nullable
            FROM information_schema.columns
            WHERE table_schema = 'public'
            ORDER BY table_name, ordinal_position
            """,
            role="read",
            read_only=True,
        )
        grouped: dict[str, list[dict[str, str]]] = {}
        for row in rows:
            grouped.setdefault(row["table_name"], []).append(
                {
                    "column_name": row["column_name"],
                    "data_type": row["data_type"],
                    "is_nullable": row["is_nullable"],
                }
            )
        await log_audit_event(
            tool_name="schema",
            ok=True,
            transport="mcp",
            details={"table_count": len(grouped)},
        )
        return {"ok": True, "schema": grouped}
    except Exception as exc:
        await log_audit_event(tool_name="schema", ok=False, transport="mcp", error=str(exc))
        return _error(str(exc))


@mcp.tool()
async def table_stats(limit: int = 50):
    """Return table sizes, row estimates, and index sizes."""

    try:
        safe_limit = _coerce_limit(limit, default=50)
        rows = await fetch_rows(
            f"""
            SELECT
              c.relname AS table_name,
              COALESCE(c.reltuples::bigint, 0) AS est_rows,
              pg_size_pretty(pg_relation_size(c.oid)) AS table_size,
              pg_size_pretty(pg_indexes_size(c.oid)) AS index_size,
              pg_size_pretty(pg_total_relation_size(c.oid)) AS total_size
            FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE c.relkind = 'r'
              AND n.nspname = 'public'
            ORDER BY pg_total_relation_size(c.oid) DESC
            LIMIT {safe_limit}
            """,
            role="read",
            read_only=True,
        )
        await log_audit_event(
            tool_name="table_stats",
            ok=True,
            transport="mcp",
            details={"limit": safe_limit, "row_count": len(rows)},
        )
        return {"ok": True, "stats": rows}
    except Exception as exc:
        await log_audit_event(
            tool_name="table_stats",
            ok=False,
            transport="mcp",
            details={"limit": limit},
            error=str(exc),
        )
        return _error(str(exc))


@mcp.tool()
async def slow_queries(limit: int = 10):
    """Return slowest queries from pg_stat_statements."""

    try:
        safe_limit = _coerce_limit(limit, default=10, maximum=100)
        total_col, mean_col = await detect_pg_stat_statements_columns()
        sql = normalize_query(
            f"""
            SELECT
                query,
                calls,
                {total_col} AS total_exec_time_ms,
                {mean_col} AS mean_exec_time_ms,
                shared_blks_hit,
                shared_blks_read
            FROM pg_stat_statements
            ORDER BY {total_col} DESC
            LIMIT {safe_limit}
            """,
            empty_message="Missing slow query SQL",
        )
        rows = await fetch_rows(sql, role="read", read_only=True)
        await log_audit_event(
            tool_name="slow_queries",
            ok=True,
            transport="mcp",
            details={"limit": safe_limit, "row_count": len(rows)},
        )
        return {"ok": True, "slow_queries": rows}
    except (QueryValidationError, RuntimeError, ValueError) as exc:
        await log_audit_event(
            tool_name="slow_queries",
            ok=False,
            transport="mcp",
            details={"limit": limit},
            error=str(exc),
        )
        return _error(str(exc))
    except Exception as exc:
        await log_audit_event(
            tool_name="slow_queries",
            ok=False,
            transport="mcp",
            details={"limit": limit},
            error=str(exc),
        )
        return _error(str(exc))


@mcp.tool()
async def explain_query(query: str):
    """Return a JSON EXPLAIN plan for a read-only SQL statement."""

    try:
        sql = normalize_query(query, empty_message="Missing SQL to explain")
        if is_likely_write_sql(sql):
            await log_audit_event(
                tool_name="explain_query",
                ok=False,
                transport="mcp",
                query=sql,
                error="EXPLAIN allowed only for read-only statements",
            )
            return _error("EXPLAIN allowed only for read-only statements")
        plan = await explain_sql(sql)
        await log_audit_event(tool_name="explain_query", ok=True, transport="mcp", query=sql)
        return {"ok": True, "plan": plan}
    except asyncpg.ReadOnlySQLTransactionError:
        await log_audit_event(
            tool_name="explain_query",
            ok=False,
            transport="mcp",
            query=query,
            error="EXPLAIN allowed only for read-only statements",
        )
        return _error("EXPLAIN allowed only for read-only statements")
    except (QueryValidationError, RuntimeError, ValueError) as exc:
        await log_audit_event(
            tool_name="explain_query",
            ok=False,
            transport="mcp",
            query=query,
            error=str(exc),
        )
        return _error(str(exc))
    except Exception as exc:
        await log_audit_event(
            tool_name="explain_query",
            ok=False,
            transport="mcp",
            query=query,
            error=str(exc),
        )
        return _error(str(exc))


@mcp.tool()
async def index_advisor(query: str):
    """Recommend indexes derived from a safe EXPLAIN plan."""

    try:
        sql = normalize_query(query, empty_message="Missing SQL to analyze")
        if is_likely_write_sql(sql):
            await log_audit_event(
                tool_name="index_advisor",
                ok=False,
                transport="mcp",
                query=sql,
                error="DDL/DML statements are not allowed",
            )
            return _error("DDL/DML statements are not allowed")

        plan_doc = await explain_sql(sql)
        plan_root = plan_doc[0]["Plan"] if isinstance(plan_doc, list) else plan_doc["Plan"]
        recommendations: list[str] = []

        def walk(node: dict[str, object]) -> None:
            node_type = node.get("Node Type")
            relation = node.get("Relation Name")
            filter_cond = node.get("Filter")

            if node_type == "Seq Scan" and relation and filter_cond:
                recommendations.append(
                    f"Seq Scan on '{relation}' with filter '{filter_cond}'. "
                    "Consider an index on equality columns first, then range columns."
                )

            for child in node.get("Plans", []):
                walk(child)

        walk(plan_root)

        if not recommendations:
            recommendations.append("No obvious index recommendations found")

        await log_audit_event(
            tool_name="index_advisor",
            ok=True,
            transport="mcp",
            query=sql,
            details={"recommendation_count": len(recommendations)},
        )
        return {"ok": True, "recommendations": recommendations}
    except asyncpg.ReadOnlySQLTransactionError:
        await log_audit_event(
            tool_name="index_advisor",
            ok=False,
            transport="mcp",
            query=query,
            error="DDL/DML statements are not allowed",
        )
        return _error("DDL/DML statements are not allowed")
    except (QueryValidationError, RuntimeError, ValueError) as exc:
        await log_audit_event(
            tool_name="index_advisor",
            ok=False,
            transport="mcp",
            query=query,
            error=str(exc),
        )
        return _error(str(exc))
    except Exception as exc:
        await log_audit_event(
            tool_name="index_advisor",
            ok=False,
            transport="mcp",
            query=query,
            error=str(exc),
        )
        return _error(str(exc))


@mcp.tool()
async def audit_logs(limit: int = 50, tool_name: str | None = None, ok: bool | None = None):
    """Return recent structured audit events for MCP tool usage."""

    try:
        safe_limit = _coerce_limit(limit, default=50, maximum=500)
        events = await read_audit_events(limit=safe_limit, tool_name=tool_name, ok=ok)
        await log_audit_event(
            tool_name="audit_logs",
            ok=True,
            transport="mcp",
            details={"limit": safe_limit, "returned": len(events), "filter_tool_name": tool_name, "filter_ok": ok},
        )
        return {"ok": True, "events": events}
    except Exception as exc:
        await log_audit_event(
            tool_name="audit_logs",
            ok=False,
            transport="mcp",
            details={"limit": limit, "filter_tool_name": tool_name, "filter_ok": ok},
            error=str(exc),
        )
        return _error(str(exc))
