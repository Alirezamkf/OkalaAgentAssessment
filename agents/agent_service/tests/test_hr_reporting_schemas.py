from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.schemas.hr_reporting import (
    AttemptCountsByStatusData,
    AttemptStatus,
    ExamScoreStatisticsData,
    NaturalLanguageReportingInput,
    NaturalLanguageReportingOutput,
    RecordingCompletenessStatus,
    ReportResultState,
    ReportingCategory,
    ReportingOutputValidationError,
    validate_natural_language_reporting_output,
)


APPROVED_ATTEMPT_STATUSES = {
    "Not Started",
    "In Progress",
    "Submitted",
    "Timed Out",
    "Interrupted",
    "Cancelled",
}

APPROVED_CATEGORIES = {
    "attempt_counts_by_status",
    "exam_score_statistics",
    "attempts_with_highest_event_count",
    "recording_completeness",
}


def status_counts(values: list[int] | None = None) -> list[dict[str, object]]:
    counts = values or [0, 1, 2, 3, 4, 5]
    return [
        {"status": status.value, "count": count}
        for status, count in zip(AttemptStatus, counts, strict=True)
    ]


def recording_counts(values: list[int] | None = None) -> list[dict[str, object]]:
    counts = values or [1, 0, 2]
    return [
        {"status": status.value, "count": count}
        for status, count in zip(RecordingCompletenessStatus, counts, strict=True)
    ]


def attempt_counts_input(
    *, state: str = "available", values: list[int] | None = None
) -> dict[str, object]:
    if state == "empty":
        result: dict[str, object] = {"state": "empty"}
    else:
        result = {
            "state": "available",
            "data": {"status_counts": status_counts(values)},
        }
    return {"category": "attempt_counts_by_status", "result": result}


def exam_score_input(*, empty: bool = False) -> dict[str, object]:
    if empty:
        result: dict[str, object] = {
            "state": "empty",
            "eligible_finalized_score_count": 0,
        }
    else:
        result = {
            "state": "available",
            "data": {
                "eligible_finalized_score_count": 4,
                "average_score": 12.5,
                "minimum_score": 10,
                "maximum_score": 15,
            },
        }
    return {"category": "exam_score_statistics", "result": result}


def highest_event_count_input(*, empty: bool = False) -> dict[str, object]:
    result: dict[str, object]
    if empty:
        result = {"state": "empty"}
    else:
        result = {
            "state": "available",
            "data": {
                "maximum_recorded_event_count": 0,
                "tied_attempt_count": 2,
            },
        }
    return {"category": "attempts_with_highest_event_count", "result": result}


def recording_input(
    *, state: str = "available", values: list[int] | None = None
) -> dict[str, object]:
    if state == "empty":
        result: dict[str, object] = {"state": "empty"}
    else:
        result = {
            "state": "available",
            "data": {"recording_counts": recording_counts(values)},
        }
    return {"category": "recording_completeness", "result": result}


def test_local_attempt_status_enum_matches_exact_six_backend_values() -> None:
    assert {status.value for status in AttemptStatus} == APPROVED_ATTEMPT_STATUSES
    assert len(AttemptStatus) == 6


def test_exactly_four_reporting_categories_are_supported() -> None:
    assert {category.value for category in ReportingCategory} == APPROVED_CATEGORIES
    assert len(ReportingCategory) == 4


@pytest.mark.parametrize(
    "payload",
    [
        attempt_counts_input(),
        exam_score_input(),
        highest_event_count_input(),
        recording_input(),
    ],
)
def test_accepts_valid_available_result_for_each_category(
    payload: dict[str, object],
) -> None:
    parsed = NaturalLanguageReportingInput.model_validate(payload)

    assert parsed.root.category in APPROVED_CATEGORIES
    assert parsed.root.result.state == "available"


