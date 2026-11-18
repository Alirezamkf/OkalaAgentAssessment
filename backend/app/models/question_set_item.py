"""ORM association between a question set and a reusable bank question."""

from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, Index, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base

if TYPE_CHECKING:
    from app.models.question import Question
    from app.models.question_set import QuestionSet


class QuestionSetItem(Base):
    """One question reference and optional score override in a question set."""

    __tablename__ = "question_set_items"
    __table_args__ = (
        UniqueConstraint("question_set_id", "question_id", name="uq_question_set_items_set_question"),
        CheckConstraint("score IS NULL OR score > 0", name="ck_question_set_items_score_positive"),
        Index("ix_question_set_items_question_set_id", "question_set_id"),
        Index("ix_question_set_items_question_id", "question_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    question_set_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("question_sets.id"),
        nullable=False,
    )
    question_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("questions.id"),
        nullable=False,
    )
    score: Mapped[int | None] = mapped_column(Integer, nullable=True)

    question_set: Mapped["QuestionSet"] = relationship(back_populates="items")
    question: Mapped["Question"] = relationship(back_populates="question_set_items")
