from __future__ import annotations

import asyncio
import hashlib
import json
import re
from collections import deque
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from mcp_server.config import AUDIT_LOG_MAX_QUERY_PREVIEW, AUDIT_LOG_PATH as _AUDIT_LOG_PATH
from mcp_server.otel import current_trace_context
from mcp_server.request_context import get_request_id

_STRING_LITERAL_RE = re.compile(r"'(?:''|[^'])*'")
_NUMERIC_LITERAL_RE = re.compile(r"\b\d+(?:\.\d+)?\b")

AUDIT_LOG_PATH = Path(_AUDIT_LOG_PATH)


def _sanitize_query(query: str | None) -> str | None:
    if not query:
        return None

    sanitized = _STRING_LITERAL_RE.sub("'?'", query)
    sanitized = _NUMERIC_LITERAL_RE.sub("?", sanitized)
    sanitized = " ".join(sanitized.split())
    return sanitized[:AUDIT_LOG_MAX_QUERY_PREVIEW]


def _query_sha256(query: str | None) -> str | None:
    if not query:
        return None
    return hashlib.sha256(query.encode("utf-8")).hexdigest()


def _audit_path() -> Path:
    return AUDIT_LOG_PATH if AUDIT_LOG_PATH.is_absolute() else Path.cwd() / AUDIT_LOG_PATH


def _write_event_sync(event: dict[str, Any]) -> None:
    path = _audit_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, sort_keys=True) + "\n")


async def log_audit_event(
    *,
    tool_name: str,
    ok: bool,
    transport: str,
    query: str | None = None,
    details: dict[str, Any] | None = None,
    error: str | None = None,
) -> None:
    trace_context = current_trace_context()
    event = {
        "timestamp": datetime.now(UTC).isoformat(),
        "level": "info" if ok else "error",
        "tool_name": tool_name,
        "ok": ok,
        "transport": transport,
        "request_id": get_request_id(),
        "trace_id": trace_context["trace_id"],
        "span_id": trace_context["span_id"],
        "query_preview": _sanitize_query(query),
        "query_sha256": _query_sha256(query),
        "error": error,
        "details": details or {},
    }
    await asyncio.to_thread(_write_event_sync, event)


def _parse_event(line: str) -> dict[str, Any] | None:
    try:
        parsed = json.loads(line)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


async def read_audit_events(
    *,
    limit: int = 50,
    tool_name: str | None = None,
    ok: bool | None = None,
) -> list[dict[str, Any]]:
    path = _audit_path()
    if not path.exists():
        return []

    # When filtering, read a larger window so filters have enough events to match against.
    scan_size = max(limit * 50, 1000) if (tool_name is not None or ok is not None) else max(limit * 20, 200)

    def _read_sync() -> list[dict[str, Any]]:
        with path.open("r", encoding="utf-8") as handle:
            lines = deque(handle, maxlen=scan_size)

        events: list[dict[str, Any]] = []
        for line in reversed(lines):
            event = _parse_event(line)
            if not event:
                continue
            if tool_name and event.get("tool_name") != tool_name:
                continue
            if ok is not None and event.get("ok") is not ok:
                continue
            events.append(event)
            if len(events) >= limit:
                break
        return events

    return await asyncio.to_thread(_read_sync)
