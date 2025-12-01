from mcp_server.db import get_pool

async def get_schema():
    sql = """
        SELECT table_name, column_name
        FROM information_schema.columns
        WHERE table_schema = 'public'
        ORDER BY table_name, ordinal_position;
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(sql)

    schema = {}
    for r in rows:
        schema.setdefault(r["table_name"], []).append(r["column_name"])

    return {"ok": True, "schema": schema}