"""ORM association between an exam invitation and its exam-owned questions."""

from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, ForeignKeyConstraint, Index, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base

if TYPE_CHECKING:
    from app.models.exam_invitation import ExamInvitation
    from app.models.exam_question import ExamQuestion


class ExamInvitationQuestion(Base):
    """One exam-owned question selected for one specific invitation."""

    __tablename__ = "exam_invitation_questions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["exam_invitation_id", "exam_id"],
            ["exam_invitations.id", "exam_invitations.exam_id"],
            name="fk_invitation_questions_invitation_exam",
        ),
        ForeignKeyConstraint(
            ["exam_question_id", "exam_id"],
            ["exam_questions.id", "exam_questions.exam_id"],
            name="fk_invitation_questions_exam_question_exam",
        ),
        UniqueConstraint(
            "exam_invitation_id",
            "exam_question_id",
            name="uq_invitation_questions_invitation_question",
        ),
        UniqueConstraint(
            "exam_question_id",
            name="uq_invitation_questions_exam_question",
        ),
        Index("ix_invitation_questions_exam_question_id", "exam_question_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    exam_invitation_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    exam_question_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    exam_id: Mapped[int] = mapped_column(BigInteger, nullable=False)

    invitation: Mapped["ExamInvitation"] = relationship(
        back_populates="selected_questions",
        overlaps="exam_question,invitation_selections",
    )
    exam_question: Mapped["ExamQuestion"] = relationship(
        back_populates="invitation_selections",
        overlaps="invitation,selected_questions",
    )
