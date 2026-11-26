import asyncio
import json
import logging
import re

import pytest
from fastapi import Request
from fastapi.exceptions import RequestValidationError

from app.core.config import LLMConfigurationError
from app.core.errors import AgentServiceError
from app.integrations.llm.errors import (
    LLMProviderConfigurationError,
    LLMProviderConnectionError,
    LLMProviderHTTPError,
    LLMProviderResponseError,
    LLMProviderTimeoutError,
)
from app.main import (
    app,
    handle_agent_service_error,
    handle_request_validation_error,
    handle_unexpected_error,
)
from app.schemas.attempt_event_summary import (
    AttemptEventSummaryInput,
    AttemptEventSummaryStatus,
    validate_attempt_event_summary_output,
)
from app.services.validation import (
    WorkflowInputValidationError,
    WorkflowOutputValidationError,
)
from app.core.correlation import CORRELATION_ID_HEADER


def request_with_correlation(correlation_id: str = "issue25-test-id") -> Request:
    return Request(
        {
            "type": "http",
            "http_version": "1.1",
            "method": "POST",
            "scheme": "http",
            "path": "/test-only-error-handler-invocation",
            "raw_path": b"/test-only-error-handler-invocation",
            "query_string": b"",
            "headers": [(b"x-correlation-id", correlation_id.encode("ascii"))],
            "server": ("testserver", 80),
            "client": ("testclient", 1),
            "root_path": "",
        }
    )


def response_payload(response) -> dict[str, object]:
    assert response.headers[CORRELATION_ID_HEADER] == "issue25-test-id"
    return json.loads(response.body)


@pytest.mark.parametrize(
    ("error", "status_code", "code"),
    [
        (LLMConfigurationError(("api_key",)), 503, "llm_configuration_error"),
        (WorkflowInputValidationError(), 422, "workflow_input_invalid"),
        (
            LLMProviderConfigurationError(),
            503,
            "provider_configuration_error",
        ),
        (LLMProviderConnectionError(), 503, "provider_connection_error"),
        (LLMProviderTimeoutError(), 504, "provider_timeout"),
        (LLMProviderHTTPError(429), 502, "provider_http_error"),
        (LLMProviderResponseError(), 502, "provider_response_error"),
        (WorkflowOutputValidationError(), 502, "workflow_output_invalid"),
    ],
)
def test_service_errors_use_stable_http_mapping_and_safe_envelope(
    error: AgentServiceError, status_code: int, code: str
) -> None:
    response = asyncio.run(handle_agent_service_error(request_with_correlation(), error))

    assert response.status_code == status_code
    assert response_payload(response) == {
        "error": {"code": code, "message": error.public_message},
        "correlation_id": "issue25-test-id",
    }
    assert "placeholder-secret" not in response.body.decode()


def test_request_validation_response_does_not_return_rejected_input(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO)
    rejected_data = "private-assessment-payload-secret"
    exc = RequestValidationError(
        [
            {
                "loc": ("body", "field"),
                "msg": "invalid value",
                "type": "value_error",
                "input": rejected_data,
            }
        ]
    )

    response = asyncio.run(handle_request_validation_error(request_with_correlation(), exc))

    assert response.status_code == 422
    assert response_payload(response) == {
        "error": {
            "code": "request_validation_error",
            "message": "Request validation failed.",
        },
        "correlation_id": "issue25-test-id",
    }
    assert rejected_data not in response.body.decode()
    assert rejected_data not in caplog.text


def test_unexpected_error_is_generic_and_does_not_log_exception_text(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.ERROR)
    sensitive_details = "provider-body-with-private-assessment-data"

    response = asyncio.run(
        handle_unexpected_error(
            request_with_correlation(), RuntimeError(sensitive_details)
        )
    )

    assert response.status_code == 500
    assert response_payload(response) == {
        "error": {
            "code": "internal_error",
            "message": "An internal error occurred.",
        },
        "correlation_id": "issue25-test-id",
    }
    assert sensitive_details not in response.body.decode()
    assert sensitive_details not in caplog.text


def test_correlation_id_is_returned_or_replaced_when_invalid() -> None:
    from fastapi.testclient import TestClient

    client = TestClient(app)
    accepted = client.get("/health", headers={CORRELATION_ID_HEADER: "valid:request-1"})
    rejected = client.get("/health", headers={CORRELATION_ID_HEADER: "bad id"})

    assert accepted.headers[CORRELATION_ID_HEADER] == "valid:request-1"
    generated = rejected.headers[CORRELATION_ID_HEADER]
    assert generated != "bad id"
    assert re.fullmatch(r"[0-9a-f]{32}", generated)


def test_empty_and_insufficient_are_workflow_outcomes_not_service_errors() -> None:
    source = AttemptEventSummaryInput.model_validate(
        {
            "events": [
                {
                    "event_type": "TabHidden",
                    "occurred_at": "2026-11-25T10:15:30Z",
                    "duration_seconds": None,
                }
            ]
        }
    )
    insufficient = validate_attempt_event_summary_output(
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
        source,
    )

    assert insufficient.status is AttemptEventSummaryStatus.INSUFFICIENT_DATA
    assert AttemptEventSummaryStatus.EMPTY.value == "empty"
    assert not isinstance(insufficient, AgentServiceError)
    assert AttemptEventSummaryStatus.EMPTY.value == "empty"
    assert not isinstance(AttemptEventSummaryStatus.EMPTY, AgentServiceError)
    assert LLMProviderConnectionError.http_status_code == 503
