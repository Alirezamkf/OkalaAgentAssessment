"""Focused schema tests for the shared staff login contract (Issue #81)."""

from datetime import datetime, timezone

import pytest
from pydantic import SecretStr, ValidationError

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


def login_data(**overrides):
    data = {
        "username": "hr.reception",
        "password": "a-strong-password",
        "login_context": "HR_PORTAL",
    }
    data.update(overrides)
    return data


def session_data(**overrides):
    data = {
        "session_token": "opaque-server-issued-handle",
        "token_type": "bearer",
        "expires_in_seconds": 900,
        "issued_at": "2026-11-28T10:00:00Z",
    }
    data.update(overrides)
    return data


def hr_identity(**overrides):
    data = {
        "identity_type": "HR",
        "hr_role": "HR",
        "display_name": "Sara Ahmadi",
        "profile_image_reference": None,
    }
    data.update(overrides)
    return data


def technical_support_identity(**overrides):
    data = {
        "identity_type": "TECHNICAL_SUPPORT",
        "display_name": "Ali Rezayi",
        "profile_image_reference": None,
    }
    data.update(overrides)
    return data


def test_login_accepts_valid_credentials_and_trims_username():
    request = StaffLoginRequest(**login_data(username="  hr.reception  "))
    assert request.username == "hr.reception"
    assert request.password.get_secret_value() == "a-strong-password"
    assert request.login_context is StaffLoginContext.HR_PORTAL


@pytest.mark.parametrize("context", ["HR_PORTAL", "HR_MANAGEMENT_PORTAL"])
def test_login_accepts_both_contexts_with_the_same_credentials(context):
    request = StaffLoginRequest(**login_data(login_context=context))
    assert request.login_context.value == context
    assert request.username == "hr.reception"
    assert request.password.get_secret_value() == "a-strong-password"


def test_login_context_values_are_exact():
    assert {member.value for member in StaffLoginContext} == {
        "HR_PORTAL",
        "HR_MANAGEMENT_PORTAL",
    }


def test_login_context_documentation_matches_the_product_entry_rules():
    documentation = StaffLoginContext.__doc__ or ""

    normalized = " ".join(documentation.split())
    assert "first-page HR Login button" in normalized
    assert "HR, HRAdmin, HRManagement, and Technical Support" in normalized
    assert "Technical Support" in normalized
    assert "HR Management button" in documentation
    assert "whose trusted backend role is HRManagement" in documentation
    assert "HRAdmin is not sufficient" in documentation
    assert "same username/password form" in documentation
    assert "same backend" in documentation
    assert "never grants access by itself" in documentation


@pytest.mark.parametrize(
    "context",
    [
        "HR",
        "HRAdmin",
        "HRManagement",
        "TECHNICAL_SUPPORT",
        "hr_portal",
        "",
        "   ",
        None,
        1,
    ],
)
def test_login_rejects_invalid_or_role_like_contexts(context):
    with pytest.raises(ValidationError):
        StaffLoginRequest(**login_data(login_context=context))


def test_login_requires_context():
    payload = login_data()
    del payload["login_context"]
    with pytest.raises(ValidationError):
        StaffLoginRequest(**payload)


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"username": "hr.reception"},
        {"password": "a-strong-password"},
        login_data(username="   "),
        login_data(password="   "),
        login_data(username=""),
        login_data(password=""),
        login_data(username="x" * 101),
        login_data(password="x" * 256),
        login_data(username=123),
        login_data(password=123),
    ],
)
def test_login_rejects_invalid_payloads(payload):
    with pytest.raises(ValidationError):
        StaffLoginRequest(**payload)


@pytest.mark.parametrize(
    "field",
    ["identity_type", "hr_role", "role", "user_id", "hr_user_id", "is_admin"],
)
def test_login_rejects_client_supplied_identity_or_role(field):
    with pytest.raises(ValidationError):
        StaffLoginRequest(**login_data(**{field: "HRManagement"}))


def test_login_password_is_masked_in_repr_and_dump():
    request = StaffLoginRequest(**login_data())
    assert "a-strong-password" not in repr(request)
    assert request.model_dump()["password"] == request.password
    assert "a-strong-password" not in str(request.model_dump())


