"""Issue #85: read-only validation of an invitation bearer token.

The raw token is the only credential accepted here. It is hashed with the
existing ``invitation_token`` helper and matched against the unique digest on
``ExamInvitation``; the resolved Candidate, Exam and optional
``AssessmentAttempt`` are reached strictly through that invitation.

This service never writes, commits, rolls back, creates attempts, changes
statuses, or exposes questions, answers, scores or candidate contact details.
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.assessment_attempt import AssessmentAttempt, AttemptStatus
from app.models.candidate import Candidate
from app.models.exam import Exam, ExamStatus
from app.models.exam_invitation import ExamInvitation, InvitationStatus
from app.schemas.invitation_validation import (
    InvitationValidationOutcome,
    InvitationValidationResponse,
)
from app.services.invitation_token import hash_invitation_token

# Generous upper bound: only rejects obvious garbage, not a token format policy.
MAX_TOKEN_LENGTH = 1024

TERMINAL_ATTEMPT_STATUSES = frozenset(
    {
        AttemptStatus.SUBMITTED,
        AttemptStatus.TIMED_OUT,
        AttemptStatus.INTERRUPTED,
        AttemptStatus.CANCELLED,
    }
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(value: datetime) -> datetime:
    """Normalize stored timestamps for comparison.

    SQLite drops ``tzinfo`` on round-trip; PostgreSQL preserves it. A naive
    stored value is interpreted as UTC, matching how the service writes it.
    """
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


def _usable_token(token: object) -> bool:
    if not isinstance(token, str):
        return False
    candidate = token.strip()
    if not candidate or len(candidate) > MAX_TOKEN_LENGTH:
        return False
    # Whitespace or control characters never occur in the generated token.
    return all(not character.isspace() and character.isprintable() for character in candidate)


@dataclass(frozen=True)
class InvitationValidationResult:
    """Internal resolution plus the only object safe to serialize.

    ``response`` is the public contract. The ORM attributes exist so callers
    can use the resolved entities internally; they must never be serialized.
    """

    response: InvitationValidationResponse
    invitation: ExamInvitation | None = None
    candidate: Candidate | None = None
    exam: Exam | None = None
    attempt: AssessmentAttempt | None = None

    @property
    def outcome(self) -> InvitationValidationOutcome:
        return self.response.outcome


def _invalid() -> InvitationValidationResult:
    """Generic outcome that reveals nothing about candidates or exams."""
    return InvitationValidationResult(
        response=InvitationValidationResponse(outcome=InvitationValidationOutcome.INVALID_TOKEN)
    )


def _response(
    outcome: InvitationValidationOutcome,
    *,
    exam: Exam,
    invitation: ExamInvitation,
    attempt: AssessmentAttempt | None,
) -> InvitationValidationResponse:
    return InvitationValidationResponse(
        outcome=outcome,
        exam_name=exam.name,
        exam_duration_minutes=exam.duration_minutes,
        exam_available_from=_as_utc(exam.available_from),
        exam_available_until=_as_utc(exam.available_until),
        invitation_expires_at=_as_utc(invitation.expires_at),
        attempt_deadline_at=_as_utc(attempt.deadline_at) if attempt is not None else None,
    )


def _result(
    outcome: InvitationValidationOutcome,
    *,
    invitation: ExamInvitation,
    candidate: Candidate,
    exam: Exam,
    attempt: AssessmentAttempt | None,
) -> InvitationValidationResult:
    return InvitationValidationResult(
        response=_response(outcome, exam=exam, invitation=invitation, attempt=attempt),
        invitation=invitation,
        candidate=candidate,
        exam=exam,
        attempt=attempt,
    )


def validate_invitation_token(
    db: Session,
    token: object,
    *,
    now_fn: Callable[[], datetime] | None = None,
) -> InvitationValidationResult:
    """Validate an invitation token and resolve its invitation-scoped entities.

    Args:
        db: Caller-owned session. No flush, commit or rollback is performed.
        token: Raw invitation bearer token. No candidate or exam identifier is
            accepted as an alternative credential.
        now_fn: Injectable server-side UTC clock for deterministic tests.

    Returns:
        A result whose ``response`` is the privacy-safe public outcome. Every
        rejection that could reveal identity information uses INVALID_TOKEN.
    """
    if not _usable_token(token):
        return _invalid()

    now = _as_utc((now_fn or _utc_now)())
    digest = hash_invitation_token(token.strip())

    # Autoflush is disabled so validation cannot flush caller-pending writes.
    with db.no_autoflush:
        invitations = db.scalars(
            select(ExamInvitation).where(ExamInvitation.token_hash == digest)
        ).all()
        if len(invitations) != 1:
            return _invalid()
        invitation = invitations[0]

        # Explicit queries (rather than Session.get) keep every lookup inside
        # no_autoflush, so validation cannot flush caller-pending writes.
        candidates = db.scalars(
            select(Candidate).where(Candidate.id == invitation.candidate_id)
        ).all()
        exams = db.scalars(
            select(Exam).where(Exam.id == invitation.exam_id)
        ).all()
        if len(candidates) != 1 or len(exams) != 1:
            return _invalid()
        candidate = candidates[0]
        exam = exams[0]
        if candidate.id != invitation.candidate_id or exam.id != invitation.exam_id:
            return _invalid()

        attempts = db.scalars(
            select(AssessmentAttempt).where(
                AssessmentAttempt.exam_invitation_id == invitation.id
            )
        ).all()
        if len(attempts) > 1:
            return _invalid()
        attempt = attempts[0] if attempts else None
        if attempt is not None and (
            attempt.exam_invitation_id != invitation.id
            or attempt.candidate_id != invitation.candidate_id
            or attempt.exam_id != invitation.exam_id
        ):
            return _invalid()

        # Cancellation is authoritative for the exam and the invitation, and
        # overrides an otherwise resumable in-progress attempt.
        if (
            invitation.status == InvitationStatus.CANCELLED
            or exam.status == ExamStatus.CANCELLED
        ):
            return _result(
                InvitationValidationOutcome.CANCELLED,
                invitation=invitation, candidate=candidate, exam=exam, attempt=attempt,
            )

        if attempt is not None:
            if attempt.status == AttemptStatus.IN_PROGRESS:
                if now < _as_utc(attempt.deadline_at):
                    return _result(
                        InvitationValidationOutcome.IN_PROGRESS,
                        invitation=invitation, candidate=candidate, exam=exam, attempt=attempt,
                    )
                return _result(
                    InvitationValidationOutcome.EXPIRED,
                    invitation=invitation, candidate=candidate, exam=exam, attempt=attempt,
                )
            if attempt.status in TERMINAL_ATTEMPT_STATUSES:
                return _result(
                    InvitationValidationOutcome.TERMINAL_ATTEMPT,
                    invitation=invitation, candidate=candidate, exam=exam, attempt=attempt,
                )
            if attempt.status != AttemptStatus.NOT_STARTED:
                return _invalid()

        # Starting (or restarting a Not Started attempt) uses the normal window.
        if (
            invitation.status == InvitationStatus.EXPIRED
            or now >= _as_utc(invitation.expires_at)
            or now >= _as_utc(exam.available_until)
        ):
            return _result(
                InvitationValidationOutcome.EXPIRED,
                invitation=invitation, candidate=candidate, exam=exam, attempt=attempt,
            )

        if (
            exam.status == ExamStatus.CREATED
            or now < _as_utc(exam.available_from)
        ):
            return _result(
                InvitationValidationOutcome.NOT_YET_ACTIVE,
                invitation=invitation, candidate=candidate, exam=exam, attempt=attempt,
            )

        if exam.status != ExamStatus.PUBLISHED:
            return _invalid()

        return _result(
            InvitationValidationOutcome.ELIGIBLE,
            invitation=invitation, candidate=candidate, exam=exam, attempt=attempt,
        )
