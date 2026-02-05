# mcp_server/tools/uptime.py
from datetime import datetime
from typing import Any
from mcp_server.db import get_pool

# Returns server uptime (interval) and start time
async def uptime() -> dict[str, Any]:
    pool = await get_pool(role="read")
    try:
        q = "SELECT pg_postmaster_start_time() AS start_time, now() - pg_postmaster_start_time() AS uptime;"
        async with pool.acquire() as conn:
            row = await conn.fetchrow(q)
        if not row:
            return {"ok": False, "error": "No uptime info"}
        return {
            "ok": True,
            "started_at": row["start_time"].isoformat() if isinstance(row["start_time"], datetime) else str(row["start_time"]),
            "uptime_interval": str(row["uptime"])
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}
