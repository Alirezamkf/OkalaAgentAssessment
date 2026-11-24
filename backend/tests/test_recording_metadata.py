"""Focused tests for recording metadata lifecycle mapping."""

import pytest
from sqlalchemy import Enum as SAEnum, create_engine, event, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.assessment_attempt import AssessmentAttempt, AttemptStatus
from app.models.attempt_event import AttemptEvent, AttemptEventType
from app.models.recording_metadata import RecordingMetadata, RecordingStatus


VALUES = ["Pending", "Starting", "Recording", "Interrupted", "Failed", "Completed"]
TRANSITIONS = {
    RecordingStatus.PENDING: {RecordingStatus.STARTING},
    RecordingStatus.STARTING: {RecordingStatus.RECORDING, RecordingStatus.FAILED},
    RecordingStatus.RECORDING: {RecordingStatus.INTERRUPTED, RecordingStatus.COMPLETED, RecordingStatus.FAILED},
    RecordingStatus.INTERRUPTED: {RecordingStatus.RECORDING, RecordingStatus.COMPLETED, RecordingStatus.FAILED},
    RecordingStatus.FAILED: set(),
    RecordingStatus.COMPLETED: set(),
}


def test_recording_status_values_and_sqlalchemy_mapping_are_strict() -> None:
    column_type = RecordingMetadata.__table__.c.status.type
    assert list(RecordingStatus._value2member_map_) == VALUES
    assert isinstance(column_type, SAEnum)
    assert column_type.enums == VALUES
    assert column_type.validate_strings is True
    constraint = next(c for c in RecordingMetadata.__table__.constraints if c.name == "ck_recording_metadata_status_allowed")
    assert all(f"'{value}'" in str(constraint.sqltext) for value in VALUES)
    assert "'INITIALIZING'" not in str(constraint.sqltext)
    with pytest.raises(ValueError):
        RecordingStatus("Unknown")


@pytest.mark.parametrize("current,allowed", TRANSITIONS.items())
def test_all_allowed_recording_status_transitions(current: RecordingStatus, allowed: set[RecordingStatus]) -> None:
    for target in allowed:
        recording = RecordingMetadata(status=current)
        recording.transition_to(target)
        assert recording.status is target


@pytest.mark.parametrize(
    "current,target",
    [(current, target) for current, allowed in TRANSITIONS.items() for target in RecordingStatus if target not in allowed],
)
def test_all_invalid_recording_status_transitions_are_rejected(current: RecordingStatus, target: RecordingStatus) -> None:
    recording = RecordingMetadata(status=current)
    with pytest.raises(ValueError):
        recording.transition_to(target)
    assert recording.status is current


@pytest.mark.parametrize("value", ["Initializing", "Active", "Terminated", "unknown", "RECORDING"])
def test_unknown_recording_status_values_are_rejected(value: str) -> None:
    with pytest.raises(ValueError):
        RecordingStatus(value)
    with pytest.raises(LookupError):
        RecordingMetadata.__table__.c.status.type._object_value_for_elem(value)


def test_recording_model_relationship_and_event_contract_remain_intact() -> None:
    assert RecordingMetadata.attempt.property.mapper.class_ is AssessmentAttempt
    assert AssessmentAttempt.recordings.property.mapper.class_ is RecordingMetadata
    assert RecordingMetadata.__table__.c.attempt_id.foreign_keys
    assert any(c.name == "uq_recording_metadata_attempt_source" for c in RecordingMetadata.__table__.constraints)
    assert AttemptEventType.RECORDING_GAP.value == "RecordingGap"
    assert AttemptEvent.__table__.c.attempt_id.foreign_keys
    # AttemptStatus already has its own interruption state; recording interruption
    # events remain independent and this model introduces no attempt-status values.
    assert "Recording Interrupted" not in [status.value for status in AttemptStatus]


def create_recording_table(engine) -> None:
    """Create the ORM table with a minimal SQLite parent table for FK checks."""
    @event.listens_for(engine, "connect")
    def enable_sqlite_foreign_keys(dbapi_connection, _connection_record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    with engine.begin() as connection:
        connection.exec_driver_sql("CREATE TABLE assessment_attempts (id BIGINT PRIMARY KEY)")
        RecordingMetadata.__table__.create(connection)


def test_database_enforces_one_recording_per_source_and_attempt() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    create_recording_table(engine)
    with engine.begin() as connection:
        connection.exec_driver_sql("INSERT INTO assessment_attempts (id) VALUES (1)")
    with Session(engine) as session:
        session.add_all([
            RecordingMetadata(id=1, attempt_id=1, source="webcam", status=RecordingStatus.PENDING),
            RecordingMetadata(id=2, attempt_id=1, source="screen", status=RecordingStatus.PENDING),
        ])
        session.commit()
        for index, source in enumerate(("webcam", "screen"), start=3):
            session.add(RecordingMetadata(id=index, attempt_id=1, source=source, status=RecordingStatus.PENDING))
            with pytest.raises(IntegrityError):
                session.commit()
            session.rollback()
    engine.dispose()


@pytest.mark.parametrize("status", list(RecordingStatus))
def test_database_accepts_each_approved_recording_status(status: RecordingStatus) -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    create_recording_table(engine)
    with engine.begin() as connection:
        connection.exec_driver_sql("INSERT INTO assessment_attempts (id) VALUES (1)")
    with Session(engine) as session:
        session.add(RecordingMetadata(id=1, attempt_id=1, source="webcam", status=status))
        session.commit()
        assert session.execute(select(RecordingMetadata.status)).scalar_one() == status
    engine.dispose()


def test_database_rejects_unknown_recording_status() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    create_recording_table(engine)
    with engine.begin() as connection:
        connection.exec_driver_sql("INSERT INTO assessment_attempts (id) VALUES (1)")
    with engine.begin() as connection, pytest.raises(IntegrityError):
        connection.exec_driver_sql(
            "INSERT INTO recording_metadata (attempt_id, source, status) VALUES (1, 'webcam', 'Unknown')"
        )
    engine.dispose()


@pytest.mark.parametrize("source", ["webcam", "screen"])
def test_database_accepts_each_approved_recording_source(source: str) -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    create_recording_table(engine)
    with engine.begin() as connection:
        connection.exec_driver_sql("INSERT INTO assessment_attempts (id) VALUES (1)")
    with Session(engine) as session:
        session.add(RecordingMetadata(id=1, attempt_id=1, source=source, status=RecordingStatus.PENDING))
        session.commit()
    engine.dispose()


def test_database_rejects_unsupported_recording_source() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    create_recording_table(engine)
    with engine.begin() as connection:
        connection.exec_driver_sql("INSERT INTO assessment_attempts (id) VALUES (1)")
    with engine.begin() as connection, pytest.raises(IntegrityError):
        connection.exec_driver_sql(
            "INSERT INTO recording_metadata (attempt_id, source, status) VALUES (1, 'microphone', 'Pending')"
        )
    engine.dispose()


def test_database_rejects_recording_for_nonexistent_attempt() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    create_recording_table(engine)
    with engine.begin() as connection, pytest.raises(IntegrityError):
        connection.exec_driver_sql(
            "INSERT INTO recording_metadata (attempt_id, source, status) VALUES (404, 'webcam', 'Pending')"
        )
    engine.dispose()
