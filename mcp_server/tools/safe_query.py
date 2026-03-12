import asyncpg
from fastapi import Request

from mcp_server.auth import require_request_api_key
from mcp_server.sql import fetch_rows, normalize_query


async def sql_safe(request: Request):
    await require_request_api_key(request)
    data = await request.json()
    query = data.get("query")

    try:
        sql = normalize_query(query)
        return {"ok": True, "rows": await fetch_rows(sql, role="read", read_only=True)}
    except asyncpg.ReadOnlySQLTransactionError:
        return {"ok": False, "error": "Read-only mode: write operations are not allowed"}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
