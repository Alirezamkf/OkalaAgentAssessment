import pytest

from app.integrations.llm.errors import LLMProviderError, LLMProviderResponseError
from app.schemas.attempt_event_summary import (
    AttemptEventSummaryInput,
    AttemptEventSummaryOutput,
)
from app.schemas.hr_reporting import (
    NaturalLanguageReportingInput,
    NaturalLanguageReportingOutput,
)
from app.services import validation as validation_module
from app.services.validation import (
    WorkflowInputValidationError,
    WorkflowOutputValidationError,
    WorkflowValidationError,
    validate_attempt_event_summary_input,
    validate_attempt_event_summary_result,
    validate_hr_reporting_input,
    validate_hr_reporting_result,
)


def attempt_payload() -> dict[str, object]:
    return {
        "events": [
            {
                "event_type": "TabVisible",
                "occurred_at": "2026-11-25T10:15:30Z",
                "duration_seconds": 0,
            }
        ]
    }


def attempt_output() -> dict[str, object]:
    return {
        "status": "success",
        "summary": "\u06cc\u06a9 \u0631\u0648\u06cc\u062f\u0627\u062f \u062b\u0628\u062a \u0634\u062f.",
        "events": attempt_payload()["events"],
    }


def hr_payload() -> dict[str, object]:
    return {
        "category": "attempt_counts_by_status",
        "result": {
            "state": "available",
            "data": {
                "status_counts": [
                    {"status": "Not Started", "count": 0},
                    {"status": "In Progress", "count": 1},
                    {"status": "Submitted", "count": 2},
                    {"status": "Timed Out", "count": 3},
                    {"status": "Interrupted", "count": 4},
                    {"status": "Cancelled", "count": 5},
                ]
            },
        },
    }


def hr_output() -> dict[str, object]:
    return {
        "category": "attempt_counts_by_status",
        "result_state": "available",
        "explanation": "\u0634\u0645\u0627\u0631 \u0648\u0636\u0639\u06cc\u062a\u200c\u0647\u0627: \u06f0\u060c \u06f1\u060c \u06f2\u060c \u06f3\u060c \u06f4 \u0648 \u06f5.",
    }


@pytest.mark.parametrize(
    ("validator", "payload", "expected_type"),
    [
        (validate_attempt_event_summary_input, attempt_payload(), AttemptEventSummaryInput),
        (validate_hr_reporting_input, hr_payload(), NaturalLanguageReportingInput),
    ],
)
def test_input_boundary_accepts_existing_schema_contracts(
    validator, payload, expected_type
) -> None:
    assert isinstance(validator(payload), expected_type)


@pytest.mark.parametrize(
    ("validator", "payload"),
    [
        (validate_attempt_event_summary_input, {"events": [{"event_type": "TabHidden"}]}),
        (validate_attempt_event_summary_input, {"events": [{**attempt_payload()["events"][0], "event_type": "tabvisible"}]}),
        (validate_attempt_event_summary_input, {**attempt_payload(), "candidate_id": "x"}),
        (validate_hr_reporting_input, {"category": "unsupported", "result": {"state": "empty"}}),
        (validate_hr_reporting_input, {"category": "attempt_counts_by_status"}),
        (validate_hr_reporting_input, {**hr_payload(), "attempt_id": "x"}),
    ],
)
def test_input_boundary_classifies_malformed_unsupported_and_extra_data(
    validator, payload
) -> None:
    with pytest.raises(WorkflowInputValidationError) as error:
        validator(payload)
    assert error.value.code == "workflow_input_invalid"
    assert "candidate" not in str(error.value).lower()
    assert "attempt" not in str(error.value).lower()


@pytest.mark.parametrize(
    ("validator", "source_payload", "output", "expected_type"),
    [
        (
            validate_attempt_event_summary_result,
            attempt_payload(),
            attempt_output(),
            AttemptEventSummaryOutput,
        ),
        (
            validate_hr_reporting_result,
            hr_payload(),
            hr_output(),
            NaturalLanguageReportingOutput,
        ),
    ],
)
def test_output_boundary_runs_schema_and_semantic_validation(
    validator, source_payload, output, expected_type
) -> None:
    if validator is validate_attempt_event_summary_result:
        source = validate_attempt_event_summary_input(source_payload)
    else:
        source = validate_hr_reporting_input(source_payload)

    result = validator(output, source)
    if expected_type is not None:
        assert isinstance(result, expected_type)


@pytest.mark.parametrize(
    ("validator", "source_payload", "output"),
    [
        (
            validate_attempt_event_summary_result,
            attempt_payload(),
            {**attempt_output(), "attempt_id": "x"},
        ),
        (
            validate_attempt_event_summary_result,
            attempt_payload(),
            {**attempt_output(), "events": []},
        ),
        (
            validate_hr_reporting_result,
            hr_payload(),
            {**hr_output(), "debug": "unexpected"},
        ),
        (
            validate_hr_reporting_result,
            hr_payload(),
            {**hr_output(), "category": "recording_completeness"},
        ),
        (
            validate_hr_reporting_result,
            hr_payload(),
            {**hr_output(), "explanation": "Ø´Ù…Ø§Ø± ÙˆØ¶Ø¹ÛŒØªâ€ŒÙ‡Ø§: Û°ØŒ Û²ØŒ Û´ØŒ Û°ØŒ Û± Ùˆ Û¹."},
        ),
    ],
)
def test_output_boundary_rejects_bad_shape_or_source_mismatch(
    validator, source_payload, output
) -> None:
    source = (
        validate_attempt_event_summary_input(source_payload)
        if validator is validate_attempt_event_summary_result
        else validate_hr_reporting_input(source_payload)
    )
    with pytest.raises(WorkflowOutputValidationError) as error:
        validator(output, source)
    assert error.value.code == "workflow_output_invalid"
    assert "unexpected" not in str(error.value)


def test_shared_validation_errors_are_distinct_from_provider_and_internal_errors() -> None:
    assert issubclass(WorkflowInputValidationError, WorkflowValidationError)
    assert issubclass(WorkflowOutputValidationError, WorkflowValidationError)
    assert not issubclass(WorkflowValidationError, LLMProviderError)

    # Provider response failures keep their existing classification and are
    # not caught or converted by this validation boundary.
    provider_error = LLMProviderResponseError()
    assert isinstance(provider_error, LLMProviderError)
    assert provider_error.code == "provider_response_error"


def test_provider_response_error_is_not_wrapped_as_validation_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider_error = LLMProviderResponseError()

    def provider_failure(output, source):
        raise provider_error

    monkeypatch.setattr(
        validation_module,
        "validate_attempt_event_summary_output",
        provider_failure,
    )

    with pytest.raises(LLMProviderResponseError) as error:
        validate_attempt_event_summary_result(
            attempt_output(),
            validate_attempt_event_summary_input(attempt_payload()),
        )
    assert error.value is provider_error


def test_unexpected_internal_errors_are_not_reclassified_as_validation_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def unexpected_failure(cls, payload):
        raise RuntimeError("internal failure")

    monkeypatch.setattr(
        AttemptEventSummaryInput,
        "model_validate",
        classmethod(unexpected_failure),
    )

    with pytest.raises(RuntimeError, match="internal failure"):
        validate_attempt_event_summary_input(attempt_payload())
