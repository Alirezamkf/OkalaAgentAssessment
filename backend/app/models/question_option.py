"""ORM model for a selectable answer option belonging to a question."""

from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Boolean, ForeignKey, Index, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base

if TYPE_CHECKING:
    from app.models.question import Question


class QuestionOption(Base):
    """Stable, database-identified option for a multiple-choice question."""

    __tablename__ = "question_options"
    __table_args__ = (
        Index(
            "uq_question_options_one_correct",
            "question_id",
            unique=True,
            postgresql_where=text("is_correct = true"),
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    question_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("questions.id"),
        nullable=False,
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)
    is_correct: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    question: Mapped["Question"] = relationship(back_populates="options")
