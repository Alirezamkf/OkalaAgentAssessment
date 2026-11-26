"""Backend Pydantic request and response schemas."""

from app.schemas.attempt_event import AttemptEventCreate, AttemptEventResponse
from app.schemas.base import StrictModel
from app.schemas.exam import ExamCreateResponse
from app.schemas.invitation_validation import (
    InvitationValidationOutcome,
    InvitationValidationResponse,
)
from app.schemas.candidate import (
    CandidateInvitationRequest,
    CandidateInvitationResponse,
    CandidateRegistrationInput,
    CandidateRegistrationRequest,
)

__all__ = [
    "AttemptEventCreate",
    "AttemptEventResponse",
    "ExamCreateResponse",
    "StrictModel",
    "CandidateRegistrationInput",
    "CandidateRegistrationRequest",
    "CandidateInvitationRequest",
    "CandidateInvitationResponse",
    "InvitationValidationOutcome",
    "InvitationValidationResponse",
]
