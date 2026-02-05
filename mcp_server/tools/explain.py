# mcp_server/tools/explain.py
from typing import Any
from mcp_server.db import get_pool

# Explain (or Explain Analyze) a given SQL. Returns JSON plan or text.
# payload: {"query": "...", "analyze": false}
async def explain_query(query: str, analyze: bool = False) -> dict[str, Any]:
    if not query or not query.strip():
        return {"ok": False, "error": "Missing SQL to explain"}

    # keep it read-only
    forbidden = ("insert", "update", "delete", "create", "drop", "alter", "truncate")
    if any(token in query.lower() for token in forbidden):
        return {"ok": False, "error": "Refusing to run EXPLAIN on DDL/DML statements"}

    # Forbid ANALYZE true entirely
    if analyze:
        return {"ok": False, "error": "ANALYZE true is forbidden for safety"}

    # Always force FORMAT JSON, ANALYZE false, BUFFERS false
    stmt = f"EXPLAIN (FORMAT JSON, ANALYZE false, BUFFERS false) {query}"

    pool = await get_pool(role="read")
    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(stmt)
            if not rows:
                return {"ok": False, "error": "No explain output"}
            raw = rows[0][0]
            return {"ok": True, "plan": raw}
    except Exception as e:
        return {"ok": False, "error": str(e)}