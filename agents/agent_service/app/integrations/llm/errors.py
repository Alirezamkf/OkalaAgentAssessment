"""Safe, provider-neutral errors for LLM requests."""

from app.core.errors import AgentServiceError


class LLMProviderError(AgentServiceError):
    code = "provider_error"
    message = "The LLM provider request failed."
    public_message = "The AI provider could not complete the request."
    http_status_code = 503



class LLMProviderConfigurationError(LLMProviderError):
    code = "provider_configuration_error"
    message = "LLM provider configuration is incomplete or invalid."
    public_message = "The AI provider is temporarily unavailable."
    http_status_code = 503


class LLMProviderTimeoutError(LLMProviderError):
    code = "provider_timeout"
    message = "The LLM provider request timed out."
    public_message = "The AI provider request timed out."
    http_status_code = 504


class LLMProviderConnectionError(LLMProviderError):
    code = "provider_connection_error"
    message = "The LLM provider could not be reached."
    public_message = "The AI provider is temporarily unavailable."
    http_status_code = 503


class LLMProviderHTTPError(LLMProviderError):
    code = "provider_http_error"
    message = "The LLM provider returned an unsuccessful HTTP response."
    public_message = "The AI provider could not complete the request."
    http_status_code = 502

    def __init__(self, status_code: int) -> None:
        self.status_code = status_code
        super().__init__()


class LLMProviderResponseError(LLMProviderError):
    code = "provider_response_error"
    message = "The LLM provider returned a malformed or invalid response."
    public_message = "The AI provider returned an unusable response."
    http_status_code = 502
