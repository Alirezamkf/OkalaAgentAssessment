"""Issue #80 focused tests for candidate registration and invitations."""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, event, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.sqlite import INTEGER
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from sqlalchemy.sql.sqltypes import BigInteger

from app.core.security import token_digest
from app.database.base import Base
from app.models import (
    Candidate,
    Exam,
    ExamInvitation,
    ExamInvitationQuestion,
    ExamQuestion,
    ExamQuestionOption,
    HRUser,
)
from app.schemas.candidate import CandidateInvitationRequest
from app.services import candidate_registration as registration
from app.services.candidate_identity import get_or_create_candidate
from app.services.invitation_token import InvitationTokenUnavailableError

EXPIRES_AT = datetime(2027, 1, 1, tzinfo=timezone.utc)


@compiles(JSONB, "sqlite")
def _jsonb_as_sqlite(type_, compiler, **kwargs):
    return "JSON"


@compiles(BigInteger, "sqlite")
def _bigint_as_sqlite(type_, compiler, **kwargs):
    # SQLite only autoincrements INTEGER PRIMARY KEY, not BIGINT.
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

    # Two PostgreSQL-only constructs need isolation on SQLite: the JSONB
    # server default and the partial unique index on correct options. Both are
    # restored after create_all so global metadata is never left modified.
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


def make_hr_user(db: Session, hr_id: int = 1) -> HRUser:
    user = HRUser(
        id=hr_id,
        username=f"hr-{hr_id}",
        password_hash="hash",
        first_name="Test",
        last_name="HR",
        position="Recruiter",
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
) -> Exam:
    now = datetime.now(timezone.utc)
    exam = Exam(
        id=exam_id,
        name=name,
        status="Created",
        duration_minutes=25,
        available_from=now,
        available_until=now + timedelta(days=7),
        created_by_hr_user_id=hr.id,
    )
    db.add(exam)
    db.flush()
    return exam


def make_question(
    db: Session,
    exam: Exam,
    *,
    question_id: int = 1,
    score: int = 10,
    option_count: int = 4,
    correct_count: int = 1,
    blank_option: bool = False,
) -> ExamQuestion:
    question = ExamQuestion(
        id=question_id,
        exam_id=exam.id,
        text=f"Question {question_id}",
        score=score,
    )
    db.add(question)
    db.flush()
    for position in range(1, option_count + 1):
        text = "   " if blank_option and position == 1 else f"Option {position}"
        db.add(
            ExamQuestionOption(
                id=question_id * 100 + position,
                exam_question_id=question.id,
                text=text,
                is_correct=position <= correct_count,
                position=position,
            )
        )
    db.flush()
    return question


def make_request(
    *,
    exam_id: int = 1,
    first_name: str = "Sara",
    last_name: str = "Ahmadi",
    email: str | None = "sara@example.com",
    phone: str | None = None,
    question_ids: list[int] | None = None,
    **extra,
) -> CandidateInvitationRequest:
    data = {
        "exam_id": exam_id,
        "first_name": first_name,
        "last_name": last_name,
        "email": email,
        "phone": phone,
        "exam_question_ids": question_ids if question_ids is not None else [1],
    }
    data.update(extra)
    return CandidateInvitationRequest(**data)


def register(db: Session, request: CandidateInvitationRequest, **kwargs):
    kwargs.setdefault("expires_at", EXPIRES_AT)
    return registration.register_candidate_for_exam(db, request, **kwargs)


@pytest.fixture
def seeded(db):
    hr = make_hr_user(db)
    exam = make_exam(db, hr)
    question = make_question(db, exam)
    db.commit()
    return hr, exam, question


# --- 1-5: candidate creation and reuse ------------------------------------

def test_new_candidate_creation(db, seeded):
    response = register(db, make_request())
    db.commit()
    assert response.candidate_reused is False
    assert db.scalar(select(Candidate).where(Candidate.email == "sara@example.com")) is not None


def test_existing_candidate_reuse_by_email(db, seeded):
    first = register(db, make_request())
    db.commit()
    first_candidate_id = db.scalar(
        select(ExamInvitation.candidate_id).where(
            ExamInvitation.id == first.invitation_id
        )
    )
    second = register(db, make_request(first_name="Sara", last_name="Ahmadi"))
    db.commit()
    second_candidate_id = db.scalar(
        select(ExamInvitation.candidate_id).where(
            ExamInvitation.id == second.invitation_id
        )
    )
    assert second.candidate_reused is True
    assert first_candidate_id == second_candidate_id
    assert db.scalar(select(Candidate.id).where(Candidate.email == "sara@example.com")) == first_candidate_id


