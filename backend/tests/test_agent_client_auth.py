import asyncio
import json
import logging
from typing import Any

import httpx
import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.core.correlation import (
    CORRELATION_ID_HEADER,
    CorrelationIdMiddleware,
    correlation_id_fingerprint,
    get_current_correlation_id,
)
from app.core.config import (
    load_agent_service_shared_secret,
    load_agent_service_timeouts,
    settings,
)
from app.integrations.agents.agent_client import (
    AgentServiceAuthenticationNotConfiguredError,
    AgentServiceClient,
    AgentServiceHTTPError,
    AgentServiceResponseError,
    AgentServiceTimeoutError,
    AgentServiceUnavailableError,
)
from app.integrations.agents.contracts import AttemptEventSummaryRequest


SERVICE_SECRET = "backend-test-shared-key-generated-with-at-least-32-bytes"
CORRELATION_EVENT_TIME_1 = "2026-11-25T10:15:30Z"
CORRELATION_EVENT_TIME_2 = "2026-11-25T10:15:34Z"


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


def valid_payload() -> dict[str, object]:
    return {
        "events": [
            event("TabHidden", CORRELATION_EVENT_TIME_1, 4),
            event("TabVisible", CORRELATION_EVENT_TIME_2, 0),
        ]
    }


def valid_response(payload: dict[str, object] | None = None) -> dict[str, object]:
    body = payload or valid_payload()
    return {
        "status": "success",
        "summary": "دو رخداد به‌ترتیب زمانی ثبت شدند.",
        "events": body["events"],
    }


def make_client(
    handler,
    *,
    secret: SecretStr | None = SecretStr(SERVICE_SECRET),
) -> AgentServiceClient:
    return AgentServiceClient(
        httpx.MockTransport(handler),
        base_url="http://agent-service:8001/",
        shared_secret=secret,
    )


async def summarize_and_close(
    client: AgentServiceClient,
    payload: AttemptEventSummaryRequest | dict[str, Any],
):
    async with client:
        return await client.summarize_attempt_events(payload)


def test_backend_shared_secret_is_optional_for_startup() -> None:
    assert load_agent_service_shared_secret({}) is None
    assert load_agent_service_shared_secret(
        {"AGENT_SERVICE_SHARED_SECRET": "  "}
    ) is None


def test_agent_service_timeouts_have_positive_defaults_and_are_configurable() -> None:
    assert load_agent_service_timeouts({}) == (5.0, 35.0)
    assert load_agent_service_timeouts(
        {
            "AGENT_SERVICE_CONNECT_TIMEOUT_SECONDS": "2.5",
            "AGENT_SERVICE_REQUEST_TIMEOUT_SECONDS": "45",
        }
    ) == (2.5, 45.0)

    with pytest.raises(ValueError, match="AGENT_SERVICE_CONNECT_TIMEOUT_SECONDS"):
        load_agent_service_timeouts({"AGENT_SERVICE_CONNECT_TIMEOUT_SECONDS": "0"})


def test_backend_request_boundary_preserves_valid_correlation_id() -> None:
    app = FastAPI()
    app.add_middleware(CorrelationIdMiddleware)

    @app.get("/correlation")
    async def correlation(request: Request) -> dict[str, str | None]:
        return {
            "state": request.state.correlation_id,
            "context": get_current_correlation_id(),
        }

    correlation_id = "backend-request:valid-123"
    with TestClient(app) as client:
        response = client.get(
            "/correlation", headers={CORRELATION_ID_HEADER: correlation_id}
        )

    assert response.json() == {"state": correlation_id, "context": correlation_id}
    assert response.headers[CORRELATION_ID_HEADER] == correlation_id
    assert get_current_correlation_id() is None


