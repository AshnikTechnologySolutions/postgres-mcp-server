import asyncpg
from contextlib import contextmanager
from typing import Any

from fastmcp import FastMCP

from mcp_server.audit import log_audit_event
from mcp_server.config import ALLOW_ARBITRARY_SQL
from mcp_server.otel import get_tracer
from mcp_server.request_context import generate_request_id, reset_request_id, set_request_id
from mcp_server.sql import (
    execute_sql,
    fetch_rows,
    is_fetch_sql,
    normalize_query,
)
from mcp_server.tools.audit import audit_logs as _audit_logs
from mcp_server.tools.explain import explain_query as _explain_query
from mcp_server.tools.health import health_check, uptime_check
from mcp_server.tools.index_advisor import index_advisor as _index_advisor
from mcp_server.tools.ops import access_scope as access_scope_tool
from mcp_server.tools.ops import audit_summary as audit_summary_tool
from mcp_server.tools.ops import config_status as config_status_tool
from mcp_server.tools.ops import index_usage as index_usage_tool
from mcp_server.tools.ops import locks as locks_tool
from mcp_server.tools.ops import pool_status as pool_status_tool
from mcp_server.tools.ops import readiness as readiness_tool
from mcp_server.tools.ops import redaction_test as redaction_test_tool
from mcp_server.tools.ops import replication_status as replication_status_tool
from mcp_server.tools.ops import vacuum_status as vacuum_status_tool
from mcp_server.tools.schema import get_schema
from mcp_server.tools.stats import slow_queries as _slow_queries
from mcp_server.tools.stats import table_stats as _table_stats

mcp = FastMCP("postgres-mcp")


def _error(message: str) -> dict[str, object]:
    return {"ok": False, "error": message}


@contextmanager
def _mcp_tool_span(tool_name: str, attrs: dict[str, Any] | None = None):
    request_id = generate_request_id()
    token = set_request_id(request_id)
    tracer = get_tracer("postgres-mcp.stdio")

    if tracer is None:
        try:
            yield request_id
        finally:
            reset_request_id(token)
        return

    with tracer.start_as_current_span(f"mcp.{tool_name}") as span:
        span.set_attribute("mcp.transport", "stdio")
        span.set_attribute("mcp.tool_name", tool_name)
        span.set_attribute("mcp.request_id", request_id)
        for key, value in (attrs or {}).items():
            if value is None or isinstance(value, (list, dict, tuple, set)):
                continue
            span.set_attribute(f"mcp.{key}", value)
        try:
            yield request_id
        finally:
            reset_request_id(token)


@mcp.tool()
async def sql_query(query: str):
    """Run a single SQL statement when arbitrary SQL is enabled."""

    with _mcp_tool_span("sql_query", {"query_present": bool(query), "allow_arbitrary_sql": ALLOW_ARBITRARY_SQL}):
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
        except Exception as exc:
            await log_audit_event(tool_name="sql_query", ok=False, transport="mcp", query=query, error=str(exc))
            return _error(str(exc))


@mcp.tool()
async def sql_safe(query: str):
    """Read-only SQL tool enforced with a database read-only transaction."""

    with _mcp_tool_span("sql_safe", {"query_present": bool(query)}):
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
        except Exception as exc:
            await log_audit_event(tool_name="sql_safe", ok=False, transport="mcp", query=query, error=str(exc))
            return _error(str(exc))


@mcp.tool()
async def health():
    """Return DB health and PostgreSQL version."""

    with _mcp_tool_span("health"):
        result = await health_check()
        await log_audit_event(
            tool_name="health",
            ok=bool(result.get("ok")),
            transport="mcp",
            details={"database_name": result.get("database_name")},
            error=result.get("error"),
        )
        return result


@mcp.tool()
async def uptime():
    """Return PostgreSQL uptime and postmaster start time."""

    with _mcp_tool_span("uptime"):
        result = await uptime_check()
        await log_audit_event(
            tool_name="uptime",
            ok=bool(result.get("ok")),
            transport="mcp",
            error=result.get("error"),
        )
        return result


