"""Resolve an HR account's authoritative role from persisted data.

This module is the single backend boundary for reading an HR role. It never
accepts a role from a request body, query parameter, header, or client state:
the role is read from the persisted ``hr_user_roles`` row for the account.

Missing or invalid assignments fail closed. There is no default role and no
implicit ``HR`` fallback, so an account without a valid assignment cannot be
treated as authorized.

HR authentication (issue #82) and HR authorization/account management
(issue #245) must call this resolver instead of reading role data directly.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.hr_user import HRUser
from app.models.hr_user_role import HRRole, HRUserRole


class HRRoleResolutionError(Exception):
    """Base class for a role that cannot be authoritatively resolved."""


class HRRoleNotAssignedError(HRRoleResolutionError):
    """The HR account has no persisted role assignment."""


class HRRoleInvalidError(HRRoleResolutionError):
    """The persisted role assignment holds an unsupported role value."""


class HRUserNotFoundError(HRRoleResolutionError):
    """No HR account exists for the requested identifier."""


def resolve_hr_role(db: Session, hr_user_id: int) -> HRRole:
    """Return the persisted role for an HR account, or fail closed.

    Raises ``HRUserNotFoundError`` when the account does not exist,
    ``HRRoleNotAssignedError`` when it has no assignment, and
    ``HRRoleInvalidError`` when the stored value is not one of the three
    approved roles.
    """

    hr_user = db.get(HRUser, hr_user_id)
    if hr_user is None:
        raise HRUserNotFoundError("HR account does not exist")

    assignment = db.scalar(
        select(HRUserRole).where(HRUserRole.hr_user_id == hr_user_id)
    )
    if assignment is None:
        raise HRRoleNotAssignedError("HR account has no role assignment")

    try:
        return HRRole(assignment.role)
    except ValueError:
        # Never echo the stored value: it is untrusted data and may be junk.
        raise HRRoleInvalidError("HR account has an unsupported role value") from None


def resolve_hr_role_for_user(db: Session, hr_user: HRUser) -> HRRole:
    """Resolve the persisted role for an already-loaded HR account."""

    return resolve_hr_role(db, hr_user.id)


def assign_hr_role(db: Session, hr_user_id: int, role: HRRole) -> HRUserRole:
    """Persist the single authoritative role for an HR account.

    This is an internal, privileged backend operation. It must never be exposed
    as an unrestricted public endpoint, and promotion to HRManagement requires
    a separately approved administrative process (not implemented here). The
    role must be an ``HRRole`` member; client-supplied strings are rejected here
    so an unvalidated value can never reach the database.

    Transaction ownership stays with the caller: this function flushes but does
    not commit, so account creation plus role assignment can be atomic. Two
    concurrent attempts to assign a role to the same account can raise
    ``IntegrityError`` from the primary key; callers must handle that conflict.
    """

    if not isinstance(role, HRRole):
        raise HRRoleInvalidError("Role must be an approved HR role")

    hr_user = db.get(HRUser, hr_user_id)
    if hr_user is None:
        raise HRUserNotFoundError("HR account does not exist")

    assignment = db.get(HRUserRole, hr_user_id)
    if assignment is None:
        assignment = HRUserRole(hr_user_id=hr_user_id, role=role)
        db.add(assignment)
    else:
        assignment.role = role

    db.flush()
    return assignment
