from __future__ import annotations

from contextvars import ContextVar, Token
from uuid import uuid4

_request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)


def generate_request_id() -> str:
    return uuid4().hex


def get_request_id() -> str | None:
    return _request_id_var.get()


def set_request_id(request_id: str) -> Token[str | None]:
    return _request_id_var.set(request_id)


def reset_request_id(token: Token[str | None]) -> None:
    _request_id_var.reset(token)
