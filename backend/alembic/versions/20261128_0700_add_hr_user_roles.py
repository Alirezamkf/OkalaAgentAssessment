"""Add authoritative HR role assignments without changing hr_users.

Revision ID: 20261128_0700
Revises: 20261120_0710
Create Date: 2026-11-28 07:00:00

One row per HR account is enforced by using hr_user_id as both the primary key
and the foreign key. No role is invented for existing accounts: accounts
without an assignment fail closed when their role is resolved.
"""

from alembic import op
import sqlalchemy as sa


revision = "20261128_0700"
down_revision = "20261120_0710"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "hr_user_roles",
        sa.Column("hr_user_id", sa.BigInteger(), autoincrement=False, nullable=False),
        sa.Column(
            "role",
            sa.Enum(
                "HR",
                "HRAdmin",
                "HRManagement",
                name="hr_role",
                native_enum=False,
                validate_strings=True,
                # The named CheckConstraint below is the single value check.
                create_constraint=False,
            ),
            nullable=False,
        ),
        sa.CheckConstraint(
            "role IN ('HR', 'HRAdmin', 'HRManagement')",
            name="ck_hr_user_roles_role_allowed",
        ),
        sa.ForeignKeyConstraint(
            ["hr_user_id"],
            ["hr_users.id"],
            name="fk_hr_user_roles_hr_user_id_hr_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("hr_user_id"),
    )


def downgrade() -> None:
    op.drop_table("hr_user_roles")
