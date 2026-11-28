"""The approved HR application roles.

This is the single authoritative definition of the HR role value set. It is a
plain domain enum with no dependency on SQLAlchemy, Pydantic, FastAPI, or any
database model, so both the persistence layer and the API schemas can import
the same definition without creating a layering dependency.

The role values must remain exactly ``HR``, ``HRAdmin``, and ``HRManagement``.
Technical Support is a staff identity type, not an HR role, and is deliberately
not included here.
"""

from enum import Enum


class HRRole(str, Enum):
    """The three approved HR application roles."""

    HR = "HR"
    HR_ADMIN = "HRAdmin"
    HR_MANAGEMENT = "HRManagement"
