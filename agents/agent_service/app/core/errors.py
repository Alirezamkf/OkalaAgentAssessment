"""Provider-neutral error and API response contract for Agent Service."""

from pydantic import BaseModel, ConfigDict


class AgentServiceError(Exception):
    """Base class for safe, typed errors that can cross the service boundary."""

    code = "agent_service_error"
    message = "The Agent Service could not complete the request."
    public_message = "The Agent Service could not complete the request."
    http_status_code = 500

    def __init__(self, message: str | None = None) -> None:
        # Exception text is safe by contract. Subclasses may retain a more
        # specific internal message while `public_message` remains API-safe.
        super().__init__(self.message if message is None else message)


class ErrorDetail(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    message: str


class ErrorResponse(BaseModel):
    """Stable JSON envelope returned for all handled API failures."""

    model_config = ConfigDict(extra="forbid")

    error: ErrorDetail
    correlation_id: str
