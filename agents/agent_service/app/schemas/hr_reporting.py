"""Strict input and output schemas for the AI-FR-04 HR reporting contract."""

from collections import Counter
from decimal import Decimal, InvalidOperation
from enum import Enum
import math
import re
from typing import Annotated, Any, Literal, TypeAlias, Union

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    RootModel,
    StrictInt,
    StrictStr,
    field_validator,
    model_validator,
)


class _StrictSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AttemptStatus(str, Enum):
    """Agent-local wire values matching the approved Backend status contract."""

    NOT_STARTED = "Not Started"
    IN_PROGRESS = "In Progress"
    SUBMITTED = "Submitted"
    TIMED_OUT = "Timed Out"
    INTERRUPTED = "Interrupted"
    CANCELLED = "Cancelled"


class ReportingCategory(str, Enum):
    ATTEMPT_COUNTS_BY_STATUS = "attempt_counts_by_status"
    EXAM_SCORE_STATISTICS = "exam_score_statistics"
    ATTEMPTS_WITH_HIGHEST_EVENT_COUNT = "attempts_with_highest_event_count"
    RECORDING_COMPLETENESS = "recording_completeness"


class ReportResultState(str, Enum):
    AVAILABLE = "available"
    EMPTY = "empty"


class RecordingCompletenessStatus(str, Enum):
    COMPLETE = "Complete"
    NO_RECORDING = "No Recording"
    INCOMPLETE = "Incomplete"


class AttemptStatusCount(_StrictSchema):
    status: AttemptStatus
    count: StrictInt

    @field_validator("count")
    @classmethod
    def count_must_be_nonnegative(cls, value: int) -> int:
        if value < 0:
            raise ValueError("count must be zero or greater")
        return value


class AttemptCountsByStatusData(_StrictSchema):
    """One Backend-supplied count for each approved attempt status."""

    status_counts: list[AttemptStatusCount]

    @model_validator(mode="after")
    def require_each_status_once(self) -> "AttemptCountsByStatusData":
        actual = [item.status for item in self.status_counts]
        if len(actual) != len(AttemptStatus) or set(actual) != set(AttemptStatus):
            raise ValueError("status_counts must contain each approved status once")
        return self


class RecordingStatusCount(_StrictSchema):
    status: RecordingCompletenessStatus
    count: StrictInt

    @field_validator("count")
    @classmethod
    def count_must_be_nonnegative(cls, value: int) -> int:
        if value < 0:
            raise ValueError("count must be zero or greater")
        return value


class RecordingCompletenessData(_StrictSchema):
    recording_counts: list[RecordingStatusCount]

    @model_validator(mode="after")
    def require_each_recording_state_once(self) -> "RecordingCompletenessData":
        actual = [item.status for item in self.recording_counts]
        if len(actual) != len(RecordingCompletenessStatus) or set(actual) != set(
            RecordingCompletenessStatus
        ):
            raise ValueError("recording_counts must contain each state once")
        return self


class ExamScoreStatisticsData(_StrictSchema):
    """Backend-finalized scores; eligibility and calculations stay in Backend."""

    eligible_finalized_score_count: StrictInt
    average_score: Decimal
    minimum_score: Decimal
    maximum_score: Decimal

    @field_validator("average_score", "minimum_score", "maximum_score", mode="before")
    @classmethod
    def score_must_be_numeric(cls, value: Any) -> Any:
        if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
            raise ValueError("score must be a JSON number")
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError("score must be finite")
        return value

    @field_validator("average_score", "minimum_score", "maximum_score")
    @classmethod
    def score_must_be_finite(cls, value: Decimal) -> Decimal:
        if not value.is_finite():
            raise ValueError("score must be finite")
        return value

    @model_validator(mode="after")
    def validate_available_statistics(self) -> "ExamScoreStatisticsData":
        if self.eligible_finalized_score_count <= 0:
            raise ValueError("available score statistics require finalized scores")
        if not self.minimum_score <= self.average_score <= self.maximum_score:
            raise ValueError("average_score must be between minimum_score and maximum_score")
        return self


class HighestEventCountData(_StrictSchema):
    maximum_recorded_event_count: StrictInt
    tied_attempt_count: StrictInt

    @model_validator(mode="after")
    def validate_counts(self) -> "HighestEventCountData":
        if self.maximum_recorded_event_count < 0:
            raise ValueError("maximum_recorded_event_count must be zero or greater")
        if self.tied_attempt_count <= 0:
            raise ValueError("available result requires at least one tied attempt")
        return self


