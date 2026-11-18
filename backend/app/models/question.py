"""ORM model for a single-answer multiple-choice question."""

from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base

if TYPE_CHECKING:
    from app.models.candidate_answer import CandidateAnswer
    from app.models.exam_invitation_question import ExamInvitationQuestion
    from app.models.exam import Exam
    from app.models.question_option import QuestionOption


class Question(Base):
    """Question belonging to exactly one exam.

    The model stores question content and an optional external image
    reference; image bytes are intentionally kept outside PostgreSQL.
    Answer options are managed by a separate model and are not represented
    here.
    """

    __tablename__ = "questions"
    __table_args__ = (
        CheckConstraint("score > 0", name="ck_questions_score_positive"),
        UniqueConstraint("id", "exam_id", name="uq_questions_id_exam"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    exam_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("exams.id"),
        nullable=False,
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    exam: Mapped["Exam"] = relationship(back_populates="questions")
    options: Mapped[list["QuestionOption"]] = relationship(back_populates="question")
    candidate_answers: Mapped[list["CandidateAnswer"]] = relationship(
        back_populates="question",
        overlaps="selected_option",
    )
    invitation_selections: Mapped[list["ExamInvitationQuestion"]] = relationship(
        back_populates="question",
        overlaps="invitation,selected_questions",
    )
