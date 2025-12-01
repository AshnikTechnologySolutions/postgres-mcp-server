from mcp_server.db import get_pool

async def health_check():
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            version = await conn.fetchval("SELECT version();")
            return {
                "ok": True,
                "service": "PostgreSQL MCP Server",
                "status": "running",
                "postgres_version": version
            }
    except Exception as e:
        return {"ok": False, "error": str(e)}

async def uptime_check():
    pool = await get_pool()
    async with pool.acquire() as conn:
        uptime = await conn.fetchval("SELECT now() - pg_postmaster_start_time();")
        return {"ok": True, "uptime": str(uptime)}