"""Issue #85 focused tests for read-only invitation token validation."""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.sqlite import INTEGER
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from sqlalchemy.sql.sqltypes import BigInteger

from app.database.base import Base
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
from app.schemas.invitation_validation import (
    InvitationValidationOutcome as Outcome,
)
from app.services import invitation_validation as validation
from app.services.invitation_validation import _as_utc
from app.services.invitation_token import (
    generate_invitation_token,
    hash_invitation_token,
)

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
    """Isolated in-memory SQLite DB with FK enforcement; no production DB."""
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


def clock(at: datetime = NOW):
    return lambda: at


def make_hr(db: Session) -> HRUser:
    user = HRUser(
        id=1, username="hr", password_hash="hash",
        first_name="Test", last_name="HR", position="Recruiter",
    )
    db.add(user)
    db.flush()
    return user


def make_exam(
    db: Session,
    hr: HRUser,
    *,
    exam_id: int = 1,
    name: str = "Backend Exam",
    status: ExamStatus = ExamStatus.PUBLISHED,
    available_from: datetime | None = None,
    available_until: datetime | None = None,
) -> Exam:
    exam = Exam(
        id=exam_id,
        name=name,
        status=status,
        duration_minutes=25,
        available_from=available_from if available_from is not None else NOW - DAY,
        available_until=available_until if available_until is not None else NOW + DAY,
        created_by_hr_user_id=hr.id,
    )
    db.add(exam)
    db.flush()
    return exam


def make_candidate(db: Session, *, candidate_id: int = 1) -> Candidate:
    candidate = Candidate(
        id=candidate_id,
        first_name="Sara",
        last_name="Ahmadi",
        email="sara@example.com",
        phone="+989121234567",
    )
    db.add(candidate)
    db.flush()
    return candidate


def make_invitation(
    db: Session,
    exam: Exam,
    candidate: Candidate,
    *,
    invitation_id: int = 1,
    token: str | None = None,
    status: InvitationStatus = InvitationStatus.PENDING,
    expires_at: datetime | None = None,
) -> tuple[ExamInvitation, str]:
    raw = token or generate_invitation_token()
    invitation = ExamInvitation(
        id=invitation_id,
        candidate_id=candidate.id,
        exam_id=exam.id,
        token_hash=hash_invitation_token(raw),
        status=status,
        created_at=NOW - 2 * DAY,
        expires_at=expires_at if expires_at is not None else NOW + DAY,
    )
    db.add(invitation)
    db.flush()
    return invitation, raw


