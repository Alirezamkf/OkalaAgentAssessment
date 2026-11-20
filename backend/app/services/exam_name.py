"""Exam-name validation helpers."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.exam import Exam


class ExamNameConflictError(ValueError):
    """Raised when an explicitly selected exam name is already in use."""


def validate_exam_name(db: Session, name: str) -> str:
    """Require a meaningful globally unique name selected by the HR user."""

    normalized = " ".join(name.strip().split())
    if not normalized:
        raise ValueError("Exam name is required")

    existing = db.scalar(select(Exam).where(Exam.name == normalized))
    if existing is not None:
        raise ExamNameConflictError(
            f"An exam with the name '{normalized}' already exists; choose a different name"
        )
    return normalized
