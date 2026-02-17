import re
from fastapi import Request
from mcp_server.db import get_pool

FORBIDDEN = re.compile(
    r"\b(insert|update|delete|drop|alter|truncate|create|grant|revoke|copy|vacuum|call|refresh)\b",
    re.IGNORECASE
)

async def execute_safe_query(query: str):
    if not query or not query.strip():
        return {"ok": False, "error": "Missing SQL query"}

    if FORBIDDEN.search(query):
        return {"ok": False, "error": "Read-only mode: write operations are not allowed"}

    pool = await get_pool(role="read")

    try:
        async with pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute("SET TRANSACTION READ ONLY;")
                rows = await conn.fetch(query)
                return {"ok": True, "rows": [dict(r) for r in rows]}
    except Exception as e:
        return {"ok": False, "error": str(e)}

async def sql_safe(request: Request):
    try:
        data = await request.json()
    except Exception:
        return {"ok": False, "error": "Invalid JSON body"}

    query = data.get("query")
    return await execute_safe_query(query)
