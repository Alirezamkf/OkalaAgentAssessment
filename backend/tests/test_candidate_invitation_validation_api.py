"""Issue #86 API tests for candidate invitation-token validation."""

import logging
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.sqlite import INTEGER
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from sqlalchemy.sql.sqltypes import BigInteger

from app.database.base import Base
from app.main import app
from app.models import (
    AssessmentAttempt,
    AttemptStatus,
    Candidate,
    Exam,
    ExamInvitation,
    ExamStatus,
    HRUser,
    InvitationStatus,
)
from app.schemas.invitation_validation import InvitationValidationOutcome as Outcome
from app.services import invitation_validation as validation
from app.services.invitation_token import generate_invitation_token, hash_invitation_token

ENDPOINT = "/api/v1/candidates/invitations/validate"
NOW = datetime(2026, 6, 15, 12, 0, tzinfo=timezone.utc)
DAY = timedelta(days=1)


@compiles(JSONB, "sqlite")
def _jsonb_as_sqlite(type_, compiler, **kwargs):
    return "JSON"


@compiles(BigInteger, "sqlite")
def _bigint_as_sqlite(type_, compiler, **kwargs):
    return compiler.visit_INTEGER(INTEGER(), **kwargs)


@pytest.fixture
def db():
    """Isolated in-memory SQLite DB; never touches the developer database."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def enable_sqlite_foreign_keys(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    from app.models import AttemptEvent, ExamQuestionOption

    column = AttemptEvent.__table__.c.event_metadata
    original_default = column.server_default
    option_index = next(
        (index for index in ExamQuestionOption.__table__.indexes
         if index.name == "uq_exam_question_options_one_correct"),
        None,
    )
    column.server_default = None
    if option_index is not None:
        ExamQuestionOption.__table__.indexes.discard(option_index)
    try:
        Base.metadata.create_all(engine)
    finally:
        column.server_default = original_default
        if option_index is not None:
            ExamQuestionOption.__table__.indexes.add(option_index)

    with Session(engine) as session:
        yield session
    engine.dispose()


@pytest.fixture
def client(db, monkeypatch):
    from app.database.connection import get_db

    monkeypatch.setattr(app, "dependency_overrides", {})
    app.dependency_overrides[get_db] = lambda: db
    # Deterministic server clock; no client-provided timestamp is trusted.
    monkeypatch.setattr(validation, "_utc_now", lambda: NOW)
    yield TestClient(app)
    app.dependency_overrides.clear()


def make_hr(db):
    user = HRUser(
        id=1, username="hr", password_hash="hash",
        first_name="Test", last_name="HR", position="Recruiter",
    )
    db.add(user)
    db.flush()
    return user


def make_exam(db, hr, *, exam_id=1, name="Backend Exam",
              status=ExamStatus.PUBLISHED,
              available_from=None, available_until=None):
    exam = Exam(
        id=exam_id, name=name, status=status, duration_minutes=25,
        available_from=available_from if available_from is not None else NOW - DAY,
        available_until=available_until if available_until is not None else NOW + DAY,
        created_by_hr_user_id=hr.id,
    )
    db.add(exam)
    db.flush()
    return exam


def make_candidate(db, *, candidate_id=1):
    candidate = Candidate(
        id=candidate_id, first_name="Sara", last_name="Ahmadi",
        email="sara@example.com", phone="+989121234567",
    )
    db.add(candidate)
    db.flush()
    return candidate


def make_invitation(db, exam, candidate, *, invitation_id=1,
                    status=InvitationStatus.PENDING, expires_at=None):
    raw = generate_invitation_token()
    invitation = ExamInvitation(
        id=invitation_id, candidate_id=candidate.id, exam_id=exam.id,
        token_hash=hash_invitation_token(raw), status=status,
        created_at=NOW - 2 * DAY,
        expires_at=expires_at if expires_at is not None else NOW + DAY,
    )
    db.add(invitation)
    db.flush()
    return invitation, raw


def make_attempt(db, invitation, *, status, deadline_at=None, attempt_id=1):
    attempt = AssessmentAttempt(
        id=attempt_id, exam_invitation_id=invitation.id,
        candidate_id=invitation.candidate_id, exam_id=invitation.exam_id,
        status=status,
        deadline_at=deadline_at if deadline_at is not None else NOW + DAY,
    )
    db.add(attempt)
    db.flush()
    return attempt


@pytest.fixture
def seeded(db):
    hr = make_hr(db)
    exam = make_exam(db, hr)
    candidate = make_candidate(db)
    invitation, raw = make_invitation(db, exam, candidate)
    db.commit()
    return hr, exam, candidate, invitation, raw


def post(client, token):
    return client.post(ENDPOINT, json={"token": token})


# --- Valid and outcome handling --------------------------------------------

def test_valid_eligible_invitation(client, seeded):
    hr, exam, candidate, invitation, raw = seeded
    response = post(client, raw)
    assert response.status_code == 200
    assert response.json() == {
        "outcome": Outcome.ELIGIBLE.value,
        "exam_name": exam.name,
        "exam_duration_minutes": 25,
        "exam_available_from": (NOW - DAY).isoformat().replace("+00:00", "Z"),
        "exam_available_until": (NOW + DAY).isoformat().replace("+00:00", "Z"),
        "invitation_expires_at": (NOW + DAY).isoformat().replace("+00:00", "Z"),
        "attempt_deadline_at": None,
    }


def test_invalid_unknown_token_is_safe(client, seeded):
    response = post(client, "unknown-token")
    assert response.status_code == 200
    assert response.json() == {
        "outcome": Outcome.INVALID_TOKEN.value,
        "exam_name": None,
        "exam_duration_minutes": None,
        "exam_available_from": None,
        "exam_available_until": None,
        "invitation_expires_at": None,
        "attempt_deadline_at": None,
    }


def test_not_yet_active_exam(client, db, seeded):
    hr, exam, candidate, invitation, raw = seeded
    exam.status = ExamStatus.CREATED
    db.commit()
    assert post(client, raw).json()["outcome"] == Outcome.NOT_YET_ACTIVE.value


def test_before_window_is_distinct_from_expired(client, db, seeded):
    hr, exam, candidate, invitation, raw = seeded
    exam.available_from = NOW + DAY
    exam.available_until = NOW + 3 * DAY
    invitation.expires_at = NOW + 4 * DAY
    db.commit()
    assert post(client, raw).json()["outcome"] == Outcome.NOT_YET_ACTIVE.value
    exam.available_from = NOW - DAY
    exam.available_until = NOW
    db.commit()
    assert post(client, raw).json()["outcome"] == Outcome.EXPIRED.value


def test_expired_invitation(client, db, seeded):
    hr, exam, candidate, invitation, raw = seeded
    invitation.status = InvitationStatus.EXPIRED
    db.commit()
    assert post(client, raw).json()["outcome"] == Outcome.EXPIRED.value


def test_cancelled_invitation_and_cancelled_exam(client, db, seeded):
    hr, exam, candidate, invitation, raw = seeded
    invitation.status = InvitationStatus.CANCELLED
    db.commit()
    assert post(client, raw).json()["outcome"] == Outcome.CANCELLED.value
    invitation.status = InvitationStatus.PENDING
    exam.status = ExamStatus.CANCELLED
    db.commit()
    assert post(client, raw).json()["outcome"] == Outcome.CANCELLED.value


def test_existing_in_progress_attempt(client, db, seeded):
    hr, exam, candidate, invitation, raw = seeded
    make_attempt(db, invitation, status=AttemptStatus.IN_PROGRESS)
    db.commit()
    response = post(client, raw)
    assert response.json()["outcome"] == Outcome.IN_PROGRESS.value
    assert response.json()["attempt_deadline_at"] == (
        (NOW + DAY).isoformat().replace("+00:00", "Z")
    )


def test_in_progress_after_link_window_is_still_resumable(client, db, seeded):
    hr, exam, candidate, invitation, raw = seeded
    exam.available_until = NOW
    invitation.expires_at = NOW
    make_attempt(db, invitation, status=AttemptStatus.IN_PROGRESS,
                 deadline_at=NOW + 3 * DAY)
    db.commit()
    assert post(client, raw).json()["outcome"] == Outcome.IN_PROGRESS.value


@pytest.mark.parametrize("terminal", [
    AttemptStatus.SUBMITTED,
    AttemptStatus.TIMED_OUT,
    AttemptStatus.INTERRUPTED,
    AttemptStatus.CANCELLED,
])
def test_terminal_attempts_cannot_resume(client, db, seeded, terminal):
    hr, exam, candidate, invitation, raw = seeded
    make_attempt(db, invitation, status=terminal)
    db.commit()
    assert post(client, raw).json()["outcome"] == Outcome.TERMINAL_ATTEMPT.value


# --- Malformed requests -----------------------------------------------------

@pytest.mark.parametrize("payload", [
    {},
    {"token": ""},
    {"token": "   "},
    {"token": None},
    {"token": 12345},
    {"token": "x", "candidate_id": 1},
    {"candidate_code": "CAND-1"},
])
def test_malformed_or_missing_token(client, seeded, payload):
    response = client.post(ENDPOINT, json=payload)
    assert response.status_code == 422


# --- Privacy, logging, delegation, read-only --------------------------------

def test_response_contains_no_protected_information(client, db, seeded):
    hr, exam, candidate, invitation, raw = seeded
    make_attempt(db, invitation, status=AttemptStatus.IN_PROGRESS)
    db.commit()
    body = post(client, raw).json()
    serialized = str(body).lower()

    assert set(body) == {
        "outcome", "exam_name", "exam_duration_minutes", "exam_available_from",
        "exam_available_until", "invitation_expires_at", "attempt_deadline_at",
    }
    for forbidden in (
        raw, hash_invitation_token(raw), candidate.email, candidate.phone,
        "question", "option", "image", "answer", "score", "candidate_id",
        "invitation_id", "exam_id", "attempt_id", "token",
    ):
        assert forbidden.lower() not in serialized


def test_raw_token_never_appears_in_logs(client, seeded, caplog):
    hr, exam, candidate, invitation, raw = seeded
    with caplog.at_level(logging.DEBUG):
        assert post(client, raw).status_code == 200
        assert post(client, "unknown-token").status_code == 200
        assert post(client, "   ").status_code == 422
        assert client.post(ENDPOINT, json={"token": None}).status_code == 422
    assert raw not in caplog.text


def test_endpoint_delegates_to_issue_85_service(client, seeded, monkeypatch):
    hr, exam, candidate, invitation, raw = seeded
    calls = []
    real = validation.validate_invitation_token

    def spy(db, token, **kwargs):
        calls.append((db, token))
        return real(db, token, **kwargs)

    monkeypatch.setattr("app.api.v1.candidates.validate_invitation_token", spy)
    response = post(client, raw)
    assert response.status_code == 200
    assert len(calls) == 1
    assert calls[0][1] == raw


def test_validation_does_not_modify_attempt_or_invitation(client, db, seeded):
    hr, exam, candidate, invitation, raw = seeded
    attempt = make_attempt(db, invitation, status=AttemptStatus.IN_PROGRESS)
    db.commit()
    before_attempt = (attempt.status, attempt.deadline_at, attempt.started_at)
    before_invitation = (invitation.status, invitation.expires_at,
                         invitation.failed_identity_attempts)

    for token in (raw, "unknown", ""):
        post(client, token)

    assert (attempt.status, attempt.deadline_at, attempt.started_at) == before_attempt
    assert (invitation.status, invitation.expires_at,
            invitation.failed_identity_attempts) == before_invitation
    assert db.scalar(select(AssessmentAttempt.id).where(
        AssessmentAttempt.exam_invitation_id == invitation.id
    )) == attempt.id