@pytest.mark.parametrize("supplied", [None, "invalid correlation id"])
def test_backend_request_boundary_generates_uuid_for_missing_or_invalid_id(
    supplied: str | None,
) -> None:
    app = FastAPI()
    app.add_middleware(CorrelationIdMiddleware)

    @app.get("/correlation")
    async def correlation(request: Request) -> dict[str, str | None]:
        return {
            "state": request.state.correlation_id,
            "context": get_current_correlation_id(),
        }

    headers = {} if supplied is None else {CORRELATION_ID_HEADER: supplied}
    with TestClient(app) as client:
        response = client.get("/correlation", headers=headers)

    generated = response.json()["state"]
    assert isinstance(generated, str)
    assert len(generated) == 32
    assert all(character in "0123456789abcdef" for character in generated)
    if supplied is not None:
        assert generated != supplied
    assert response.json() == {"state": generated, "context": generated}
    assert response.headers[CORRELATION_ID_HEADER] == generated
    assert get_current_correlation_id() is None


def test_backend_correlation_middleware_is_installed_on_production_app() -> None:
    from app.main import app as backend_app

    assert any(
        middleware.cls is CorrelationIdMiddleware
        for middleware in backend_app.user_middleware
    )


def test_backend_correlation_context_resets_after_request_exception() -> None:
    app = FastAPI()
    app.add_middleware(CorrelationIdMiddleware)

    @app.get("/fail")
    async def fail() -> None:
        assert get_current_correlation_id() == "exception-request-id"
        raise RuntimeError("private request failure")

    @app.get("/echo")
    async def echo() -> dict[str, str | None]:
        return {"correlation_id": get_current_correlation_id()}

    async def exercise() -> None:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://backend.test"
        ) as client:
            with pytest.raises(RuntimeError, match="private request failure"):
                await client.get(
                    "/fail", headers={CORRELATION_ID_HEADER: "exception-request-id"}
                )
            assert get_current_correlation_id() is None
            response = await client.get(
                "/echo", headers={CORRELATION_ID_HEADER: "subsequent-request-id"}
            )
            assert response.json() == {"correlation_id": "subsequent-request-id"}
            assert response.headers[CORRELATION_ID_HEADER] == "subsequent-request-id"
            assert get_current_correlation_id() is None

    asyncio.run(exercise())


def test_backend_correlation_context_isolated_between_overlapping_requests() -> None:
    app = FastAPI()
    app.add_middleware(CorrelationIdMiddleware)

    @app.get("/overlap")
    async def overlap(request: Request) -> dict[str, str | None]:
        before = get_current_correlation_id()
        await request.app.state.barrier.wait()
        await asyncio.sleep(0)
        return {
            "before": before,
            "after": get_current_correlation_id(),
            "state": request.state.correlation_id,
        }

    async def exercise() -> list[httpx.Response]:
        app.state.barrier = asyncio.Barrier(2)
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://backend.test"
        ) as client:
            return await asyncio.gather(
                client.get("/overlap", headers={CORRELATION_ID_HEADER: "overlap-a"}),
                client.get("/overlap", headers={CORRELATION_ID_HEADER: "overlap-b"}),
            )

    responses = asyncio.run(exercise())
    by_id = {response.json()["before"]: response for response in responses}
    assert set(by_id) == {"overlap-a", "overlap-b"}
    for correlation_id, response in by_id.items():
        assert response.json() == {
            "before": correlation_id,
            "after": correlation_id,
            "state": correlation_id,
        }
        assert response.headers[CORRELATION_ID_HEADER] == correlation_id
    assert get_current_correlation_id() is None


