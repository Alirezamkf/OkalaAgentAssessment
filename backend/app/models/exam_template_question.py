"""Ordered questions belonging to an exam template."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base

if TYPE_CHECKING:
    from app.models.exam_template import ExamTemplate
    from app.models.exam_template_question_option import ExamTemplateQuestionOption


class ExamTemplateQuestion(Base):
    """A template-owned question that is copied only when an exam is created."""

    __tablename__ = "exam_template_questions"
    __table_args__ = (
        CheckConstraint("position >= 1", name="ck_exam_template_questions_position_positive"),
        CheckConstraint("score > 0", name="ck_exam_template_questions_score_positive"),
        UniqueConstraint("exam_template_id", "position", name="uq_exam_template_questions_template_position"),
        Index("ix_exam_template_questions_exam_template_id", "exam_template_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    exam_template_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("exam_templates.id", ondelete="CASCADE"),
        nullable=False,
    )
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    image_reference: Mapped[str | None] = mapped_column(String(500), nullable=True)
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

    exam_template: Mapped["ExamTemplate"] = relationship(back_populates="questions")
    options: Mapped[list["ExamTemplateQuestionOption"]] = relationship(
        back_populates="exam_template_question",
        cascade="all, delete-orphan",
    )