class EmptyReportResult(_StrictSchema):
    state: Literal["empty"]


class AttemptCountsByStatusAvailable(_StrictSchema):
    state: Literal["available"]
    data: AttemptCountsByStatusData


class ExamScoreStatisticsAvailable(_StrictSchema):
    state: Literal["available"]
    data: ExamScoreStatisticsData


class ExamScoreStatisticsEmpty(_StrictSchema):
    state: Literal["empty"]
    eligible_finalized_score_count: StrictInt

    @field_validator("eligible_finalized_score_count")
    @classmethod
    def empty_result_must_have_zero_scores(cls, value: int) -> int:
        if value != 0:
            raise ValueError("empty score statistics require a zero finalized score count")
        return value


class HighestEventCountAvailable(_StrictSchema):
    state: Literal["available"]
    data: HighestEventCountData


class RecordingCompletenessAvailable(_StrictSchema):
    state: Literal["available"]
    data: RecordingCompletenessData


class AttemptCountsByStatusInput(_StrictSchema):
    category: Literal["attempt_counts_by_status"]
    result: Annotated[
        Union[AttemptCountsByStatusAvailable, EmptyReportResult],
        Field(discriminator="state"),
    ]


class ExamScoreStatisticsInput(_StrictSchema):
    category: Literal["exam_score_statistics"]
    result: Annotated[
        Union[ExamScoreStatisticsAvailable, ExamScoreStatisticsEmpty],
        Field(discriminator="state"),
    ]


class HighestEventCountInput(_StrictSchema):
    category: Literal["attempts_with_highest_event_count"]
    result: Annotated[
        Union[HighestEventCountAvailable, EmptyReportResult],
        Field(discriminator="state"),
    ]


class RecordingCompletenessInput(_StrictSchema):
    category: Literal["recording_completeness"]
    result: Annotated[
        Union[RecordingCompletenessAvailable, EmptyReportResult],
        Field(discriminator="state"),
    ]


ReportingInputVariant: TypeAlias = Annotated[
    Union[
        AttemptCountsByStatusInput,
        ExamScoreStatisticsInput,
        HighestEventCountInput,
        RecordingCompletenessInput,
    ],
    Field(discriminator="category"),
]