def _assert_raw_value_absent_from_records(
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


def test_client_without_request_context_uses_one_generated_id_for_wire_and_logs(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.setenv("AGENT_SERVICE_SHARED_SECRET", SERVICE_SECRET)
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, json=valid_response())

    client = make_client(handler)
    caplog.set_level(logging.INFO)

    async def invoke_twice() -> None:
        async with client:
            await client.summarize_attempt_events(valid_payload())
            await client.summarize_attempt_events(valid_payload())

    asyncio.run(invoke_twice())

    assert get_current_correlation_id() is None
    assert len(captured) == 2
    generated_ids = [request.headers[CORRELATION_ID_HEADER] for request in captured]
    assert generated_ids[0] != generated_ids[1]
    for generated in generated_ids:
        assert len(generated) == 32
        assert all(character in "0123456789abcdef" for character in generated)
        assert sum(
            getattr(record, "correlation_fingerprint", None)
            == correlation_id_fingerprint(generated)
            for record in caplog.records
        ) == 2
        _assert_raw_value_absent_from_records(caplog.records, generated)


def test_from_settings_applies_configured_timeouts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AGENT_SERVICE_CONNECT_TIMEOUT_SECONDS", "2.5")
    monkeypatch.setenv("AGENT_SERVICE_REQUEST_TIMEOUT_SECONDS", "48")
    monkeypatch.setattr(settings, "agent_service_url", "http://agent-service:8001")
    monkeypatch.setattr(settings, "agent_service_shared_secret", SecretStr(SERVICE_SECRET))
    client = AgentServiceClient.from_settings(httpx.MockTransport(lambda request: httpx.Response(200)))

    assert client._client.timeout.connect == 2.5
    assert client._client.timeout.read == 48.0
    asyncio.run(client.aclose())


def test_wire_event_enum_matches_the_exact_approved_twelve_values() -> None:
    from app.integrations.agents.contracts import AttemptEventType

    assert {event_type.value for event_type in AttemptEventType} == {
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


def test_client_sends_typed_request_and_parses_typed_response() -> None:
    captured: list[httpx.Request] = []
    body = valid_response()

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, json=body)

    result = asyncio.run(
        summarize_and_close(
            make_client(handler),
            AttemptEventSummaryRequest.model_validate(valid_payload()),
        )
    )

    assert result.status == "success"
    assert result.model_dump(mode="json") == body
    assert len(captured) == 1
    assert str(captured[0].url) == (
        "http://agent-service:8001/api/v1/workflows/attempt-event-summary"
    )
    assert captured[0].headers["authorization"] == f"AgentService {SERVICE_SECRET}"
    assert json.loads(captured[0].read()) == valid_payload()


def test_multiple_requests_reuse_the_same_async_client() -> None:
    requests: list[httpx.Request] = []
    body = valid_response()

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json=body)

    client = make_client(handler)
    underlying_client = client._client

    async def send_twice() -> None:
        async with client:
            first = await client.summarize_attempt_events(valid_payload())
            second = await client.summarize_attempt_events(valid_payload())
            assert first.model_dump(mode="json") == body
            assert second.model_dump(mode="json") == body

    asyncio.run(send_twice())

    assert len(requests) == 2
    assert client._client is underlying_client
    assert underlying_client.is_closed


def test_client_can_be_closed_multiple_times_safely() -> None:
    client = make_client(lambda request: httpx.Response(200, json=valid_response()))

    async def close_twice() -> None:
        await client.aclose()
        await client.aclose()

    asyncio.run(close_twice())

    assert client._client.is_closed


@pytest.mark.parametrize(
    ("payload", "body"),
    [
        (
            {"events": []},
            {
                "status": "empty",
                "summary": "هیچ رخدادی ثبت نشده است",
                "events": [],
            },
        ),
        (
            {"events": [event("TabHidden", CORRELATION_EVENT_TIME_1, None)]},
            {
                "status": "insufficient_data",
                "summary": None,
                "events": [event("TabHidden", CORRELATION_EVENT_TIME_1, None)],
            },
        ),
    ],
)
def test_client_parses_empty_and_insufficient_contract_outcomes(
    payload: dict[str, object],
    body: dict[str, object],
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=body)

    result = asyncio.run(summarize_and_close(make_client(handler), payload))

    assert result.model_dump(mode="json") == body


def test_typed_request_rejects_unapproved_fields_before_transport() -> None:
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(200, json=valid_response())

    client = make_client(handler)
    payload = valid_payload()
    payload["candidate_id"] = "must-not-be-forwarded"

    with pytest.raises(ValueError, match="Attempt Event Summary request is invalid") as error:
        asyncio.run(summarize_and_close(client, payload))

    assert "must-not-be-forwarded" not in str(error.value)
    assert calls == []


@pytest.mark.parametrize(
    ("status_code", "expected_code"),
    [
        (401, "agent_authentication_failed"),
        (422, "agent_service_error"),
        (502, "agent_service_bad_gateway"),
        (503, "agent_service_unavailable"),
        (504, "agent_service_timeout"),
    ],
)
def test_unsuccessful_http_responses_become_safe_typed_errors(
    status_code: int,
    expected_code: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    response_secret = "private-agent-response-body"
    credential = "private-agent-credential"

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, text=response_secret)

    client = make_client(handler, secret=SecretStr(credential))
    caplog.set_level(logging.DEBUG)
    with pytest.raises(AgentServiceHTTPError) as error:
        asyncio.run(summarize_and_close(client, valid_payload()))

    assert error.value.code == expected_code
    assert error.value.http_status_code == status_code
    for sensitive in (response_secret, credential, str(valid_payload())):
        assert sensitive not in str(error.value)
        assert sensitive not in caplog.text


