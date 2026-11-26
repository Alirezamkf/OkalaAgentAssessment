"""Authenticated HTTP client boundary for the independent Agent Service."""

from typing import Any, Protocol

from pydantic import SecretStr


WORKFLOW_ENDPOINTS = frozenset(
    {
        "/api/v1/workflows/attempt-event-summary",
        "/api/v1/workflows/hr-reporting",
    }
)


class AgentServiceAuthenticationNotConfiguredError(RuntimeError):
    """Raised before transport when Backend has no Agent Service credential."""

    code = "agent_service_auth_not_configured"
    message = "Agent Service authentication is not configured."

    def __init__(self) -> None:
        super().__init__(self.message)


class AgentServiceUnavailableError(RuntimeError):
    """Safe Backend-facing error that does not retain transport details."""

    code = "agent_service_unavailable"
    message = "Agent Service is unavailable."

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


class AsyncHTTPTransport(Protocol):
    async def post(
        self,
        url: str,
        *,
        json: Any,
        headers: dict[str, str],
    ) -> Any: ...


class AgentServiceClient:
    """Post permitted workflow payloads with the Backend service credential.

    The HTTP transport is injected so its lifecycle and timeout policy remain
    owned by the Backend application. No request is sent without credentials.
    """

    def __init__(
        self,
        transport: AsyncHTTPTransport,
        *,
        base_url: str,
        shared_secret: SecretStr | None,
    ) -> None:
        self._transport = transport
        self._base_url = base_url.rstrip("/")
        self._shared_secret = shared_secret

    @classmethod
    def from_settings(cls, transport: AsyncHTTPTransport) -> "AgentServiceClient":
        """Build from Backend configuration; the service secret is optional."""

        from app.core.config import settings

        return cls(
            transport,
            base_url=settings.agent_service_url,
            shared_secret=settings.agent_service_shared_secret,
        )

    async def post_workflow(self, path: str, payload: Any) -> Any:
        """Send a request to one of the two contract-defined workflow paths."""

        if path not in WORKFLOW_ENDPOINTS:
            raise ValueError("unsupported Agent Service workflow endpoint")

        secret = self._shared_secret
        if secret is None or not secret.get_secret_value().strip():
            raise AgentServiceAuthenticationNotConfiguredError()

        try:
            response = await self._transport.post(
                f"{self._base_url}{path}",
                json=payload,
                headers={
                    "Authorization": f"AgentService {secret.get_secret_value()}"
                },
            )
            status_code = getattr(response, "status_code", None)
            if status_code is not None:
                if not isinstance(status_code, int):
                    raise AgentServiceUnavailableError()
                if not 200 <= status_code < 300:
                    raise AgentServiceHTTPError(status_code)
            return response
        except AgentServiceHTTPError:
            raise
        except AgentServiceUnavailableError:
            raise
        except Exception:
            # Transport exceptions may retain the request and its headers.
            raise AgentServiceUnavailableError() from None
