import asyncpg

from mcp_server.sql import explain_sql, is_likely_write_sql, normalize_query


async def explain_query(query: str, analyze: bool = False):
    if analyze:
        return {"ok": False, "error": "ANALYZE true is forbidden for safety"}

    try:
        sql = normalize_query(query, empty_message="Missing SQL to explain")
        if is_likely_write_sql(sql):
            return {"ok": False, "error": "Refusing to run EXPLAIN on DDL/DML statements"}
        return {"ok": True, "plan": await explain_sql(sql)}
    except asyncpg.ReadOnlySQLTransactionError:
        return {"ok": False, "error": "Refusing to run EXPLAIN on DDL/DML statements"}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