def make_attempt(
    db: Session,
    invitation: ExamInvitation,
    *,
    attempt_id: int = 1,
    status: AttemptStatus = AttemptStatus.NOT_STARTED,
    deadline_at: datetime | None = None,
    candidate_id: int | None = None,
    exam_id: int | None = None,
) -> AssessmentAttempt:
    attempt = AssessmentAttempt(
        id=attempt_id,
        exam_invitation_id=invitation.id,
        candidate_id=invitation.candidate_id if candidate_id is None else candidate_id,
        exam_id=invitation.exam_id if exam_id is None else exam_id,
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


def validate(db, token, at: datetime = NOW):
    return validation.validate_invitation_token(db, token, now_fn=clock(at))


# --- Token resolution and safe invalid outcomes ----------------------------

def test_valid_token_resolves_exactly_its_invitation_candidate_and_exam(db, seeded):
    hr, exam, candidate, invitation, raw = seeded
    result = validate(db, raw)
    assert result.outcome is Outcome.ELIGIBLE
    assert result.invitation is invitation
    assert result.candidate is candidate
    assert result.exam is exam
    assert result.attempt is None
    assert result.response.exam_name == exam.name


@pytest.mark.parametrize("bad_token", [None, "", "   ", 12345, "bad\ntoken", "x" * 1025])
def test_invalid_blank_malformed_and_unknown_tokens_are_safe(db, seeded, bad_token):
    _, _, _, _, raw = seeded
    result = validate(db, bad_token)
    assert result.outcome is Outcome.INVALID_TOKEN
    assert result.invitation is None
    assert result.candidate is None
    assert result.exam is None
    assert result.response.model_dump() == {"outcome": Outcome.INVALID_TOKEN, **{
        key: None for key in (
            "exam_name", "exam_duration_minutes", "exam_available_from",
            "exam_available_until", "invitation_expires_at", "attempt_deadline_at",
        )
    }}
    assert validate(db, "unknown-token").outcome is Outcome.INVALID_TOKEN
    assert validate(db, raw).outcome is Outcome.ELIGIBLE


def test_raw_token_is_never_stored_and_digest_helper_is_used(db, seeded, monkeypatch):
    hr, exam, candidate, invitation, raw = seeded
    assert db.scalar(select(ExamInvitation.token_hash).where(
        ExamInvitation.id == invitation.id
    )) == hash_invitation_token(raw)
    assert raw not in db.scalar(select(ExamInvitation.token_hash).where(
        ExamInvitation.id == invitation.id
    ))

    seen = []

    def spy(token):
        seen.append(token)
        return hash_invitation_token(token)

    monkeypatch.setattr(validation, "hash_invitation_token", spy)
    result = validate(db, raw)
    assert result.outcome is Outcome.ELIGIBLE
    assert seen == [raw]


def test_duplicate_digest_is_rejected_safely(db, seeded, monkeypatch):
    """A token digest matching two invitation rows is ambiguous, not usable.

    The DB unique index forbids a real duplicate; the ambiguous query result is
    simulated at the session boundary to exercise the service's guard.
    """
    hr, exam, candidate, invitation, raw = seeded
    twin = ExamInvitation(
        id=999, candidate_id=candidate.id, exam_id=exam.id,
        token_hash=invitation.token_hash, created_at=NOW, expires_at=NOW + DAY,
    )

    class ScalarResult:
        def all(self):
            return [invitation, twin]

    class AmbiguousSession:
        @property
        def no_autoflush(self):
            from contextlib import nullcontext
            return nullcontext()

        def scalars(self, statement):
            return ScalarResult()

    result = validation.validate_invitation_token(AmbiguousSession(), raw, now_fn=clock())
    assert result.outcome is Outcome.INVALID_TOKEN
    assert result.invitation is None


# --- Multiple invitations and attempt isolation ----------------------------

def test_one_candidate_two_exams_each_token_resolves_only_its_own_data(db):
    hr = make_hr(db)
    exam_a = make_exam(db, hr, exam_id=1, name="Exam A")
    exam_b = make_exam(db, hr, exam_id=2, name="Exam B")
    candidate = make_candidate(db)
    inv_a, token_a = make_invitation(db, exam_a, candidate, invitation_id=1)
    inv_b, token_b = make_invitation(db, exam_b, candidate, invitation_id=2)
    attempt_b = make_attempt(db, inv_b, attempt_id=2, status=AttemptStatus.IN_PROGRESS)
    db.commit()

    result_a = validate(db, token_a)
    result_b = validate(db, token_b)
    assert result_a.invitation is inv_a and result_a.exam is exam_a
    assert result_a.attempt is None
    assert result_a.response.exam_name == "Exam A"
    assert result_b.invitation is inv_b and result_b.exam is exam_b
    assert result_b.attempt is attempt_b
    assert result_b.outcome is Outcome.IN_PROGRESS
    assert result_b.response.exam_name == "Exam B"


def test_attempt_is_never_discovered_by_candidate_id_alone(db):
    hr = make_hr(db)
    exam = make_exam(db, hr)
    candidate = make_candidate(db)
    inv_a, token_a = make_invitation(db, exam, candidate, invitation_id=1)
    inv_b, _ = make_invitation(db, exam, candidate, invitation_id=2)
    attempt_b = make_attempt(db, inv_b, attempt_id=2, status=AttemptStatus.IN_PROGRESS)
    db.commit()

    result = validate(db, token_a)
    assert result.attempt is None
    assert result.outcome is Outcome.ELIGIBLE
    assert result.invitation is inv_a
    assert attempt_b.exam_invitation_id == inv_b.id


def test_inconsistent_attempt_ownership_is_rejected_safely(db):
    hr = make_hr(db)
    exam_a = make_exam(db, hr, exam_id=1, name="Exam A")
    exam_b = make_exam(db, hr, exam_id=2, name="Exam B")
    candidate_a = make_candidate(db, candidate_id=1)
    candidate_b = make_candidate(db, candidate_id=2)
    invitation, raw = make_invitation(db, exam_a, candidate_a)
    db.commit()
    # Insert a cross-linked attempt with the composite FK disabled: this is a
    # deliberately corrupt row the service must reject. It is reachable only
    # through invitation A's token.
    connection = db.connection()
    connection.exec_driver_sql("PRAGMA foreign_keys=OFF")
    connection.exec_driver_sql(
        "INSERT INTO assessment_attempts "
        "(exam_id, candidate_id, exam_invitation_id, status, deadline_at, hr_decision) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (
            exam_b.id, candidate_a.id, invitation.id, "Not Started",
            (NOW + DAY).replace(tzinfo=None).isoformat(), "Unset",
        ),
    )
    connection.exec_driver_sql("PRAGMA foreign_keys=ON")
    db.expire_all()

    result = validate(db, raw)
    assert result.outcome is Outcome.INVALID_TOKEN
    assert result.attempt is None
    assert candidate_b.id == 2

