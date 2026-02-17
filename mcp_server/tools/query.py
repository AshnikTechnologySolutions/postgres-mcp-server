from fastapi import Request
from mcp_server.db import get_pool
from mcp_server.config import ALLOW_ARBITRARY_SQL

async def sql_query(request: Request):
    try:
        data = await request.json()
    except Exception:
        return {"ok": False, "error": "Invalid JSON body"}

    query = data.get("query")

    if not query:
        return {"ok": False, "error": "Missing SQL query"}

    if not ALLOW_ARBITRARY_SQL:
        return {
            "ok": False,
            "error": "Unsafe SQL disabled. Set ALLOW_ARBITRARY_SQL=true in .env"
        }

    pool = await get_pool(role="write")

    try:
        async with pool.acquire() as conn:
            # Return rows for row-producing statements, command status otherwise.
            if query.lstrip().lower().startswith(("select", "with", "show", "explain", "values")):
                rows = await conn.fetch(query)
                return {"ok": True, "rows": [dict(r) for r in rows]}

            result = await conn.execute(query)
            return {"ok": True, "result": result}
    except Exception as e:
        return {"ok": False, "error": str(e)}
