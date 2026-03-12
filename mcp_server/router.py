from fastapi import FastAPI, Request

from mcp_server.auth import require_request_api_key
from mcp_server.tools.query import sql_query
from mcp_server.tools.safe_query import sql_safe
from mcp_server.tools.health import health_check, uptime_check
from mcp_server.tools.schema import get_schema
from mcp_server.tools.explain import explain_query
from mcp_server.tools.stats import table_stats, slow_queries
from mcp_server.tools.index_advisor import index_advisor
from mcp_server.tools.audit import audit_logs


def register_mcp_tools(app: FastAPI):
    async def health_http(request: Request):
        await require_request_api_key(request)
        return await health_check()

    async def uptime_http(request: Request):
        await require_request_api_key(request)
        return await uptime_check()

    async def schema_http(request: Request):
        await require_request_api_key(request)
        return await get_schema()

    async def explain_query_http(request: Request):
        await require_request_api_key(request)
        data = await request.json()
        return await explain_query(data.get("query"), data.get("analyze", False))

    async def index_advisor_http(request: Request):
        await require_request_api_key(request)
        data = await request.json()
        return await index_advisor(data.get("query"))

    async def table_stats_http(request: Request, limit: int = 50):
        await require_request_api_key(request)
        return await table_stats(limit)

    async def slow_queries_http(request: Request, limit: int = 10):
        await require_request_api_key(request)
        return await slow_queries(limit)

    async def audit_logs_http(request: Request, limit: int = 50, tool_name: str | None = None, ok: bool | None = None):
        await require_request_api_key(request)
        return await audit_logs(limit=limit, tool_name=tool_name, ok=ok)

    app.get("/")(health_http)
    app.get("/uptime")(uptime_http)
    app.get("/get_schema")(schema_http)

    app.post("/sql_query")(sql_query)
    app.post("/sql_safe_query")(sql_safe)

    app.post("/explain_query")(explain_query_http)
    app.post("/index_advisor")(index_advisor_http)

    app.get("/stats/table_stats")(table_stats_http)
    app.get("/stats/slow_queries")(slow_queries_http)
    app.get("/audit_logs")(audit_logs_http)
