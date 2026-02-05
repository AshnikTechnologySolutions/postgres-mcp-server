# mcp_server/server.py

from fastmcp import FastMCP
from mcp_server.config import ALLOW_ARBITRARY_SQL
from mcp_server.db import get_pool
import json

# Create MCP Server
mcp = FastMCP("postgres-mcp")




# ======================================================
# SQL QUERY TOOL (unsafe: read/write)
# ======================================================
@mcp.tool()
async def sql_query(query: str):
    """Run any SQL query (unsafe: read/write)."""

    if not ALLOW_ARBITRARY_SQL:
        return {
            "ok": False,
            "error": "Unsafe SQL disabled. Set ALLOW_ARBITRARY_SQL=true in .env"
        }

    try:
        pool = await get_pool(role="write")
        async with pool.acquire() as conn:
            rows = await conn.fetch(query)
            return {"ok": True, "rows": [dict(r) for r in rows]}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ======================================================
# SAFE SQL TOOL (read-only)
# ======================================================
@mcp.tool()
async def sql_safe(query: str):
    """Read-only SQL tool that blocks write operations."""
    forbidden = ["insert", "update", "delete", "drop", "alter", "truncate"]

    if any(f in query.lower() for f in forbidden):
        return {"ok": False, "error": "Write operations blocked (SAFE MODE)"}

    try:
        pool = await get_pool(role="read")
        async with pool.acquire() as conn:
            rows = await conn.fetch(query)
            return {"ok": True, "rows": [dict(r) for r in rows]}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ======================================================
# HEALTH TOOL
# ======================================================
@mcp.tool()
async def health():
    """Return DB health and PostgreSQL version."""
    pool = await get_pool(role="read")
    async with pool.acquire() as conn:
        version = await conn.fetchval("SELECT version()")
        return {"status": "ok", "postgres_version": version}


# ======================================================
# UPTIME TOOL
# ======================================================
@mcp.tool()
async def uptime():
    """Return PostgreSQL uptime & postmaster start time."""
    pool = await get_pool(role="read")
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT pg_postmaster_start_time() AS start_time,
                   now() - pg_postmaster_start_time() AS uptime;
        """)
        result = [dict(r) for r in rows]
        return {"ok": True, **result[0]}


# ======================================================
# TABLE STATS TOOL
# ======================================================
@mcp.tool()
async def table_stats(limit: int = 50):
    """Return table sizes, row estimates, index sizes."""
    q = """
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
        LIMIT $1;
    """

    try:
        pool = await get_pool(role="read")
        async with pool.acquire() as conn:
            rows = await conn.fetch(q, limit)
            return {"ok": True, "stats": [dict(r) for r in rows]}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ======================================================
# SLOW QUERIES TOOL
# ======================================================
@mcp.tool()
async def slow_queries(limit: int = 10):
    """Return slowest queries from pg_stat_statements."""

    q = """
        SELECT query, calls, total_time, mean_time
        FROM pg_stat_statements
        ORDER BY total_time DESC
        LIMIT $1;
    """

    try:
        pool = await get_pool(role="read")
        async with pool.acquire() as conn:
            rows = await conn.fetch(q, limit)
            return {"ok": True, "slow_queries": [dict(r) for r in rows]}
    except Exception as e:
        # Check for pg_stat_statements not enabled
        if "pg_stat_statements" in str(e):
            return {"ok": False, "error": "pg_stat_statements not enabled"}
        return {"ok": False, "error": str(e)}


# ======================================================
# EXPLAIN QUERY TOOL
# ======================================================
@mcp.tool()
async def explain_query(query: str):
    """EXPLAIN (FORMAT JSON, ANALYZE false, BUFFERS false) for any read-only SQL."""
    bad = ["insert", "update", "delete", "drop", "alter", "truncate"]
    if any(b in query.lower() for b in bad):
        return {"ok": False, "error": "EXPLAIN allowed only for SELECT"}

    stmt = f"EXPLAIN (FORMAT JSON, ANALYZE false, BUFFERS false) {query}"

    pool = await get_pool(role="read")
    async with pool.acquire() as conn:
        try:
            rows = await conn.fetch(stmt)
            plan = rows[0][0]
            return {"ok": True, "plan": plan}
        except Exception as e:
            return {"ok": False, "error": str(e)}


# ======================================================
# INDEX ADVISOR TOOL
# ======================================================

@mcp.tool()
async def index_advisor(query: str):
    """Recommend indexes derived from safe EXPLAIN (no execution)."""
    if not query or not query.strip():
        return {"ok": False, "error": "Missing SQL to analyze"}

    forbidden = ["insert", "update", "delete", "drop", "alter", "truncate", "create"]
    if any(f in query.lower() for f in forbidden):
        return {"ok": False, "error": "DDL/DML statements are not allowed"}

    stmt = f"EXPLAIN (FORMAT JSON, ANALYZE false, BUFFERS false) {query}"

    try:
        pool = await get_pool(role="read")
        async with pool.acquire() as conn:
            rows = await conn.fetch(stmt)
            raw = rows[0][0]

            if isinstance(raw, str):
                raw = json.loads(raw)

            if isinstance(raw, list):
                plan = raw[0]["Plan"]
            elif isinstance(raw, dict):
                plan = raw["Plan"]
            else:
                return {"ok": False, "error": "Unexpected EXPLAIN JSON format"}

        recommendations = []

        def walk(node):
            node_type = node.get("Node Type")
            rel = node.get("Relation Name")
            filter_cond = node.get("Filter")

            if node_type == "Seq Scan" and rel and filter_cond:
                recommendations.append(
                    f"Seq Scan on '{rel}' with filter '{filter_cond}'. "
                    f"Consider an index on the filtered columns (equality columns first, range columns next)."
                )

            for child in node.get("Plans", []):
                walk(child)

        walk(plan)

        if not recommendations:
            recommendations.append("No obvious index recommendations found")

        return {"ok": True, "recommendations": recommendations}

    except Exception as e:
        return {"ok": False, "error": str(e)}