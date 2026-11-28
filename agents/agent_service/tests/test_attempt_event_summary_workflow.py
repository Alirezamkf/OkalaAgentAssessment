import asyncio
import logging
from typing import Any, TypeVar

import pytest
from pydantic import BaseModel

from app.integrations.llm.errors import (
    LLMProviderConnectionError,
    LLMProviderHTTPError,
    LLMProviderResponseError,
    LLMProviderTimeoutError,
)
from app.core.correlation import correlation_id_fingerprint
from app.integrations.llm.protocol import LLMResult
from app.schemas.attempt_event_summary import (
    AttemptEventSummaryInput,
    AttemptEventSummaryOutput,
    AttemptEventSummaryStatus,
)
from app.services.validation import WorkflowOutputValidationError
from app.services.workflows.attempt_event_summary import (
    handle_attempt_event_summary,
)


OutputT = TypeVar("OutputT", bound=BaseModel)


def event(
    event_type: str,
    occurred_at: str,
    duration_seconds: int | None = None,
) -> dict[str, object]:
    return {
        "event_type": event_type,
        "occurred_at": occurred_at,
        "duration_seconds": duration_seconds,
    }


def source_with_events(*events: dict[str, object]) -> AttemptEventSummaryInput:
    return AttemptEventSummaryInput.model_validate({"events": list(events)})


class FakeProvider:
    def __init__(
        self,
        output: Any = None,
        error: Exception | None = None,
    ) -> None:
        self.output = output
        self.error = error
        self.calls: list[dict[str, object]] = []

    async def generate(
        self,
        prompt: str,
        *,
        response_model: type[OutputT],
        correlation_id: str | None = None,
    ) -> LLMResult[OutputT]:
        self.calls.append(
            {
                "prompt": prompt,
                "response_model": response_model,
                "correlation_id": correlation_id,
            }
        )
        if self.error is not None:
            raise self.error
        return LLMResult(
            output=self.output,
            provider="mock-provider",
            model="mock-model",
        )


def valid_output(source: AttemptEventSummaryInput) -> dict[str, object]:
    return {
        "status": "success",
        "summary": "دو رخداد به‌ترتیب زمانی ثبت شدند.",
        "events": [event.model_dump(mode="json") for event in source.events],
    }


def assert_raw_value_absent_from_records(
    records: list[logging.LogRecord], raw_value: str
) -> None:
    standard_fields = set(logging.LogRecord("x", logging.INFO, "", 0, "", (), None).__dict__)
    for record in records:
        assert raw_value not in record.getMessage()
        for key, value in record.__dict__.items():
            if key in standard_fields:
                continue
            assert value is None or isinstance(value, (str, int, float, bool))
            if isinstance(value, str):
                assert raw_value not in value


def test_empty_input_returns_exact_empty_result_without_provider_call() -> None:
    source = source_with_events()
    provider = FakeProvider()

    result = asyncio.run(
        handle_attempt_event_summary(
            source,
            provider=provider,
            correlation_id="empty-test-correlation",
        )
    )

    assert result.model_dump(mode="json") == {
        "status": "empty",
        "summary": "هیچ رخدادی ثبت نشده است",
        "events": [],
    }
    assert provider.calls == []


@pytest.mark.parametrize("duration", [None, 0, 9])
def test_one_event_returns_insufficient_data_without_provider_call(
    duration: int | None,
) -> None:
    source = source_with_events(
        event("TabHidden", "2026-11-25T10:15:30Z", duration)
    )
    provider = FakeProvider()

    result = asyncio.run(
        handle_attempt_event_summary(
            source,
            provider=provider,
            correlation_id="insufficient-test-correlation",
        )
    )

    assert result.model_dump(mode="json") == {
        "status": "insufficient_data",
        "summary": None,
        "events": [event("TabHidden", "2026-11-25T10:15:30Z", duration)],
    }
    assert provider.calls == []


def test_two_events_use_prompt_provider_and_return_validated_summary() -> None:
    source = source_with_events(
        event("TabHidden", "2026-11-25T10:15:30Z", 4),
        event("TabVisible", "2026-11-25T10:15:34Z", 0),
    )
    provider = FakeProvider(valid_output(source))
    correlation_id = "summary-test-correlation"

    result = asyncio.run(
        handle_attempt_event_summary(
            source,
            provider=provider,
            correlation_id=correlation_id,
        )
    )

    assert result.status is AttemptEventSummaryStatus.SUCCESS
    assert result.summary == "دو رخداد به‌ترتیب زمانی ثبت شدند."
    assert result.events == source.events
    assert len(provider.calls) == 1
    assert provider.calls[0]["response_model"] is AttemptEventSummaryOutput
    assert provider.calls[0]["correlation_id"] == correlation_id
    assert '"event_type":"TabHidden"' in str(provider.calls[0]["prompt"])