# --- Lifecycle and exact boundaries ----------------------------------------

def test_created_exam_is_not_yet_active(db, seeded):
    hr, exam, candidate, invitation, raw = seeded
    exam.status = ExamStatus.CREATED
    db.commit()
    assert validate(db, raw).outcome is Outcome.NOT_YET_ACTIVE


def test_published_before_start_and_exact_start_boundary(db, seeded):
    hr, exam, candidate, invitation, raw = seeded
    exam.available_from = NOW + DAY
    exam.available_until = NOW + 3 * DAY
    invitation.expires_at = NOW + 4 * DAY
    db.commit()
    assert validate(db, raw, NOW).outcome is Outcome.NOT_YET_ACTIVE
    assert validate(db, raw, NOW + DAY).outcome is Outcome.ELIGIBLE


def test_exact_end_boundary_and_after_end(db, seeded):
    hr, exam, candidate, invitation, raw = seeded
    exam.available_until = NOW + DAY
    invitation.expires_at = NOW + 5 * DAY
    db.commit()
    assert validate(db, raw, NOW + DAY).outcome is Outcome.EXPIRED
    assert validate(db, raw, NOW + DAY + timedelta(seconds=1)).outcome is Outcome.EXPIRED


def test_exact_invitation_expiry_boundary(db, seeded):
    hr, exam, candidate, invitation, raw = seeded
    invitation.expires_at = NOW + DAY
    db.commit()
    assert validate(db, raw, NOW + DAY - timedelta(seconds=1)).outcome is Outcome.ELIGIBLE
    assert validate(db, raw, NOW + DAY).outcome is Outcome.EXPIRED


def test_expired_invitation_by_status(db, seeded):
    hr, exam, candidate, invitation, raw = seeded
    invitation.status = InvitationStatus.EXPIRED
    db.commit()
    assert validate(db, raw).outcome is Outcome.EXPIRED


def test_cancelled_invitation_and_cancelled_exam(db, seeded):
    hr, exam, candidate, invitation, raw = seeded
    invitation.status = InvitationStatus.CANCELLED
    db.commit()
    assert validate(db, raw).outcome is Outcome.CANCELLED
    invitation.status = InvitationStatus.PENDING
    exam.status = ExamStatus.CANCELLED
    db.commit()
    assert validate(db, raw).outcome is Outcome.CANCELLED


def test_cancellation_overrides_in_progress_reentry(db, seeded):
    hr, exam, candidate, invitation, raw = seeded
    make_attempt(db, invitation, status=AttemptStatus.IN_PROGRESS)
    invitation.status = InvitationStatus.CANCELLED
    db.commit()
    assert validate(db, raw).outcome is Outcome.CANCELLED


def test_not_started_attempt_inside_and_outside_window(db, seeded):
    hr, exam, candidate, invitation, raw = seeded
    make_attempt(db, invitation, status=AttemptStatus.NOT_STARTED)
    db.commit()
    assert validate(db, raw).outcome is Outcome.ELIGIBLE
    exam.available_until = NOW
    db.commit()
    assert validate(db, raw).outcome is Outcome.EXPIRED


def test_in_progress_attempt_inside_window(db, seeded):
    hr, exam, candidate, invitation, raw = seeded
    attempt = make_attempt(db, invitation, status=AttemptStatus.IN_PROGRESS)
    db.commit()
    result = validate(db, raw)
    assert result.outcome is Outcome.IN_PROGRESS
    assert result.attempt is attempt
    assert result.response.attempt_deadline_at == _as_utc(attempt.deadline_at)


def test_in_progress_attempt_after_link_window_before_own_deadline_is_resumable(db, seeded):
    hr, exam, candidate, invitation, raw = seeded
    exam.available_until = NOW
    invitation.expires_at = NOW
    make_attempt(
        db, invitation, status=AttemptStatus.IN_PROGRESS,
        deadline_at=NOW + 3 * DAY,
    )
    db.commit()
    result = validate(db, raw, NOW + DAY)
    assert result.outcome is Outcome.IN_PROGRESS
    assert result.response.attempt_deadline_at == NOW + 3 * DAY


def test_in_progress_attempt_at_and_after_own_deadline_not_resumable(db, seeded):
    hr, exam, candidate, invitation, raw = seeded
    make_attempt(
        db, invitation, status=AttemptStatus.IN_PROGRESS,
        deadline_at=NOW + DAY,
    )
    db.commit()
    assert validate(db, raw, NOW + DAY).outcome is Outcome.EXPIRED
    assert validate(db, raw, NOW + DAY + timedelta(seconds=1)).outcome is Outcome.EXPIRED


