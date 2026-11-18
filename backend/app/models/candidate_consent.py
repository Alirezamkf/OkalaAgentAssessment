"""ORM model for a candidate's recording-consent decision."""

from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, CheckConstraint, DateTime, Enum as SAEnum, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base

if TYPE_CHECKING:
    from app.models.exam_invitation import ExamInvitation


class ConsentDecision(str, Enum):
    """Allowed candidate consent decisions."""

    ACCEPTED = "Accepted"
    REJECTED = "Rejected"


class CandidateConsent(Base):
    """Consent decision recorded for an invitation before an attempt exists.

    Multiple records per invitation are allowed so a future submission flow
    can preserve decision history and consent-version changes.
    """

    __tablename__ = "candidate_consents"
    __table_args__ = (
        CheckConstraint(
            "(decision = 'Accepted' AND accepted_at IS NOT NULL) "
            "OR (decision = 'Rejected' AND accepted_at IS NULL)",
            name="ck_candidate_consents_decision_timestamp",
        ),
        Index("ix_candidate_consents_invitation_id", "exam_invitation_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    exam_invitation_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("exam_invitations.id"),
        nullable=False,
    )
    decision: Mapped[ConsentDecision] = mapped_column(
        SAEnum(ConsentDecision, name="consent_decision", native_enum=False),
        nullable=False,
    )
    consent_version: Mapped[str] = mapped_column(String(100), nullable=False)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    exam_invitation: Mapped["ExamInvitation"] = relationship(back_populates="consents")
