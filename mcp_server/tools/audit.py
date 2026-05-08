from mcp_server.audit import read_audit_events
from mcp_server.sql import coerce_limit


async def audit_logs(limit: int = 50, tool_name: str | None = None, ok: bool | None = None):
    try:
        safe_limit = coerce_limit(limit, default=50)
        events = await read_audit_events(limit=safe_limit, tool_name=tool_name, ok=ok)
        return {"ok": True, "events": events}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
