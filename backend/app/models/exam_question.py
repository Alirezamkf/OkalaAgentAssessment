"""ORM model for an independent copy of a question inside an exam."""

from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base

if TYPE_CHECKING:
    from app.models.attempt_question_order import AttemptQuestionOrder
    from app.models.candidate_answer import CandidateAnswer
    from app.models.exam import Exam
    from app.models.exam_invitation_question import ExamInvitationQuestion
    from app.models.exam_question_option import ExamQuestionOption


class ExamQuestion(Base):
    """Exam-owned question content that remains independent of the bank."""

    __tablename__ = "exam_questions"
    __table_args__ = (
        CheckConstraint("score > 0", name="ck_exam_questions_score_positive"),
        UniqueConstraint("id", "exam_id", name="uq_exam_questions_id_exam"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    exam_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("exams.id"),
        nullable=False,
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    image_reference: Mapped[str | None] = mapped_column(String(500), nullable=True)

    exam: Mapped["Exam"] = relationship(back_populates="exam_questions")
    options: Mapped[list["ExamQuestionOption"]] = relationship(
        back_populates="exam_question",
        cascade="all, delete-orphan",
    )
    invitation_selections: Mapped[list["ExamInvitationQuestion"]] = relationship(
        back_populates="exam_question",
    )
    attempt_question_orders: Mapped[list["AttemptQuestionOrder"]] = relationship(
        back_populates="exam_question",
    )
    candidate_answers: Mapped[list["CandidateAnswer"]] = relationship(
        back_populates="exam_question",
        overlaps="selected_option",
    )
