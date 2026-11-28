"""Authoritative HR role assignment, stored separately from hr_users.

The approved hr_users table has exactly seven columns and must not gain a
role column. One row in this table is the single effective role assignment for
one HR account: hr_user_id is both the primary key and a foreign key, so an
account cannot hold multiple conflicting roles.

Technical Support identities are deliberately not represented here. This table
is only for the three approved HR application roles.
"""

from sqlalchemy import BigInteger, CheckConstraint, Enum as SAEnum, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base
from app.domain.hr_roles import HRRole


class HRUserRole(Base):
    """One authoritative role assignment for one HR account."""

    __tablename__ = "hr_user_roles"
    __table_args__ = (
        CheckConstraint(
            "role IN ('HR', 'HRAdmin', 'HRManagement')",
            name="ck_hr_user_roles_role_allowed",
        ),
    )

    # Primary key and foreign key are the same column: at most one effective
    # role per HR account. Deleting the account removes its assignment.
    hr_user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("hr_users.id", ondelete="CASCADE"),
        primary_key=True,
        autoincrement=False,
    )
    role: Mapped[HRRole] = mapped_column(
        SAEnum(
            HRRole,
            name="hr_role",
            native_enum=False,
            validate_strings=True,
            # The single named CheckConstraint above enforces the value set.
            # Do not let SAEnum emit a second, differently named CHECK.
            create_constraint=False,
            values_callable=lambda enum_type: [member.value for member in enum_type],
        ),
        nullable=False,
    )
