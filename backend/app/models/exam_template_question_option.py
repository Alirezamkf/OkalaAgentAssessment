"""Ordered answer options belonging to a template question."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, Text, UniqueConstraint, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base

if TYPE_CHECKING:
    from app.models.exam_template_question import ExamTemplateQuestion


class ExamTemplateQuestionOption(Base):
    """A template-owned option that is copied with its parent question."""

    __tablename__ = "exam_template_question_options"
    __table_args__ = (
        CheckConstraint("position >= 1", name="ck_exam_template_question_options_position_positive"),
        UniqueConstraint(
            "exam_template_question_id",
            "position",
            name="uq_exam_template_question_options_question_position",
        ),
        Index(
            "uq_exam_template_question_options_one_correct",
            "exam_template_question_id",
            unique=True,
            postgresql_where=text("is_correct = true"),
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    exam_template_question_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("exam_template_questions.id", ondelete="CASCADE"),
        nullable=False,
    )
    option_text: Mapped[str] = mapped_column(Text, nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    is_correct: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
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

    exam_template_question: Mapped["ExamTemplateQuestion"] = relationship(back_populates="options")
