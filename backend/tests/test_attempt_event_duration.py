"""Tests for AttemptEvent duration metadata and contracts."""

from datetime import datetime, timezone

from pydantic import ValidationError
from sqlalchemy import create_engine, text

from app.models.attempt_event import AttemptEvent, AttemptEventType
from app.schemas.attempt_event import AttemptEventCreate, AttemptEventResponse


def create_event_table(engine: object) -> None:
    with engine.begin() as connection:
        connection.exec_driver_sql(
            "CREATE TABLE attempt_events_test ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "event_type VARCHAR(100) NOT NULL, "
            "duration_seconds INTEGER NULL, "
            "event_metadata TEXT NOT NULL, "
            "CONSTRAINT ck_attempt_events_duration_seconds_non_negative "
            "CHECK (duration_seconds IS NULL OR duration_seconds >= 0)"
            ")"
        )


def test_positive_duration_can_be_saved() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    create_event_table(engine)
    with engine.begin() as connection:
        connection.execute(text(
            "INSERT INTO attempt_events_test "
            "(event_type, duration_seconds, event_metadata) VALUES (:type, :duration, :metadata)"
        ), {"type": "RecordingGap", "duration": 15, "metadata": "{}"})
        assert connection.execute(text(
            "SELECT duration_seconds FROM attempt_events_test"
        )).scalar_one() == 15
    engine.dispose()


def test_zero_duration_can_be_saved() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    create_event_table(engine)
    with engine.begin() as connection:
        connection.execute(text(
            "INSERT INTO attempt_events_test "
            "(event_type, duration_seconds, event_metadata) VALUES (:type, :duration, :metadata)"
        ), {"type": "Idle", "duration": 0, "metadata": "{}"})
        assert connection.execute(text(
            "SELECT duration_seconds FROM attempt_events_test"
        )).scalar_one() == 0
    engine.dispose()


def test_null_duration_can_be_saved() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    create_event_table(engine)
    with engine.begin() as connection:
        connection.execute(text(
            "INSERT INTO attempt_events_test "
            "(event_type, duration_seconds, event_metadata) VALUES (:type, :duration, :metadata)"
        ), {"type": "TabHidden", "duration": None, "metadata": "{}"})
        assert connection.execute(text(
            "SELECT duration_seconds FROM attempt_events_test"
        )).scalar_one() is None
    engine.dispose()


def test_negative_duration_is_rejected_by_database_constraint() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    create_event_table(engine)
    from sqlalchemy.exc import IntegrityError

    try:
        with engine.begin() as connection:
            connection.execute(text(
                "INSERT INTO attempt_events_test "
                "(event_type, duration_seconds, event_metadata) VALUES (:type, :duration, :metadata)"
            ), {"type": "RecordingGap", "duration": -1, "metadata": "{}"})
        raise AssertionError("Negative duration was accepted")
    except IntegrityError:
        pass
    finally:
        engine.dispose()


def test_existing_event_types_and_metadata_behavior_remain_unchanged() -> None:
    assert AttemptEventType.RECORDING_GAP.value == "RecordingGap"
    assert AttemptEventType.TAB_HIDDEN.value == "TabHidden"
    assert AttemptEvent.__table__.c.event_metadata.nullable is False
    assert AttemptEvent.__table__.c.occurred_at.nullable is False


def test_duration_column_and_check_constraint_are_defined() -> None:
    table = AttemptEvent.__table__
    assert table.c.duration_seconds.nullable is True
    assert any(
        constraint.name == "ck_attempt_events_duration_seconds_non_negative"
        for constraint in table.constraints
    )


def test_api_schemas_expose_optional_duration() -> None:
    create = AttemptEventCreate(
        event_type=AttemptEventType.RECORDING_GAP,
        duration_seconds=12,
        event_metadata={"source": "test"},
    )
    assert create.duration_seconds == 12

    null_create = AttemptEventCreate(event_type=AttemptEventType.RECORDING_GAP)
    assert null_create.duration_seconds is None

    try:
        AttemptEventCreate(event_type=AttemptEventType.RECORDING_GAP, duration_seconds=-1)
        raise AssertionError("Negative API duration was accepted")
    except ValidationError:
        pass

    response = AttemptEventResponse(
        id=1,
        attempt_id=2,
        event_type=AttemptEventType.RECORDING_GAP,
        occurred_at=datetime.now(timezone.utc),
        duration_seconds=12,
        event_metadata={"source": "test"},
    )
    assert response.duration_seconds == 12
