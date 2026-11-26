import asyncio
import json
import logging

import pytest
from fastapi import APIRouter, FastAPI, Request
from fastapi.testclient import TestClient

from app.api.v1.workflows import create_protected_workflow_router
from app.core.authentication import (
    AgentServiceAuthenticationError,
    AgentServiceAuthNotConfiguredError,
    require_backend_service_auth,
)
from app.core.config import load_agent_service_auth_settings
from app.core.correlation import CORRELATION_ID_HEADER
from app.core.errors import AgentServiceError
from app.main import app, handle_agent_service_error


def make_request(*authorization_values: str) -> Request:
    headers = [(b"x-correlation-id", b"service-auth-test")]
    headers.extend(
        (b"authorization", value.encode("utf-8"))
        for value in authorization_values
    )
    return Request(
        {
            "type": "http",
            "http_version": "1.1",
            "method": "POST",
            "scheme": "http",
            "path": "/api/v1/workflows/test",
            "raw_path": b"/api/v1/workflows/test",
            "query_string": b"",
            "headers": headers,
            "server": ("testserver", 80),
            "client": ("testclient", 1),
            "root_path": "",
        }
    )


def test_loads_secret_without_exposing_it() -> None:
    secret = "high-entropy-placeholder"
    settings = load_agent_service_auth_settings(
        {"AGENT_SERVICE_SHARED_SECRET": secret}
    )

    assert settings.shared_secret is not None
    assert settings.shared_secret.get_secret_value() == secret
    assert secret not in str(settings)
    assert secret not in repr(settings)


def test_missing_secret_does_not_disable_public_health_but_blocks_protected_calls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("AGENT_SERVICE_SHARED_SECRET", raising=False)
    response = TestClient(app).get("/health")
    assert response.status_code == 200

    with pytest.raises(AgentServiceAuthNotConfiguredError):
        require_backend_service_auth(make_request("AgentService any-value"))


def test_valid_backend_credential_is_accepted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AGENT_SERVICE_SHARED_SECRET", "shared-secret-for-tests")

    assert (
        require_backend_service_auth(
            make_request("AgentService shared-secret-for-tests")
        )
        is None
    )


@pytest.mark.parametrize(
    "authorization_values",
    [
        (),
        ("AgentService wrong-secret",),
        ("Bearer shared-secret-for-tests",),
        ("AgentService",),
        ("AgentService  shared-secret-for-tests",),
        ("AgentService shared-secret-for-tests extra",),
        ("AgentService shared-secret-for-tests", "AgentService shared-secret-for-tests"),
    ],
)
def test_missing_invalid_and_malformed_credentials_are_rejected(
    monkeypatch: pytest.MonkeyPatch,
    authorization_values: tuple[str, ...],
) -> None:
    monkeypatch.setenv("AGENT_SERVICE_SHARED_SECRET", "shared-secret-for-tests")

    with pytest.raises(AgentServiceAuthenticationError):
        require_backend_service_auth(make_request(*authorization_values))


def test_authentication_error_uses_issue_25_envelope_and_challenge(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.WARNING)
    error = AgentServiceAuthenticationError()
    response = asyncio.run(
        handle_agent_service_error(make_request(), error)
    )

    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "AgentService"
    assert response.headers[CORRELATION_ID_HEADER] == "service-auth-test"
    assert json.loads(response.body) == {
        "error": {
            "code": "agent_authentication_failed",
            "message": "Agent Service authentication failed.",
        },
        "correlation_id": "service-auth-test",
    }
    assert "shared-secret" not in caplog.text


def test_rejected_credential_is_not_returned_or_logged(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    configured_secret = "configured-secret-never-log"
    supplied_secret = "attacker-supplied-secret-never-log"
    monkeypatch.setenv("AGENT_SERVICE_SHARED_SECRET", configured_secret)
    caplog.set_level(logging.WARNING)

    failed_request = make_request(f"AgentService {supplied_secret}")
    with pytest.raises(AgentServiceAuthenticationError) as error:
        require_backend_service_auth(failed_request)

    response = asyncio.run(
        handle_agent_service_error(failed_request, error.value)
    )
    response_text = response.body.decode()
    for secret in (configured_secret, supplied_secret):
        assert secret not in response_text
        assert secret not in caplog.text


def test_missing_agent_side_configuration_uses_safe_503_envelope() -> None:
    error = AgentServiceAuthNotConfiguredError()
    response = asyncio.run(handle_agent_service_error(make_request(), error))

    assert response.status_code == 503
    assert json.loads(response.body) == {
        "error": {
            "code": "agent_service_auth_not_configured",
            "message": "The Agent Service is not configured to accept protected requests.",
        },
        "correlation_id": "service-auth-test",
    }


def test_routes_registered_through_workflow_router_require_authentication(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AGENT_SERVICE_SHARED_SECRET", "workflow-router-test-secret")
    workflow_router = create_protected_workflow_router()
    test_routes = APIRouter()

    @test_routes.post("/test-only")
    def test_only_workflow() -> dict[str, str]:
        return {"result": "ok"}

    workflow_router.include_router(test_routes)
    test_app = FastAPI()
    test_app.add_exception_handler(AgentServiceError, handle_agent_service_error)
    test_app.include_router(workflow_router)

    response = TestClient(test_app).post(
        "/api/v1/workflows/test-only", json={}
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "agent_authentication_failed"
