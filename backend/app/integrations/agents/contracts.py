"""Backend-local wire contracts for the Agent Service AI-FR-01 endpoint."""

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
    ValidationError,
    field_validator,
    model_validator,
)


EMPTY_EVENT_SUMMARY = "هیچ رخدادی ثبت نشده است"
_TIMESTAMP_PATTERN = re.compile(
    r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-]\d{2}:\d{2})\Z"
)
_PERSIAN_LETTER_PATTERN = re.compile(
    r"[\u0620-\u064A\u067E\u0686\u0698\u06A9\u06AF\u06CC]"
)
_FORBIDDEN_SUMMARY_PATTERN = re.compile(
    r"(?<!\w)(?:cheat(?:ing)?|dishonest|suspicious|rank(?:ed|ing)?|"
    r"severity|intent(?:ion)?|cause)(?!\w)"
    r"|تقلب|متقلب|مشکوک|رتبه|شدت|عمدی|قصد|نیت",
    re.IGNORECASE,
)
_CANDIDATE_SUITABILITY_PATTERN = re.compile(
    r"(?:candidate|applicant|job\s+seeker|داوطلب|کاندیدا|متقاضی|نامزد|فرد|شخص)"
    r"[^\n.!?؟؛]{0,40}(?:unsuitable|suitable|نامناسب|مناسب)"
    r"|(?:unsuitable|suitable|نامناسب|مناسب)[^\n.!?؟؛]{0,40}"
    r"(?:candidate|applicant|job\s+seeker|داوطلب|کاندیدا|متقاضی|نامزد|فرد|شخص)",
    re.IGNORECASE,
)


class AttemptEventType(str, Enum):
    """The exact twelve event values in the approved Issue #32 wire contract."""

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
    if not _TIMESTAMP_PATTERN.fullmatch(value):
        raise ValueError("must be a timezone-aware ISO 8601 timestamp")
    normalized = f"{value[:-1]}+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        raise ValueError("must be a valid ISO 8601 timestamp") from None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("timestamp must include a timezone")
    return parsed.astimezone(timezone.utc)


class _StrictWireModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AttemptEventRecord(_StrictWireModel):
    event_type: AttemptEventType
    occurred_at: StrictStr
    duration_seconds: StrictInt | None = Field(default=None, ge=0)

    @field_validator("occurred_at")
    @classmethod
    def validate_timestamp(cls, value: str) -> str:
        _parse_timestamp(value)
        return value


class AttemptEventSummaryRequest(_StrictWireModel):
    events: list[AttemptEventRecord]

    @model_validator(mode="after")
    def validate_chronological_order(self) -> "AttemptEventSummaryRequest":
        instants = [_parse_timestamp(event.occurred_at) for event in self.events]
        if instants != sorted(instants):
            raise ValueError("events must be in ascending chronological order")
        return self


class AttemptEventSummaryStatus(str, Enum):
    SUCCESS = "success"
    EMPTY = "empty"
    INSUFFICIENT_DATA = "insufficient_data"


class AttemptEventSummaryResponse(_StrictWireModel):
    status: AttemptEventSummaryStatus
    summary: StrictStr | None
    events: list[AttemptEventRecord]

    @model_validator(mode="after")
    def validate_outcome_shape(self) -> "AttemptEventSummaryResponse":
        if self.status is AttemptEventSummaryStatus.EMPTY:
            if self.events or self.summary != EMPTY_EVENT_SUMMARY:
                raise ValueError("empty outcome must use the approved empty result")
        elif not self.events:
            raise ValueError("non-empty outcomes must preserve source events")
        elif self.status is AttemptEventSummaryStatus.INSUFFICIENT_DATA:
            if self.summary is not None:
                raise ValueError("insufficient outcome must have a null summary")
        elif (
            self.summary is None
            or not _PERSIAN_LETTER_PATTERN.search(self.summary)
            or _FORBIDDEN_SUMMARY_PATTERN.search(self.summary)
            or _CANDIDATE_SUITABILITY_PATTERN.search(self.summary)
        ):
            raise ValueError("successful summary does not match the approved contract")

        instants = [_parse_timestamp(event.occurred_at) for event in self.events]
        if instants != sorted(instants):
            raise ValueError("response events must be chronological")
        return self


def validate_attempt_event_summary_response(
    payload: Any,
    source: AttemptEventSummaryRequest,
) -> AttemptEventSummaryResponse:
    """Validate response shape and exact ordered correspondence to the request."""

    try:
        response = AttemptEventSummaryResponse.model_validate(payload)
    except ValidationError:
        raise ValueError("Agent Service response failed contract validation") from None

    if response.events != source.events:
        raise ValueError("Agent Service response did not preserve source events")
    if not source.events and response.status is not AttemptEventSummaryStatus.EMPTY:
        raise ValueError("empty request requires the empty outcome")
    if source.events and response.status is AttemptEventSummaryStatus.EMPTY:
        raise ValueError("non-empty request cannot have the empty outcome")
    return response
