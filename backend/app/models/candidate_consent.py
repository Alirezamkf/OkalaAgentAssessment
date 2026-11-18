"""ORM model for positive recording consent recorded by an invitation."""

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base

if TYPE_CHECKING:
    from app.models.exam_invitation import ExamInvitation


class CandidateConsent(Base):
    """Positive consent acceptance for exactly one exam invitation."""

    __tablename__ = "candidate_consents"
    __table_args__ = (
        UniqueConstraint(
            "exam_invitation_id",
            name="uq_candidate_consents_exam_invitation_id",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    exam_invitation_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("exam_invitations.id"),
        nullable=False,
    )
    accepted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    exam_invitation: Mapped["ExamInvitation"] = relationship(
        back_populates="consent",
    )
