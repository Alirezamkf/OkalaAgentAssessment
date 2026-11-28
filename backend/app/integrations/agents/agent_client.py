"""Authenticated, reusable HTTP client boundary for the Agent Service."""

import logging
import math
import time
from datetime import datetime, timezone
from typing import Any

import httpx
from pydantic import SecretStr, ValidationError

from app.core.config import (
    DEFAULT_AGENT_SERVICE_CONNECT_TIMEOUT_SECONDS,
    DEFAULT_AGENT_SERVICE_REQUEST_TIMEOUT_SECONDS,
    load_agent_service_timeouts,
)
from app.core.correlation import (
    correlation_id_fingerprint,
    get_current_correlation_id,
    is_valid_correlation_id,
    new_correlation_id,
)
from app.integrations.agents.contracts import (
    AttemptEventSummaryRequest,
    AttemptEventSummaryResponse,
    validate_attempt_event_summary_response,
)


ATTEMPT_EVENT_SUMMARY_PATH = "/api/v1/workflows/attempt-event-summary"
HR_REPORTING_PATH = "/api/v1/workflows/hr-reporting"
WORKFLOW_ENDPOINTS = frozenset({ATTEMPT_EVENT_SUMMARY_PATH, HR_REPORTING_PATH})
WORKFLOW_OPERATIONS = {
    ATTEMPT_EVENT_SUMMARY_PATH: "attempt_event_summary",
    HR_REPORTING_PATH: "hr_reporting",
}
logger = logging.getLogger(__name__)


class AgentServiceAuthenticationNotConfiguredError(RuntimeError):
    """Raised before transport when Backend has no Agent Service credential."""

    code = "agent_service_auth_not_configured"
    message = "Agent Service authentication is not configured."

    def __init__(self) -> None:
        super().__init__(self.message)


class AgentServiceUnavailableError(RuntimeError):
    """Safe Backend-facing error for Agent Service connection failures."""

    code = "agent_service_unavailable"
    message = "Agent Service is unavailable."

    def __init__(self) -> None:
        super().__init__(self.message)


class AgentServiceTimeoutError(RuntimeError):
    """Safe Backend-facing error for connect or request timeouts."""

    code = "agent_service_timeout"
    message = "Agent Service request timed out."

    def __init__(self) -> None:
        super().__init__(self.message)


class AgentServiceResponseError(RuntimeError):
    """Safe error for malformed or contract-invalid successful responses."""

    code = "agent_service_invalid_response"
    message = "Agent Service returned an invalid response."

    def __init__(self) -> None:
        super().__init__(self.message)


class AgentServiceHTTPError(RuntimeError):
    """Safe representation of an unsuccessful Agent Service HTTP response."""

    _ERRORS = {
        401: ("agent_authentication_failed", "Agent Service authentication failed."),
        502: ("agent_service_bad_gateway", "Agent Service could not complete the request."),
        503: ("agent_service_unavailable", "Agent Service is unavailable."),
        504: ("agent_service_timeout", "Agent Service request timed out."),
    }

    def __init__(self, status_code: int) -> None:
        self.http_status_code = status_code
        self.code, message = self._ERRORS.get(
            status_code,
            ("agent_service_error", "Agent Service could not complete the request."),
        )
        super().__init__(message)


