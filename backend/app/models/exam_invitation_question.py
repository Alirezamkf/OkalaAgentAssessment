"""ORM association between an exam invitation and an HR-selected question."""

from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, ForeignKeyConstraint, Index, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base

if TYPE_CHECKING:
    from app.models.exam_invitation import ExamInvitation
    from app.models.question import Question


class ExamInvitationQuestion(Base):
    """One question selected for one specific invitation.

    The association stores no question content, options, scores, or answer
    keys. The invitation and question exam IDs are linked by composite
    foreign keys so a question cannot cross exam boundaries.
    """

    __tablename__ = "exam_invitation_questions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["exam_invitation_id", "exam_id"],
            ["exam_invitations.id", "exam_invitations.exam_id"],
            name="fk_invitation_questions_invitation_exam",
        ),
        ForeignKeyConstraint(
            ["question_id", "exam_id"],
            ["questions.id", "questions.exam_id"],
            name="fk_invitation_questions_question_exam",
        ),
        UniqueConstraint(
            "exam_invitation_id",
            "question_id",
            name="uq_invitation_questions_invitation_question",
        ),
        Index("ix_invitation_questions_question_id", "question_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    exam_invitation_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    question_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    exam_id: Mapped[int] = mapped_column(BigInteger, nullable=False)

    invitation: Mapped["ExamInvitation"] = relationship(
        back_populates="selected_questions",
        overlaps="question",
    )
    question: Mapped["Question"] = relationship(
        back_populates="invitation_selections",
        overlaps="invitation",
    )