def test_existing_candidate_reuse_by_phone(db, seeded):
    first = register(db, make_request(email=None, phone="+989121234567"))
    db.commit()
    second = register(db, make_request(email=None, phone="+989121234567"))
    db.commit()
    assert second.candidate_reused is True
    assert db.scalar(select(Candidate).where(Candidate.phone == "+989121234567")) is not None


def test_existing_candidate_reuse_with_both_contacts(db, seeded):
    register(db, make_request(phone="+989121234567"))
    db.commit()
    response = register(db, make_request(phone="+989121234567"))
    db.commit()
    assert response.candidate_reused is True


def test_equivalent_national_and_international_phones(db, seeded):
    register(db, make_request(email=None, phone="09121234567", phone_region="IR"))
    db.commit()
    response = register(db, make_request(email=None, phone="+989121234567"))
    db.commit()
    assert response.candidate_reused is True
    assert db.scalar(select(Candidate).where(Candidate.phone == "+989121234567")) is not None


# --- 6-9: identity conflicts ----------------------------------------------

def test_conflicting_email_and_phone_rejected(db, seeded):
    register(db, make_request(first_name="Mina", last_name="Salehi", email="mina@example.com"))
    db.commit()
    register(db, make_request(
        first_name="Reza", last_name="Nouri", email=None, phone="+989123456789"
    ))
    db.commit()
    with pytest.raises(registration.CandidateIdentityConflictError):
        register(db, make_request(
            first_name="Mina", last_name="Salehi",
            email="mina@example.com", phone="+989123456789",
        ))
    db.rollback()


def test_ambiguous_identity_match_rejected(db, seeded):
    # Two candidates share an email; the match is ambiguous and must not merge.
    db.add_all([
        Candidate(first_name="A", last_name="B", email="dupe@example.com"),
        Candidate(first_name="C", last_name="D", email="dupe@example.com"),
    ])
    db.flush()
    with pytest.raises(registration.CandidateIdentityConflictError):
        register(db, make_request(email="dupe@example.com"))
    db.rollback()


def test_anonymized_candidate_not_reused(db, seeded):
    original = get_or_create_candidate(
        db, first_name="Sara", last_name="Ahmadi", email="sara@example.com"
    )
    original.first_name = "Deleted"
    original.last_name = "Deleted"
    original.email = None
    original.phone = None
    db.flush()
    response = register(db, make_request())
    db.commit()
    assert response.candidate_reused is False
    assert db.scalar(select(Candidate).where(Candidate.first_name == "Sara")) is not None


def test_missing_contact_information_rejected(db, seeded):
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        make_request(email=None, phone=None)


# --- 10-19: exam and question validation ----------------------------------

def test_missing_exam_rejected(db, seeded):
    with pytest.raises(registration.ExamNotFoundError):
        register(db, make_request(exam_id=999))


def test_empty_question_selection_rejected(db, seeded):
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        make_request(question_ids=[])

    # The service itself must also reject an empty selection on direct calls.
    from types import SimpleNamespace

    raw = SimpleNamespace(
        exam_id=1, first_name="Sara", last_name="Ahmadi",
        email="sara@example.com", phone=None, exam_question_ids=[],
    )
    with pytest.raises(registration.InvalidQuestionSelectionError):
        registration.register_candidate_for_exam(db, raw, expires_at=EXPIRES_AT)


def test_duplicate_question_ids_rejected_direct_service_call(db, seeded):
    from types import SimpleNamespace

    raw = SimpleNamespace(
        exam_id=1, first_name="Sara", last_name="Ahmadi",
        email="sara@example.com", phone=None, exam_question_ids=[1, 1],
    )
    with pytest.raises(registration.InvalidQuestionSelectionError):
        registration.register_candidate_for_exam(db, raw, expires_at=EXPIRES_AT)


def test_nonexistent_question_id_rejected(db, seeded):
    with pytest.raises(registration.InvalidQuestionSelectionError):
        register(db, make_request(question_ids=[999]))


