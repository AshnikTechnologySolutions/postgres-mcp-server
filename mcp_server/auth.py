import hmac
import os

from fastapi import HTTPException, Request, status


async def require_request_api_key(request: Request) -> None:
    expected = os.getenv("MCP_HTTP_API_KEY")
    if not expected:
        return

    provided = request.headers.get("x-api-key") or ""
    if not hmac.compare_digest(provided, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid API key",
        )
