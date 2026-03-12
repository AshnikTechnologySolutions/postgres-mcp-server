from mcp_server.sql import fetch_rows


async def health_check():
    try:
        rows = await fetch_rows(
            """
            SELECT
                version() AS postgres_version,
                current_database() AS database_name,
                current_user AS database_user
            """,
            role="read",
            read_only=True,
        )
        return {
            "ok": True,
            "service": "PostgreSQL MCP Server",
            "status": "running",
            **rows[0],
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


async def uptime_check():
    try:
        rows = await fetch_rows(
            """
            SELECT
                pg_postmaster_start_time() AS start_time,
                now() - pg_postmaster_start_time() AS uptime
            """,
            role="read",
            read_only=True,
        )
        row = rows[0]
        return {
            "ok": True,
            "start_time": row["start_time"].isoformat(),
            "uptime": str(row["uptime"]),
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
