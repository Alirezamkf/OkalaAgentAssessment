"""Reusable exam template owned by an HR user."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base

if TYPE_CHECKING:
    from app.models.exam import Exam
    from app.models.exam_template_question import ExamTemplateQuestion
    from app.models.hr_user import HRUser


class ExamTemplate(Base):
    """A reusable exam definition that remains separate from actual exams."""

    __tablename__ = "exam_templates"
    __table_args__ = (
        CheckConstraint("length(name) >= 1", name="ck_exam_templates_name_not_empty"),
        Index("ix_exam_templates_created_by_hr_user_id", "created_by_hr_user_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_hr_user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("hr_users.id"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    creator: Mapped["HRUser"] = relationship(back_populates="created_exam_templates")
    questions: Mapped[list["ExamTemplateQuestion"]] = relationship(
        back_populates="exam_template",
        cascade="all, delete-orphan",
    )
    exams: Mapped[list["Exam"]] = relationship(back_populates="exam_template")