def test_identity_type_values_are_exact():
    assert {member.value for member in StaffIdentityType} == {
        "HR",
        "TECHNICAL_SUPPORT",
    }


def test_hr_role_values_are_exact():
    assert {member.value for member in HRRole} == {
        "HR",
        "HRAdmin",
        "HRManagement",
    }


@pytest.mark.parametrize("role", ["HR", "HRAdmin", "HRManagement"])
def test_hr_identity_accepts_each_authoritative_role(role):
    identity = HRStaffIdentity(**hr_identity(hr_role=role))
    assert identity.hr_role.value == role
    assert identity.identity_type is StaffIdentityType.HR


@pytest.mark.parametrize(
    "reference",
    [
        "profile-images/42.png",
        "hr/avatars/sara.jpg",
        "https://storage.example.com/profile/42.png",
        "s3://okala-profiles/42.png",
        "a" * 500,
    ],
)
@pytest.mark.parametrize(
    ("factory", "model"),
    [
        (hr_identity, HRStaffIdentity),
        (technical_support_identity, TechnicalSupportStaffIdentity),
    ],
)
def test_profile_image_reference_accepts_storage_references_and_urls(factory, model, reference):
    identity = model.model_validate(factory(profile_image_reference=reference))
    assert identity.profile_image_reference == reference


@pytest.mark.parametrize(
    "reference",
    ["   ", "", "a" * 501],
)
@pytest.mark.parametrize(
    ("factory", "model"),
    [
        (hr_identity, HRStaffIdentity),
        (technical_support_identity, TechnicalSupportStaffIdentity),
    ],
)
def test_profile_image_reference_rejects_blank_or_oversized_values(factory, model, reference):
    with pytest.raises(ValidationError):
        model.model_validate(factory(profile_image_reference=reference))


def test_hr_identity_rejects_wrong_identity_type():
    with pytest.raises(ValidationError):
        HRStaffIdentity(**hr_identity(identity_type="TECHNICAL_SUPPORT"))


def test_technical_support_identity_rejects_wrong_identity_type():
    with pytest.raises(ValidationError):
        TechnicalSupportStaffIdentity(**technical_support_identity(identity_type="HR"))


def test_technical_support_identity_has_no_hr_role_field():
    identity = TechnicalSupportStaffIdentity(**technical_support_identity())
    assert "hr_role" not in type(identity).model_fields
    with pytest.raises(ValidationError):
        TechnicalSupportStaffIdentity(**technical_support_identity(hr_role="HR"))


def test_session_requires_positive_lifetime_and_valid_token_type():
    assert StaffSession(**session_data()).token_type is SessionTokenType.BEARER
    with pytest.raises(ValidationError):
        StaffSession(**session_data(expires_in_seconds=0))
    with pytest.raises(ValidationError):
        StaffSession(**session_data(token_type="jwt"))
    with pytest.raises(ValidationError):
        StaffSession(**session_data(session_token=""))


def test_session_token_is_an_opaque_string_in_the_response_body():
    session = StaffSession(**session_data())
    assert session.model_dump(mode="json")["session_token"] == "opaque-server-issued-handle"
    assert not session.session_token.startswith("ey")


def test_session_token_accepts_long_opaque_handles_but_rejects_oversized_values():
    assert StaffSession(**session_data(session_token="x" * 512)).session_token == "x" * 512
    with pytest.raises(ValidationError):
        StaffSession(**session_data(session_token="x" * 513))


def test_issued_at_accepts_timezone_aware_datetime_objects():
    aware = datetime(2026, 11, 28, 10, 0, tzinfo=timezone.utc)
    session = StaffSession(**session_data(issued_at=aware))
    assert session.issued_at.tzinfo is not None


def test_issued_at_rejects_naive_datetime_objects_and_strings():
    naive = datetime(2026, 11, 28, 10, 0)
    with pytest.raises(ValidationError, match="timezone-aware"):
        StaffSession(**session_data(issued_at=naive))
    with pytest.raises(ValidationError, match="timezone-aware"):
        StaffSession(**session_data(issued_at="2026-11-28T10:00:00"))


