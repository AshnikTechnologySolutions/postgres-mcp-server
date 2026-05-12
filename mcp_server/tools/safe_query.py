import asyncpg

from mcp_server.sql import fetch_rows, normalize_query


async def sql_safe(query: str):
    try:
        sql = normalize_query(query)
        return {"ok": True, "rows": await fetch_rows(sql, role="read", read_only=True)}
    except asyncpg.ReadOnlySQLTransactionError:
        return {"ok": False, "error": "Read-only mode: write operations are not allowed"}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
