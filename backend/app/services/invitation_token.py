"""Reusable secure token generation for candidate invitations.

This module owns only the invitation token itself: it never creates invitations,
sends messages, or records lifecycle state. The raw token is returned exactly
once to the caller; only its SHA-256 digest is stored on ``ExamInvitation``.
"""

import secrets
from collections.abc import Callable

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import token_digest
from app.models.exam_invitation import ExamInvitation

# 32 random bytes = 256 bits, matching the existing HR session token width.
TOKEN_ENTROPY_BYTES = 32
MIN_TOKEN_ENTROPY_BITS = 128
DEFAULT_MAX_ATTEMPTS = 5

# The unique index declared on ExamInvitation.token_hash.
TOKEN_HASH_CONSTRAINT = "uq_exam_invitations_token_hash"
_SQLITE_TOKEN_HASH_CONFLICT = f"UNIQUE constraint failed: exam_invitations.token_hash"


class InvitationTokenUnavailableError(RuntimeError):
    """Raised when no unique invitation token could be allocated.

    The message is deliberately static: it never includes a raw token, a
    digest, or any candidate/exam identifiers.
    """

    def __init__(self) -> None:
        super().__init__("Unable to allocate a unique invitation token")


def generate_invitation_token() -> str:
    """Return a fresh URL-safe invitation token with 256 bits of entropy.

    ``secrets.token_urlsafe`` uses the operating system's cryptographically
    secure random source and emits URL-safe Base64 without padding. The token
    is independent of candidate, exam, time, and personal data.
    """
    return secrets.token_urlsafe(TOKEN_ENTROPY_BYTES)


def hash_invitation_token(token: str) -> str:
    """Return the SHA-256 digest stored for an invitation token.

    Thin wrapper around the shared ``token_digest`` utility so callers do not
    reimplement hashing and cannot accidentally choose a different digest.
    """
    return token_digest(token)


def token_hash_exists(db: Session, digest: str) -> bool:
    """Report whether ``digest`` is already present in the invitation table."""
    return db.scalar(
        select(ExamInvitation.id).where(ExamInvitation.token_hash == digest).limit(1)
    ) is not None


def allocate_unique_invitation_token(
    db: Session,
    *,
    hash_exists: Callable[[str], bool] | None = None,
    generate: Callable[[], str] | None = None,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
) -> str:
    """Return a raw token whose digest is not yet used by an invitation.

    Each candidate token is hashed and checked against existing invitation
    records before it is returned. A collision triggers a fresh random token,
    up to ``max_attempts`` total attempts. The database unique index on
    ``exam_invitations.token_hash`` remains the final protection: if a
    concurrent writer wins that race, the resulting ``IntegrityError`` is
    translated into ``InvitationTokenUnavailableError`` without exposing the
    token, the digest, or the underlying database message.

    Args:
        db: SQLAlchemy session used for the uniqueness lookup.
        hash_exists: Optional injectable lookup, primarily for tests.
        generate: Optional injectable generator, primarily for tests.
        max_attempts: Maximum number of tokens to try. Must be positive.

    Raises:
        ValueError: If ``max_attempts`` is not positive.
        InvitationTokenUnavailableError: If every attempt collides or the
            database reports a uniqueness conflict.
    """
    if max_attempts < 1:
        raise ValueError("max_attempts must be positive")

    exists = hash_exists or (lambda digest: token_hash_exists(db, digest))
    new_token = generate or generate_invitation_token

    for _ in range(max_attempts):
        token = new_token()
        if not exists(hash_invitation_token(token)):
            return token

    raise InvitationTokenUnavailableError()


def translate_token_conflict(error: IntegrityError) -> None:
    """Translate only the token-hash unique conflict into a token-free error.

    Call this at the invitation persistence boundary when a flush or commit
    fails. The original error is inspected only to identify the exact
    constraint; its text and SQL parameters are never included in the raised
    message. Every other integrity failure is re-raised unchanged.

    Args:
        error: The ``IntegrityError`` raised by SQLAlchemy.

    Raises:
        InvitationTokenUnavailableError: If the error is positively identified
            as a violation of ``uq_exam_invitations_token_hash``.
        IntegrityError: For every other integrity failure.
    """
    if _is_token_hash_conflict(error):
        raise InvitationTokenUnavailableError() from None
    raise error


def _is_token_hash_conflict(error: IntegrityError) -> bool:
    """Identify only the exact invitation token-hash uniqueness violation."""
    original = error.orig

    if not isinstance(original, Exception):
        return False

    # PostgreSQL: inspect the exact violated constraint.
    diagnostic = getattr(original, "diag", None)
    constraint_name = getattr(diagnostic, "constraint_name", None)

    if constraint_name == TOKEN_HASH_CONSTRAINT:
        return True

    # SQLite: match the exact table and column.
    return str(original).strip() == _SQLITE_TOKEN_HASH_CONFLICT