@mcp.tool()
async def schema():
    """Return public schema table and column metadata."""

    with _mcp_tool_span("schema"):
        result = await get_schema()
        await log_audit_event(
            tool_name="schema",
            ok=bool(result.get("ok")),
            transport="mcp",
            details={"table_count": len(result.get("schema", {})) if result.get("ok") else None},
            error=result.get("error"),
        )
        return result


@mcp.tool()
async def table_stats(limit: int = 50):
    """Return table sizes, row estimates, and index sizes."""

    with _mcp_tool_span("table_stats", {"limit": limit}):
        result = await _table_stats(limit)
        await log_audit_event(
            tool_name="table_stats",
            ok=bool(result.get("ok")),
            transport="mcp",
            details={"limit": limit, "row_count": len(result.get("stats", [])) if result.get("ok") else 0},
            error=result.get("error"),
        )
        return result


@mcp.tool()
async def slow_queries(limit: int = 10):
    """Return slowest queries from pg_stat_statements."""

    with _mcp_tool_span("slow_queries", {"limit": limit}):
        result = await _slow_queries(limit)
        await log_audit_event(
            tool_name="slow_queries",
            ok=bool(result.get("ok")),
            transport="mcp",
            details={"limit": limit, "row_count": len(result.get("slow_queries", [])) if result.get("ok") else 0},
            error=result.get("error"),
        )
        return result


@mcp.tool()
async def explain_query(query: str):
    """Return a JSON EXPLAIN plan for a read-only SQL statement."""

    with _mcp_tool_span("explain_query", {"query_present": bool(query)}):
        result = await _explain_query(query)
        await log_audit_event(
            tool_name="explain_query",
            ok=bool(result.get("ok")),
            transport="mcp",
            query=query,
            error=result.get("error"),
        )
        return result


@mcp.tool()
async def index_advisor(query: str):
    """Recommend indexes derived from a safe EXPLAIN plan."""

    with _mcp_tool_span("index_advisor", {"query_present": bool(query)}):
        result = await _index_advisor(query)
        await log_audit_event(
            tool_name="index_advisor",
            ok=bool(result.get("ok")),
            transport="mcp",
            query=query,
            details={"recommendation_count": len(result.get("recommendations", [])) if result.get("ok") else 0},
            error=result.get("error"),
        )
        return result


@mcp.tool()
async def audit_logs(limit: int = 50, tool_name: str | None = None, ok: bool | None = None):
    """Return recent structured audit events for MCP tool usage."""

    with _mcp_tool_span("audit_logs", {"limit": limit}):
        result = await _audit_logs(limit=limit, tool_name=tool_name, ok=ok)
        await log_audit_event(
            tool_name="audit_logs",
            ok=bool(result.get("ok")),
            transport="mcp",
            details={
                "limit": limit,
                "returned": len(result.get("events", [])) if result.get("ok") else 0,
                "filter_tool_name": tool_name,
                "filter_ok": ok,
            },
            error=result.get("error"),
        )
        return result


@mcp.tool()
async def readiness():
    """Return operational readiness checks for PostgreSQL connectivity and extensions."""

    with _mcp_tool_span("readiness"):
        result = await readiness_tool()
        await log_audit_event(
            tool_name="readiness",
            ok=bool(result.get("ok")),
            transport="mcp",
            details={"status": result.get("status")},
            error=result.get("error"),
        )
        return result


@mcp.tool()
async def config_status():
    """Return current runtime configuration without exposing secrets."""

    with _mcp_tool_span("config_status"):
        result = await config_status_tool()
        await log_audit_event(
            tool_name="config_status",
            ok=bool(result.get("ok")),
            transport="mcp",
            details={"default_db": result.get("config", {}).get("default_db")},
            error=result.get("error"),
        )
        return result


