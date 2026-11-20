"""ORM model for one candidate's participation in an invited exam."""

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, CheckConstraint, DateTime, Enum as SAEnum, ForeignKey, ForeignKeyConstraint, Index, Integer, Numeric, UniqueConstraint, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base

if TYPE_CHECKING:
    from app.models.attempt_event import AttemptEvent
    from app.models.attempt_question_order import AttemptQuestionOrder
    from app.models.candidate_answer import CandidateAnswer
    from app.models.candidate import Candidate
    from app.models.exam import Exam
    from app.models.exam_invitation import ExamInvitation
    from app.models.recording_metadata import RecordingMetadata
    from app.models.hr_user import HRUser


class AttemptStatus(str, Enum):
    """Approved lifecycle states for an assessment attempt."""

    NOT_STARTED = "Not Started"
    IN_PROGRESS = "In Progress"
    SUBMITTED = "Submitted"
    TIMED_OUT = "Timed Out"
    INTERRUPTED = "Interrupted"
    CANCELLED = "Cancelled"


class HRDecision(str, Enum):
    """Latest decision values available to an HR administrator."""

    UNSET = "Unset"
    ACCEPTED = "Accepted"
    REJECTED = "Rejected"
    NEEDS_REVIEW = "Needs Review"


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
        UniqueConstraint("id", "exam_invitation_id", name="uq_assessment_attempts_id_invitation"),
        CheckConstraint(
            "current_question_position IS NULL OR current_question_position >= 1",
            name="ck_assessment_attempts_current_position_positive",
        ),
        CheckConstraint(
            "(hr_decision = 'Unset' AND hr_decided_by_id IS NULL AND hr_decision_updated_at IS NULL) "
            "OR (hr_decision <> 'Unset' AND hr_decided_by_id IS NOT NULL AND hr_decision_updated_at IS NOT NULL)",
            name="ck_assessment_attempts_hr_decision_consistency",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    exam_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("exams.id"), nullable=False)
    candidate_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("candidates.id"), nullable=False)
    exam_invitation_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    status: Mapped[AttemptStatus] = mapped_column(
        SAEnum(
            AttemptStatus,
            name="attempt_status",
            native_enum=False,
            values_callable=lambda enum_type: [member.value for member in enum_type],
        ),
        nullable=False,
        default=AttemptStatus.NOT_STARTED,
        server_default=text("'Not Started'"),
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deadline_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    current_question_position: Mapped[int | None] = mapped_column(Integer, nullable=True)
    official_score: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    max_score: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    hr_decision: Mapped[HRDecision] = mapped_column(
        SAEnum(
            HRDecision,
            name="hr_decision",
            native_enum=False,
            values_callable=lambda enum_type: [member.value for member in enum_type],
        ),
        nullable=False,
        default=HRDecision.UNSET,
        server_default=text("'Unset'"),
    )
    hr_decided_by_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("hr_users.id"), nullable=True)
    hr_decision_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    exam: Mapped["Exam"] = relationship(back_populates="attempts")
    candidate: Mapped["Candidate"] = relationship(back_populates="attempts")
    exam_invitation: Mapped["ExamInvitation"] = relationship(
        back_populates="attempt",
        uselist=False,
        overlaps="exam,candidate",
    )
    answers: Mapped[list["CandidateAnswer"]] = relationship(back_populates="attempt")
    events: Mapped[list["AttemptEvent"]] = relationship(back_populates="attempt")
    recordings: Mapped[list["RecordingMetadata"]] = relationship(back_populates="attempt")
    question_order: Mapped[list["AttemptQuestionOrder"]] = relationship(back_populates="attempt")
    hr_decided_by: Mapped["HRUser | None"] = relationship(
        back_populates="hr_decided_attempts",
        foreign_keys=[hr_decided_by_id],
    )
