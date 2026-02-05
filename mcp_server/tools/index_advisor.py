from typing import Any, Dict, List
from mcp_server.db import get_pool

# Index advisor derived from EXPLAIN JSON
async def index_advisor(query: str) -> Dict[str, Any]:
    if not query or not query.strip():
        return {"ok": False, "error": "Missing SQL to analyze"}

    forbidden = ("insert", "update", "delete", "create", "drop", "alter", "truncate")
    if any(tok in query.lower() for tok in forbidden):
        return {"ok": False, "error": "DDL/DML statements are not allowed"}

    # Safe EXPLAIN only
    stmt = f"EXPLAIN (FORMAT JSON, ANALYZE false, BUFFERS false) {query}"

    pool = await get_pool(role="read")

    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(stmt)
            plan = rows[0][0][0]["Plan"]

        recommendations: List[str] = []

        def walk(node: Dict[str, Any]):
            node_type = node.get("Node Type", "")
            relation = node.get("Relation Name")
            filter_cond = node.get("Filter")
            index_cond = node.get("Index Cond")

            # Classic anti-pattern: Seq Scan + Filter
            if node_type == "Seq Scan" and relation and filter_cond:
                recommendations.append(
                    f"Seq Scan on '{relation}' with filter '{filter_cond}'. "
                    f"Consider an index on the filtered columns."
                )

            for child in node.get("Plans", []):
                walk(child)

        walk(plan)

        if not recommendations:
            recommendations.append("No obvious index recommendations found")

        return {
            "ok": True,
            "recommendations": recommendations
        }

    except Exception as e:
        return {"ok": False, "error": str(e)}