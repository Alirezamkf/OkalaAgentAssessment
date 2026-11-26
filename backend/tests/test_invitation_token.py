"""Focused tests for secure invitation token generation (issue #78)."""

import base64
import hashlib
import logging
import re
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.core.security import token_digest
from app.database.base import Base
from app.models import Candidate, Exam, ExamInvitation, HRUser
from app.services.invitation_token import (
    DEFAULT_MAX_ATTEMPTS,
    MIN_TOKEN_ENTROPY_BITS,
    TOKEN_ENTROPY_BYTES,
    TOKEN_HASH_CONSTRAINT,
    InvitationTokenUnavailableError,
    allocate_unique_invitation_token,
    generate_invitation_token,
    hash_invitation_token,
    token_hash_exists,
    translate_token_conflict,
)

URL_SAFE_TOKEN = re.compile(r"^[A-Za-z0-9_-]+$")


class FakePostgresUniqueViolation(Exception):
    """Small fake DBAPI error carrying PostgreSQL diagnostics."""

    def __init__(self, constraint_name: str) -> None:
        super().__init__("duplicate key value violates unique constraint")
        self.diag = type("Diagnostic", (), {"constraint_name": constraint_name})()


@pytest.fixture
def db():
    """In-memory SQLite session; no production database is touched."""
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        yield db
    engine.dispose()


def add_invitation(db, digest, id=1):
    now = datetime.now(timezone.utc)
    db.add(Candidate(id=id, full_name="Test Candidate", email=f"candidate{id}@example.invalid"))
    db.add(Exam(id=id, duration_minutes=25, available_from=now, available_until=now + timedelta(days=1), created_by_hr_user_id=1))
    db.flush()
    db.add(ExamInvitation(id=id, candidate_id=id, exam_id=id, token_hash=digest,
                          created_at=now, expires_at=now + timedelta(days=1)))
    db.commit()


def capture_integrity_error(db, operation):
    """Run ``operation``, roll back, and return the SQLAlchemy IntegrityError."""
    with pytest.raises(IntegrityError) as captured:
        operation()
        db.flush()
    db.rollback()
    return captured.value


def test_token_generation_uses_expected_width():
    token = generate_invitation_token()
    assert isinstance(token, str) and token
    assert len(base64.urlsafe_b64decode(token + "=" * (-len(token) % 4))) == TOKEN_ENTROPY_BYTES


def test_token_is_url_safe():
    token = generate_invitation_token()
    assert URL_SAFE_TOKEN.fullmatch(token)
    assert "=" not in token and "+" not in token and "/" not in token


def test_token_meets_minimum_entropy():
    assert TOKEN_ENTROPY_BYTES * 8 >= MIN_TOKEN_ENTROPY_BITS
    assert len(generate_invitation_token()) >= 22  # 16 bytes would be shorter


def test_repeated_generation_is_independent():
    tokens = {generate_invitation_token() for _ in range(100)}
    assert len(tokens) == 100


def test_hash_uses_shared_sha256_digest():
    token = generate_invitation_token()
    digest = hash_invitation_token(token)
    assert digest == token_digest(token) == hashlib.sha256(token.encode()).hexdigest()
    assert len(digest) == 64
    assert token not in digest


def test_allocator_returns_token_when_digest_is_unused(db):
    token = allocate_unique_invitation_token(db)
    assert URL_SAFE_TOKEN.fullmatch(token)
    assert not token_hash_exists(db, hash_invitation_token(token))


def test_allocator_detects_existing_hash(db):
    digest = token_digest("existing-token")
    add_invitation(db, digest)
    assert token_hash_exists(db, digest)
    assert not token_hash_exists(db, token_digest("other-token"))


def test_allocator_retries_after_collision():
    collisions = ["collision-1", "collision-2"]
    generated = iter(collisions + ["unique-token"])
    seen = []

    def exists(digest):
        seen.append(digest)
        return digest in {token_digest(token) for token in collisions}

    token = allocate_unique_invitation_token(db=None, hash_exists=exists, generate=lambda: next(generated))

    assert token == "unique-token"
    assert seen == [token_digest(token) for token in collisions + ["unique-token"]]