def test_timeout_is_distinguished_and_safe() -> None:
    credential = "timeout-secret-never-exposed"

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout(
            f"timeout with credential {credential} and body {request.content!r}",
            request=request,
        )

    client = make_client(handler, secret=SecretStr(credential))
    with pytest.raises(AgentServiceTimeoutError) as error:
        asyncio.run(summarize_and_close(client, valid_payload()))

    assert error.value.code == "agent_service_timeout"
    assert credential not in str(error.value)
    assert str(valid_payload()) not in str(error.value)
    assert error.value.__cause__ is None


def test_connection_failure_is_distinguished_and_safe() -> None:
    credential = "connection-secret-never-exposed"

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError(
            f"connection failed with credential {credential}", request=request
        )

    client = make_client(handler, secret=SecretStr(credential))
    with pytest.raises(AgentServiceUnavailableError) as error:
        asyncio.run(summarize_and_close(client, valid_payload()))

    assert error.value.code == "agent_service_unavailable"
    assert credential not in str(error.value)
    assert error.value.__cause__ is None


def test_unexpected_transport_exception_is_sanitized(
    caplog: pytest.LogCaptureFixture,
) -> None:
    credential = "private-transport-credential"
    sensitive_payload = str(valid_payload())

    def handler(request: httpx.Request) -> httpx.Response:
        raise RuntimeError(f"transport leaked {credential} {sensitive_payload}")

    client = make_client(handler, secret=SecretStr(credential))
    caplog.set_level(logging.DEBUG)
    with pytest.raises(AgentServiceUnavailableError) as error:
        asyncio.run(summarize_and_close(client, valid_payload()))

    assert credential not in str(error.value)
    assert sensitive_payload not in str(error.value)
    assert credential not in caplog.text
    assert sensitive_payload not in caplog.text
    assert error.value.__cause__ is None


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(200, content=b"not json"),
        httpx.Response(
            200,
            json={"status": "success", "summary": "Only some fields", "events": []},
        ),
        httpx.Response(
            200,
            json={
                **valid_response(),
                "unexpected_sensitive_field": "private-response-value",
            },
        ),
        httpx.Response(
            200,
            json={**valid_response(), "summary": "این رخداد مشکوک است."},
        ),
        httpx.Response(
            200,
            json={**valid_response(), "events": [event("TabHidden", CORRELATION_EVENT_TIME_1)]},
        ),
    ],
)
def test_malformed_or_contract_invalid_response_is_safe(
    response: httpx.Response,
    caplog: pytest.LogCaptureFixture,
) -> None:
    sensitive = "private-response-value"

    def handler(request: httpx.Request) -> httpx.Response:
        return response

    client = make_client(handler)
    caplog.set_level(logging.DEBUG)
    with pytest.raises(AgentServiceResponseError) as error:
        asyncio.run(summarize_and_close(client, valid_payload()))

    assert error.value.code == "agent_service_invalid_response"
    assert sensitive not in str(error.value)
    assert sensitive not in caplog.text
    assert str(valid_payload()) not in str(error.value)


def test_missing_credential_fails_before_sending_request() -> None:
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(200, json=valid_response())

    client = make_client(handler, secret=None)
    with pytest.raises(AgentServiceAuthenticationNotConfiguredError) as error:
        asyncio.run(summarize_and_close(client, valid_payload()))

    assert error.value.code == "agent_service_auth_not_configured"
    assert calls == []


def test_client_rejects_unapproved_workflow_path_before_transport() -> None:
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(200, json={})

    client = make_client(handler)

    async def invoke() -> None:
        async with client:
            await client.post_workflow("/health", {})

    with pytest.raises(ValueError, match="unsupported Agent Service workflow endpoint"):
        asyncio.run(invoke())

    assert calls == []
