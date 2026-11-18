"""ORM model for a candidate's selected answer within an attempt."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, DateTime, ForeignKey, ForeignKeyConstraint, Index, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base

if TYPE_CHECKING:
    from app.models.assessment_attempt import AssessmentAttempt
    from app.models.exam_question import ExamQuestion
    from app.models.exam_question_option import ExamQuestionOption


class CandidateAnswer(Base):
    """One answer record for one exam-owned question in an attempt.

    Only the selected exam question option is stored. Correctness is owned
    by ExamQuestionOption and is not duplicated here.
    """

    __tablename__ = "candidate_answers"
    __table_args__ = (
        ForeignKeyConstraint(
            ["selected_option_id", "exam_question_id"],
            ["exam_question_options.id", "exam_question_options.exam_question_id"],
            name="fk_candidate_answers_selected_option_exam_question",
        ),
        UniqueConstraint("attempt_id", "exam_question_id", name="uq_candidate_answers_attempt_question"),
        Index("ix_candidate_answers_exam_question_id", "exam_question_id"),
        Index("ix_candidate_answers_selected_option_id", "selected_option_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    attempt_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("assessment_attempts.id"),
        nullable=False,
    )
    exam_question_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("exam_questions.id"),
        nullable=False,
    )
    selected_option_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    attempt: Mapped["AssessmentAttempt"] = relationship(back_populates="answers")
    exam_question: Mapped["ExamQuestion"] = relationship(
        back_populates="candidate_answers",
    )
    selected_option: Mapped["ExamQuestionOption | None"] = relationship(
        back_populates="candidate_answers",
        overlaps="exam_question",
    )