def test_hr_response_serialization_distinguishes_identity_without_secrets():
    response = StaffAuthenticationResponse(
        session=StaffSession(**session_data()),
        identity=HRStaffIdentity(**hr_identity(hr_role="HRManagement")),
    )
    payload = response.model_dump(mode="json")

    assert payload["identity"]["identity_type"] == "HR"
    assert payload["identity"]["hr_role"] == "HRManagement"
    assert payload["session"]["token_type"] == "bearer"
    assert payload["session"]["expires_in_seconds"] == 900
    assert payload["session"]["session_token"] == "opaque-server-issued-handle"
    assert datetime.fromisoformat(
        payload["session"]["issued_at"].replace("Z", "+00:00")
    ).tzinfo is not None

    serialized = str(payload).lower()
    for forbidden in ("password", "password_hash", "user_id", "role_id"):
        assert forbidden not in serialized
    assert "id" not in payload["identity"]
    assert "id" not in payload["session"]


def test_technical_support_response_serialization_has_no_hr_role():
    response = StaffAuthenticationResponse(
        session=StaffSession(**session_data()),
        identity=TechnicalSupportStaffIdentity(**technical_support_identity()),
    )
    payload = response.model_dump(mode="json")
    assert payload["identity"]["identity_type"] == "TECHNICAL_SUPPORT"
    assert "hr_role" not in payload["identity"]


@pytest.mark.parametrize(
    "payload",
    [
        {"session": session_data(), "identity": hr_identity(hr_role="NotARole")},
        {"session": session_data(), "identity": hr_identity(identity_type="UNKNOWN")},
        {
            "session": session_data(),
            "identity": hr_identity(user_id=42),
        },
        {
            "session": session_data(),
            "identity": hr_identity(),
            "extra": "not allowed",
        },
        {"session": session_data(), "identity": {}},
        {"session": {}, "identity": hr_identity()},
    ],
)
def test_response_rejects_invalid_or_untrusted_payloads(payload):
    with pytest.raises(ValidationError):
        StaffAuthenticationResponse(**payload)


def test_response_validates_identity_variants_by_discriminator():
    hr_response = StaffAuthenticationResponse(
        session=StaffSession(**session_data()),
        identity=hr_identity(hr_role="HRAdmin"),
    )
    support_response = StaffAuthenticationResponse(
        session=StaffSession(**session_data()),
        identity=technical_support_identity(),
    )
    assert hr_response.identity.identity_type is StaffIdentityType.HR
    assert isinstance(hr_response.identity, HRStaffIdentity)
    assert support_response.identity.identity_type is StaffIdentityType.TECHNICAL_SUPPORT
    assert isinstance(support_response.identity, TechnicalSupportStaffIdentity)


@pytest.mark.parametrize(
    "identity",
    [
        hr_identity(identity_type="TECHNICAL_SUPPORT"),
        technical_support_identity(identity_type="HR"),
        hr_identity(identity_type="UNKNOWN"),
        {"identity_type": "HR", "hr_role": "HR", "display_name": "x", "hr_user_id": 1},
    ],
)
def test_response_rejects_invalid_discriminator_values(identity):
    with pytest.raises(ValidationError):
        StaffAuthenticationResponse(
            session=StaffSession(**session_data()),
            identity=identity,
        )


def test_json_schema_exposes_identity_discriminator():
    schema = StaffAuthenticationResponse.model_json_schema()
    identity_schema = schema["properties"]["identity"]
    assert identity_schema["discriminator"]["propertyName"] == "identity_type"
    assert identity_schema["discriminator"]["mapping"] == {
        "HR": "#/$defs/HRStaffIdentity",
        "TECHNICAL_SUPPORT": "#/$defs/TechnicalSupportStaffIdentity",
    }


def test_response_rejects_password_and_internal_database_ids():
    with pytest.raises(ValidationError):
        StaffAuthenticationResponse(
            session=StaffSession(**session_data()),
            identity=hr_identity(id=42, password_hash="hash"),
        )


def test_request_and_response_models_are_importable_from_schemas_package():
    from app.schemas import (
        HRRole,
        StaffAuthenticationResponse,
        StaffIdentityType,
        StaffLoginRequest,
    )

    assert StaffLoginRequest(**login_data()).username == "hr.reception"
    assert HRRole.HR_ADMIN.value == "HRAdmin"
    assert StaffIdentityType.TECHNICAL_SUPPORT.value == "TECHNICAL_SUPPORT"
    assert StaffAuthenticationResponse is not None