class NaturalLanguageReportingInput(RootModel[ReportingInputVariant]):
    """Discriminated input union; each category accepts only its own result."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "category": "attempt_counts_by_status",
                    "result": {
                        "state": "available",
                        "data": {
                            "status_counts": [
                                {"status": "Not Started", "count": 0},
                                {"status": "In Progress", "count": 2},
                                {"status": "Submitted", "count": 4},
                                {"status": "Timed Out", "count": 0},
                                {"status": "Interrupted", "count": 1},
                                {"status": "Cancelled", "count": 0},
                            ]
                        },
                    },
                },
                {
                    "category": "exam_score_statistics",
                    "result": {
                        "state": "empty",
                        "eligible_finalized_score_count": 0,
                    },
                },
            ]
        }
    )


class NaturalLanguageReportingOutput(_StrictSchema):
    """Persian explanation metadata; Backend result values remain authoritative."""

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "examples": [
                {
                    "category": "attempt_counts_by_status",
                    "result_state": "available",
                    "explanation": "تعداد وضعیت‌ها: شروع‌نشده ۰، در حال انجام ۲، ارسال‌شده ۴، پایان‌یافته با وقفه زمانی ۰، متوقف‌شده ۱، لغوشده ۰.",
                },
                {
                    "category": "exam_score_statistics",
                    "result_state": "empty",
                    "explanation": "نتیجه‌ای برای این گزارش در دسترس نیست.",
                },
            ]
        },
    )

    category: ReportingCategory
    result_state: ReportResultState
    explanation: StrictStr = Field(min_length=1)

    @field_validator("explanation")
    @classmethod
    def explanation_must_be_persian(cls, value: str) -> str:
        if not re.search(r"[\u0620-\u064A\u067E\u0686\u0698\u06A9\u06AF\u06CC]", value):
            raise ValueError("explanation must be written in Persian")
        if _FORBIDDEN_EXPLANATION_PATTERN.search(value) or _CANDIDATE_SUITABILITY_PATTERN.search(value):
            raise ValueError("explanation contains prohibited inference or judgment")
        return value


class ReportingOutputValidationError(ValueError):
    """Raised when a valid-shaped explanation diverges from Backend results."""

    code = "hr_reporting_output_mismatch"


_DIGIT_TRANSLATION = str.maketrans(
    "۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩",
    "01234567890123456789",
)
_CANDIDATE_REFERENCE = (
    r"(?<!\w)(?:candidate|applicant|job\s+seeker|داوطلب|کاندیدا|متقاضی|نامزد)(?!\w)"
)
_SUITABILITY_TERM = r"(?<!\w)(?:unsuitable|suitable|نامناسب|مناسب)(?!\w)"
_CANDIDATE_SUITABILITY_PATTERN = re.compile(
    rf"(?:{_CANDIDATE_REFERENCE})[^\n.!?؟؛]{{0,40}}(?:{_SUITABILITY_TERM})"
    rf"|(?:{_SUITABILITY_TERM})[^\n.!?؟؛]{{0,40}}(?:{_CANDIDATE_REFERENCE})"
    rf"|(?:{_SUITABILITY_TERM})[^\n.!?؟؛]{{0,20}}(?:for\s+(?:the\s+)?(?:job|role|position)|برای\s+(?:این\s+)?(?:شغل|استخدام|سمت|موقعیت|جایگاه))",
    re.IGNORECASE,
)
_FORBIDDEN_EXPLANATION_PATTERN = re.compile(
    r"(?<!\w)(?:fraud(?:ulent)?|cheat(?:ing)?|dishonest|suspicious|"
    r"intended|intentionally|motive|intent(?:ion)?|because\s+of|due\s+to|caused\s+by)(?!\w)"
    r"|تقلب|متقلب|مشکوک|عمدی|قصد|نیت|انگیزه"
    r"|(?:به\s+(?:علت|دلیل)|باعث|منجر(?:\s+به)?|سبب)\s+[^.!?؟؛]{1,80}(?:شد|شده|می‌شود|است)",
    re.IGNORECASE,
)
_NUMBER_PATTERN = re.compile(
    r"(?<![\w.])[-+]?(?:[0-9۰-۹٠-٩]+(?:[.٫][0-9۰-۹٠-٩]+)?)(?![\w.])"
)


def _canonical_number(value: int | float | Decimal | str) -> Decimal:
    try:
        normalized = str(value).translate(_DIGIT_TRANSLATION).replace("٫", ".")
        number = Decimal(normalized)
    except (InvalidOperation, ValueError) as exc:
        raise ReportingOutputValidationError("invalid numeric source value") from exc
    if not number.is_finite():
        raise ReportingOutputValidationError("numeric source value must be finite")
    return number.normalize()


def _source_numbers(report: ReportingInputVariant) -> Counter[Decimal]:
    result = report.result
    if result.state == "empty":
        return Counter()

    data = result.data
    if isinstance(report, AttemptCountsByStatusInput):
        values = [item.count for item in data.status_counts]
    elif isinstance(report, ExamScoreStatisticsInput):
        values = [
            data.eligible_finalized_score_count,
            data.average_score,
            data.minimum_score,
            data.maximum_score,
        ]
    elif isinstance(report, HighestEventCountInput):
        values = [data.maximum_recorded_event_count, data.tied_attempt_count]
    else:
        values = [item.count for item in data.recording_counts]
    return Counter(_canonical_number(value) for value in values)


def validate_natural_language_reporting_output(
    output: NaturalLanguageReportingOutput | dict[str, Any],
    source: NaturalLanguageReportingInput,
) -> NaturalLanguageReportingOutput:
    """Validate the output schema, category/state, and every numeric token."""

    validated = NaturalLanguageReportingOutput.model_validate(output)
    report = source.root
    if validated.category.value != report.category:
        raise ReportingOutputValidationError("output category must match input")
    if validated.result_state.value != report.result.state:
        raise ReportingOutputValidationError("output result_state must match input")

    supplied = _source_numbers(report)
    stated = Counter(
        _canonical_number(token)
        for token in _NUMBER_PATTERN.findall(validated.explanation)
    )
    if stated != supplied:
        raise ReportingOutputValidationError(
            "explanation must preserve exactly the Backend-supplied numbers"
        )
    return validated