def test_cross_exam_question_id_rejected(db, seeded):
    hr, exam, _ = seeded
    other = make_exam(db, hr, exam_id=2, name="Other Exam")
    other_question = make_question(db, other, question_id=2)
    db.commit()
    with pytest.raises(registration.InvalidQuestionSelectionError):
        register(db, make_request(question_ids=[other_question.id]))


def test_invalid_option_count_rejected(db, seeded):
    from sqlalchemy import delete

    # Create a fresh question with only one option (below the 2-option minimum).
    bad = ExamQuestion(id=50, exam_id=1, text="Bad question", score=10)
    db.add(bad)
    db.flush()
    db.add(
        ExamQuestionOption(
            id=5001, exam_question_id=bad.id, text="Only option",
            is_correct=True, position=1,
        )
    )
    db.commit()
    with pytest.raises(registration.InvalidQuestionSelectionError):
        register(db, make_request(question_ids=[50]))


def test_blank_option_text_rejected(db, seeded):
    hr, exam, question = seeded
    question.options[0].text = "   "
    db.flush()
    with pytest.raises(registration.InvalidQuestionSelectionError):
        register(db, make_request())


def test_zero_correct_options_rejected(db, seeded):
    hr, exam, question = seeded
    for option in question.options:
        option.is_correct = False
    db.flush()
    with pytest.raises(registration.InvalidQuestionSelectionError):
        register(db, make_request())


def test_multiple_correct_options_rejected(db, seeded):
    hr, exam, question = seeded
    for option in question.options[:2]:
        option.is_correct = True
    db.flush()
    with pytest.raises(registration.InvalidQuestionSelectionError):
        register(db, make_request())


def test_invalid_question_score_rejected(db, seeded):
    """A question with a non-positive score must be rejected by validation."""
    from types import SimpleNamespace

    fake_question = SimpleNamespace(
        id=1,
        score=0,
        options=[
            SimpleNamespace(text="A", is_correct=True),
            SimpleNamespace(text="B", is_correct=False),
        ],
    )
    with pytest.raises(registration.InvalidQuestionSelectionError):
        registration._validate_question_snapshot(fake_question)


# --- 20-23: successful creation, repeats, token security ------------------

def test_successful_invitation_with_exact_selection(db, seeded):
    hr, exam, question = seeded
    second_question = make_question(db, exam, question_id=2)
    db.commit()
    response = register(db, make_request(question_ids=[1, 2]))
    db.commit()
    invitation = db.get(ExamInvitation, response.invitation_id)
    assert invitation.exam_id == exam.id
    selections = db.scalars(
        select(ExamInvitationQuestion).where(
            ExamInvitationQuestion.exam_invitation_id == invitation.id
        )
    ).all()
    assert {s.exam_question_id for s in selections} == {1, 2}
    assert all(s.exam_id == exam.id for s in selections)


def test_repeated_registration_creates_independent_invitations(db, seeded):
    first = register(db, make_request())
    db.commit()
    second = register(db, make_request())
    db.commit()
    assert first.invitation_id != second.invitation_id
    assert second.candidate_reused is True
    assert db.scalar(select(ExamInvitation.id).where(ExamInvitation.id == first.invitation_id)) is not None


def test_raw_token_not_persisted(db, seeded, monkeypatch):
    monkeypatch.setattr(
        registration, "allocate_unique_invitation_token",
        lambda _db: "fixed-raw-token-for-test",
    )
    response = register(db, make_request())
    db.commit()
    invitation = db.get(ExamInvitation, response.invitation_id)
    assert invitation.token_hash == token_digest("fixed-raw-token-for-test")
    assert "fixed-raw-token-for-test" not in str(invitation.token_hash)
    assert response.invitation_url is None