def test_workflow_logs_safe_timing_and_correlation_metadata(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.setenv(
        "AGENT_SERVICE_SHARED_SECRET",
        "agent-workflow-test-key-generated-with-32-or-more-bytes",
    )
    source = source_with_events(
        event("TabHidden", "2026-11-25T10:15:30Z", 4),
        event("TabVisible", "2026-11-25T10:15:34Z", 0),
    )
    provider = FakeProvider(valid_output(source))
    correlation_id = "workflow-correlation-123"

    with caplog.at_level(logging.INFO):
        asyncio.run(
            handle_attempt_event_summary(
                source,
                provider=provider,
                correlation_id=correlation_id,
            )
        )

    workflow_records = [
        record
        for record in caplog.records
        if getattr(record, "operation", None) == "attempt_event_summary"
    ]
    assert [record.getMessage() for record in workflow_records] == [
        "Agent workflow started",
        "Agent workflow completed",
    ]
    expected_fingerprint = correlation_id_fingerprint(correlation_id)
    start_record, completion_record = workflow_records
    assert start_record.operation == "attempt_event_summary"
    assert start_record.started_at
    assert start_record.correlation_fingerprint == expected_fingerprint
    assert completion_record.operation == "attempt_event_summary"
    assert completion_record.completed_at
    assert completion_record.duration_ms >= 0
    assert completion_record.outcome == "success"
    assert completion_record.correlation_fingerprint == expected_fingerprint
    assert all(
        record.correlation_fingerprint == expected_fingerprint
        for record in workflow_records
    )
    assert workflow_records[0].started_at
    assert workflow_records[1].completed_at
    assert workflow_records[1].duration_ms >= 0
    assert workflow_records[1].outcome == "success"
    assert workflow_records[1].workflow_status == "success"
    assert "2026-11-25T10:15:30Z" not in caplog.text
    assert str(provider.calls[0]["prompt"]) not in caplog.text
    assert_raw_value_absent_from_records(caplog.records, "2026-11-25T10:15:30Z")
    assert_raw_value_absent_from_records(
        caplog.records, str(provider.calls[0]["prompt"])
    )
    assert all(not hasattr(record, "correlation_id") for record in workflow_records)
    assert_raw_value_absent_from_records(workflow_records, correlation_id)


def test_two_events_with_null_durations_are_summarized() -> None:
    source = source_with_events(
        event("NetworkDisconnected", "2026-11-25T10:16:00Z", None),
        event("NetworkRestored", "2026-11-25T10:16:12Z", None),
    )
    provider = FakeProvider(valid_output(source))

    result = asyncio.run(
        handle_attempt_event_summary(
            source,
            provider=provider,
            correlation_id="null-duration-correlation",
        )
    )

    assert result.status is AttemptEventSummaryStatus.SUCCESS
    assert result.events == source.events
    assert len(provider.calls) == 1


@pytest.mark.parametrize(
    "output_factory",
    [
        lambda source: {
            **valid_output(source),
            "summary": "This summary is not Persian.",
        },
        lambda source: {
            **valid_output(source),
            "events": [event("TabHidden", "2026-11-25T10:15:30Z", 4)],
        },
    ],
)
def test_invalid_or_mismatched_provider_output_is_rejected(output_factory) -> None:
    source = source_with_events(
        event("TabHidden", "2026-11-25T10:15:30Z", 4),
        event("TabVisible", "2026-11-25T10:15:34Z", 0),
    )
    provider = FakeProvider(output_factory(source))

    with pytest.raises(WorkflowOutputValidationError):
        asyncio.run(
            handle_attempt_event_summary(
                source,
                provider=provider,
                correlation_id="invalid-output-correlation",
            )
        )

    assert len(provider.calls) == 1


@pytest.mark.parametrize(
    "provider_error",
    [
        LLMProviderTimeoutError(),
        LLMProviderConnectionError(),
        LLMProviderHTTPError(429),
        LLMProviderResponseError(),
    ],
)
def test_provider_failures_propagate_without_fabricated_summary(
    provider_error: Exception,
) -> None:
    source = source_with_events(
        event("TabHidden", "2026-11-25T10:15:30Z"),
        event("TabVisible", "2026-11-25T10:15:34Z"),
    )
    provider = FakeProvider(error=provider_error)

    with pytest.raises(type(provider_error)) as raised:
        asyncio.run(
            handle_attempt_event_summary(
                source,
                provider=provider,
                correlation_id="provider-error-correlation",
            )
        )

    assert raised.value is provider_error
    assert len(provider.calls) == 1


def test_workflow_failure_logs_category_without_exception_details(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.setenv(
        "AGENT_SERVICE_SHARED_SECRET",
        "agent-workflow-test-key-generated-with-32-or-more-bytes",
    )
    source = source_with_events(
        event("TabHidden", "2026-11-25T10:15:30Z"),
        event("TabVisible", "2026-11-25T10:15:34Z"),
    )
    private_detail = "private-provider-error-sentinel"
    provider = FakeProvider(error=LLMProviderTimeoutError(private_detail))

    with caplog.at_level(logging.INFO):
        with pytest.raises(LLMProviderTimeoutError):
            asyncio.run(
                handle_attempt_event_summary(
                    source,
                    provider=provider,
                    correlation_id="workflow-failure-correlation",
                )
            )

    completed = next(
        record
        for record in caplog.records
        if record.getMessage() == "Agent workflow completed"
    )
    assert completed.operation == "attempt_event_summary"
    expected_fingerprint = correlation_id_fingerprint("workflow-failure-correlation")
    assert completed.correlation_fingerprint == expected_fingerprint
    assert completed.duration_ms >= 0
    assert completed.outcome == "failure"
    assert completed.failure_category == "provider_timeout"
    assert private_detail not in caplog.text
    assert "2026-11-25T10:15:30Z" not in caplog.text
    assert not hasattr(completed, "correlation_id")
    assert_raw_value_absent_from_records(caplog.records, "workflow-failure-correlation")
    assert_raw_value_absent_from_records(caplog.records, private_detail)
