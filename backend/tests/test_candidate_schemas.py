"""Focused tests for candidate registration and invitation schemas (issues #78/#79)."""

import pytest
from pydantic import ValidationError

from app.schemas.candidate import (
    CandidateInvitationRequest,
    CandidateInvitationResponse,
    CandidateRegistrationInput,
    CandidateRegistrationRequest,
)


def registration_data(**overrides):
    data = {
        "exam_id": 10,
        "first_name": "Sara",
        "last_name": "Ahmadi",
        "email": "sara@example.com",
    }
    data.update(overrides)
    return data


def invitation_data(**overrides):
    data = {
        "exam_id": 10,
        "first_name": "Sara",
        "last_name": "Ahmadi",
        "email": "sara@example.com",
        "exam_question_ids": [101, 102],
    }
    data.update(overrides)
    return data


def test_registration_accepts_email_only():
    request = CandidateRegistrationRequest(**registration_data(email="sara@example.com"))
    assert request.email == "sara@example.com"
    assert request.phone is None


def test_registration_accepts_phone_only():
    request = CandidateRegistrationRequest(**registration_data(email=None, phone="+989121234567"))
    assert request.email is None
    assert request.phone == "+989121234567"


def test_registration_accepts_email_and_phone():
    request = CandidateRegistrationRequest(**registration_data(phone="+989121234567"))
    assert request.email == "sara@example.com"
    assert request.phone == "+989121234567"


def test_registration_rejects_missing_contact_details():
    with pytest.raises(ValidationError):
        CandidateRegistrationRequest(**registration_data(email=None, phone=None))


def test_registration_normalizes_email():
    request = CandidateRegistrationRequest(**registration_data(email="  Sara@Example.COM  "))
    assert request.email == "sara@example.com"


def test_registration_normalizes_iranian_national_phone():
    request = CandidateRegistrationRequest(
        **registration_data(email=None, phone="09121234567", phone_region="ir")
    )
    assert request.phone == "+989121234567"
    assert request.phone_region == "IR"


def test_registration_normalizes_international_phone():
    request = CandidateRegistrationRequest(**registration_data(email=None, phone="+989121234567"))
    assert request.phone == "+989121234567"


def test_registration_rejects_national_phone_without_region():
    with pytest.raises(ValidationError, match="phone region"):
        CandidateRegistrationRequest(**registration_data(email=None, phone="09121234567"))


def test_registration_rejects_invalid_phone():
    with pytest.raises(ValidationError, match="Invalid phone number"):
        CandidateRegistrationRequest(**registration_data(email=None, phone="12345", phone_region="IR"))


def test_registration_rejects_invalid_email():
    with pytest.raises(ValidationError):
        CandidateRegistrationRequest(**registration_data(email="not-an-email"))


def test_registration_rejects_phone_region_without_phone():
    with pytest.raises(ValidationError, match="requires a phone"):
        CandidateRegistrationRequest(**registration_data(phone_region="IR"))


def test_registration_rejects_client_candidate_id():
    with pytest.raises(ValidationError):
        CandidateRegistrationRequest(**registration_data(candidate_id=123))


def test_registration_rejects_client_candidate_code():
    with pytest.raises(ValidationError):
        CandidateRegistrationRequest(**registration_data(candidate_code="CAND-123"))


def test_invitation_requires_at_least_one_question():
    with pytest.raises(ValidationError):
        CandidateInvitationRequest(**invitation_data(exam_question_ids=[]))


def test_invitation_rejects_duplicate_question_ids():
    with pytest.raises(ValidationError, match="unique"):
        CandidateInvitationRequest(**invitation_data(exam_question_ids=[101, 101]))


def test_invitation_rejects_non_positive_question_ids():
    with pytest.raises(ValidationError):
        CandidateInvitationRequest(**invitation_data(exam_question_ids=[101, 0]))


def test_invitation_accepts_unique_question_ids():
    request = CandidateInvitationRequest(**invitation_data())
    assert request.exam_question_ids == [101, 102]


def test_invitation_response_supports_new_candidate():
    response = CandidateInvitationResponse(
        invitation_id=50,
        exam_id=10,
        candidate_name="Sara Ahmadi",
        email="sara@example.com",
        phone=None,
        candidate_reused=False,
        invitation_url="https://example.com/invitation/secure-token",
    )
    assert response.candidate_reused is False
    assert response.invitation_id == 50
    assert response.exam_id == 10


def test_invitation_response_supports_reused_candidate():
    response = CandidateInvitationResponse(
        invitation_id=51,
        exam_id=10,
        candidate_name="Sara Ahmadi",
        email="sara@example.com",
        phone=None,
        candidate_reused=True,
        invitation_url="https://example.com/invitation/secure-token",
    )
    assert response.candidate_reused is True


