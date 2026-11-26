"""Issue #80: register a candidate and create one independent exam invitation.

The service composes existing, already-tested components:

* ``candidate_identity`` for conservative candidate reuse;
* ``invitation_token`` for 256-bit tokens, SHA-256 digests and collision handling;
* the exam-owned ``ExamQuestion`` snapshots and their ``ExamInvitationQuestion``
  selection associations.

It deliberately does not commit the caller-owned session. The whole operation
runs inside a SAVEPOINT so a failure cannot leave a partial candidate,
invitation, or question-selection record behind.
"""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.models.exam import Exam
from app.models.exam_invitation import ExamInvitation
from app.models.exam_invitation_question import ExamInvitationQuestion
from app.models.exam_question import ExamQuestion
from app.schemas.candidate import CandidateInvitationRequest, CandidateInvitationResponse
from app.services.candidate_identity import (
    get_or_create_candidate,
    resolve_candidate,
)
from app.services.invitation_token import (
    InvitationTokenUnavailableError,
    allocate_unique_invitation_token,
    hash_invitation_token,
    translate_token_conflict,
)

MAX_TOKEN_PERSIST_ATTEMPTS = 5
MIN_OPTIONS = 2
MAX_OPTIONS = 6


class CandidateRegistrationError(ValueError):
    """Base class for rejected candidate registrations."""


class ExamNotFoundError(CandidateRegistrationError):
    """The requested actual Exam does not exist."""


class InvalidQuestionSelectionError(CandidateRegistrationError):
    """The HR-selected question subset is missing, invalid, or cross-exam."""


class CandidateIdentityConflictError(CandidateRegistrationError):
    """Identity details match conflicting or ambiguous candidate records."""


def _validate_question_ids(question_ids: list[int]) -> list[int]:
    """Reject empty or duplicate IDs even when the service is called directly."""
    if not question_ids:
        raise InvalidQuestionSelectionError("At least one exam question is required")

    normalized = [int(question_id) for question_id in question_ids]
    if any(question_id < 1 for question_id in normalized):
        raise InvalidQuestionSelectionError("Exam question IDs must be positive")
    if len(normalized) != len(set(normalized)):
        raise InvalidQuestionSelectionError("Exam question IDs must be unique")
    return normalized


def _validate_question_snapshot(question: ExamQuestion) -> None:
    """Validate the exam-owned question snapshot and its options."""
    if question.score is None or question.score <= 0:
        raise InvalidQuestionSelectionError(
            f"Exam question {question.id} must have a positive score"
        )

    options = list(question.options)
    if not MIN_OPTIONS <= len(options) <= MAX_OPTIONS:
        raise InvalidQuestionSelectionError(
            f"Exam question {question.id} must have between {MIN_OPTIONS} and "
            f"{MAX_OPTIONS} options"
        )

    for option in options:
        if not option.text or not option.text.strip():
            raise InvalidQuestionSelectionError(
                f"Exam question {question.id} has an empty option"
            )

    correct = sum(1 for option in options if option.is_correct)
    if correct != 1:
        raise InvalidQuestionSelectionError(
            f"Exam question {question.id} must have exactly one correct option"
        )


def _load_and_validate_questions(
    db: Session,
    *,
    exam: Exam,
    question_ids: list[int],
) -> list[ExamQuestion]:
    """Load only questions owned by this exam and validate every snapshot."""
    rows = db.scalars(
        select(ExamQuestion)
        .where(
            ExamQuestion.exam_id == exam.id,
            ExamQuestion.id.in_(question_ids),
        )
        .options(selectinload(ExamQuestion.options))
    ).all()
    questions = list(rows)

    found_ids = {question.id for question in questions}
    missing = [question_id for question_id in question_ids if question_id not in found_ids]
    if missing:
        raise InvalidQuestionSelectionError(
            "Every selected question must belong to the target exam"
        )

    by_id = {question.id: question for question in questions}
    ordered = [by_id[question_id] for question_id in question_ids]
    for question in ordered:
        _validate_question_snapshot(question)
    return ordered


def _persist_invitation(
    db: Session,
    *,
    candidate_id: int,
    exam: Exam,
    expires_at: datetime,
    questions: list[ExamQuestion],
) -> ExamInvitation:
    """Create the invitation and selections; only the digest is persisted."""
    for _ in range(MAX_TOKEN_PERSIST_ATTEMPTS):
        raw_token = allocate_unique_invitation_token(db)
        digest = hash_invitation_token(raw_token)
        invitation = ExamInvitation(
            candidate_id=candidate_id,
            exam_id=exam.id,
            token_hash=digest,
            created_at=datetime.now(timezone.utc),
            expires_at=expires_at,
        )
        db.add(invitation)
        savepoint = db.begin_nested()
        try:
            # A nested savepoint isolates a single token insert. A collision
            # rolls back only that insert, not the candidate changes made
            # earlier in the outer savepoint.
            db.flush()
            savepoint.commit()
        except IntegrityError as error:
            if invitation in db:
                db.expunge(invitation)
            savepoint.rollback()
            try:
                # Only the exact token-hash conflict is a retryable collision.
                translate_token_conflict(error)
            except InvitationTokenUnavailableError:
                continue
            raise

        for question in questions:
            db.add(
                ExamInvitationQuestion(
                    exam_invitation_id=invitation.id,
                    exam_question_id=question.id,
                    exam_id=exam.id,
                )
            )
        db.flush()
        return invitation

    raise InvitationTokenUnavailableError()


def register_candidate_for_exam(
    db: Session,
    request: CandidateInvitationRequest,
    *,
    expires_at: datetime,
) -> CandidateInvitationResponse:
    """Register/reuse a candidate and create one independent exam invitation.

    Args:
        db: Caller-owned SQLAlchemy session. It is never committed here.
        request: Already-validated HR registration request.
        expires_at: Explicit invitation expiry supplied by the caller. Issue #80
            defines no expiration policy, so the service does not derive one.

    Raises:
        ExamNotFoundError: The target exam does not exist.
        CandidateIdentityConflictError: Identity details conflict or are ambiguous.
        InvalidQuestionSelectionError: The selected subset is invalid.
        InvitationTokenUnavailableError: No unique token could be allocated.
    """
    question_ids = _validate_question_ids(request.exam_question_ids)

    # Read-only checks happen before any write.
    exam = db.get(Exam, request.exam_id)
    if exam is None:
        raise ExamNotFoundError(f"Exam {request.exam_id} does not exist")

    questions = _load_and_validate_questions(
        db, exam=exam, question_ids=question_ids
    )

    match = resolve_candidate(
        db,
        first_name=request.first_name,
        last_name=request.last_name,
        email=request.email,
        phone=request.phone,
    )
    candidate_reused = match.status == "reuse"

    with db.begin_nested():
        # begin_nested() rolls this savepoint back on any exception. Unrelated
        # database failures propagate unchanged with their original diagnostics.
        try:
            candidate = get_or_create_candidate(
                db,
                first_name=request.first_name,
                last_name=request.last_name,
                email=request.email,
                phone=request.phone,
            )
        except ValueError as error:
            raise CandidateIdentityConflictError(str(error)) from error

        invitation = _persist_invitation(
            db,
            candidate_id=candidate.id,
            exam=exam,
            expires_at=expires_at,
            questions=questions,
        )

    return CandidateInvitationResponse(
        invitation_id=invitation.id,
        exam_id=exam.id,
        candidate_name=f"{candidate.first_name} {candidate.last_name}",
        email=candidate.email,
        phone=candidate.phone,
        candidate_reused=candidate_reused,
    )
