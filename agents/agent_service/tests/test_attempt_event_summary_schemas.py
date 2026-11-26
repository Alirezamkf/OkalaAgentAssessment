import pytest
from pydantic import ValidationError

from app.schemas.attempt_event_summary import (
    AttemptEventRecord,
    AttemptEventSummaryInput,
    AttemptEventSummaryOutput,
    AttemptEventSummaryOutputValidationError,
    AttemptEventSummaryStatus,
    AttemptEventType,
    validate_attempt_event_summary_output,
)


APPROVED_EVENT_TYPES = {
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
    "TabVisible",
}


def event(
    event_type: str = "TabHidden",
    occurred_at: str = "2026-11-25T10:15:30Z",
    duration_seconds: int | None = None,
) -> dict[str, object]:
    return {
        "event_type": event_type,
        "occurred_at": occurred_at,
        "duration_seconds": duration_seconds,
    }


def test_enum_contains_exactly_the_12_issue_32_event_values() -> None:
    assert {value.value for value in AttemptEventType} == APPROVED_EVENT_TYPES
    assert len(AttemptEventType) == 12
    assert AttemptEventType.TAB_VISIBLE is not AttemptEventType.REENTERED


@pytest.mark.parametrize("event_type", sorted(APPROVED_EVENT_TYPES))
def test_input_accepts_each_approved_event_type(event_type: str) -> None:
    parsed = AttemptEventSummaryInput.model_validate({"events": [event(event_type)]})

    assert parsed.events[0].event_type.value == event_type


@pytest.mark.parametrize(
    "event_type",
    ["tabhidden", "TABHIDDEN", "UnknownEvent", ""],
)
def test_input_rejects_unknown_or_incorrectly_cased_event_types(
    event_type: str,
) -> None:
    with pytest.raises(ValidationError):
        AttemptEventSummaryInput.model_validate({"events": [event(event_type)]})


def test_empty_event_list_is_a_valid_input() -> None:
    parsed = AttemptEventSummaryInput.model_validate({"events": []})

    assert parsed.events == []


