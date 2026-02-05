from fastapi import Request
from mcp_server.db import get_pool
import re

FORBIDDEN = re.compile(r"\b(insert|update|delete|drop|alter|truncate)\b", re.I)

async def sql_safe(request: Request):
    data = await request.json()
    query = data.get("query")

    if not query:
        return {"ok": False, "error": "Missing SQL query"}

    if FORBIDDEN.search(query):
        return {
            "ok": False,
            "error": "Read-only mode: write operations are not allowed"
        }

    pool = await get_pool(role="read")

    try:
        async with pool.acquire() as conn:
            await conn.execute("SET TRANSACTION READ ONLY")
            rows = await conn.fetch(query)
            return {"ok": True, "rows": [dict(r) for r in rows]}
    except Exception as e:
        return {"ok": False, "error": str(e)}
