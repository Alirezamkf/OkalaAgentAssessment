"""Shared staff login and authentication response contracts (Issue #81).

HR and Technical Support use the same username/password login experience. The
client sends only credentials. The backend resolves the staff identity type and,
for HR identities, the authoritative HR role from trusted persisted account
data, then returns a server-built response.

Session design
--------------
This module deliberately defines an opaque, backend-managed session handle
instead of a JWT or any client-readable identity token:

* ``session_token`` is an opaque string issued by the backend. It carries no
  client-readable claims, so the client cannot choose or edit an identity type
  or role. The backend maps the handle to a server-side session record and
  decides its lifetime, rotation, and revocation.
* ``token_type`` is fixed to ``"bearer"``. It tells the client how to send the
  handle in the ``Authorization`` header; it is not a claim.
* ``expires_in_seconds`` is a positive lifetime hint for the client. The backend
  remains the authority on expiry and may end the session sooner.

This contract does not generate, validate, store, or revoke tokens and does not
implement a login endpoint. Those belong to the authentication implementation
issue. The response model is strict, so a client cannot supply identity or role
fields and have them echoed back as authoritative data.

The HR role is a separate typed value and is not a column on ``HRUser``. The
authentication implementation must resolve it from trusted persisted account
data (for example a separate HR role assignment store), never from the login
request or from the seven-column ``HRUser`` table. ``HRRole`` is imported from
``app.domain.hr_roles`` so the API contract and the persistence layer use the
same enum definition; it is re-exported here for existing callers.
"""

from datetime import datetime
from enum import Enum
from typing import Annotated, Literal

from pydantic import Field, SecretStr, field_validator

from app.domain.hr_roles import HRRole
from app.schemas.base import StrictModel


def _validate_profile_reference(value: str | None) -> str | None:
    """Keep profile_image_reference a plain reference string, not a URL.

    The HRUser column is ``String(500)`` and other image_reference columns use
    the same type, so a storage key, relative path, or URL are all valid. Only
    an empty/whitespace-only reference is rejected as not a usable reference.
    """

    if value is None:
        return None
    if not value.strip():
        raise ValueError("Profile image reference must not be blank")
    return value


class StaffIdentityType(str, Enum):
    """The two staff identity kinds that share the login experience."""

    HR = "HR"
    TECHNICAL_SUPPORT = "TECHNICAL_SUPPORT"


class StaffLoginContext(str, Enum):
    """Which staff portal the login form was submitted from.

    This is a routing hint, NOT an identity type or a role. The backend must
    never treat it as proof of authorization: it must resolve the account's
    identity type and role from trusted persisted records and reject accounts
    not permitted to use the requested context.

    * ``HR_PORTAL``: the first-page HR Login button. Permits HR, HRAdmin,
      HRManagement, and Technical Support accounts.
    * ``HR_MANAGEMENT_PORTAL``: the HR Management button. Permits only accounts
      whose trusted backend role is HRManagement; HRAdmin is not sufficient.

    Both contexts use the same username/password form and the same backend
    authentication mechanism. The context only selects which account set is
    allowed; it never grants access by itself.
    """

    HR_PORTAL = "HR_PORTAL"
    HR_MANAGEMENT_PORTAL = "HR_MANAGEMENT_PORTAL"


class StaffLoginRequest(StrictModel):
    """Shared HR / Technical Support username and password login request.

    ``password`` uses ``SecretStr`` so it is masked in repr and serialization.
    ``login_context`` records which portal button was used; it is not an
    identity type or role and is never trusted as authorization. Identity type
    and role are intentionally absent: the client never selects them. Unknown
    fields are rejected by ``StrictModel``.
    """

    username: str = Field(min_length=1, max_length=100)
    password: SecretStr = Field(min_length=1, max_length=255)
    login_context: StaffLoginContext

    @field_validator("username")
    @classmethod
    def username_must_not_be_blank(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Username must not be blank")
        return normalized

    @field_validator("password")
    @classmethod
    def password_must_not_be_blank(cls, value: SecretStr) -> SecretStr:
        if not value.get_secret_value().strip():
            raise ValueError("Password must not be blank")
        return value


class SessionTokenType(str, Enum):
    """How the client presents the opaque session handle."""

    BEARER = "bearer"


class StaffSession(StrictModel):
    """Opaque backend-managed session details returned after login."""

    # An opaque handle, not a client-readable credential such as a JWT. It is a
    # plain str because FastAPI must serialize it into the response body; the
    # login implementation must never log it or include it in error messages.
    # The upper bound only prevents oversized handles; it does not assume a
    # particular token-generation algorithm.
    session_token: str = Field(min_length=1, max_length=512)
    token_type: SessionTokenType
    expires_in_seconds: int = Field(gt=0)
    issued_at: datetime

    @field_validator("issued_at")
    @classmethod
    def issued_at_must_be_timezone_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("issued_at must be timezone-aware")
        return value


class HRStaffIdentity(StrictModel):
    """Backend-resolved HR identity and its authoritative HR role."""

    identity_type: Literal[StaffIdentityType.HR]
    hr_role: HRRole
    display_name: str = Field(min_length=1, max_length=255)
    profile_image_reference: Annotated[
        str | None,
        Field(max_length=500),
    ] = None

    @field_validator("profile_image_reference")
    @classmethod
    def validate_profile_image_reference(cls, value: str | None) -> str | None:
        return _validate_profile_reference(value)


class TechnicalSupportStaffIdentity(StrictModel):
    """Backend-resolved Technical Support identity.

    Technical Support is separate from the HR role system, so this identity
    carries no HR role. Restricted permissions are enforced later by the
    authorization implementation, not by a client-supplied role field.
    """

    identity_type: Literal[StaffIdentityType.TECHNICAL_SUPPORT]
    display_name: str = Field(min_length=1, max_length=255)
    profile_image_reference: Annotated[
        str | None,
        Field(max_length=500),
    ] = None

    @field_validator("profile_image_reference")
    @classmethod
    def validate_profile_image_reference(cls, value: str | None) -> str | None:
        return _validate_profile_reference(value)


class StaffAuthenticationResponse(StrictModel):
    """Safe client-facing result of a successful staff login.

    The backend constructs this model from trusted persisted account data. It
    contains no password, password hash, database ID, or client-supplied
    identity/role. ``identity`` is a discriminated union keyed by
    ``identity_type`` so the client can distinguish HR from Technical Support
    without ever choosing the identity itself.
    """

    session: StaffSession
    identity: Annotated[
        HRStaffIdentity | TechnicalSupportStaffIdentity,
        Field(discriminator="identity_type"),
    ]
