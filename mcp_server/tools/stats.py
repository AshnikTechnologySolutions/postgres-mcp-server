from mcp_server.sql import QueryValidationError, detect_pg_stat_statements_columns, fetch_rows


def _coerce_limit(limit: int, *, default: int, maximum: int = 200) -> int:
    value = int(limit if limit is not None else default)
    if value < 1 or value > maximum:
        raise QueryValidationError(f"limit must be between 1 and {maximum}")
    return value


async def table_stats(limit: int = 50):
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
        return {"ok": True, "stats": rows}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


async def slow_queries(limit: int = 10):
    try:
        safe_limit = _coerce_limit(limit, default=10, maximum=100)
        total_col, mean_col = await detect_pg_stat_statements_columns()
        rows = await fetch_rows(
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
            role="read",
            read_only=True,
        )
        return {"ok": True, "slow_queries": rows}
    except QueryValidationError as exc:
        return {"ok": False, "error": str(exc)}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
