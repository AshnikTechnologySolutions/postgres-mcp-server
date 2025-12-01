from fastapi import FastAPI

from mcp_server.tools.query import sql_query
from mcp_server.tools.safe_query import sql_safe
from mcp_server.tools.health import health_check, uptime_check
from mcp_server.tools.schema import get_schema
from mcp_server.tools.explain import explain_query
from mcp_server.tools.stats import table_stats, slow_queries


def register_mcp_tools(app: FastAPI):

    app.get("/")(health_check)
    app.get("/uptime")(uptime_check)
    app.get("/get_schema")(get_schema)

    app.post("/sql_query")(sql_query)
    app.post("/sql_safe_query")(sql_safe)

    app.post("/explain_query")(explain_query)

    app.get("/stats/table_stats")(table_stats)
    app.get("/stats/slow_queries")(slow_queries)