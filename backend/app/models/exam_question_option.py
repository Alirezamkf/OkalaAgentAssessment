"""ORM model for an option copied onto an exam-owned question."""

from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Boolean, CheckConstraint, ForeignKey, Index, Integer, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base

if TYPE_CHECKING:
    from app.models.candidate_answer import CandidateAnswer
    from app.models.exam_question import ExamQuestion


class ExamQuestionOption(Base):
    """Stable, ordered option belonging exclusively to an exam question."""

    __tablename__ = "exam_question_options"
    __table_args__ = (
        CheckConstraint("position >= 1", name="ck_exam_question_options_position_positive"),
        UniqueConstraint("exam_question_id", "position", name="uq_exam_question_options_question_position"),
        UniqueConstraint("id", "exam_question_id", name="uq_exam_question_options_id_question"),
        Index(
            "uq_exam_question_options_one_correct",
            "exam_question_id",
            unique=True,
            postgresql_where=text("is_correct = true"),
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    exam_question_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("exam_questions.id"),
        nullable=False,
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)
    is_correct: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)

    exam_question: Mapped["ExamQuestion"] = relationship(back_populates="options")
    candidate_answers: Mapped[list["CandidateAnswer"]] = relationship(
        back_populates="selected_option",
        overlaps="candidate_answers,exam_question",
    )
