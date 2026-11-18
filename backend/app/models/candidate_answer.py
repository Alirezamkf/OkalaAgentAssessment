"""ORM model for a candidate's selected answer within an attempt."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, DateTime, ForeignKey, ForeignKeyConstraint, Index, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base

if TYPE_CHECKING:
    from app.models.assessment_attempt import AssessmentAttempt
    from app.models.question import Question
    from app.models.question_option import QuestionOption


class CandidateAnswer(Base):
    """One answer record for one question in one assessment attempt.

    Only the selected option reference is stored. Correctness and scoring
    remain in the question-option model and future assessment services.
    """

    __tablename__ = "candidate_answers"
    __table_args__ = (
        ForeignKeyConstraint(
            ["selected_option_id", "question_id"],
            ["question_options.id", "question_options.question_id"],
            name="fk_candidate_answers_selected_option_question",
        ),
        UniqueConstraint("attempt_id", "question_id", name="uq_candidate_answers_attempt_question"),
        Index("ix_candidate_answers_question_id", "question_id"),
        Index("ix_candidate_answers_selected_option_id", "selected_option_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    attempt_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("assessment_attempts.id"),
        nullable=False,
    )
    question_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("questions.id"),
        nullable=False,
    )
    selected_option_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    attempt: Mapped["AssessmentAttempt"] = relationship(back_populates="answers")
    question: Mapped["Question"] = relationship(
        back_populates="candidate_answers",
        overlaps="selected_option",
    )
    selected_option: Mapped["QuestionOption | None"] = relationship(
        back_populates="candidate_answers",
        overlaps="question",
    )
