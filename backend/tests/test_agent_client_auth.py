import asyncio

import pytest
from pydantic import SecretStr

from app.core.config import load_agent_service_shared_secret
from app.integrations.agents.agent_client import (
    AgentServiceAuthenticationNotConfiguredError,
    AgentServiceClient,
    AgentServiceHTTPError,
    AgentServiceUnavailableError,
)


class FakeTransport:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    async def post(self, url: str, *, json: object, headers: dict[str, str]) -> object:
        self.calls.append({"url": url, "json": json, "headers": headers})
        return {"status": "sent"}


def test_backend_shared_secret_is_optional_for_startup() -> None:
    assert load_agent_service_shared_secret({}) is None
    assert load_agent_service_shared_secret(
        {"AGENT_SERVICE_SHARED_SECRET": "  "}
    ) is None


def test_client_attaches_dedicated_agent_service_authorization_header() -> None:
    transport = FakeTransport()
    client = AgentServiceClient(
        transport,
        base_url="http://agent-service:8001/",
        shared_secret=SecretStr("shared-secret-for-tests"),
    )

    response = asyncio.run(
        client.post_workflow(
            "/api/v1/workflows/hr-reporting",
            {"category": "recording_completeness"},
        )
    )

    assert response == {"status": "sent"}
    assert transport.calls == [
        {
            "url": "http://agent-service:8001/api/v1/workflows/hr-reporting",
            "json": {"category": "recording_completeness"},
            "headers": {"Authorization": "AgentService shared-secret-for-tests"},
        }
    ]


@pytest.mark.parametrize(
    ("status_code", "expected_code"),
    [
        (401, "agent_authentication_failed"),
        (503, "agent_service_unavailable"),
    ],
)
def test_client_converts_unsuccessful_http_responses_to_safe_errors(
    status_code: int, expected_code: str
) -> None:
    response_secret = "response-body-must-not-leak"

    class FailedResponse:
        def __init__(self) -> None:
            self.status_code = status_code
            self.text = response_secret

    class ResponseTransport(FakeTransport):
        async def post(self, url: str, *, json: object, headers: dict[str, str]) -> object:
            self.calls.append({"url": url, "json": json, "headers": headers})
            return FailedResponse()

    credential = "credential-must-not-leak"
    client = AgentServiceClient(
        ResponseTransport(),
        base_url="http://agent-service:8001",
        shared_secret=SecretStr(credential),
    )

    with pytest.raises(AgentServiceHTTPError) as error:
        asyncio.run(
            client.post_workflow(
                "/api/v1/workflows/hr-reporting", {"category": "recording_completeness"}
            )
        )

    assert error.value.code == expected_code
    assert error.value.http_status_code == status_code
    assert response_secret not in str(error.value)
    assert credential not in str(error.value)


@pytest.mark.parametrize("secret", [None, SecretStr("  ")])
def test_client_fails_safely_without_credential_and_sends_no_request(secret) -> None:
    transport = FakeTransport()
    client = AgentServiceClient(
        transport,
        base_url="http://agent-service:8001",
        shared_secret=secret,
    )

    with pytest.raises(AgentServiceAuthenticationNotConfiguredError) as error:
        asyncio.run(
            client.post_workflow(
                "/api/v1/workflows/attempt-event-summary", {"events": []}
            )
        )

    assert error.value.code == "agent_service_auth_not_configured"
    assert "shared-secret" not in str(error.value)
    assert transport.calls == []


def test_client_rejects_unapproved_workflow_path_before_transport() -> None:
    transport = FakeTransport()
    client = AgentServiceClient(
        transport,
        base_url="http://agent-service:8001",
        shared_secret=SecretStr("shared-secret-for-tests"),
    )

    with pytest.raises(ValueError, match="unsupported Agent Service workflow endpoint"):
        asyncio.run(client.post_workflow("/health", {}))

    assert transport.calls == []


def test_transport_error_is_safe_and_does_not_retain_credentials() -> None:
    class FailingTransport:
        async def post(self, url: str, *, json: object, headers: dict[str, str]) -> object:
            raise RuntimeError(f"failed request with headers {headers!r}")

    secret = "private-service-credential"
    client = AgentServiceClient(
        FailingTransport(),
        base_url="http://agent-service:8001",
        shared_secret=SecretStr(secret),
    )

    with pytest.raises(AgentServiceUnavailableError) as error:
        asyncio.run(
            client.post_workflow(
                "/api/v1/workflows/hr-reporting", {"category": "recording_completeness"}
            )
        )

    assert secret not in str(error.value)
