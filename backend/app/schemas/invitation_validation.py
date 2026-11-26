"""Public, privacy-safe response contract for invitation token validation."""

from datetime import datetime
from enum import Enum

from app.schemas.base import StrictModel


class InvitationValidationOutcome(str, Enum):
    """Distinguishable results of validating an invitation bearer token."""

    INVALID_TOKEN = "Invalid Token"
    NOT_YET_ACTIVE = "Not Yet Active"
    EXPIRED = "Expired"
    CANCELLED = "Cancelled"
    ELIGIBLE = "Eligible"
    IN_PROGRESS = "In Progress"
    TERMINAL_ATTEMPT = "Terminal Attempt"


class InvitationValidationResponse(StrictModel):
    """Candidate-facing validation result.

    Deliberately contains no candidate identifiers or contact details, no exam,
    invitation or attempt database IDs, no token or digest, no questions,
    options, answers or scores. Only scheduling metadata needed by a candidate
    is exposed, and it is absent entirely for an invalid token so that the
    response cannot reveal whether a candidate or exam exists.
    """

    outcome: InvitationValidationOutcome
    exam_name: str | None = None
    exam_duration_minutes: int | None = None
    exam_available_from: datetime | None = None
    exam_available_until: datetime | None = None
    invitation_expires_at: datetime | None = None
    attempt_deadline_at: datetime | None = None
