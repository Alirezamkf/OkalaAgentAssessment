"""ORM model for exams and the base rules for their scheduling and status."""

from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, CheckConstraint, DateTime, Enum as SAEnum, ForeignKey, Index, Integer, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base

if TYPE_CHECKING:
    from app.models.assessment_retention_processing import AssessmentRetentionProcessing
    from app.models.assessment_attempt import AssessmentAttempt
    from app.models.exam_question import ExamQuestion
    from app.models.exam_invitation import ExamInvitation
    from app.models.exam_template import ExamTemplate
    from app.models.hr_user import HRUser


class ExamStatus(str, Enum):
    """Allowed states in the exam lifecycle."""

    CREATED = "Created"
    PUBLISHED = "Published"
    CANCELLED = "Cancelled"


class Exam(Base):
    """Exam created by an HR user.

    This model inherits from the shared ``Base`` so the exam table is
    registered in the same SQLAlchemy metadata. Exam status is independent
    of attempt status and HR decisions.
    """

    __tablename__ = "exams"
    __table_args__ = (
        UniqueConstraint("name", name="uq_exams_name"),
        CheckConstraint("length(trim(name)) >= 1", name="ck_exams_name_not_empty"),
        Index("ix_exams_exam_template_id", "exam_template_id"),
        CheckConstraint(
            "duration_minutes >= 20 AND duration_minutes <= 25",
            name="ck_exams_duration_minutes_range",
        ),
        CheckConstraint(
            "available_until > available_from",
            name="ck_exams_availability_order",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    # HR explicitly chooses this globally unique name; no backend default or suffix is generated.
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    exam_template_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("exam_templates.id"),
        nullable=True,
    )
    # The status is restricted to one of the three defined stages, and every exam starts at Created.
    status: Mapped[ExamStatus] = mapped_column(
        SAEnum(
            ExamStatus,
            name="exam_status",
            native_enum=False,
            values_callable=lambda enum_type: [member.value for member in enum_type],
        ),
        nullable=False,
        default=ExamStatus.CREATED,
        server_default=text("'Created'"),
    )
    # Exam duration is measured in minutes and restricted to the approved range of 20 to 25 minutes.
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=25)
    # Availability start and end times are stored with timezone information.
    available_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    available_until: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # The exam must reference the existing HR user who created it.
    created_by_hr_user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("hr_users.id"),
        nullable=False,
    )

    exam_template: Mapped["ExamTemplate | None"] = relationship(back_populates="exams")
    # The creator is exposed only from Exam; HRUser has no reverse Exam relationship.
    creator: Mapped["HRUser"] = relationship()
    exam_questions: Mapped[list["ExamQuestion"]] = relationship(
        back_populates="exam",
        cascade="all, delete-orphan",
    )
    invitations: Mapped[list["ExamInvitation"]] = relationship(back_populates="exam")
    attempts: Mapped[list["AssessmentAttempt"]] = relationship(
        back_populates="exam",
        overlaps="exam_invitation",
    )
    retention_processing: Mapped["AssessmentRetentionProcessing | None"] = relationship(
        back_populates="exam",
        uselist=False,
    )