def test_all_six_attempt_statuses_are_required_once() -> None:
    parsed = NaturalLanguageReportingInput.model_validate(attempt_counts_input())
    assert isinstance(parsed.root.result.data, AttemptCountsByStatusData)
    assert {item.status.value for item in parsed.root.result.data.status_counts} == (
        APPROVED_ATTEMPT_STATUSES
    )


@pytest.mark.parametrize("values", [[0, 0, 0, 0, 0, 0], [1, 0, 3, 2, 0, 8]])
def test_zero_and_positive_status_counts_are_available_results(
    values: list[int],
) -> None:
    parsed = NaturalLanguageReportingInput.model_validate(
        attempt_counts_input(values=values)
    )

    assert parsed.root.result.state == "available"
    assert [item.count for item in parsed.root.result.data.status_counts] == values


def test_score_statistics_accept_backend_computed_values_without_recalculation() -> None:
    parsed = NaturalLanguageReportingInput.model_validate(exam_score_input())
    data = parsed.root.result.data

    assert isinstance(data, ExamScoreStatisticsData)
    assert data.eligible_finalized_score_count == 4
    assert data.average_score == Decimal("12.5")
    assert data.minimum_score == Decimal("10")
    assert data.maximum_score == Decimal("15")


def test_recording_states_are_exact_and_remain_distinct() -> None:
    parsed = NaturalLanguageReportingInput.model_validate(recording_input())
    counts = parsed.root.result.data.recording_counts

    assert [item.status.value for item in counts] == [
        "Complete",
        "No Recording",
        "Incomplete",
    ]
    assert counts[0].status is not counts[1].status
    assert counts[1].status is not counts[2].status


@pytest.mark.parametrize(
    "payload",
    [
        attempt_counts_input(state="empty"),
        exam_score_input(empty=True),
        highest_event_count_input(empty=True),
        recording_input(state="empty"),
    ],
)
def test_each_category_has_an_explicit_empty_result(
    payload: dict[str, object],
) -> None:
    parsed = NaturalLanguageReportingInput.model_validate(payload)

    assert parsed.root.result.state == "empty"


def test_available_zero_counts_are_not_reclassified_as_empty() -> None:
    parsed = NaturalLanguageReportingInput.model_validate(
        recording_input(values=[0, 0, 0])
    )

    assert parsed.root.result.state == "available"
    assert all(item.count == 0 for item in parsed.root.result.data.recording_counts)


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"category": "attempt_counts_by_status"},
        {"category": "unsupported", "result": {"state": "empty"}},
        {"category": "attempt_counts_by_status", "result": {"state": "unknown"}},
        {
            "category": "exam_score_statistics",
            "result": {"state": "available", "data": {"status_counts": []}},
        },
        {
            "category": "recording_completeness",
            "result": {"state": "empty", "data": {}},
        },
    ],
)
def test_rejects_missing_unknown_or_wrong_category_payloads(
    payload: dict[str, object],
) -> None:
    with pytest.raises(ValidationError):
        NaturalLanguageReportingInput.model_validate(payload)


@pytest.mark.parametrize(
    "payload",
    [
        {"category": "attempt_counts_by_status", "result": {"state": "available"}},
        {
            "category": "attempt_counts_by_status",
            "result": {
                "state": "available",
                "data": {"status_counts": status_counts()[:-1]},
            },
        },
        {
            "category": "attempt_counts_by_status",
            "result": {
                "state": "available",
                "data": {
                    "status_counts": status_counts()[:-1]
                    + [{"status": "Interrupted", "count": 5}]
                },
            },
        },
        {
            "category": "attempt_counts_by_status",
            "result": {
                "state": "available",
                "data": {
                    "status_counts": [
                        {"status": "Started", "count": 0},
                        *status_counts()[1:],
                    ]
                },
            },
        },
    ],
)
def test_rejects_incomplete_duplicate_or_unknown_attempt_statuses(
    payload: dict[str, object],
) -> None:
    with pytest.raises(ValidationError):
        NaturalLanguageReportingInput.model_validate(payload)


