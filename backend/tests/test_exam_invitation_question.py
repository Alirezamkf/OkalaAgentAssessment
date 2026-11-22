"""Database behavior tests for exam invitation question selections."""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, delete, event
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database.base import Base
from app.models.assessment_attempt import AssessmentAttempt
from app.models.candidate import Candidate
from app.models.exam import Exam, ExamStatus
from app.models.exam_invitation import ExamInvitation, InvitationStatus
from app.models.exam_invitation_question import ExamInvitationQuestion
from app.models.exam_question import ExamQuestion
from app.models.exam_template import ExamTemplate
from app.models.hr_user import HRUser


@pytest.fixture
def db():
    engine = create_engine("sqlite+pysqlite:///:memory:")

    @event.listens_for(engine, "connect")
    def enable_sqlite_foreign_keys(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    tables = [
        HRUser.__table__,
        ExamTemplate.__table__,
        Candidate.__table__,
        Exam.__table__,
        ExamQuestion.__table__,
        ExamInvitation.__table__,
        AssessmentAttempt.__table__,
        ExamInvitationQuestion.__table__,
    ]
    Base.metadata.create_all(engine, tables=tables)

    session = Session(engine)
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def create_hr_user(session: Session, username: str = "hr-user") -> HRUser:
    hr_user = HRUser(
        id=1,
        username=username,
        password_hash="hash",
        first_name="Test",
        last_name="HR",
        position="Recruiter",
    )
    session.add(hr_user)
    session.flush()
    return hr_user


def create_exam(session: Session, hr_user: HRUser, name: str, exam_id: int = 1) -> Exam:
    now = datetime.now(timezone.utc)
    exam = Exam(
        id=exam_id,
        name=name,
        status=ExamStatus.CREATED,
        duration_minutes=25,
        available_from=now,
        available_until=now + timedelta(days=7),
        created_by_hr_user_id=hr_user.id,
    )
    session.add(exam)
    session.flush()
    return exam


def create_question(session: Session, exam: Exam, text: str, question_id: int = 1) -> ExamQuestion:
    question = ExamQuestion(id=question_id, exam_id=exam.id, text=text, score=10)
    session.add(question)
    session.flush()
    return question


def create_candidate(session: Session, email: str = "candidate@example.com", candidate_id: int = 1) -> Candidate:
    candidate = Candidate(
        id=candidate_id,
        first_name="Test",
        last_name="Candidate",
        email=email,
    )
    session.add(candidate)
    session.flush()
    return candidate


def create_invitation(
    session: Session,
    exam: Exam,
    candidate: Candidate,
    token_hash: str,
    invitation_id: int = 1,
) -> ExamInvitation:
    now = datetime.now(timezone.utc)
    invitation = ExamInvitation(
        id=invitation_id,
        candidate_id=candidate.id,
        exam_id=exam.id,
        token_hash=token_hash,
        status=InvitationStatus.PENDING,
        created_at=now,
        expires_at=now + timedelta(days=7),
    )
    session.add(invitation)
    session.flush()
    return invitation


def test_candidate_can_have_independent_invitations_for_multiple_exams(db: Session) -> None:
    hr_user = create_hr_user(db)
    first_exam = create_exam(db, hr_user, "Exam One", exam_id=1)
    second_exam = create_exam(db, hr_user, "Exam Two", exam_id=2)
    candidate = create_candidate(db)

    first_invitation = create_invitation(db, first_exam, candidate, "token-first", invitation_id=1)
    second_invitation = create_invitation(db, second_exam, candidate, "token-second", invitation_id=2)
    db.commit()

    stored_candidate = db.get(Candidate, candidate.id)
    assert stored_candidate is not None
    assert {invitation.id for invitation in stored_candidate.invitations} == {
        first_invitation.id,
        second_invitation.id,
    }
    assert first_invitation.candidate_id == second_invitation.candidate_id == candidate.id
    assert first_invitation.exam_id != second_invitation.exam_id


def test_valid_question_can_be_selected_for_exam_invitation(db: Session) -> None:
    hr_user = create_hr_user(db)
    exam = create_exam(db, hr_user, "Exam One")
    candidate = create_candidate(db)
    invitation = create_invitation(db, exam, candidate, "token-valid")
    question = create_question(db, exam, "What is the answer?")

    selection = ExamInvitationQuestion(
        id=1,
        exam_invitation_id=invitation.id,
        exam_question_id=question.id,
        exam_id=exam.id,
    )
    db.add(selection)
    db.commit()

    stored = db.get(ExamInvitationQuestion, selection.id)
    assert stored is not None
    assert stored.invitation.id == invitation.id
    assert stored.exam_question.id == question.id
    assert stored.exam_id == exam.id


def test_same_question_cannot_be_selected_twice_for_same_invitation(db: Session) -> None:
    hr_user = create_hr_user(db)
    exam = create_exam(db, hr_user, "Exam One")
    candidate = create_candidate(db)
    invitation = create_invitation(db, exam, candidate, "token-duplicate")
    question = create_question(db, exam, "Duplicate question")

    db.add(ExamInvitationQuestion(
        id=1,
        exam_invitation_id=invitation.id,
        exam_question_id=question.id,
        exam_id=exam.id,
    ))
    db.flush()

    db.add(ExamInvitationQuestion(
        id=2,
        exam_invitation_id=invitation.id,
        exam_question_id=question.id,
        exam_id=exam.id,
    ))
    with pytest.raises(IntegrityError):
        db.flush()
    db.rollback()


def test_same_question_can_be_selected_for_different_invitations(db: Session) -> None:
    hr_user = create_hr_user(db)
    exam = create_exam(db, hr_user, "Exam One")
    first_candidate = create_candidate(db, "first@example.com")
    second_candidate = create_candidate(db, "second@example.com", candidate_id=2)
    first_invitation = create_invitation(db, exam, first_candidate, "token-first")
    second_invitation = create_invitation(db, exam, second_candidate, "token-second", invitation_id=2)
    question = create_question(db, exam, "Shared question")

    db.add_all([
        ExamInvitationQuestion(
            id=1,
            exam_invitation_id=first_invitation.id,
            exam_question_id=question.id,
            exam_id=exam.id,
        ),
        ExamInvitationQuestion(
            id=2,
            exam_invitation_id=second_invitation.id,
            exam_question_id=question.id,
            exam_id=exam.id,
        ),
    ])
    db.commit()

    assert db.query(ExamInvitationQuestion).filter_by(exam_question_id=question.id).count() == 2


def test_question_from_another_exam_cannot_be_selected(db: Session) -> None:
    hr_user = create_hr_user(db)
    first_exam = create_exam(db, hr_user, "Exam One")
    second_exam = create_exam(db, hr_user, "Exam Two", exam_id=2)
    candidate = create_candidate(db)
    invitation = create_invitation(db, first_exam, candidate, "token-mismatch")
    question = create_question(db, second_exam, "Question from Exam Two", question_id=2)

    # Composite foreign keys must keep the invitation, question, and exam ID aligned.
    db.add(ExamInvitationQuestion(
        id=1,
        exam_invitation_id=invitation.id,
        exam_question_id=question.id,
        exam_id=first_exam.id,
    ))
    with pytest.raises(IntegrityError):
        db.flush()
    db.rollback()


@pytest.mark.parametrize("missing_column", ["exam_invitation_id", "exam_question_id", "exam_id"])
def test_required_foreign_key_columns_reject_null_values(db: Session, missing_column: str) -> None:
    hr_user = create_hr_user(db)
    exam = create_exam(db, hr_user, "Exam One")
    candidate = create_candidate(db)
    invitation = create_invitation(db, exam, candidate, "token-required")
    question = create_question(db, exam, "Required question")

    values = {
        "exam_invitation_id": invitation.id,
        "exam_question_id": question.id,
        "exam_id": exam.id,
    }
    values[missing_column] = None

    db.add(ExamInvitationQuestion(id=1, **values))
    with pytest.raises(IntegrityError):
        db.flush()
    db.rollback()


def test_association_columns_and_composite_constraints_are_defined() -> None:
    table = ExamInvitationQuestion.__table__

    assert table.c.exam_invitation_id.nullable is False
    assert table.c.exam_question_id.nullable is False
    assert table.c.exam_id.nullable is False
    assert any(
        constraint.name == "fk_invitation_questions_invitation_exam"
        for constraint in table.constraints
    )
    assert any(
        constraint.name == "fk_invitation_questions_exam_question_exam"
        for constraint in table.constraints
    )
    assert any(
        constraint.name == "uq_invitation_questions_invitation_question"
        for constraint in table.constraints
    )


def test_deleting_selection_removes_only_the_association(db: Session) -> None:
    hr_user = create_hr_user(db)
    exam = create_exam(db, hr_user, "Exam One")
    candidate = create_candidate(db)
    invitation = create_invitation(db, exam, candidate, "token-delete-selection")
    question = create_question(db, exam, "Selectable question")
    selection = ExamInvitationQuestion(
        id=1,
        exam_invitation_id=invitation.id,
        exam_question_id=question.id,
        exam_id=exam.id,
    )
    db.add(selection)
    db.commit()

    db.delete(selection)
    db.commit()

    assert db.get(ExamInvitationQuestion, selection.id) is None
    assert db.get(ExamInvitation, invitation.id) is not None
    assert db.get(ExamQuestion, question.id) is not None


@pytest.mark.parametrize("parent", ["invitation", "question"])
def test_deleting_selected_parent_is_restricted(db: Session, parent: str) -> None:
    hr_user = create_hr_user(db)
    exam = create_exam(db, hr_user, "Exam One")
    candidate = create_candidate(db)
    invitation = create_invitation(db, exam, candidate, f"token-delete-{parent}")
    question = create_question(db, exam, "Protected question")
    db.add(ExamInvitationQuestion(
        id=1,
        exam_invitation_id=invitation.id,
        exam_question_id=question.id,
        exam_id=exam.id,
    ))
    db.commit()

    statement = (
        delete(ExamInvitation).where(ExamInvitation.id == invitation.id)
        if parent == "invitation"
        else delete(ExamQuestion).where(ExamQuestion.id == question.id)
    )
    with pytest.raises(IntegrityError):
        db.execute(statement)
        db.commit()
    db.rollback()
