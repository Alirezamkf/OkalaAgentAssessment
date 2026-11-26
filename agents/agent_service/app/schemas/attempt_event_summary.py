"""Strict schemas for the AI-FR-01 Attempt Event Summary contract."""

from datetime import datetime, timezone
from enum import Enum
import re
from typing import Any

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictInt,
    StrictStr,
    field_validator,
    model_validator,
)


_TIMESTAMP_PATTERN = re.compile(
    r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-]\d{2}:\d{2})\Z"
)
_PERSIAN_LETTER_PATTERN = re.compile(r"[\u0620-\u064A\u067E\u0686\u0698\u06A9\u06AF\u06CC]")
_CANDIDATE_REFERENCE = (
    r"(?<!\w)(?:candidate|applicant|job\s+seeker|داوطلب|کاندیدا|متقاضی|نامزد|فرد|شخص)(?!\w)"
)
_SUITABILITY_TERM = r"(?<!\w)(?:unsuitable|suitable|نامناسب|مناسب)(?!\w)"
_CANDIDATE_SUITABILITY_PATTERN = re.compile(
    rf"(?:{_CANDIDATE_REFERENCE})[^\n.!?؟؛]{{0,40}}(?:{_SUITABILITY_TERM})"
    rf"|(?:{_SUITABILITY_TERM})[^\n.!?؟؛]{{0,40}}(?:{_CANDIDATE_REFERENCE})"
    rf"|(?:{_SUITABILITY_TERM})[^\n.!?؟؛]{{0,20}}(?:for\s+(?:the\s+)?(?:job|role|position)|برای\s+(?:این\s+)?(?:شغل|استخدام|سمت|موقعیت|جایگاه))",
    re.IGNORECASE,
)
_FORBIDDEN_SUMMARY_PATTERN = re.compile(
    r"(?<!\w)(?:cheat(?:ing)?|dishonest|suspicious|rank(?:ed|ing)?|"
    r"severity|intent(?:ion)?|cause)(?!\w)"
    r"|تقلب|متقلب|مشکوک|رتبه|شدت|عمدی|قصد|نیت",
    re.IGNORECASE,
)


class AttemptEventType(str, Enum):
    """The exact 12 event values approved by Issue #32."""

    TAB_HIDDEN = "TabHidden"
    CAMERA_STOPPED = "CameraStopped"
    SCREEN_SHARE_STOPPED = "ScreenShareStopped"
    COPY_ATTEMPT = "CopyAttempt"
    PASTE_ATTEMPT = "PasteAttempt"
    REENTERED = "Reentered"
    CONCURRENT_SESSION_BLOCKED = "ConcurrentSessionBlocked"
    IDLE = "Idle"
    NETWORK_DISCONNECTED = "NetworkDisconnected"
    NETWORK_RESTORED = "NetworkRestored"
    RECORDING_GAP = "RecordingGap"
    TAB_VISIBLE = "TabVisible"


def _parse_timestamp(value: str) -> datetime:
    """Parse a timezone-aware RFC 3339 timestamp without changing its text."""

    if not _TIMESTAMP_PATTERN.fullmatch(value):
        raise ValueError("must be a timezone-aware ISO 8601 timestamp")
    normalized = f"{value[:-1]}+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ValueError("must be a valid ISO 8601 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("timestamp must include a timezone")
    return parsed


def _timestamp_key(event: "AttemptEventRecord") -> datetime:
    return _parse_timestamp(event.occurred_at).astimezone(timezone.utc)


class _StrictSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AttemptEventRecord(_StrictSchema):
    """Only the event fields permitted in the LLM input and output."""

    event_type: AttemptEventType
    occurred_at: StrictStr = Field(
        description="Server-recorded event timestamp in ISO 8601 with timezone."
    )
    duration_seconds: StrictInt | None = Field(
        default=None,
        description="Measured duration in integer seconds; null when unavailable.",
    )

    @field_validator("occurred_at")
    @classmethod
    def validate_occurred_at(cls, value: str) -> str:
        _parse_timestamp(value)
        return value

    @field_validator("duration_seconds")
    @classmethod
    def validate_duration_seconds(cls, value: int | None) -> int | None:
        if value is not None and value < 0:
            raise ValueError("duration_seconds must be zero or greater")
        return value