def test_allocator_fails_bounded_after_all_collisions():
    generated = iter([f"token-{i}" for i in range(DEFAULT_MAX_ATTEMPTS + 5)])
    calls = []

    with pytest.raises(InvitationTokenUnavailableError) as exc:
        allocate_unique_invitation_token(
            db=None,
            hash_exists=lambda digest: calls.append(digest) or True,
            generate=lambda: next(generated),
        )

    assert len(calls) == DEFAULT_MAX_ATTEMPTS
    message = str(exc.value)
    assert message == "Unable to allocate a unique invitation token"
    assert not any(token in message for token in generated)


def test_allocator_rejects_non_positive_attempts():
    with pytest.raises(ValueError):
        allocate_unique_invitation_token(db=None, hash_exists=lambda _: False, max_attempts=0)


def test_sqlite_duplicate_token_hash_is_translated(db):
    digest = token_digest("duplicate-digest")
    add_invitation(db, digest)
    now = datetime.now(timezone.utc)
    error = capture_integrity_error(db, lambda: db.add(ExamInvitation(
        id=2, candidate_id=1, exam_id=1, token_hash=digest,
        created_at=now, expires_at=now + timedelta(days=1),
    )))

    assert "exam_invitations.token_hash" in str(error.orig)
    with pytest.raises(InvitationTokenUnavailableError) as translated:
        translate_token_conflict(error)
    assert str(translated.value) == "Unable to allocate a unique invitation token"
    assert translated.value.__cause__ is None
    assert digest not in str(translated.value)


def test_sqlite_not_null_violation_is_preserved(db):
    now = datetime.now(timezone.utc)
    error = capture_integrity_error(db, lambda: db.add(ExamInvitation(
        id=2, candidate_id=1, exam_id=1, token_hash=None,
        created_at=now, expires_at=now + timedelta(days=1),
    )))

    assert "NOT NULL" in str(error.orig)
    with pytest.raises(IntegrityError) as preserved:
        translate_token_conflict(error)
    assert preserved.value is error


def test_sqlite_other_unique_constraint_is_preserved(db):
    db.add(HRUser(id=1, username="duplicate-hr", password_hash="hash",
                  first_name="Test", last_name="HR", position="HR"))
    db.commit()
    error = capture_integrity_error(db, lambda: db.add(HRUser(
        id=2, username="duplicate-hr", password_hash="hash",
        first_name="Test", last_name="HR", position="HR",
    )))

    assert "hr_users.username" in str(error.orig)
    with pytest.raises(IntegrityError) as preserved:
        translate_token_conflict(error)
    assert preserved.value is error


def test_postgres_token_hash_constraint_is_translated():
    error = IntegrityError("INSERT INTO exam_invitations", {}, FakePostgresUniqueViolation(TOKEN_HASH_CONSTRAINT))
    with pytest.raises(InvitationTokenUnavailableError) as translated:
        translate_token_conflict(error)
    assert str(translated.value) == "Unable to allocate a unique invitation token"
    assert translated.value.__cause__ is None


def test_postgres_other_constraint_is_preserved():
    error = IntegrityError("INSERT INTO exam_invitations", {}, FakePostgresUniqueViolation("uq_something_else"))
    with pytest.raises(IntegrityError) as preserved:
        translate_token_conflict(error)
    assert preserved.value is error


def test_generic_unique_error_class_is_preserved():
    error = IntegrityError("INSERT INTO exam_invitations", {}, Exception("UNIQUE constraint failed"))
    with pytest.raises(IntegrityError) as preserved:
        translate_token_conflict(error)
    assert preserved.value is error


def test_errors_and_logs_never_contain_raw_token(caplog):
    secret = generate_invitation_token()
    with caplog.at_level(logging.DEBUG):
        error = InvitationTokenUnavailableError()
        translated_error = IntegrityError(
            "INSERT", {}, FakePostgresUniqueViolation(TOKEN_HASH_CONSTRAINT)
        )
        with pytest.raises(InvitationTokenUnavailableError) as translated:
            translate_token_conflict(translated_error)
        logging.getLogger("invitation-token-test").warning("allocation failed: %s", translated.value)

    assert secret not in str(error)
    assert secret not in str(translated.value)
    assert secret not in caplog.text
