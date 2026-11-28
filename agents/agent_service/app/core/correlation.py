"""Validation helpers for request correlation metadata."""

import hmac
import os
import re
from hashlib import sha256
from uuid import uuid4


CORRELATION_ID_HEADER = "X-Correlation-ID"
_CORRELATION_ID_PATTERN = re.compile(r"[A-Za-z0-9._:-]{1,128}\Z")


def is_valid_correlation_id(value: str | None) -> bool:
    return value is not None and _CORRELATION_ID_PATTERN.fullmatch(value) is not None


def new_correlation_id() -> str:
    return uuid4().hex


def correlation_id_fingerprint(value: str | None) -> str | None:
    """Return the same keyed, non-raw log fingerprint as Backend."""

    if value is None:
        return None
    key = os.getenv("AGENT_SERVICE_SHARED_SECRET", "").strip().encode("utf-8")
    # The setup guide generates 32 random bytes. Missing or shorter credentials
    # must not silently fall back to an unkeyed hash.
    if len(key) < 32:
        return None
    digest = hmac.new(key, value.encode("utf-8"), sha256).hexdigest()
    return f"hmac-sha256:{digest}"


def request_correlation_id(request: object) -> str:
    """Return the middleware value, or a fresh safe ID for direct handler use."""

    state = getattr(request, "state", None)
    current = getattr(state, "correlation_id", None)
    if is_valid_correlation_id(current):
        return current

    headers = getattr(request, "headers", {})
    candidate = headers.get(CORRELATION_ID_HEADER)
    return candidate if is_valid_correlation_id(candidate) else new_correlation_id()
