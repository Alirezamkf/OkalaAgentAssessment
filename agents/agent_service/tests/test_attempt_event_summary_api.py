from typing import Any, TypeVar

import pytest
from fastapi.testclient import TestClient
from pydantic import BaseModel

from app.core.correlation import CORRELATION_ID_HEADER
from app.integrations.llm.errors import LLMProviderTimeoutError
from app.integrations.llm.protocol import LLMResult
from app.main import app
from app.api.v1.attempt_event_summary import get_llm_provider


OutputT = TypeVar("OutputT", bound=BaseModel)
SERVICE_SECRET = "api-test-shared-secret"


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


def request_events(*events: dict[str, object]) -> dict[str, object]:
    return {"events": list(events)}


def successful_output(payload: dict[str, object]) -> dict[str, object]:
    return {
        "status": "success",
        "summary": "دو رخداد به‌ترتیب زمانی ثبت شدند.",
        "events": payload["events"],
    }


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


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("AGENT_SERVICE_SHARED_SECRET", SERVICE_SECRET)
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def authorized_headers(**headers: str) -> dict[str, str]:
    return {
        "Authorization": f"AgentService {SERVICE_SECRET}",
        **headers,
    }


def test_authenticated_request_returns_summary_and_propagates_correlation_id(
    client: TestClient,
) -> None:
    payload = request_events(
        event("TabHidden", "2026-11-25T10:15:30Z", 4),
        event("TabVisible", "2026-11-25T10:15:34Z", 0),
    )
    provider = FakeProvider(successful_output(payload))
    app.dependency_overrides[get_llm_provider] = lambda: provider
    correlation_id = "api-summary-correlation"

    response = client.post(
        "/api/v1/workflows/attempt-event-summary",
        json=payload,
        headers=authorized_headers(**{CORRELATION_ID_HEADER: correlation_id}),
    )

    assert response.status_code == 200
    assert response.json() == successful_output(payload)
    assert response.headers[CORRELATION_ID_HEADER] == correlation_id
    assert len(provider.calls) == 1
    assert provider.calls[0]["correlation_id"] == correlation_id


@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        (
            request_events(),
            {
                "status": "empty",
                "summary": "هیچ رخدادی ثبت نشده است",
                "events": [],
            },
        ),
        (
            request_events(event("TabHidden", "2026-11-25T10:15:30Z", None)),
            {
                "status": "insufficient_data",
                "summary": None,
                "events": [event("TabHidden", "2026-11-25T10:15:30Z", None)],
            },
        ),
    ],
)
def test_deterministic_outcomes_do_not_call_provider(
    client: TestClient,
    payload: dict[str, object],
    expected: dict[str, object],
) -> None:
    provider = FakeProvider()
    app.dependency_overrides[get_llm_provider] = lambda: provider

    response = client.post(
        "/api/v1/workflows/attempt-event-summary",
        json=payload,
        headers=authorized_headers(),
    )

    assert response.status_code == 200
    assert response.json() == expected
    assert provider.calls == []


def test_empty_outcome_does_not_require_llm_configuration(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for setting in (
        "LLM_PROVIDER",
        "LLM_MODEL",
        "LLM_API_ENDPOINT",
        "LLM_API_KEY",
    ):
        monkeypatch.delenv(setting, raising=False)

    response = client.post(
        "/api/v1/workflows/attempt-event-summary",
        json=request_events(),
        headers=authorized_headers(),
    )

    assert response.status_code == 200
    assert response.json() == {
        "status": "empty",
        "summary": "هیچ رخدادی ثبت نشده است",
        "events": [],
    }


def test_invalid_input_uses_safe_request_validation_response(client: TestClient) -> None:
    response = client.post(
        "/api/v1/workflows/attempt-event-summary",
        json=request_events(event("UnsupportedEvent", "2026-11-25T10:15:30Z")),
        headers=authorized_headers(),
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "request_validation_error"
    assert "UnsupportedEvent" not in response.text


def test_unauthorized_request_is_rejected(client: TestClient) -> None:
    response = client.post(
        "/api/v1/workflows/attempt-event-summary",
        json=request_events(),
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "agent_authentication_failed"
    assert response.headers["WWW-Authenticate"] == "AgentService"


def test_provider_failure_uses_shared_error_response(client: TestClient) -> None:
    payload = request_events(
        event("TabHidden", "2026-11-25T10:15:30Z"),
        event("TabVisible", "2026-11-25T10:15:34Z"),
    )
    provider = FakeProvider(error=LLMProviderTimeoutError())
    app.dependency_overrides[get_llm_provider] = lambda: provider

    response = client.post(
        "/api/v1/workflows/attempt-event-summary",
        json=payload,
        headers=authorized_headers(),
    )

    assert response.status_code == 504
    assert response.json()["error"]["code"] == "provider_timeout"


def test_invalid_provider_output_uses_shared_output_validation_error(
    client: TestClient,
) -> None:
    payload = request_events(
        event("TabHidden", "2026-11-25T10:15:30Z"),
        event("TabVisible", "2026-11-25T10:15:34Z"),
    )
    provider = FakeProvider(
        {
            "status": "success",
            "summary": "This is not a Persian factual summary.",
            "events": payload["events"],
        }
    )
    app.dependency_overrides[get_llm_provider] = lambda: provider

    response = client.post(
        "/api/v1/workflows/attempt-event-summary",
        json=payload,
        headers=authorized_headers(),
    )

    assert response.status_code == 502
    assert response.json()["error"]["code"] == "workflow_output_invalid"