class AttemptEventSummaryInput(_StrictSchema):
    """LLM input: events from one authorized attempt, without identifiers."""

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "examples": [
                {
                    "events": [
                        {
                            "event_type": "TabHidden",
                            "occurred_at": "2026-11-25T10:15:30Z",
                            "duration_seconds": 4,
                        },
                        {
                            "event_type": "TabVisible",
                            "occurred_at": "2026-11-25T10:15:34Z",
                            "duration_seconds": 0,
                        },
                    ]
                },
                {"events": []},
            ]
        },
    )

    events: list[AttemptEventRecord]

    @property
    def chronological_events(self) -> tuple[AttemptEventRecord, ...]:
        """Return source events ordered by instant, preserving timestamp text."""

        return tuple(sorted(self.events, key=_timestamp_key))


class AttemptEventSummaryStatus(str, Enum):
    SUCCESS = "success"
    EMPTY = "empty"
    INSUFFICIENT_DATA = "insufficient_data"


class AttemptEventSummaryOutput(_StrictSchema):
    """Validated Persian summary and the exact source events it describes."""

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "examples": [
                {
                    "status": "success",
                    "summary": "در ساعت ۱۰:۱۵:۳۰ رویداد پنهان‌شدن زبانه ثبت شد.",
                    "events": [
                        {
                            "event_type": "TabHidden",
                            "occurred_at": "2026-11-25T10:15:30Z",
                            "duration_seconds": 4,
                        }
                    ],
                },
                {
                    "status": "empty",
                    "summary": "هیچ رخدادی ثبت نشده است",
                    "events": [],
                },
                {
                    "status": "insufficient_data",
                    "summary": None,
                    "events": [
                        {
                            "event_type": "TabHidden",
                            "occurred_at": "2026-11-25T10:15:30Z",
                            "duration_seconds": None,
                        }
                    ],
                },
            ]
        },
    )

    status: AttemptEventSummaryStatus
    summary: StrictStr | None
    events: list[AttemptEventRecord]

    @model_validator(mode="after")
    def validate_outcome(self) -> "AttemptEventSummaryOutput":
        if self.status is AttemptEventSummaryStatus.EMPTY:
            if self.events or self.summary != "هیچ رخدادی ثبت نشده است":
                raise ValueError(
                    "empty output requires the exact empty message and no events"
                )
            return self

        if not self.events:
            raise ValueError("non-empty outcomes require source events")

        timestamps = [_timestamp_key(event) for event in self.events]
        if timestamps != sorted(timestamps):
            raise ValueError("output events must be in chronological order")

        if self.status is AttemptEventSummaryStatus.INSUFFICIENT_DATA:
            if self.summary is not None:
                raise ValueError("insufficient data output must not contain a summary")
            return self

        if self.summary is None or not self.summary.strip():
            raise ValueError("successful output requires a non-empty summary")
        if not _PERSIAN_LETTER_PATTERN.search(self.summary):
            raise ValueError("summary must be written in Persian")
        if (
            _FORBIDDEN_SUMMARY_PATTERN.search(self.summary)
            or _CANDIDATE_SUITABILITY_PATTERN.search(self.summary)
        ):
            raise ValueError("summary contains prohibited judgment or inference terms")
        return self


class AttemptEventSummaryOutputValidationError(ValueError):
    """Raised when a valid-shaped output does not match its source input."""

    code = "attempt_event_summary_output_mismatch"


def validate_attempt_event_summary_output(
    output: AttemptEventSummaryOutput | dict[str, Any],
    source: AttemptEventSummaryInput,
) -> AttemptEventSummaryOutput:
    """Validate output shape and ensure it preserves the exact source events."""

    validated = AttemptEventSummaryOutput.model_validate(output)
    expected_events = source.chronological_events

    if not source.events:
        if validated.status is not AttemptEventSummaryStatus.EMPTY:
            raise AttemptEventSummaryOutputValidationError(
                "empty source input requires the empty outcome"
            )
        return validated

    if validated.status is AttemptEventSummaryStatus.EMPTY:
        raise AttemptEventSummaryOutputValidationError(
            "non-empty source input cannot produce the empty outcome"
        )
    if tuple(validated.events) != expected_events:
        raise AttemptEventSummaryOutputValidationError(
            "output events must preserve all source event fields"
        )
    return validated
