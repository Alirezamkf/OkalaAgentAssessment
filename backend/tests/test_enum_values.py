"""Static tests for SQLAlchemy enum database values and constraints."""

from app.models.assessment_attempt import AttemptStatus, HRDecision
from app.models.assessment_attempt import AssessmentAttempt
from app.models.attempt_event import AttemptEvent, AttemptEventType
from app.models.exam import Exam, ExamStatus
from app.models.exam_invitation import ExamInvitation, InvitationStatus


def test_exam_status_uses_values_not_names() -> None:
    expected = ["Created", "Published", "Cancelled"]
    assert ExamStatus._value2member_map_.keys() == set(expected)
    assert Exam.__table__.c.status.type.enums == expected
    assert ExamStatus.CREATED.value == "Created"
    assert ExamStatus.CREATED.name == "CREATED"


def test_invitation_status_uses_values_not_names() -> None:
    expected = ["Pending", "Accepted", "Expired", "Cancelled"]
    assert list(InvitationStatus._value2member_map_) == expected
    assert ExamInvitation.__table__.c.status.type.enums == expected


def test_attempt_status_uses_values_not_names() -> None:
    expected = [
        "Not Started",
        "In Progress",
        "Submitted",
        "Timed Out",
        "Interrupted",
        "Cancelled",
    ]
    assert list(AttemptStatus._value2member_map_) == expected
    assert AssessmentAttempt.__table__.c.status.type.enums == expected


def test_hr_decision_uses_values_and_matches_constraint() -> None:
    expected = ["Unset", "Accepted", "Rejected", "Needs Review"]
    assert list(HRDecision._value2member_map_) == expected
    assert AssessmentAttempt.__table__.c.hr_decision.type.enums == expected

    constraint = next(
        item
        for item in AssessmentAttempt.__table__.constraints
        if item.name == "ck_assessment_attempts_hr_decision_consistency"
    )
    sql = str(constraint.sqltext)
    assert "hr_decision = 'Unset'" in sql
    assert "hr_decision <> 'Unset'" in sql


def test_attempt_event_type_uses_all_approved_values() -> None:
    expected = [
        "TabHidden",
        "CameraStopped",
        "ScreenShareStopped",
        "CopyAttempt",
        "PasteAttempt",
        "Reentered",
        "ConcurrentSessionBlocked",
        "Idle",
        "NetworkDisconnected",
        "NetworkRestored",
        "RecordingGap",
    ]
    assert list(AttemptEventType._value2member_map_) == expected
    assert AttemptEvent.__table__.c.event_type.type.enums == expected
    assert AttemptEventType.RECORDING_GAP.value == "RecordingGap"
    assert AttemptEventType.RECORDING_GAP.name == "RECORDING_GAP"
