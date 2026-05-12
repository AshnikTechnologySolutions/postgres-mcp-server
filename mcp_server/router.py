from typing import Any

from fastapi import FastAPI, HTTPException, Request

from mcp_server.auth import require_request_api_key
from mcp_server.audit import log_audit_event
from mcp_server.tools.query import sql_query
from mcp_server.tools.safe_query import sql_safe
from mcp_server.tools.health import health_check, uptime_check
from mcp_server.tools.schema import get_schema
from mcp_server.tools.explain import explain_query
from mcp_server.tools.stats import table_stats, slow_queries
from mcp_server.tools.index_advisor import index_advisor
from mcp_server.tools.audit import audit_logs
from mcp_server.tools.ops import (
    access_scope,
    audit_summary,
    config_status,
    index_usage,
    locks,
    pool_status,
    readiness,
    redaction_test,
    replication_status,
    vacuum_status,
)


def register_mcp_tools(app: FastAPI):
    async def _request_json_object(request: Request) -> dict[str, Any]:
        try:
            data = await request.json()
        except Exception:
            return {}
        return data if isinstance(data, dict) else {}

    async def _audit_http_result(
        *,
        request: Request,
        tool_name: str,
        result: Any,
        query: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> Any:
        ok = True
        error = None
        response_details = {
            "path": request.url.path,
            "method": request.method,
        }
        if details:
            response_details.update(details)

        if isinstance(result, dict):
            ok = bool(result.get("ok", True))
            if not ok:
                error = str(result.get("error") or "request failed")
            if "rows" in result and isinstance(result["rows"], list):
                response_details.setdefault("row_count", len(result["rows"]))
            if "events" in result and isinstance(result["events"], list):
                response_details.setdefault("event_count", len(result["events"]))
            if "stats" in result and isinstance(result["stats"], list):
                response_details.setdefault("row_count", len(result["stats"]))

        await log_audit_event(
            tool_name=tool_name,
            ok=ok,
            transport="http",
            query=query,
            details=response_details,
            error=error,
        )
        return result

    async def _call_http_tool(
        *,
        request: Request,
        tool_name: str,
        callback,
        query: str | None = None,
        details: dict[str, Any] | None = None,
    ):
        await require_request_api_key(request)
        try:
            result = await callback()
        except HTTPException as exc:
            await log_audit_event(
                tool_name=tool_name,
                ok=False,
                transport="http",
                query=query,
                details={"path": request.url.path, "method": request.method, "status_code": exc.status_code},
                error=str(exc.detail),
            )
            raise
        except Exception as exc:
            await log_audit_event(
                tool_name=tool_name,
                ok=False,
                transport="http",
                query=query,
                details={"path": request.url.path, "method": request.method},
                error=str(exc),
            )
            raise

        return await _audit_http_result(
            request=request,
            tool_name=tool_name,
            result=result,
            query=query,
            details=details,
        )

    async def health_http(request: Request):
        return await _call_http_tool(request=request, tool_name="health", callback=health_check)

    async def uptime_http(request: Request):
        return await _call_http_tool(request=request, tool_name="uptime", callback=uptime_check)

    async def schema_http(request: Request):
        return await _call_http_tool(request=request, tool_name="schema", callback=get_schema)

    async def sql_query_http(request: Request):
        data = await _request_json_object(request)
        query = data.get("query")
        return await _call_http_tool(
            request=request,
            tool_name="sql_query",
            callback=lambda: sql_query(query),
            query=query,
        )

    async def sql_safe_http(request: Request):
        data = await _request_json_object(request)
        query = data.get("query")
        return await _call_http_tool(
            request=request,
            tool_name="sql_safe",
            callback=lambda: sql_safe(query),
            query=query,
        )

    async def explain_query_http(request: Request):
        data = await _request_json_object(request)
        query = data.get("query")
        analyze = bool(data.get("analyze", False))
        return await _call_http_tool(
            request=request,
            tool_name="explain_query",
            callback=lambda: explain_query(query, analyze),
            query=query,
            details={"analyze": analyze},
        )

    async def index_advisor_http(request: Request):
        data = await _request_json_object(request)
        query = data.get("query")
        return await _call_http_tool(
            request=request,
            tool_name="index_advisor",
            callback=lambda: index_advisor(query),
            query=query,
        )

    async def table_stats_http(request: Request, limit: int = 50):
        return await _call_http_tool(
            request=request,
            tool_name="table_stats",
            callback=lambda: table_stats(limit),
            details={"limit": limit},
        )

    async def slow_queries_http(request: Request, limit: int = 10):
        return await _call_http_tool(
            request=request,
            tool_name="slow_queries",
            callback=lambda: slow_queries(limit),
            details={"limit": limit},
        )

    async def audit_logs_http(request: Request, limit: int = 50, tool_name: str | None = None, ok: bool | None = None):
        return await _call_http_tool(
            request=request,
            tool_name="audit_logs",
            callback=lambda: audit_logs(limit=limit, tool_name=tool_name, ok=ok),
            details={"limit": limit, "filter_tool_name": tool_name, "filter_ok": ok},
        )

    async def readiness_http(request: Request):
        return await _call_http_tool(request=request, tool_name="readiness", callback=readiness)

    async def config_status_http(request: Request):
        return await _call_http_tool(request=request, tool_name="config_status", callback=config_status)

    async def audit_summary_http(request: Request, limit: int = 200):
        return await _call_http_tool(
            request=request,
            tool_name="audit_summary",
            callback=lambda: audit_summary(limit=limit),
            details={"limit": limit},
        )

    async def access_scope_http(request: Request, limit: int = 200):
        return await _call_http_tool(
            request=request,
            tool_name="access_scope",
            callback=lambda: access_scope(limit=limit),
            details={"limit": limit},
        )

    async def pool_status_http(request: Request):
        return await _call_http_tool(request=request, tool_name="pool_status", callback=pool_status)

    async def locks_http(request: Request, limit: int = 50):
        return await _call_http_tool(
            request=request,
            tool_name="locks",
            callback=lambda: locks(limit=limit),
            details={"limit": limit},
        )

    async def index_usage_http(request: Request, limit: int = 100):
        return await _call_http_tool(
            request=request,
            tool_name="index_usage",
            callback=lambda: index_usage(limit=limit),
            details={"limit": limit},
        )

    async def vacuum_status_http(request: Request, limit: int = 100):
        return await _call_http_tool(
            request=request,
            tool_name="vacuum_status",
            callback=lambda: vacuum_status(limit=limit),
            details={"limit": limit},
        )

    async def replication_status_http(request: Request, limit: int = 50):
        return await _call_http_tool(
            request=request,
            tool_name="replication_status",
            callback=lambda: replication_status(limit=limit),
            details={"limit": limit},
        )

    async def redaction_test_http(request: Request):
        data = await _request_json_object(request)
        value = data.get("value")
        return await _call_http_tool(
            request=request,
            tool_name="redaction_test",
            callback=lambda: redaction_test(value),
            details={"input_present": bool(value)},
        )

    app.get("/")(health_http)
    app.get("/uptime")(uptime_http)
    app.get("/get_schema")(schema_http)

    app.post("/sql_query")(sql_query_http)
    app.post("/sql_safe_query")(sql_safe_http)

    app.post("/explain_query")(explain_query_http)
    app.post("/index_advisor")(index_advisor_http)

    app.get("/stats/table_stats")(table_stats_http)
    app.get("/stats/slow_queries")(slow_queries_http)
    app.get("/audit_logs")(audit_logs_http)
    app.get("/readiness")(readiness_http)
    app.get("/config_status")(config_status_http)
    app.get("/audit_summary")(audit_summary_http)
    app.get("/access_scope")(access_scope_http)
    app.get("/pool_status")(pool_status_http)
    app.get("/locks")(locks_http)
    app.get("/index_usage")(index_usage_http)
    app.get("/vacuum_status")(vacuum_status_http)
    app.get("/replication_status")(replication_status_http)
    app.post("/redaction_test")(redaction_test_http)