@pytest.mark.parametrize("terminal", [
    AttemptStatus.SUBMITTED,
    AttemptStatus.TIMED_OUT,
    AttemptStatus.INTERRUPTED,
    AttemptStatus.CANCELLED,
])
def test_terminal_attempts_cannot_resume(db, seeded, terminal):
    hr, exam, candidate, invitation, raw = seeded
    make_attempt(db, invitation, status=terminal)
    db.commit()
    result = validate(db, raw)
    assert result.outcome is Outcome.TERMINAL_ATTEMPT
    assert result.attempt.status is terminal


# --- Read-only guarantee ----------------------------------------------------

def test_validation_never_mutates_invitation_or_attempt(db, seeded):
    hr, exam, candidate, invitation, raw = seeded
    attempt = make_attempt(db, invitation, status=AttemptStatus.IN_PROGRESS)
    db.commit()

    def snapshot(obj, fields):
        return tuple(getattr(obj, field) for field in fields)

    invitation_fields = (
        "status", "expires_at", "created_at", "failed_identity_attempts",
        "identity_locked_until", "token_hash", "candidate_id", "exam_id",
    )
    attempt_fields = (
        "status", "started_at", "completed_at", "deadline_at",
        "current_question_position", "official_score", "max_score",
        "hr_decision", "hr_decided_by_id", "hr_decision_updated_at",
    )
    before_invitation = snapshot(invitation, invitation_fields)
    before_attempt = snapshot(attempt, attempt_fields)
    before_count = db.scalar(select(func.count(AssessmentAttempt.id)))

    for at in (NOW, NOW + DAY, NOW + 10 * DAY):
        for token in (raw, "unknown", "", None):
            validate(db, token, at)

    assert snapshot(invitation, invitation_fields) == before_invitation
    assert snapshot(attempt, attempt_fields) == before_attempt
    assert db.scalar(select(func.count(AssessmentAttempt.id))) == before_count
    assert len(db.new) == 0 and len(db.deleted) == 0 and len(db.dirty) == 0


def test_validation_does_not_create_an_attempt(db, seeded):
    hr, exam, candidate, invitation, raw = seeded
    db.commit()
    assert db.scalar(select(func.count(AssessmentAttempt.id))) == 0
    for token in (raw, "unknown", None):
        validate(db, token)
    assert db.scalar(select(func.count(AssessmentAttempt.id))) == 0


def test_validation_does_not_flush_pending_caller_writes(db, seeded):
    hr, exam, candidate, invitation, raw = seeded
    db.commit()
    db.add(Candidate(
        id=99, first_name="Pending", last_name="Write", email="pending@example.com"
    ))
    validate(db, raw)
    # Pending objects live in session.new; db.get() would itself autoflush.
    assert any(isinstance(obj, Candidate) and obj.id == 99 for obj in db.new)
    # Raw SQL bypasses ORM autoflush, so this sees only what validation flushed.
    raw_count = db.connection().exec_driver_sql(
        "SELECT COUNT(*) FROM candidates WHERE id = 99"
    ).scalar_one()
    assert raw_count == 0
    db.rollback()


# --- Privacy ----------------------------------------------------------------

def test_public_response_contains_no_private_data(db, seeded):
    hr, exam, candidate, invitation, raw = seeded
    make_attempt(db, invitation, status=AttemptStatus.IN_PROGRESS)
    db.commit()
    payload = validate(db, raw).response.model_dump()

    # Structured identifier/secret values must never appear as field values.
    secret_values = {
        candidate.id, invitation.id, exam.id, raw,
        hash_invitation_token(raw), candidate.email, candidate.phone,
    }
    assert not secret_values.intersection(
        value for value in payload.values() if isinstance(value, (str, int))
    )
    assert not {"candidate_id", "exam_id", "invitation_id", "attempt_id",
                "token", "token_hash", "email", "phone"} & set(payload)
    assert "id" not in payload
    assert set(payload) == {
        "outcome", "exam_name", "exam_duration_minutes", "exam_available_from",
        "exam_available_until", "invitation_expires_at", "attempt_deadline_at",
    }
    assert validate(db, "unknown").response.model_dump() == {
        "outcome": Outcome.INVALID_TOKEN,
        "exam_name": None, "exam_duration_minutes": None,
        "exam_available_from": None, "exam_available_until": None,
        "invitation_expires_at": None, "attempt_deadline_at": None,
    }


def test_internal_orm_objects_are_not_part_of_public_response(db, seeded):
    hr, exam, candidate, invitation, raw = seeded
    result = validate(db, raw)
    assert not isinstance(result.response, (Candidate, Exam, ExamInvitation, AssessmentAttempt))
    assert all(
        not isinstance(value, (Candidate, Exam, ExamInvitation, AssessmentAttempt))
        for value in result.response.model_dump().values()
    )
