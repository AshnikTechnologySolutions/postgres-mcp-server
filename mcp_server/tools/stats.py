# mcp_server/tools/stats.py
from typing import Any
from mcp_server.db import get_pool

# Returns per-table stats: relname, estimated_rows, table_size, index_size, total_size
async def table_stats(limit: int = 50) -> dict[str, Any]:
    pool = await get_pool(role="read")
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
        WHERE c.relkind = 'r' -- ordinary table
          AND n.nspname = 'public'
        ORDER BY pg_total_relation_size(c.oid) DESC
        LIMIT $1;
        """
        async with pool.acquire() as conn:
            rows = await conn.fetch(q, limit)
            return {"ok": True, "stats": [dict(r) for r in rows]}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# Returns top slow queries (requires pg_stat_statements extension), fallback to empty list with message
async def slow_queries(limit: int = 10) -> dict[str, Any]:
    pool = await get_pool(role="read")
    try:
        # prefer pg_stat_statements if available
        q = """
        SELECT
          query,
          calls,
          total_time,
          mean_time,
          shared_blks_hit,
          shared_blks_read
        FROM pg_stat_statements
        ORDER BY total_time DESC
        LIMIT $1;
        """
        async with pool.acquire() as conn:
            rows = await conn.fetch(q, limit)
            if not rows:
                return {"ok": True, "slow_queries": []}
            # convert numeric fields into floats for JSON friendliness
            parsed = []
            for r in rows:
                parsed.append({
                    "query": r["query"],
                    "calls": int(r["calls"]) if r["calls"] is not None else 0,
                    "total_time_ms": float(r["total_time"]) if r["total_time"] is not None else None,
                    "mean_time_ms": float(r["mean_time"]) if r["mean_time"] is not None else None,
                    "shared_blks_hit": int(r.get("shared_blks_hit") or 0),
                    "shared_blks_read": int(r.get("shared_blks_read") or 0),
                })
            return {"ok": True, "slow_queries": parsed}
    except Exception as e:
        # Handle pg_stat_statements not enabled error by message match
        if getattr(e, "__class__", None) and e.__class__.__name__ == "UndefinedTableError":
            return {"ok": False, "error": "pg_stat_statements extension not enabled. Enable it with: CREATE EXTENSION pg_stat_statements;"}
        return {"ok": False, "error": str(e)}