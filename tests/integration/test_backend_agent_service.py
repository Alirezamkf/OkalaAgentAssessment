"""In-process integration tests for the Backend-to-Agent HTTP boundary."""

from __future__ import annotations

import importlib
import asyncio
import json
import logging
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any

import httpx
import pytest
from pydantic import SecretStr


ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = ROOT / "backend"
AGENT_ROOT = ROOT / "agents" / "agent_service"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.integrations.agents.agent_client import (  # noqa: E402
    AgentServiceAuthenticationNotConfiguredError,
    AgentServiceClient,
    AgentServiceHTTPError,
    AgentServiceResponseError,
)


def _load_agent_application() -> tuple[ModuleType, Any]:
    """Load Agent Service's `app` package without mixing Backend's `app` modules."""

    backend_modules = {
        name: module
        for name, module in sys.modules.items()
        if name == "app" or name.startswith("app.")
    }
    for name in backend_modules:
        sys.modules.pop(name, None)
    sys.path.insert(0, str(AGENT_ROOT))
    try:
        agent_main = importlib.import_module("app.main")
        agent_api = importlib.import_module("app.api.v1.attempt_event_summary")
        return agent_main, agent_api.get_llm_provider
    finally:
        for name in tuple(sys.modules):
            if name == "app" or name.startswith("app."):
                sys.modules.pop(name, None)
        sys.path.remove(str(AGENT_ROOT))
        sys.modules.update(backend_modules)


AGENT_MAIN, AGENT_PROVIDER_DEPENDENCY = _load_agent_application()
AGENT_APP = AGENT_MAIN.app