def test_token_hash_collision_is_bounded_and_translated(db, seeded, monkeypatch):
    """Unit-level retry test: a simulated token conflict is bounded and token-free.

    This stubs the session's savepoint, add and flush methods. It verifies the
    retry loop and error translation, not real database concurrency.
    """
    from types import SimpleNamespace

    from app.services.invitation_token import translate_token_conflict

    collision_error = IntegrityError(
        "INSERT INTO exam_invitations",
        {},
        Exception("UNIQUE constraint failed: exam_invitations.token_hash"),
    )
    # translate_token_conflict inspects error.orig, not the wrapper message.
    collision_error.orig = Exception(
        "UNIQUE constraint failed: exam_invitations.token_hash"
    )
    exam_id_value = seeded[1].id
    question_id_value = seeded[2].id
    expiry = seeded[1].available_until
    attempts = {"count": 0}

    def colliding_allocator(_db):
        attempts["count"] += 1
        return "collision-token"

    def failing_savepoint_commit(*args, **kwargs):
        raise collision_error

    monkeypatch.setattr(
        registration, "allocate_unique_invitation_token", colliding_allocator
    )
    monkeypatch.setattr(
        registration, "translate_token_conflict", translate_token_conflict
    )

    # Drive the bounded retry loop with a fake savepoint whose flush always
    # reports the exact token-hash conflict. No DB rows are touched.
    class CollidingSavepoint:
        def commit(self):
            return None

        def rollback(self):
            return None

    def colliding_flush():
        raise collision_error

    monkeypatch.setattr(db, "begin_nested", lambda: CollidingSavepoint())
    monkeypatch.setattr(db, "add", lambda instance: None)
    monkeypatch.setattr(db, "flush", colliding_flush)

    exam_stub = SimpleNamespace(id=exam_id_value)
    question_stub = SimpleNamespace(id=question_id_value)
    with pytest.raises(InvitationTokenUnavailableError) as exc:
        registration._persist_invitation(
            db,
            candidate_id=1,
            exam=exam_stub,
            expires_at=expiry,
            questions=[question_stub],
        )

    assert attempts["count"] == registration.MAX_TOKEN_PERSIST_ATTEMPTS
    assert "collision-token" not in str(exc.value)
    assert "token_hash" not in str(exc.value)


# --- 24-25: atomicity ------------------------------------------------------

def test_database_failure_rolls_back(db, seeded, monkeypatch):
    def failing_candidate(*args, **kwargs):
        raise IntegrityError("INSERT", {}, Exception("simulated failure"))

    monkeypatch.setattr(registration, "get_or_create_candidate", failing_candidate)
    with pytest.raises(IntegrityError):
        register(db, make_request())
    assert db.scalar(select(ExamInvitation).where(ExamInvitation.exam_id == 1)) is None
    assert db.scalar(select(ExamInvitationQuestion)) is None


def test_failure_during_selection_persistence_leaves_no_partial_records(db, seeded, monkeypatch):
    original_add = db.add

    def failing_add(instance):
        if isinstance(instance, ExamInvitationQuestion):
            raise IntegrityError("INSERT", {}, Exception("simulated selection failure"))
        return original_add(instance)

    monkeypatch.setattr(db, "add", failing_add)
    with pytest.raises(IntegrityError):
        register(db, make_request())
    assert db.scalar(select(ExamInvitation)) is None
    assert db.scalar(select(ExamInvitationQuestion)) is None


# --- 26: client-controlled identifiers ------------------------------------

def test_candidate_id_and_code_are_not_accepted(db, seeded):
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        make_request(candidate_id=999)
    with pytest.raises(ValidationError):
        make_request(candidate_code="CAND-123")


# --- URL-free registration and explicit expiration ------------------------

def test_registration_succeeds_without_any_url_configuration(db, seeded, monkeypatch):
    monkeypatch.delenv("INVITATION_BASE_URL", raising=False)
    response = register(db, make_request())
    db.commit()
    assert response.invitation_url is None
    assert "candidate/verify" not in str(response.model_dump())
    assert db.scalar(select(ExamInvitation).where(
        ExamInvitation.id == response.invitation_id
    )) is not None


def test_registration_uses_explicit_expiration(db, seeded):
    explicit = datetime(2030, 6, 30, 12, 0, tzinfo=timezone.utc)
    response = register(db, make_request(), expires_at=explicit)
    db.commit()
    invitation = db.get(ExamInvitation, response.invitation_id)
    # SQLite stores DateTime(timezone=True) without tzinfo; compare in UTC.
    assert invitation.expires_at == explicit.replace(tzinfo=None)
    assert invitation.expires_at != seeded[1].available_until


def test_missing_expiration_is_rejected_before_database_writes(db, seeded):
    with pytest.raises(TypeError):
        registration.register_candidate_for_exam(db, make_request())
    assert db.scalar(select(ExamInvitation)) is None
    assert db.scalar(select(Candidate).where(Candidate.email == "sara@example.com")) is None