@pytest.mark.parametrize("count", [-1, 1.5, True, "2"])
def test_rejects_negative_or_non_integer_counts(count: object) -> None:
    payload = attempt_counts_input()
    payload["result"]["data"]["status_counts"][0]["count"] = count

    with pytest.raises(ValidationError):
        NaturalLanguageReportingInput.model_validate(payload)


@pytest.mark.parametrize(
    "data",
    [
        {
            "eligible_finalized_score_count": 0,
            "average_score": 1,
            "minimum_score": 0,
            "maximum_score": 2,
        },
        {
            "eligible_finalized_score_count": -1,
            "average_score": 1,
            "minimum_score": 0,
            "maximum_score": 2,
        },
        {
            "eligible_finalized_score_count": 1,
            "average_score": float("nan"),
            "minimum_score": 0,
            "maximum_score": 2,
        },
        {
            "eligible_finalized_score_count": 1,
            "average_score": 3,
            "minimum_score": 0,
            "maximum_score": 2,
        },
        {
            "eligible_finalized_score_count": 1,
            "average_score": "1.5",
            "minimum_score": 0,
            "maximum_score": 2,
        },
    ],
)
def test_rejects_invalid_score_statistics(data: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        NaturalLanguageReportingInput.model_validate(
            {
                "category": "exam_score_statistics",
                "result": {"state": "available", "data": data},
            }
        )


def test_empty_score_result_requires_zero_eligible_finalized_scores() -> None:
    with pytest.raises(ValidationError):
        NaturalLanguageReportingInput.model_validate(
            {
                "category": "exam_score_statistics",
                "result": {"state": "empty", "eligible_finalized_score_count": 1},
            }
        )


@pytest.mark.parametrize(
    "data",
    [
        {"maximum_recorded_event_count": -1, "tied_attempt_count": 1},
        {"maximum_recorded_event_count": 2, "tied_attempt_count": 0},
        {"maximum_recorded_event_count": 2, "tied_attempt_count": 1, "attempt_id": 8},
    ],
)
def test_rejects_invalid_or_identifying_highest_event_results(
    data: dict[str, object],
) -> None:
    with pytest.raises(ValidationError):
        NaturalLanguageReportingInput.model_validate(
            {
                "category": "attempts_with_highest_event_count",
                "result": {"state": "available", "data": data},
            }
        )


def test_highest_event_count_allows_zero_events_when_attempts_are_tied() -> None:
    parsed = NaturalLanguageReportingInput.model_validate(highest_event_count_input())

    assert parsed.root.result.data.maximum_recorded_event_count == 0
    assert parsed.root.result.data.tied_attempt_count == 2


@pytest.mark.parametrize(
    "counts",
    [
        [{"status": "Complete", "count": 1}, {"status": "Incomplete", "count": 1}],
        [
            {"status": "Complete", "count": 1},
            {"status": "Complete", "count": 0},
            {"status": "Incomplete", "count": 1},
        ],
        [
            {"status": "Complete", "count": 1},
            {"status": "No Recording", "count": -1},
            {"status": "Incomplete", "count": 1},
        ],
    ],
)
def test_rejects_missing_duplicate_or_negative_recording_states(
    counts: list[dict[str, object]],
) -> None:
    with pytest.raises(ValidationError):
        NaturalLanguageReportingInput.model_validate(
            {
                "category": "recording_completeness",
                "result": {
                    "state": "available",
                    "data": {"recording_counts": counts},
                },
            }
        )


@pytest.mark.parametrize(
    "extra",
    [
        {"query": "Which candidate did best?"},
        {"attempt_id": 17},
        {"candidate_name": "Example"},
        {"candidate_answer": "A"},
        {"answer_key": "A"},
        {"question_text": "Question"},
        {"video": "video-bytes"},
        {"image": "image-bytes"},
        {"raw_events": [{"event_type": "TabHidden"}]},
    ],
)
def test_rejects_prohibited_top_level_data(extra: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        NaturalLanguageReportingInput.model_validate(
            {**attempt_counts_input(), **extra}
        )


@pytest.mark.parametrize(
    "extra",
    [
        {"attempt_id": 17},
        {"candidate_id": 9},
        {"candidate_name": "Example"},
        {"question_text": "Question"},
        {"answer_key": "A"},
        {"recording_path": "/private/video"},
        {"raw_events": []},
    ],
)
def test_rejects_prohibited_data_inside_category_result(
    extra: dict[str, object],
) -> None:
    payload = attempt_counts_input()
    payload["result"]["data"].update(extra)

    with pytest.raises(ValidationError):
        NaturalLanguageReportingInput.model_validate(payload)


def test_validates_persian_output_and_preserves_normalized_numbers() -> None:
    source = NaturalLanguageReportingInput.model_validate(exam_score_input())
    output = validate_natural_language_reporting_output(
        {
            "category": "exam_score_statistics",
            "result_state": "available",
            "explanation": "۴ نمره نهایی؛ میانگین ۱۲٫۵، کمینه ۱۰ و بیشینه ۱۵.",
        },
        source,
    )

    assert output.category is ReportingCategory.EXAM_SCORE_STATISTICS
    assert output.result_state is ReportResultState.AVAILABLE


@pytest.mark.parametrize(
    ("source_payload", "output_payload"),
    [
        (
            attempt_counts_input(),
            {
                "category": "attempt_counts_by_status",
                "result_state": "available",
                "explanation": "شمار وضعیت‌ها: ۰، ۱، ۲، ۳، ۴ و ۵.",
            },
        ),
        (
            highest_event_count_input(),
            {
                "category": "attempts_with_highest_event_count",
                "result_state": "available",
                "explanation": "بیشترین تعداد رویداد ۰ و شمار تلاش‌های برابر ۲ است.",
            },
        ),
        (
            recording_input(),
            {
                "category": "recording_completeness",
                "result_state": "available",
                "explanation": "کامل ۱، بدون ضبط ۰ و ناقص ۲.",
            },
        ),
    ],
)
def test_validates_output_for_each_other_available_category(
    source_payload: dict[str, object], output_payload: dict[str, object]
) -> None:
    source = NaturalLanguageReportingInput.model_validate(source_payload)
    output = validate_natural_language_reporting_output(output_payload, source)

    assert output.category.value == source.root.category
    assert output.result_state.value == source.root.result.state


def test_output_rejects_missing_added_or_changed_numbers() -> None:
    source = NaturalLanguageReportingInput.model_validate(exam_score_input())
    for explanation in (
        "۴ نمره نهایی؛ میانگین ۱۲٫۵، کمینه ۱۰.",
        "۴ نمره نهایی؛ میانگین ۱۲٫۵، کمینه ۱۰، بیشینه ۱۵ و نتیجه ۹۹.",
        "۴ نمره نهایی؛ میانگین ۱۲٫۴، کمینه ۱۰ و بیشینه ۱۵.",
    ):
        with pytest.raises(ReportingOutputValidationError):
            validate_natural_language_reporting_output(
                {
                    "category": "exam_score_statistics",
                    "result_state": "available",
                    "explanation": explanation,
                },
                source,
            )


def test_empty_output_does_not_need_a_fabricated_number() -> None:
    source = NaturalLanguageReportingInput.model_validate(exam_score_input(empty=True))
    output = validate_natural_language_reporting_output(
        {
            "category": "exam_score_statistics",
            "result_state": "empty",
            "explanation": "نتیجه‌ای برای این گزارش در دسترس نیست.",
        },
        source,
    )

    assert output.result_state is ReportResultState.EMPTY


@pytest.mark.parametrize(
    "source_payload",
    [
        attempt_counts_input(state="empty"),
        exam_score_input(empty=True),
        highest_event_count_input(empty=True),
        recording_input(state="empty"),
    ],
)
def test_empty_output_state_is_valid_for_each_category(
    source_payload: dict[str, object],
) -> None:
    source = NaturalLanguageReportingInput.model_validate(source_payload)
    output = validate_natural_language_reporting_output(
        {
            "category": source.root.category,
            "result_state": "empty",
            "explanation": "نتیجه‌ای برای این گزارش در دسترس نیست.",
        },
        source,
    )

    assert output.result_state is ReportResultState.EMPTY


def test_output_normalizes_arabic_digits() -> None:
    source = NaturalLanguageReportingInput.model_validate(exam_score_input())
    output = validate_natural_language_reporting_output(
        {
            "category": "exam_score_statistics",
            "result_state": "available",
            "explanation": "٤ نمره؛ میانگین ١٢٫٥، کمینه ١٠ و بیشینه ١٥.",
        },
        source,
    )

    assert output.result_state is ReportResultState.AVAILABLE


def test_output_accepts_latin_digits_for_supplied_values() -> None:
    source = NaturalLanguageReportingInput.model_validate(exam_score_input())
    output = validate_natural_language_reporting_output(
        {
            "category": "exam_score_statistics",
            "result_state": "available",
            "explanation": "4 نمره؛ میانگین 12.5، کمینه 10 و بیشینه 15.",
        },
        source,
    )

    assert output.result_state is ReportResultState.AVAILABLE


@pytest.mark.parametrize(
    "explanation",
    [
        "این نتیجه رفتار مشکوک را ثابت می‌کند.",
        "این داوطلب برای این موقعیت مناسب است.",
        "نتیجه به دلیل رفتار داوطلب ایجاد شد.",
        "The result is due to candidate intent.",
    ],
)
def test_output_rejects_prohibited_inference_or_suitability(
    explanation: str,
) -> None:
    with pytest.raises(ValidationError):
        NaturalLanguageReportingOutput.model_validate(
            {
                "category": "attempt_counts_by_status",
                "result_state": "available",
                "explanation": explanation,
            }
        )


@pytest.mark.parametrize(
    "explanation",
    [
        "علت در داده‌های این گزارش ذکر نشده است.",
        "رخداد در زمان مناسب ثبت شد.",
    ],
)
def test_output_allows_ordinary_persian_cause_and_suitability_words(
    explanation: str,
) -> None:
    parsed = NaturalLanguageReportingOutput.model_validate(
        {
            "category": "attempt_counts_by_status",
            "result_state": "available",
            "explanation": explanation,
        }
    )

    assert parsed.explanation == explanation


def test_output_category_and_state_must_match_input() -> None:
    source = NaturalLanguageReportingInput.model_validate(exam_score_input(empty=True))
    with pytest.raises(ReportingOutputValidationError):
        validate_natural_language_reporting_output(
            {
                "category": "attempt_counts_by_status",
                "result_state": "empty",
                "explanation": "نتیجه‌ای برای این گزارش در دسترس نیست.",
            },
            source,
        )


@pytest.mark.parametrize(
    "payload",
    [
        {"category": "exam_score_statistics", "result_state": "available"},
        {
            "category": "exam_score_statistics",
            "result_state": "available",
            "explanation": "No result available.",
        },
        {
            "category": "exam_score_statistics",
            "result_state": "unavailable",
            "explanation": "نتیجه‌ای برای این گزارش در دسترس نیست.",
        },
        {
            "category": "exam_score_statistics",
            "result_state": "available",
            "explanation": "نتیجه‌ای برای این گزارش در دسترس نیست.",
            "attempt_id": 5,
        },
    ],
)
def test_rejects_invalid_output_payloads(payload: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        NaturalLanguageReportingOutput.model_validate(payload)
