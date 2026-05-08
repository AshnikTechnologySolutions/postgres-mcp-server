from mcp_server.config import ALLOW_ARBITRARY_SQL
from mcp_server.sql import execute_sql, fetch_rows, is_fetch_sql, normalize_query


async def sql_query(query: str):
    if not ALLOW_ARBITRARY_SQL:
        return {"ok": False, "error": "Unsafe SQL disabled. Set ALLOW_ARBITRARY_SQL=true in .env"}

    try:
        sql = normalize_query(query)
        if is_fetch_sql(sql):
            return {"ok": True, "rows": await fetch_rows(sql, role="write")}
        return {"ok": True, "command": await execute_sql(sql, role="write")}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