@pytest.mark.parametrize(
    "payload",
    [
        {"events": [event()], "attempt_id": 12},
        {"events": [{**event(), "candidate_name": "Example"}]},
        {"events": [{**event(), "event_metadata": {"extra": True}}]},
        {"events": [{}]},
        {"events": [{"event_type": "TabHidden", "duration_seconds": 2}]},
        {"events": [{"occurred_at": "2026-11-25T10:15:30Z"}]},
    ],
)
def test_input_rejects_extra_or_incomplete_payloads(payload: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        AttemptEventSummaryInput.model_validate(payload)


@pytest.mark.parametrize("duration", [-1, 1.5, True, "2"])
def test_duration_must_be_nonnegative_integer_seconds(duration: object) -> None:
    with pytest.raises(ValidationError):
        AttemptEventRecord.model_validate(
            {**event(), "duration_seconds": duration}
        )


@pytest.mark.parametrize("duration", [None, 0, 12])
def test_duration_null_zero_and_positive_seconds_are_preserved(
    duration: int | None,
) -> None:
    parsed = AttemptEventRecord.model_validate(
        {**event(duration_seconds=duration)}
    )

    assert parsed.duration_seconds == duration


@pytest.mark.parametrize(
    "timestamp",
    [
        "2026-11-25T10:15:30",  # No timezone.
        "2026-11-25",  # Not a timestamp.
        "2026-02-30T10:15:30Z",  # Invalid calendar date.
        "2026-11-25 10:15:30Z",  # Wrong separator.
        1795601730,  # No numeric timestamp coercion.
    ],
)
def test_malformed_or_timezone_free_timestamp_is_rejected(timestamp: object) -> None:
    with pytest.raises(ValidationError):
        AttemptEventRecord.model_validate({**event(), "occurred_at": timestamp})


def test_timestamp_text_is_preserved_and_chronology_uses_timezone_offsets() -> None:
    source = AttemptEventSummaryInput.model_validate(
        {
            "events": [
                event("TabVisible", "2026-11-25T13:15:31+03:00", 0),
                event("TabHidden", "2026-11-25T10:15:30Z", None),
            ]
        }
    )

    ordered = source.chronological_events
    assert [item.event_type for item in ordered] == [
        AttemptEventType.TAB_HIDDEN,
        AttemptEventType.TAB_VISIBLE,
    ]
    assert ordered[1].occurred_at == "2026-11-25T13:15:31+03:00"
    assert ordered[1].duration_seconds == 0


def test_success_output_preserves_source_events_and_requires_persian_summary() -> None:
    source = AttemptEventSummaryInput.model_validate(
        {"events": [event("TabHidden", "2026-11-25T10:15:30Z", 4)]}
    )
    payload = {
        "status": "success",
        "summary": "در ساعت ۱۰:۱۵:۳۰ رویداد پنهان‌شدن زبانه ثبت شد.",
        "events": [event("TabHidden", "2026-11-25T10:15:30Z", 4)],
    }

    output = validate_attempt_event_summary_output(payload, source)

    assert output.status is AttemptEventSummaryStatus.SUCCESS
    assert output.events[0].occurred_at == source.events[0].occurred_at
    assert output.events[0].duration_seconds == 4


def test_output_event_order_must_be_chronological() -> None:
    with pytest.raises(ValidationError):
        AttemptEventSummaryOutput.model_validate(
            {
                "status": "success",
                "summary": "دو رویداد ثبت‌شده به ترتیب زمانی نمایش داده شده‌اند.",
                "events": [
                    event("TabVisible", "2026-11-25T10:15:31Z"),
                    event("TabHidden", "2026-11-25T10:15:30Z"),
                ],
            }
        )


def test_output_rejects_events_or_timestamps_changed_from_source() -> None:
    source = AttemptEventSummaryInput.model_validate(
        {"events": [event("TabHidden", "2026-11-25T10:15:30Z", 4)]}
    )
    payload = {
        "status": "success",
        "summary": "یک رویداد در زمان ثبت‌شده گزارش شد.",
        "events": [event("TabHidden", "2026-11-25T10:15:30+00:00", 4)],
    }

    with pytest.raises(AttemptEventSummaryOutputValidationError):
        validate_attempt_event_summary_output(payload, source)


def test_empty_outcome_requires_exact_semantic_message() -> None:
    output = AttemptEventSummaryOutput.model_validate(
        {
            "status": "empty",
            "summary": "هیچ رخدادی ثبت نشده است",
            "events": [],
        }
    )

    assert output.summary == "هیچ رخدادی ثبت نشده است"
    assert output.status is AttemptEventSummaryStatus.EMPTY


@pytest.mark.parametrize(
    "payload",
    [
        {"status": "empty", "summary": "رخدادی نیست", "events": []},
        {
            "status": "empty",
            "summary": "هیچ رخدادی ثبت نشده است",
            "events": [event()],
        },
    ],
)
def test_invalid_empty_outcomes_are_rejected(payload: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        AttemptEventSummaryOutput.model_validate(payload)


def test_insufficient_outcome_has_no_fabricated_summary() -> None:
    source = AttemptEventSummaryInput.model_validate({"events": [event()]})
    output = validate_attempt_event_summary_output(
        {
            "status": "insufficient_data",
            "summary": None,
            "events": [event()],
        },
        source,
    )

    assert output.status is AttemptEventSummaryStatus.INSUFFICIENT_DATA
    assert output.summary is None


def test_output_rejects_prohibited_judgment_language() -> None:
    with pytest.raises(ValidationError):
        AttemptEventSummaryOutput.model_validate(
            {
                "status": "success",
                "summary": "این رویداد مشکوک است.",
                "events": [event()],
            }
        )


def test_output_rejects_unexpected_fields_and_unknown_outcomes() -> None:
    valid = {
        "status": "success",
        "summary": "یک رویداد ثبت شد.",
        "events": [event()],
    }
    with pytest.raises(ValidationError):
        AttemptEventSummaryOutput.model_validate({**valid, "attempt_id": 42})
    with pytest.raises(ValidationError):
        AttemptEventSummaryOutput.model_validate({**valid, "status": "unavailable"})
