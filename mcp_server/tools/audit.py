from mcp_server.audit import read_audit_events
from mcp_server.sql import QueryValidationError


def _coerce_limit(limit: int, *, default: int, maximum: int = 500) -> int:
    value = int(limit if limit is not None else default)
    if value < 1 or value > maximum:
        raise QueryValidationError(f"limit must be between 1 and {maximum}")
    return value


async def audit_logs(limit: int = 50, tool_name: str | None = None, ok: bool | None = None):
    try:
        safe_limit = _coerce_limit(limit, default=50)
        events = await read_audit_events(limit=safe_limit, tool_name=tool_name, ok=ok)
        return {"ok": True, "events": events}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
