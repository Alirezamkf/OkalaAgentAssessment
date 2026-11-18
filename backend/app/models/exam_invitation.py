"""ORM model for secure invitations connecting candidates to exams."""

from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, CheckConstraint, DateTime, Enum as SAEnum, ForeignKey, Index, Integer, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base

if TYPE_CHECKING:
    from app.models.candidate_consent import CandidateConsent
    from app.models.assessment_attempt import AssessmentAttempt
    from app.models.exam_invitation_question import ExamInvitationQuestion
    from app.models.candidate import Candidate
    from app.models.exam import Exam


class InvitationStatus(str, Enum):
    """States in the invitation lifecycle, independent of exam status."""

    PENDING = "Pending"
    ACCEPTED = "Accepted"
    EXPIRED = "Expired"
    CANCELLED = "Cancelled"


class ExamInvitation(Base):
    """Invitation linking one candidate to one exam.

    The token hash is a SHA-256 hexadecimal digest; the raw token is never
    represented or persisted by this model. Separate rows for the same
    candidate and exam are intentionally allowed.
    """

    __tablename__ = "exam_invitations"
    __table_args__ = (
        Index("uq_exam_invitations_token_hash", "token_hash", unique=True),
        UniqueConstraint("id", "candidate_id", "exam_id", name="uq_invitation_identity"),
        UniqueConstraint("id", "exam_id", name="uq_invitation_id_exam"),
        CheckConstraint(
            "failed_identity_attempts >= 0",
            name="ck_exam_invitations_failed_identity_attempts_non_negative",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    candidate_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("candidates.id"), nullable=False)
    exam_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("exams.id"), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[InvitationStatus] = mapped_column(
        SAEnum(InvitationStatus, name="invitation_status", native_enum=False),
        nullable=False,
        default=InvitationStatus.PENDING,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    failed_identity_attempts: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
    )
    identity_locked_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    candidate: Mapped["Candidate"] = relationship(back_populates="invitations")
    exam: Mapped["Exam"] = relationship(back_populates="invitations")
    attempt: Mapped["AssessmentAttempt"] = relationship(
        back_populates="exam_invitation",
        uselist=False,
        overlaps="attempts,exam,candidate",
    )
    selected_questions: Mapped[list["ExamInvitationQuestion"]] = relationship(
        back_populates="invitation",
        overlaps="exam_question,invitation_selections",
    )
    consents: Mapped[list["CandidateConsent"]] = relationship(back_populates="exam_invitation")
