"""ORM model for a globally identifiable assessment candidate."""

from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, CheckConstraint, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base

if TYPE_CHECKING:
    from app.models.exam_invitation import ExamInvitation


class Candidate(Base):
    """Candidate identity and contact details shared across examinations.

    A candidate is intentionally not tied directly to an exam. Future
    invitation records will connect this global identity to one or more exams.
    """

    __tablename__ = "candidates"
    __table_args__ = (
        CheckConstraint(
            "email IS NOT NULL OR phone IS NOT NULL",
            name="ck_candidates_contact_method",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)

    invitations: Mapped[list["ExamInvitation"]] = relationship(back_populates="candidate")
