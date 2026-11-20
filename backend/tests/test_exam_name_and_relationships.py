"""Metadata and duplicate-name checks for actual exams."""

from app.models.exam import Exam
from app.models.hr_user import HRUser
from app.services.exam_name import ExamNameConflictError, validate_exam_name


class DummySession:
    def __init__(self, existing: object = None) -> None:
        self.existing = existing

    def scalar(self, statement: object) -> object:
        return self.existing


def test_exam_name_is_required_globally_unique_and_nonempty() -> None:
    table = Exam.__table__
    assert table.c.name.nullable is False
    assert any(
        constraint.name == "uq_exams_name"
        for constraint in table.constraints
    )
    assert any(
        constraint.name == "ck_exams_name_not_empty"
        for constraint in table.constraints
    )


def test_exam_hr_relationship_is_bidirectional() -> None:
    exam_relationships = {relationship.key for relationship in Exam.__mapper__.relationships}
    hr_relationships = {relationship.key for relationship in HRUser.__mapper__.relationships}
    assert "creator" in exam_relationships
    assert "created_exams" in hr_relationships


def test_exam_name_validation_rejects_duplicate_without_renaming() -> None:
    try:
        validate_exam_name(DummySession(existing=object()), "20261120")
        raise AssertionError("Duplicate exam name was accepted")
    except ExamNameConflictError as error:
        assert "choose a different name" in str(error)


def test_exam_name_validation_requires_explicit_name() -> None:
    try:
        validate_exam_name(DummySession(), "   ")
        raise AssertionError("Empty exam name was accepted")
    except ValueError:
        pass


def test_exam_name_validation_preserves_hr_choice() -> None:
    assert validate_exam_name(DummySession(), "  20261120  ") == "20261120"