EVENTS = [
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
PAYLOAD = {"events": EVENTS}
SHARED_SECRET = "integration-shared-secret"
CORRELATION_HEADER = "X-Correlation-ID"


class RecordingProvider:
    """Deterministic provider double installed through Agent dependency injection."""

    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.calls: list[dict[str, Any]] = []

    async def generate(
        self,
        prompt: str,
        *,
        response_model: type,
        correlation_id: str | None = None,
    ) -> SimpleNamespace:
        self.calls.append({"prompt": prompt, "correlation_id": correlation_id})
        if self.error is not None:
            raise self.error
        output = response_model.model_validate(
            {
                "status": "success",
                "summary": "در این نمونه دو رویداد ثبت شد.",
                "events": EVENTS,
            }
        )
        return SimpleNamespace(output=output, provider="fake", model="test")


@pytest.fixture(autouse=True)
def clear_dependency_overrides() -> Any:
    AGENT_APP.dependency_overrides.clear()
    yield
    AGENT_APP.dependency_overrides.clear()


class RecordingASGITransport(httpx.AsyncBaseTransport):
    """Forward Backend requests to the actual Agent ASGI app and retain wire data."""

    def __init__(self) -> None:
        self.inner = httpx.ASGITransport(app=AGENT_APP)
        self.requests: list[httpx.Request] = []
        self.responses: list[httpx.Response] = []

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        response = await self.inner.handle_async_request(request)
        self.responses.append(response)
        return response

    async def aclose(self) -> None:
        await self.inner.aclose()


def make_client(
    transport: httpx.AsyncBaseTransport,
    secret: str | None = SHARED_SECRET,
) -> AgentServiceClient:
    return AgentServiceClient(
        transport,
        base_url="http://agent-service.test",
        shared_secret=SecretStr(secret) if secret is not None else None,
    )


async def summarize(client: AgentServiceClient, payload: Any = PAYLOAD) -> Any:
    async with client:
        return await client.summarize_attempt_events(payload)


def test_backend_client_successfully_calls_protected_agent_and_preserves_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AGENT_SERVICE_SHARED_SECRET", SHARED_SECRET)
    provider = RecordingProvider()
    AGENT_APP.dependency_overrides[AGENT_PROVIDER_DEPENDENCY] = lambda: provider
    transport = RecordingASGITransport()

    result = asyncio.run(summarize(make_client(transport)))

    assert result.model_dump(mode="json") == {
        "status": "success",
        "summary": "در این نمونه دو رویداد ثبت شد.",
        "events": EVENTS,
    }
    assert len(transport.requests) == len(transport.responses) == 1
    request = transport.requests[0]
    assert request.method == "POST"
    assert request.url.path == "/api/v1/workflows/attempt-event-summary"
    assert request.headers["authorization"] == f"AgentService {SHARED_SECRET}"
    assert json.loads(request.content) == PAYLOAD
    assert transport.responses[0].status_code == 200
    assert CORRELATION_HEADER in transport.responses[0].headers
    assert len(provider.calls) == 1
    assert provider.calls[0]["correlation_id"] == transport.responses[0].headers[
        CORRELATION_HEADER
    ]


def test_wrong_backend_credential_is_rejected_by_actual_agent_endpoint(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.setenv("AGENT_SERVICE_SHARED_SECRET", SHARED_SECRET)
    provider = RecordingProvider()
    AGENT_APP.dependency_overrides[AGENT_PROVIDER_DEPENDENCY] = lambda: provider
    transport = RecordingASGITransport()
    wrong_secret = "wrong-secret-must-not-leak"

    caplog.set_level(logging.DEBUG)
    with pytest.raises(AgentServiceHTTPError) as caught:
        asyncio.run(
            summarize(make_client(transport, secret=wrong_secret))
        )

    assert caught.value.code == "agent_authentication_failed"
    assert transport.responses[0].status_code == 401
    assert provider.calls == []
    assert wrong_secret not in str(caught.value)
    assert wrong_secret not in caplog.text
    assert SHARED_SECRET not in caplog.text


def test_missing_backend_credential_fails_before_any_transport_request() -> None:
    transport = RecordingASGITransport()

    with pytest.raises(AgentServiceAuthenticationNotConfiguredError) as caught:
        asyncio.run(summarize(make_client(transport, secret=None)))

    assert caught.value.code == "agent_service_auth_not_configured"
    assert transport.requests == []


def test_agent_http_boundary_rejects_invalid_payload_before_provider_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Direct route case: Backend's strict client rejects bad input before sending it."""

    from fastapi.testclient import TestClient

    monkeypatch.setenv("AGENT_SERVICE_SHARED_SECRET", SHARED_SECRET)
    provider = RecordingProvider()
    AGENT_APP.dependency_overrides[AGENT_PROVIDER_DEPENDENCY] = lambda: provider
    bad_payload = {
        "events": [
            {
                **EVENTS[0],
                "question_text": "private-question-sentinel",
            }
        ]
    }

    response = TestClient(AGENT_APP).post(
        "/api/v1/workflows/attempt-event-summary",
        json=bad_payload,
        headers={"Authorization": f"AgentService {SHARED_SECRET}"},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "request_validation_error"
    assert "private-question-sentinel" not in response.text
    assert provider.calls == []


def test_agent_provider_failure_returns_safe_error_to_backend_client(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.setenv("AGENT_SERVICE_SHARED_SECRET", SHARED_SECRET)
    provider_secret = "provider-secret-sentinel"
    # Reuse the typed error class imported by the already-loaded Agent app so
    # its AgentServiceError base class is the exact one registered by FastAPI.
    provider_adapter = AGENT_PROVIDER_DEPENDENCY.__globals__["OpenAICompatibleProvider"]
    timeout_error = provider_adapter.generate.__globals__["LLMProviderTimeoutError"]
    provider = RecordingProvider(error=timeout_error(provider_secret))
    AGENT_APP.dependency_overrides[AGENT_PROVIDER_DEPENDENCY] = lambda: provider
    transport = RecordingASGITransport()
    caplog.set_level(logging.DEBUG)

    with pytest.raises(AgentServiceHTTPError) as caught:
        asyncio.run(summarize(make_client(transport)))

    assert caught.value.code == "agent_service_timeout"
    assert caught.value.http_status_code == 504
    assert str(caught.value) == "Agent Service request timed out."
    assert transport.responses[0].status_code == 504
    agent_error = transport.responses[0].json()
    assert agent_error["error"] == {
        "code": "provider_timeout",
        "message": "The AI provider request timed out.",
    }
    assert "correlation_id" in agent_error
    assert provider_secret not in transport.responses[0].text
    assert provider_secret not in str(caught.value)
    assert SHARED_SECRET not in str(caught.value)
    assert provider_secret not in caplog.text
    assert SHARED_SECRET not in caplog.text
    assert len(provider.calls) == 1


class MalformedResponseTransport(httpx.AsyncBaseTransport):
    """Represent a broken/malformed HTTP peer response at the transport seam."""

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=b"not-json private-response-sentinel",
            request=request,
        )


def test_backend_client_rejects_malformed_agent_http_response_safely() -> None:
    with pytest.raises(AgentServiceResponseError) as caught:
        asyncio.run(
            summarize(make_client(MalformedResponseTransport()))
        )

    assert caught.value.code == "agent_service_invalid_response"
    assert "private-response-sentinel" not in str(caught.value)
    assert "not-json" not in str(caught.value)


def test_fake_provider_input_contains_only_approved_event_facts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AGENT_SERVICE_SHARED_SECRET", SHARED_SECRET)
    provider = RecordingProvider()
    AGENT_APP.dependency_overrides[AGENT_PROVIDER_DEPENDENCY] = lambda: provider

    asyncio.run(summarize(make_client(RecordingASGITransport())))

    prompt = provider.calls[0]["prompt"]
    marker = "Input events (use these values as the sole source of facts):\n"
    serialized_input = prompt.split(marker, maxsplit=1)[1]
    assert json.loads(serialized_input) == PAYLOAD
    assert set(json.loads(serialized_input)["events"][0]) == {
        "event_type",
        "occurred_at",
        "duration_seconds",
    }
    for prohibited in (
        "private-video-sentinel",
        "private-image-sentinel",
        "private-question-sentinel",
        "private-answer-key-sentinel",
        "private-candidate-answer-sentinel",
    ):
        assert prohibited not in prompt

