"""Candidate-facing API routes.

Issue #86 exposes invitation-token validation here. All token, exam-status,
link-window, expiry, and attempt-status rules stay in the Issue #85 service;
this module only adapts the HTTP request to that service and returns its
privacy-safe response.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.schemas.invitation_validation import (
    InvitationValidationRequest,
    InvitationValidationResponse,
)
from app.services.invitation_validation import validate_invitation_token

router = APIRouter(prefix="/api/v1/candidates", tags=["candidates"])


@router.post("/invitations/validate", response_model=InvitationValidationResponse)
def validate_invitation(
    request: InvitationValidationRequest,
    db: Session = Depends(get_db),
) -> InvitationValidationResponse:
    """Validate an invitation bearer token without starting an attempt.

    Every validation outcome, including invalid tokens, is returned as a 200
    with the service's safe response. Malformed request bodies are rejected by
    FastAPI with 422 before this handler runs. The raw token is never logged.
    """
    return validate_invitation_token(db, request.token).response
