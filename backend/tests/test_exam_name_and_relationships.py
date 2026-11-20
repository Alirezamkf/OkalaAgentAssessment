"""Metadata and duplicate-name allocation checks for actual exams."""

from contextlib import contextmanager
from types import SimpleNamespace

from sqlalchemy.exc import IntegrityError

from app.models.exam import Exam
from app.models.hr_user import HRUser
from app.schemas.exam import ExamCreateResponse
from app.services.exam_name import (
    create_exam_with_unique_name,
    find_first_available_exam_name,
    is_exam_name_unique_violation,
    validate_exam_name,
)


class ScalarRows:
    def __init__(self, rows: list[str]) -> None:
        self.rows = rows

    def all(self) -> list[str]:
        return self.rows


class DummySession:
    def __init__(self, existing_names: list[str] | None = None) -> None:
        self.existing_names = existing_names or []

    def scalars(self, statement: object) -> ScalarRows:
        return ScalarRows(self.existing_names)


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


def test_unique_base_name_is_unchanged() -> None:
    assert find_first_available_exam_name(DummySession(), "20261120") == "20261120"


def test_backward_compatible_validator_returns_available_name() -> None:
    assert validate_exam_name(DummySession(["20261120"]), "20261120") == "20261120 (2)"


def test_duplicate_base_name_gets_second_version() -> None:
    assert find_first_available_exam_name(
        DummySession(["20261120"]), "20261120"
    ) == "20261120 (2)"


def test_existing_second_version_gets_third_version() -> None:
    assert find_first_available_exam_name(
        DummySession(["20261120", "20261120 (2)"]), "20261120"
    ) == "20261120 (3)"


def test_first_available_gap_is_selected() -> None:
    assert find_first_available_exam_name(
        DummySession(["20261120", "20261120 (2)", "20261120 (4)"]), "20261120"
    ) == "20261120 (3)"


def test_similar_names_do_not_conflict() -> None:
    assert find_first_available_exam_name(
        DummySession(["20261120-copy", "20261120", "20261120 (2) extra"]), "20261120"
    ) == "20261120 (2)"


def test_empty_exam_name_is_rejected() -> None:
    try:
        find_first_available_exam_name(DummySession(), "   ")
        raise AssertionError("Empty exam name was accepted")
    except ValueError:
        pass


def test_api_response_exposes_final_name() -> None:
    response = ExamCreateResponse(id=1, name="20261120 (3)")
    assert response.model_dump() == {"id": 1, "name": "20261120 (3)"}


class FakeDatabaseOrigin:
    def __init__(self, constraint_name: str = "uq_exams_name") -> None:
        self.pgcode = "23505"
        self.constraint_name = constraint_name

    def __str__(self) -> str:
        return f'violates unique constraint "{self.constraint_name}"'


class FakeRetrySession:
    def __init__(self, existing_names: list[str], conflicts_on_names: set[str] | None = None) -> None:
        self.existing_names = set(existing_names)
        self.conflicts_on_names = conflicts_on_names or set()
        self.pending_name: str | None = None
        self.flush_count = 0

    def scalars(self, statement: object) -> ScalarRows:
        return ScalarRows(list(self.existing_names))

    def add(self, exam: object) -> None:
        self.pending_name = exam.name

    @contextmanager
    def begin_nested(self):
        yield

    def flush(self) -> None:
        self.flush_count += 1
        if self.pending_name in self.conflicts_on_names:
            self.existing_names.add(self.pending_name)
            raise IntegrityError("insert", {}, FakeDatabaseOrigin())
        self.existing_names.add(self.pending_name)


def test_concurrent_unique_conflict_retries_to_next_free_name() -> None:
    db = FakeRetrySession(["20261120"], {"20261120 (2)"})
    exam = create_exam_with_unique_name(
        db,
        "20261120",
        lambda name: SimpleNamespace(name=name),
        max_retries=5,
    )
    assert exam.name == "20261120 (3)"
    assert db.flush_count == 2


def test_unique_violation_detection_accepts_only_exam_name_constraint() -> None:
    assert is_exam_name_unique_violation(
        IntegrityError("insert", {}, FakeDatabaseOrigin("uq_exams_name"))
    )
    assert not is_exam_name_unique_violation(
        IntegrityError("insert", {}, FakeDatabaseOrigin("uq_other_constraint"))
    )


def test_unrelated_database_error_is_not_retried() -> None:
    db = FakeRetrySession([], set())

    def conflicting_add(name: str) -> object:
        return SimpleNamespace(name=name)

    def raise_unrelated_error() -> None:
        raise IntegrityError("insert", {}, FakeDatabaseOrigin("uq_other_constraint"))

    db.flush = raise_unrelated_error

    try:
        create_exam_with_unique_name(
            db,
            "20261120",
            conflicting_add,
            max_retries=5,
        )
        raise AssertionError("Unrelated database error was retried as an exam-name conflict")
    except IntegrityError:
        pass
