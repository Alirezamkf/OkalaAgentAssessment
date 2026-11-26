"""Backend-to-Agent Service authentication for protected workflow routes."""

import hmac

from fastapi import Request

from app.core.config import load_agent_service_auth_settings
from app.core.errors import AgentServiceError


class AgentServiceAuthNotConfiguredError(AgentServiceError):
    code = "agent_service_auth_not_configured"
    message = "Agent Service authentication is not configured."
    public_message = "The Agent Service is not configured to accept protected requests."
    http_status_code = 503


class AgentServiceAuthenticationError(AgentServiceError):
    code = "agent_authentication_failed"
    message = "Agent Service authentication failed."
    public_message = "Agent Service authentication failed."
    http_status_code = 401
    response_headers = {"WWW-Authenticate": "AgentService"}


def require_backend_service_auth(request: Request) -> None:
    """Reject protected requests unless they carry the configured shared secret."""

    settings = load_agent_service_auth_settings()
    expected_secret = settings.shared_secret
    if expected_secret is None:
        raise AgentServiceAuthNotConfiguredError()

    authorization_values = request.headers.getlist("authorization")
    if len(authorization_values) != 1:
        raise AgentServiceAuthenticationError()

    authorization = authorization_values[0]
    scheme, separator, credential = authorization.partition(" ")
    if (
        not separator
        or scheme.casefold() != "agentservice".casefold()
        or not credential
        or credential != credential.strip()
        or any(character.isspace() for character in credential)
        or "," in credential
    ):
        raise AgentServiceAuthenticationError()

    expected = expected_secret.get_secret_value()
    if not hmac.compare_digest(credential.encode("utf-8"), expected.encode("utf-8")):
        raise AgentServiceAuthenticationError()
