"""ORM model for the persisted presentation order of attempt questions."""

from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, ForeignKeyConstraint, Index, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base

if TYPE_CHECKING:
    from app.models.assessment_attempt import AssessmentAttempt
    from app.models.question import Question


class AttemptQuestionOrder(Base):
    """One HR-selected question assigned to a stable position in an attempt."""

    __tablename__ = "attempt_question_orders"
    __table_args__ = (
        ForeignKeyConstraint(
            ["attempt_id", "exam_invitation_id"],
            ["assessment_attempts.id", "assessment_attempts.exam_invitation_id"],
            name="fk_attempt_question_orders_attempt_invitation",
        ),
        ForeignKeyConstraint(
            ["exam_invitation_id", "question_id"],
            ["exam_invitation_questions.exam_invitation_id", "exam_invitation_questions.question_id"],
            name="fk_attempt_question_orders_selected_question",
        ),
        CheckConstraint("position >= 1", name="ck_attempt_question_orders_position_positive"),
        UniqueConstraint("attempt_id", "position", name="uq_attempt_question_orders_attempt_position"),
        UniqueConstraint("attempt_id", "question_id", name="uq_attempt_question_orders_attempt_question"),
        Index("ix_attempt_question_orders_question_id", "question_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    attempt_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    exam_invitation_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    question_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("questions.id"),
        nullable=False,
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)

    attempt: Mapped["AssessmentAttempt"] = relationship(back_populates="question_order")
    question: Mapped["Question"] = relationship(back_populates="attempt_question_orders")
