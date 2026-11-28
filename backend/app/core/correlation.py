"""Backend request correlation IDs shared with downstream services."""

import hmac
import os
import re
from contextvars import ContextVar
from hashlib import sha256
from uuid import uuid4


CORRELATION_ID_HEADER = "X-Correlation-ID"
_CORRELATION_ID_PATTERN = re.compile(r"[A-Za-z0-9._:-]{1,128}\Z")
_current_correlation_id: ContextVar[str | None] = ContextVar(
    "backend_correlation_id", default=None
)


def is_valid_correlation_id(value: str | None) -> bool:
    return value is not None and _CORRELATION_ID_PATTERN.fullmatch(value) is not None


def new_correlation_id() -> str:
    return uuid4().hex


def correlation_id_fingerprint(value: str | None) -> str | None:
    """Return a keyed, non-raw log identifier when the shared key is strong."""

    if value is None:
        return None
    key = os.getenv("AGENT_SERVICE_SHARED_SECRET", "").strip().encode("utf-8")
    # The setup guide generates 32 random bytes. Missing or shorter credentials
    # must not silently fall back to an unkeyed hash.
    if len(key) < 32:
        return None
    digest = hmac.new(key, value.encode("utf-8"), sha256).hexdigest()
    return f"hmac-sha256:{digest}"


def get_current_correlation_id() -> str | None:
    """Return the ID bound to the current request, if one is active."""

    return _current_correlation_id.get()


class CorrelationIdMiddleware:
    """Validate or create a request ID and bind it for downstream calls."""

    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        from starlette.requests import Request

        request = Request(scope, receive=receive)
        supplied = request.headers.get(CORRELATION_ID_HEADER)
        correlation_id = (
            supplied if is_valid_correlation_id(supplied) else new_correlation_id()
        )
        scope.setdefault("state", {})["correlation_id"] = correlation_id
        token = _current_correlation_id.set(correlation_id)

        async def send_with_correlation_id(message) -> None:
            if message["type"] == "http.response.start":
                headers = [
                    (name, value)
                    for name, value in message.get("headers", [])
                    if name.lower() != CORRELATION_ID_HEADER.lower().encode("ascii")
                ]
                headers.append(
                    (
                        CORRELATION_ID_HEADER.lower().encode("ascii"),
                        correlation_id.encode("ascii"),
                    )
                )
                message["headers"] = headers
            await send(message)

        try:
            await self.app(scope, receive, send_with_correlation_id)
        finally:
            _current_correlation_id.reset(token)
