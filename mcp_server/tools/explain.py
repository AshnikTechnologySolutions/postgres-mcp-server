# mcp_server/tools/explain.py
import asyncpg
import json
from typing import Any
from mcp_server.config import DATABASE_URL

# Explain (or Explain Analyze) a given SQL. Returns JSON plan or text.
# payload: {"query": "...", "analyze": false}
async def explain_query(query: str, analyze: bool = False) -> dict[str, Any]:
    if not query or not query.strip():
        return {"ok": False, "error": "Missing SQL to explain"}

    # keep it read-only
    forbidden = ("insert", "update", "delete", "create", "drop", "alter", "truncate")
    if any(token in query.lower() for token in forbidden):
        return {"ok": False, "error": "Refusing to run EXPLAIN on DDL/DML statements"}

    conn = await asyncpg.connect(DATABASE_URL)
    try:
        stmt = "EXPLAIN (FORMAT JSON"
        if analyze:
            stmt += ", ANALYZE true"
        stmt += ") " + query

        # fetch returns rows where first column contains JSON text
        rows = await conn.fetch(stmt)
        # PostgreSQL returns one row, first column is JSON array (explain output)
        if not rows:
            return {"ok": False, "error": "No explain output"}
        raw = rows[0][0]  # first row, first column
        # raw is usually a list with plan structure
        return {"ok": True, "plan": raw}
    except Exception as e:
        return {"ok": False, "error": str(e)}
    finally:
        await conn.close()