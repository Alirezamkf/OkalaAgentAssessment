"""ORM model for one candidate's participation in an invited exam."""

from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, DateTime, Enum as SAEnum, ForeignKey, ForeignKeyConstraint, Index, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base

if TYPE_CHECKING:
    from app.models.candidate import Candidate
    from app.models.exam import Exam
    from app.models.exam_invitation import ExamInvitation


class AttemptStatus(str, Enum):
    """Approved lifecycle states for an assessment attempt."""

    NOT_STARTED = "Not Started"
    IN_PROGRESS = "In Progress"
    SUBMITTED = "Submitted"
    TIMED_OUT = "Timed Out"
    INTERRUPTED = "Interrupted"
    CANCELLED = "Cancelled"


class AssessmentAttempt(Base):
    """Attempt tied to one candidate, exam, and invitation."""

    __tablename__ = "assessment_attempts"
    __table_args__ = (
        ForeignKeyConstraint(
            ["exam_invitation_id", "candidate_id", "exam_id"],
            ["exam_invitations.id", "exam_invitations.candidate_id", "exam_invitations.exam_id"],
            name="fk_attempt_invitation_identity",
        ),
        Index("ix_assessment_attempts_exam_id", "exam_id"),
        Index("ix_assessment_attempts_candidate_id", "candidate_id"),
        Index("ix_assessment_attempts_invitation_id", "exam_invitation_id", unique=True),
        Index("ix_assessment_attempts_status", "status"),
        UniqueConstraint("exam_invitation_id", name="uq_assessment_attempts_invitation_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    exam_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("exams.id"), nullable=False)
    candidate_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("candidates.id"), nullable=False)
    exam_invitation_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    status: Mapped[AttemptStatus] = mapped_column(
        SAEnum(AttemptStatus, name="attempt_status", native_enum=False),
        nullable=False,
        default=AttemptStatus.NOT_STARTED,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deadline_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    exam: Mapped["Exam"] = relationship(back_populates="attempts")
    candidate: Mapped["Candidate"] = relationship(back_populates="attempts")
    exam_invitation: Mapped["ExamInvitation"] = relationship(
        back_populates="attempt",
        uselist=False,
        overlaps="exam,candidate",
    )