@mcp.tool()
async def audit_summary(limit: int = 200):
    """Return aggregated audit activity by tool and top recent errors."""

    with _mcp_tool_span("audit_summary", {"limit": limit}):
        result = await audit_summary_tool(limit=limit)
        await log_audit_event(
            tool_name="audit_summary",
            ok=bool(result.get("ok")),
            transport="mcp",
            details={"limit": limit, "scanned_events": result.get("summary", {}).get("scanned_events")},
            error=result.get("error"),
        )
        return result


@mcp.tool()
async def access_scope(limit: int = 200):
    """Return the schemas and tables currently visible to the active read role."""

    with _mcp_tool_span("access_scope", {"limit": limit}):
        result = await access_scope_tool(limit=limit)
        await log_audit_event(
            tool_name="access_scope",
            ok=bool(result.get("ok")),
            transport="mcp",
            details={
                "limit": limit,
                "visible_object_count": result.get("scope", {}).get("visible_object_count"),
            },
            error=result.get("error"),
        )
        return result


@mcp.tool()
async def pool_status():
    """Return current asyncpg pool configuration and utilization snapshot."""

    with _mcp_tool_span("pool_status"):
        result = await pool_status_tool()
        await log_audit_event(
            tool_name="pool_status",
            ok=bool(result.get("ok")),
            transport="mcp",
            details={"pool_roles": sorted(result.get("pools", {}).keys())},
            error=result.get("error"),
        )
        return result


@mcp.tool()
async def locks(limit: int = 50):
    """Show blocked and blocking sessions for the current database."""

    with _mcp_tool_span("locks", {"limit": limit}):
        result = await locks_tool(limit=limit)
        await log_audit_event(
            tool_name="locks",
            ok=bool(result.get("ok")),
            transport="mcp",
            details={"limit": limit, "returned": len(result.get("locks", [])) if result.get("ok") else 0},
            error=result.get("error"),
        )
        return result


@mcp.tool()
async def index_usage(limit: int = 100):
    """Show PostgreSQL index usage and identify low-usage or unused indexes."""

    with _mcp_tool_span("index_usage", {"limit": limit}):
        result = await index_usage_tool(limit=limit)
        await log_audit_event(
            tool_name="index_usage",
            ok=bool(result.get("ok")),
            transport="mcp",
            details={"limit": limit, "returned": len(result.get("indexes", [])) if result.get("ok") else 0},
            error=result.get("error"),
        )
        return result


@mcp.tool()
async def vacuum_status(limit: int = 100):
    """Show vacuum/analyze activity and dead-tuple pressure by table."""

    with _mcp_tool_span("vacuum_status", {"limit": limit}):
        result = await vacuum_status_tool(limit=limit)
        await log_audit_event(
            tool_name="vacuum_status",
            ok=bool(result.get("ok")),
            transport="mcp",
            details={"limit": limit, "returned": len(result.get("tables", [])) if result.get("ok") else 0},
            error=result.get("error"),
        )
        return result


@mcp.tool()
async def replication_status(limit: int = 50):
    """Show PostgreSQL replication state, connected replicas, and replication slots."""

    with _mcp_tool_span("replication_status", {"limit": limit}):
        result = await replication_status_tool(limit=limit)
        await log_audit_event(
            tool_name="replication_status",
            ok=bool(result.get("ok")),
            transport="mcp",
            details={
                "limit": limit,
                "replica_count": result.get("summary", {}).get("replica_count"),
                "slot_count": result.get("summary", {}).get("slot_count"),
            },
            error=result.get("error"),
        )
        return result


@mcp.tool()
async def redaction_test(value: str):
    """Test masking behavior for emails, phones, SSNs, and payment cards."""

    with _mcp_tool_span("redaction_test", {"input_present": bool(value)}):
        result = await redaction_test_tool(value)
        await log_audit_event(
            tool_name="redaction_test",
            ok=bool(result.get("ok")),
            transport="mcp",
            details={
                "input_present": bool(value),
                "changed": result.get("result", {}).get("changed") if result.get("ok") else None,
                "matched_rules": result.get("result", {}).get("matched_rules", []) if result.get("ok") else [],
            },
            error=result.get("error"),
        )
        return result
