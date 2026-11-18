"""ORM model for a reusable single-answer multiple-choice question."""

from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, CheckConstraint, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base

if TYPE_CHECKING:
    from app.models.question_option import QuestionOption
    from app.models.question_set_item import QuestionSetItem


class Question(Base):
    """Independent reusable bank question with a suggested default score.

    Question content and image references do not belong to a specific exam.
    Answer options are managed separately, and question-set membership is
    represented by QuestionSetItem associations.
    """

    __tablename__ = "questions"
    __table_args__ = (
        CheckConstraint("score > 0", name="ck_questions_score_positive"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    image_reference: Mapped[str | None] = mapped_column(String(500), nullable=True)

    options: Mapped[list["QuestionOption"]] = relationship(
        back_populates="question",
        cascade="all, delete-orphan",
    )
    question_set_items: Mapped[list["QuestionSetItem"]] = relationship(
        back_populates="question",
    )