class AgentServiceClient:
    """Own and reuse one async HTTP client for protected Agent Service calls.

    Use as an async context manager or call ``aclose`` when the owning
    application lifespan ends. Credentials and request/response bodies are
    never logged or copied into exceptions.
    """

    def __init__(
        self,
        transport: httpx.AsyncBaseTransport | None = None,
        *,
        base_url: str,
        shared_secret: SecretStr | None,
        connection_timeout_seconds: float = DEFAULT_AGENT_SERVICE_CONNECT_TIMEOUT_SECONDS,
        request_timeout_seconds: float = DEFAULT_AGENT_SERVICE_REQUEST_TIMEOUT_SECONDS,
    ) -> None:
        if (
            not math.isfinite(connection_timeout_seconds)
            or not math.isfinite(request_timeout_seconds)
            or connection_timeout_seconds <= 0
            or request_timeout_seconds <= 0
        ):
            raise ValueError("Agent Service timeouts must be positive")
        self._base_url = base_url.rstrip("/")
        self._shared_secret = shared_secret
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            transport=transport,
            timeout=httpx.Timeout(
                timeout=request_timeout_seconds,
                connect=connection_timeout_seconds,
            ),
        )

    @classmethod
    def from_settings(
        cls,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> "AgentServiceClient":
        """Build the reusable client from centralized Backend settings."""

        from app.core.config import settings

        connect_timeout, request_timeout = load_agent_service_timeouts()
        return cls(
            transport,
            base_url=settings.agent_service_url,
            shared_secret=settings.agent_service_shared_secret,
            connection_timeout_seconds=connect_timeout,
            request_timeout_seconds=request_timeout,
        )

    async def __aenter__(self) -> "AgentServiceClient":
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        await self._client.aclose()

    async def post_workflow(
        self,
        path: str,
        payload: Any,
        *,
        correlation_id: str | None = None,
        _log_operation: bool = True,
    ) -> httpx.Response:
        """Send JSON to a contract-approved workflow path."""

        if path not in WORKFLOW_ENDPOINTS:
            raise ValueError("unsupported Agent Service workflow endpoint")

        secret = self._shared_secret
        if secret is None or not secret.get_secret_value().strip():
            raise AgentServiceAuthenticationNotConfiguredError()

        if not is_valid_correlation_id(correlation_id):
            correlation_id = get_current_correlation_id()
        if not is_valid_correlation_id(correlation_id):
            correlation_id = new_correlation_id()

        start_clock = time.perf_counter()
        log_context = {
            "operation": WORKFLOW_OPERATIONS[path],
            "correlation_fingerprint": correlation_id_fingerprint(correlation_id),
            "started_at": datetime.now(timezone.utc).isoformat(),
        }
        if _log_operation:
            logger.info("Backend Agent Service request started", extra=log_context)
        try:
            try:
                headers = {
                    "Authorization": f"AgentService {secret.get_secret_value()}"
                }
                headers["X-Correlation-ID"] = correlation_id
                response = await self._client.post(
                    path,
                    json=payload,
                    headers=headers,
                )
            except httpx.TimeoutException:
                raise AgentServiceTimeoutError() from None
            except httpx.RequestError:
                raise AgentServiceUnavailableError() from None
            except Exception:
                # Custom transport failures can also retain headers or request data.
                raise AgentServiceUnavailableError() from None

            if not 200 <= response.status_code < 300:
                raise AgentServiceHTTPError(response.status_code)
        except Exception as exc:
            failure_category = (
                exc.code
                if isinstance(
                    exc,
                    (
                        AgentServiceAuthenticationNotConfiguredError,
                        AgentServiceUnavailableError,
                        AgentServiceTimeoutError,
                        AgentServiceResponseError,
                        AgentServiceHTTPError,
                    ),
                )
                else "request_failed"
            )
            if _log_operation:
                logger.warning(
                    "Backend Agent Service request completed",
                    extra={
                        **log_context,
                        "completed_at": datetime.now(timezone.utc).isoformat(),
                        "duration_ms": (time.perf_counter() - start_clock) * 1000,
                        "outcome": "failure",
                        "failure_category": failure_category,
                    },
                )
            raise

        if _log_operation:
            logger.info(
                "Backend Agent Service request completed",
                extra={
                    **log_context,
                    "completed_at": datetime.now(timezone.utc).isoformat(),
                    "duration_ms": (time.perf_counter() - start_clock) * 1000,
                    "outcome": "success",
                    "http_status": response.status_code,
                },
            )
        return response

    async def summarize_attempt_events(
        self,
        payload: AttemptEventSummaryRequest,
    ) -> AttemptEventSummaryResponse:
        """Invoke AI-FR-01 using the strict Backend-local wire contract."""

        try:
            request = AttemptEventSummaryRequest.model_validate(payload)
        except ValidationError:
            raise ValueError("Attempt Event Summary request is invalid") from None

        correlation_id = get_current_correlation_id()
        if not is_valid_correlation_id(correlation_id):
            correlation_id = new_correlation_id()
        started_at = datetime.now(timezone.utc).isoformat()
        start_clock = time.perf_counter()
        log_context = {
            "operation": "attempt_event_summary",
            "correlation_fingerprint": correlation_id_fingerprint(correlation_id),
            "started_at": started_at,
        }
        logger.info("Backend Agent Service workflow started", extra=log_context)
        try:
            response = await self.post_workflow(
                ATTEMPT_EVENT_SUMMARY_PATH,
                request.model_dump(mode="json"),
                correlation_id=correlation_id,
                _log_operation=False,
            )
            body = response.json()
            result = validate_attempt_event_summary_response(body, request)
        except Exception as exc:
            failure_category = (
                exc.code
                if isinstance(
                    exc,
                    (
                        AgentServiceAuthenticationNotConfiguredError,
                        AgentServiceUnavailableError,
                        AgentServiceTimeoutError,
                        AgentServiceResponseError,
                        AgentServiceHTTPError,
                    ),
                )
                else "request_failed"
            )
            logger.warning(
                "Backend Agent Service workflow completed",
                extra={
                    **log_context,
                    "completed_at": datetime.now(timezone.utc).isoformat(),
                    "duration_ms": (time.perf_counter() - start_clock) * 1000,
                    "outcome": "failure",
                    "failure_category": failure_category,
                },
            )
            if isinstance(exc, (ValueError, TypeError)):
                raise AgentServiceResponseError() from None
            raise

        logger.info(
            "Backend Agent Service workflow completed",
            extra={
                **log_context,
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "duration_ms": (time.perf_counter() - start_clock) * 1000,
                "outcome": "success",
            },
        )
        return result
