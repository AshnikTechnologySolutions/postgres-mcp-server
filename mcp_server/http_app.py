from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from mcp_server.otel import init_otel
from mcp_server.otel import set_current_span_attribute
from mcp_server.request_context import generate_request_id, reset_request_id, set_request_id
from mcp_server.router import register_mcp_tools
from mcp_server.tools.ops import readiness as readiness_check

app = FastAPI(title="postgres-mcp-http", version="1.0.0")


@app.middleware("http")
async def request_context_middleware(request: Request, call_next):
    request_id = request.headers.get("x-request-id") or generate_request_id()
    request.state.request_id = request_id
    token = set_request_id(request_id)
    set_current_span_attribute("http.request_id", request_id)

    try:
        response = await call_next(request)
    finally:
        reset_request_id(token)

    response.headers["x-request-id"] = request_id
    return response


@app.get("/healthz")
async def healthz():
    return {"ok": True, "status": "alive"}


@app.get("/readyz")
async def readyz():
    result = await readiness_check()
    return JSONResponse(result, status_code=200 if result.get("ok") else 503)


register_mcp_tools(app)
init_otel(app)
