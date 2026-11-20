"""Pydantic schemas for Candidate registration contact details."""

from pydantic import BaseModel, Field, field_validator

from app.services.candidate_identity import normalize_phone


class CandidateRegistrationInput(BaseModel):
    """Backend-validated candidate registration fields."""

    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    email: str | None = Field(default=None, max_length=320)
    phone: str | None = Field(default=None, max_length=50)

    @field_validator("phone")
    @classmethod
    def validate_and_normalize_phone(cls, value: str | None) -> str | None:
        """Normalize candidate phone input at the Backend boundary."""

        return normalize_phone(value)
