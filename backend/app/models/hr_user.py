"""Human resources user model and the information needed to identify the user."""

from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base

if TYPE_CHECKING:
    from app.models.assessment_attempt import AssessmentAttempt


class HRUser(Base):
    """HR user who is authorized to use the system's human resources section.

    Inheritance from ``Base`` maps this model using the shared SQLAlchemy
    declarative convention and registers its table in ``Base.metadata``.
    """

    __tablename__ = "hr_users"

    # Unique numeric identifier generated automatically for each user.
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    # The username must be required and unique so that every account is identifiable.
    username: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    # Only the hash is stored so the raw password is not kept in the database.
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)

    hr_decided_attempts: Mapped[list["AssessmentAttempt"]] = relationship(
        back_populates="hr_decided_by",
        foreign_keys="AssessmentAttempt.hr_decided_by_id",
    )
