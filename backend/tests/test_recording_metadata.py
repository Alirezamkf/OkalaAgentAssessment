"""Focused tests for recording metadata lifecycle mapping."""

import pytest
from sqlalchemy import Enum as SAEnum

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
