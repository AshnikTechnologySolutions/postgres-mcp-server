from fastapi import Request
from mcp_server.db import get_pool

async def sql_query(request: Request):
    data = await request.json()
    query = data.get("query")

    if not query:
        return {"ok": False, "error": "Missing SQL query"}

    pool = await get_pool()

    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(query)
            return {"ok": True, "rows": [dict(r) for r in rows]}
    except Exception as e:
        return {"ok": False, "error": str(e)}