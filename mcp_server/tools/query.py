from fastapi import Request
from mcp_server.db import get_pool
import os

async def sql_query(request: Request):
    data = await request.json()
    query = data.get("query")

    if not query:
        return {"ok": False, "error": "Missing SQL query"}

    # Hard guard: never allow writes in production
    if os.getenv("ENV", "development") == "production":
        return {
            "ok": False,
            "error": "sql_query is disabled in production environments"
        }

    pool = await get_pool(role="write")

    try:
        async with pool.acquire() as conn:
            result = await conn.execute(query)
            return {"ok": True, "result": result}
    except Exception as e:
        return {"ok": False, "error": str(e)}