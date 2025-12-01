# mcp_server/server.py

from fastmcp import FastMCP
import asyncpg
from mcp_server.config import DATABASE_URL
import json

# Create MCP Server
mcp = FastMCP("postgres-mcp")


# ======================================================
# SQL QUERY TOOL (unsafe)
# ======================================================
@mcp.tool()
async def sql_query(query: str):
    """Run any SQL query (unsafe: read/write)."""
    conn = await asyncpg.connect(DATABASE_URL)
    try:
        rows = await conn.fetch(query)
        return {"ok": True, "rows": [dict(r) for r in rows]}
    except Exception as e:
        return {"ok": False, "error": str(e)}
    finally:
        await conn.close()


# ======================================================
# SAFE SQL TOOL (read-only)
# ======================================================
@mcp.tool()
async def sql_safe(query: str):
    """Read-only SQL tool that blocks write operations."""
    forbidden = ["insert", "update", "delete", "drop", "alter", "truncate"]

    if any(f in query.lower() for f in forbidden):
        return {"ok": False, "error": "Write operations blocked (SAFE MODE)"}

    conn = await asyncpg.connect(DATABASE_URL)
    try:
        rows = await conn.fetch(query)
        return {"ok": True, "rows": [dict(r) for r in rows]}
    except Exception as e:
        return {"ok": False, "error": str(e)}
    finally:
        await conn.close()


# ======================================================
# HEALTH TOOL
# ======================================================
@mcp.tool()
async def health():
    """Return DB health and PostgreSQL version."""
    conn = await asyncpg.connect(DATABASE_URL)
    try:
        version = await conn.fetchval("SELECT version()")
        return {"status": "ok", "postgres_version": version}
    finally:
        await conn.close()


# ======================================================
# UPTIME TOOL
# ======================================================
@mcp.tool()
async def uptime():
    """Return PostgreSQL uptime & postmaster start time."""
    conn = await asyncpg.connect(DATABASE_URL)
    try:
        row = await conn.fetchrow("""
            SELECT pg_postmaster_start_time() AS start_time,
                   now() - pg_postmaster_start_time() AS uptime;
        """)
        return {
            "ok": True,
            "started_at": str(row["start_time"]),
            "uptime": str(row["uptime"])
        }
    finally:
        await conn.close()


# ======================================================
# TABLE STATS TOOL
# ======================================================
@mcp.tool()
async def table_stats(limit: int = 50):
    """Return table sizes, row estimates, index sizes."""
    conn = await asyncpg.connect(DATABASE_URL)
    try:
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
        rows = await conn.fetch(q, limit)
        return {"ok": True, "stats": [dict(r) for r in rows]}
    except Exception as e:
        return {"ok": False, "error": str(e)}
    finally:
        await conn.close()


# ======================================================
# SLOW QUERIES TOOL
# ======================================================
@mcp.tool()
async def slow_queries(limit: int = 10):
    """Return slowest queries from pg_stat_statements."""
    conn = await asyncpg.connect(DATABASE_URL)
    try:
        q = """
        SELECT query, calls, total_time, mean_time
        FROM pg_stat_statements
        ORDER BY total_time DESC
        LIMIT $1;
        """
        rows = await conn.fetch(q, limit)

        parsed = []
        for r in rows:
            parsed.append({
                "query": r["query"],
                "calls": int(r["calls"]),
                "total_time_ms": float(r["total_time"]),
                "mean_time_ms": float(r["mean_time"])
            })
        return {"ok": True, "slow_queries": parsed}
    except asyncpg.UndefinedTableError:
        return {"ok": False, "error": "pg_stat_statements not enabled"}
    except Exception as e:
        return {"ok": False, "error": str(e)}
    finally:
        await conn.close()


# ======================================================
# EXPLAIN QUERY TOOL
# ======================================================
@mcp.tool()
async def explain_query(query: str, analyze: bool = False):
    """EXPLAIN (FORMAT JSON) for any read-only SQL."""
    bad = ["insert", "update", "delete", "drop", "alter", "truncate"]
    if any(x in query.lower() for x in bad):
        return {"ok": False, "error": "EXPLAIN allowed only for SELECT"}

    conn = await asyncpg.connect(DATABASE_URL)
    try:
        stmt = "EXPLAIN (FORMAT JSON"
        if analyze:
            stmt += ", ANALYZE true"
        stmt += ") " + query

        rows = await conn.fetch(stmt)
        plan = rows[0][0]  # JSON plan

        return {"ok": True, "plan": plan}
    except Exception as e:
        return {"ok": False, "error": str(e)}
    finally:
        await conn.close()