def test_invitation_response_rejects_candidate_id():
    with pytest.raises(ValidationError):
        CandidateInvitationResponse(
            invitation_id=50,
            exam_id=10,
            candidate_id=123,
            candidate_name="Sara Ahmadi",
            email="sara@example.com",
            candidate_reused=False,
            invitation_url="https://example.com/invitation/secure-token",
        )


def test_invitation_response_rejects_candidate_code():
    with pytest.raises(ValidationError):
        CandidateInvitationResponse(
            invitation_id=50,
            exam_id=10,
            candidate_code="CAND-123",
            candidate_name="Sara Ahmadi",
            email="sara@example.com",
            candidate_reused=False,
            invitation_url="https://example.com/invitation/secure-token",
        )


def test_iranian_national_and_international_phones_are_equivalent():
    national = CandidateRegistrationRequest(
        **registration_data(email=None, phone="09121234567", phone_region="IR")
    )
    international = CandidateRegistrationRequest(
        **registration_data(email=None, phone="+989121234567")
    )
    assert national.phone == international.phone
    assert national.phone == "+989121234567"


def test_registration_normalizes_phone_region_whitespace():
    request = CandidateRegistrationRequest(
        **registration_data(email=None, phone="09121234567", phone_region=" ir ")
    )
    assert request.phone_region == "IR"
    assert request.phone == "+989121234567"


def test_registration_rejects_unsupported_phone_region():
    with pytest.raises(ValidationError, match="Unsupported phone region"):
        CandidateRegistrationRequest(
            **registration_data(email=None, phone="09121234567", phone_region="XX")
        )


def test_invitation_response_rejects_invalid_url():
    with pytest.raises(ValidationError):
        CandidateInvitationResponse(
            invitation_id=50,
            exam_id=10,
            candidate_name="Sara Ahmadi",
            email="sara@example.com",
            phone=None,
            candidate_reused=False,
            invitation_url="not-a-valid-url",
        )


def test_registration_rejects_blank_names():
    with pytest.raises(ValidationError):
        CandidateRegistrationRequest(**registration_data(first_name="   "))


def test_strict_models_reject_unknown_fields():
    with pytest.raises(ValidationError):
        CandidateRegistrationRequest(**registration_data(unexpected_field="x"))
    with pytest.raises(ValidationError):
        CandidateInvitationResponse(
            invitation_id=50,
            exam_id=10,
            candidate_name="Sara Ahmadi",
            candidate_reused=False,
            invitation_url="https://example.com/invitation/token",
            unexpected_field="x",
        )


def test_candidate_registration_input_normalizes_phone():
    """The pre-existing input schema keeps its phone normalization behavior."""
    registration = CandidateRegistrationInput(
        first_name="Ali", last_name="Rezayi", phone="09121234567"
    )
    assert registration.first_name == "Ali"
    assert registration.phone == "+989121234567"


def test_registration_accepts_100_character_names():
    request = CandidateRegistrationRequest(
        **registration_data(first_name="A" * 100, last_name="B" * 100)
    )
    assert request.first_name == "A" * 100
    assert request.last_name == "B" * 100


def test_registration_rejects_101_character_names():
    with pytest.raises(ValidationError):
        CandidateRegistrationRequest(**registration_data(first_name="A" * 101))
    with pytest.raises(ValidationError):
        CandidateRegistrationRequest(**registration_data(last_name="B" * 101))


def test_registration_input_accepts_email_only():
    value = CandidateRegistrationInput(
        first_name="Ali", last_name="Rezayi", email="ali@example.com"
    )
    assert value.email == "ali@example.com"
    assert value.phone is None


def test_registration_input_accepts_phone_only():
    value = CandidateRegistrationInput(
        first_name="Ali", last_name="Rezayi", phone="09121234567"
    )
    assert value.email is None
    assert value.phone == "+989121234567"


def test_registration_input_accepts_both_contact_methods():
    value = CandidateRegistrationInput(
        first_name="Ali",
        last_name="Rezayi",
        email="ali@example.com",
        phone="09121234567",
    )
    assert value.email == "ali@example.com"
    assert value.phone == "+989121234567"


def test_registration_input_rejects_missing_contact_methods():
    with pytest.raises(ValidationError, match="At least one of email or phone"):
        CandidateRegistrationInput(first_name="Ali", last_name="Rezayi")


@pytest.mark.parametrize("blank_phone", ["", "   ", "\t\n"])
def test_registration_input_rejects_blank_phone_as_contact(blank_phone):
    """Blank phone normalizes to None, so it cannot satisfy the contact rule."""

    with pytest.raises(ValidationError, match="At least one of email or phone"):
        CandidateRegistrationInput(
            first_name="Ali", last_name="Rezayi", phone=blank_phone
        )
