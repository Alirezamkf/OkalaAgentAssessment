"""Safe, provider-neutral errors for LLM requests."""


class LLMProviderError(RuntimeError):
    code = "provider_error"
    message = "The LLM provider request failed."

    def __init__(self) -> None:
        super().__init__(self.message)


class LLMProviderConfigurationError(LLMProviderError):
    code = "provider_configuration_error"
    message = "LLM provider configuration is incomplete or invalid."


class LLMProviderTimeoutError(LLMProviderError):
    code = "provider_timeout"
    message = "The LLM provider request timed out."


class LLMProviderConnectionError(LLMProviderError):
    code = "provider_connection_error"
    message = "The LLM provider could not be reached."


class LLMProviderHTTPError(LLMProviderError):
    code = "provider_http_error"
    message = "The LLM provider returned an unsuccessful HTTP response."

    def __init__(self, status_code: int) -> None:
        self.status_code = status_code
        super().__init__()


class LLMProviderResponseError(LLMProviderError):
    code = "provider_response_error"
    message = "The LLM provider returned a malformed or invalid response."
