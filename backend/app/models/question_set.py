"""ORM model for reusable collections of bank questions."""

from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base

if TYPE_CHECKING:
    from app.models.hr_user import HRUser
    from app.models.question_set_item import QuestionSetItem


class QuestionSet(Base):
    """Named collection of reusable questions owned by an HR user."""

    __tablename__ = "question_sets"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_hr_user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("hr_users.id"),
        nullable=False,
    )

    creator: Mapped["HRUser"] = relationship(back_populates="created_question_sets")
    items: Mapped[list["QuestionSetItem"]] = relationship(
        back_populates="question_set",
        cascade="all, delete-orphan",
    )
