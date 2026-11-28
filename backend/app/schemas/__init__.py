"""Backend Pydantic request and response schemas."""

from app.schemas.attempt_event import AttemptEventCreate, AttemptEventResponse
from app.schemas.base import StrictModel
from app.schemas.exam import ExamCreateResponse
from app.schemas.invitation_validation import (
    InvitationValidationOutcome,
    InvitationValidationRequest,
    InvitationValidationResponse,
)
from app.schemas.candidate import (
    CandidateInvitationRequest,
    CandidateInvitationResponse,
    CandidateRegistrationInput,
    CandidateRegistrationRequest,
)
from app.schemas.staff_auth import (
    HRRole,
    HRStaffIdentity,
    SessionTokenType,
    StaffAuthenticationResponse,
    StaffIdentityType,
    StaffLoginContext,
    StaffLoginRequest,
    StaffSession,
    TechnicalSupportStaffIdentity,
)

__all__ = [
    "HRRole",
    "HRStaffIdentity",
    "SessionTokenType",
    "StaffAuthenticationResponse",
    "StaffIdentityType",
    "StaffLoginContext",
    "StaffLoginRequest",
    "StaffSession",
    "TechnicalSupportStaffIdentity",
    "AttemptEventCreate",
    "AttemptEventResponse",
    "ExamCreateResponse",
    "StrictModel",
    "CandidateRegistrationInput",
    "CandidateRegistrationRequest",
    "CandidateInvitationRequest",
    "CandidateInvitationResponse",
    "InvitationValidationOutcome",
    "InvitationValidationRequest",
    "InvitationValidationResponse",
]
