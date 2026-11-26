"""Shared security primitives used by backend services."""

import hashlib


def token_digest(token: str) -> str:
    """Return the SHA-256 hexadecimal digest of a token.

    Store and compare this digest rather than persisting the raw token.
    """
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
