"""Exam-name normalization and concurrent-safe allocation helpers."""

from collections.abc import Callable
from typing import TypeVar

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.exam import Exam
from app.models.exam_question import ExamQuestion
from app.models.exam_question_option import ExamQuestionOption
from app.models.exam_template import ExamTemplate
from app.models.exam_template_question import ExamTemplateQuestion


ExamT = TypeVar("ExamT", bound=Exam)


class ExamNameConflictError(ValueError):
    """Raised when a database name conflict cannot be resolved safely."""


def normalize_exam_name(name: str) -> str:
    """Normalize whitespace while preserving the HR-selected base name."""

    normalized = " ".join(name.strip().split())
    if not normalized:
        raise ValueError("Exam name is required")
    if len(normalized) > 200:
        raise ValueError("Exam name must be 200 characters or fewer")
    return normalized


def find_first_available_exam_name(db: Session, base_name: str) -> str:
    """Find the exact first free name in the base, base (2), base (3) sequence."""

    base_name = normalize_exam_name(base_name)
    # Load only names that begin with the base name, then filter exact version names in Python.
    rows = db.scalars(
        select(Exam.name).where(Exam.name.startswith(base_name))
    ).all()
    existing = set(rows)

    if base_name not in existing:
        return base_name

    number = 2
    while f"{base_name} ({number})" in existing:
        number += 1
    return f"{base_name} ({number})"


def is_exam_name_unique_violation(error: IntegrityError) -> bool:
    """Retry only a UNIQUE violation on uq_exams_name or exams.name."""

    original = error.orig
    constraint_name = getattr(original, "constraint_name", None)
    if constraint_name is None:
        constraint_name = getattr(getattr(original, "diag", None), "constraint_name", None)

    if constraint_name == "uq_exams_name":
        return True

    sqlstate = getattr(original, "pgcode", None) or getattr(original, "sqlstate", None)
    message = str(original)

    if sqlstate == "23505":
        if constraint_name is not None:
            return constraint_name == "uq_exams_name"
        return "uq_exams_name" in message or "exams.name" in message

    return "UNIQUE constraint failed: exams.name" in message


def validate_exam_name(db: Session, name: str) -> str:
    """Backward-compatible name validator that now returns the first available final name."""

    return find_first_available_exam_name(db, name)


def allocate_exam_name(db: Session, name: str) -> str:
    """Public allocation helper for the HR-selected base exam name."""

    return find_first_available_exam_name(db, name)


def create_exam_with_unique_name(
    db: Session,
    base_name: str,
    exam_factory: Callable[[str], ExamT],
    max_retries: int = 5,
) -> ExamT:
    """Allocate and persist an exam name, retrying only database name UNIQUE conflicts."""

    base_name = normalize_exam_name(base_name)
    if max_retries < 1:
        raise ValueError("max_retries must be at least 1")

    for _ in range(max_retries):
        final_name = find_first_available_exam_name(db, base_name)
        exam = exam_factory(final_name)
        db.add(exam)

        try:
            # A nested transaction rolls back only this insert/savepoint on a race.
            with db.begin_nested():
                db.flush()
            return exam
        except IntegrityError as error:
            if not is_exam_name_unique_violation(error):
                raise

    raise ExamNameConflictError(
        f"Unable to allocate an available name for '{base_name}' after {max_retries} attempts"
    )


def create_exam_from_template(
    db: Session,
    *,
    name: str,
    duration_minutes: int,
    available_from,
    available_until,
    created_by_hr_user_id: int,
    template: ExamTemplate | int,
) -> Exam:
    """Create an exam and copy its template questions/options in one transaction."""

    template_id = template.id if isinstance(template, ExamTemplate) else template
    source_template = db.get(ExamTemplate, template_id)
    if source_template is None:
        raise ValueError("Exam template does not exist")

    def exam_factory(final_name: str) -> Exam:
        return Exam(
            name=final_name,
            duration_minutes=duration_minutes,
            available_from=available_from,
            available_until=available_until,
            created_by_hr_user_id=created_by_hr_user_id,
            exam_template_id=template_id,
        )

    with db.begin_nested():
        exam = create_exam_with_unique_name(db, name, exam_factory)

        source_questions = db.scalars(
            select(ExamTemplateQuestion)
            .where(ExamTemplateQuestion.exam_template_id == template_id)
            .order_by(ExamTemplateQuestion.position)
        ).all()

        for source_question in source_questions:
            copied_question = ExamQuestion(
                exam_id=exam.id,
                text=source_question.question_text,
                score=source_question.score,
                image_reference=source_question.image_reference,
            )
            db.add(copied_question)
            db.flush()

            for source_option in sorted(source_question.options, key=lambda option: option.position):
                db.add(ExamQuestionOption(
                    exam_question_id=copied_question.id,
                    text=source_option.option_text,
                    position=source_option.position,
                    is_correct=source_option.is_correct,
                ))

        db.flush()

    return exam
