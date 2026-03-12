import asyncpg

from mcp_server.sql import explain_sql, is_likely_write_sql, normalize_query


async def index_advisor(query: str):
    try:
        sql = normalize_query(query, empty_message="Missing SQL to analyze")
        if is_likely_write_sql(sql):
            return {"ok": False, "error": "DDL/DML statements are not allowed"}

        plan_doc = await explain_sql(sql)
        plan_root = plan_doc[0]["Plan"] if isinstance(plan_doc, list) else plan_doc["Plan"]
        recommendations: list[str] = []

        def walk(node):
            node_type = node.get("Node Type")
            relation = node.get("Relation Name")
            filter_cond = node.get("Filter")

            if node_type == "Seq Scan" and relation and filter_cond:
                recommendations.append(
                    f"Seq Scan on '{relation}' with filter '{filter_cond}'. "
                    "Consider an index on the filtered columns."
                )

            for child in node.get("Plans", []):
                walk(child)

        walk(plan_root)

        if not recommendations:
            recommendations.append("No obvious index recommendations found")

        return {"ok": True, "recommendations": recommendations}
    except asyncpg.ReadOnlySQLTransactionError:
        return {"ok": False, "error": "DDL/DML statements are not allowed"}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
