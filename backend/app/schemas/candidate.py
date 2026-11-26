"""Pydantic schemas for Candidate registration contact details."""

from typing import Self

import phonenumbers
from pydantic import (
    AnyHttpUrl,
    BaseModel,
    EmailStr,
    Field,
    PositiveInt,
    field_validator,
    model_validator,
)

from app.schemas.base import StrictModel
from app.services.candidate_identity import InvalidPhoneNumberError, normalize_phone


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


class CandidateRegistrationRequest(StrictModel):
    """HR-provided candidate details for registration in an actual exam.

    The client cannot choose a Candidate database ID or candidate code.
    Candidate lookup and safe reuse are responsibilities of the service layer.
    """

    exam_id: PositiveInt
    first_name: str = Field(min_length=1, max_length=120)
    last_name: str = Field(min_length=1, max_length=120)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=50)

    # Optional ISO 3166-1 alpha-2 region, e.g. IR or GB.
    # Required for national-format phone numbers.
    phone_region: str | None = None

    @field_validator("first_name", "last_name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Name must not be blank")
        return value

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: EmailStr | None) -> EmailStr | None:
        if value is None:
            return None
        return str(value).strip().casefold()

    @field_validator("phone_region")
    @classmethod
    def normalize_phone_region(cls, value: str | None) -> str | None:
        if value is None:
            return None

        region = value.strip().upper()

        if len(region) != 2:
            raise ValueError("Phone region must be a two-letter country code")

        if region not in phonenumbers.SUPPORTED_REGIONS:
            raise ValueError("Unsupported phone region")

        return region

    @field_validator("phone")
    @classmethod
    def normalize_phone_value(cls, value: str | None) -> str | None:
        if value is None:
            return None

        value = value.strip()
        if not value:
            raise ValueError("Phone must not be blank")

        return value

    @model_validator(mode="after")
    def validate_contact_and_phone(self) -> Self:
        if self.email is None and self.phone is None:
            raise ValueError("At least one of email or phone is required")

        if self.phone is None:
            if self.phone_region is not None:
                raise ValueError("Phone region requires a phone number")
            return self

        # Never guess a country code for a national-format number. Delegate
        # canonicalization to the single backend utility so lookup and storage
        # use exactly the same E.164 rules as candidate_identity.
        if not self.phone.startswith("+") and self.phone_region is None:
            raise ValueError(
                "A phone region is required for national-format phone numbers"
            )

        try:
            self.phone = normalize_phone(self.phone, region=self.phone_region)
        except InvalidPhoneNumberError as exc:
            raise ValueError("Invalid phone number") from exc
        return self


class CandidateInvitationRequest(CandidateRegistrationRequest):
    """HR registration details plus explicit question selection for an exam."""

    exam_question_ids: list[PositiveInt] = Field(min_length=1)

    @field_validator("exam_question_ids")
    @classmethod
    def validate_unique_question_ids(
        cls,
        value: list[PositiveInt],
    ) -> list[PositiveInt]:
        if len(value) != len(set(value)):
            raise ValueError("Exam question IDs must be unique")
        return value


class CandidateInvitationResponse(StrictModel):
    """Safe HR-facing result after an invitation has been created."""

    invitation_id: PositiveInt
    exam_id: PositiveInt
    candidate_name: str = Field(min_length=1, max_length=255)
    email: EmailStr | None = None
    phone: str | None = None
    candidate_reused: bool
    invitation_url: AnyHttpUrl
