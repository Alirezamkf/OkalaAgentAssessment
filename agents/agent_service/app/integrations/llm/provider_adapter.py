"""Shared async integration for OpenAI-compatible Chat Completions APIs."""

import json
import logging
import re
from typing import TypeVar

import httpx
from pydantic import BaseModel

from app.core.config import LLMSettings, get_llm_settings
from app.integrations.llm.errors import (
    LLMProviderConfigurationError,
    LLMProviderConnectionError,
    LLMProviderHTTPError,
    LLMProviderResponseError,
    LLMProviderTimeoutError,
)
from app.integrations.llm.protocol import LLMResult


logger = logging.getLogger(__name__)
OutputT = TypeVar("OutputT", bound=BaseModel)
_CORRELATION_ID = re.compile(r"[A-Za-z0-9._:-]{1,128}\Z")


class OpenAICompatibleProvider:
    """Send typed prompts to the configured compatible chat-completions URL.

    `LLM_API_ENDPOINT` is the complete request URL. It is intentionally
    required here; this integration does not infer a provider URL or append a
    provider-specific path.
    """

    def __init__(
        self,
        settings: LLMSettings | None = None,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.settings = settings or get_llm_settings()
        self._transport = transport
        if not self.settings.api_endpoint:
            raise LLMProviderConfigurationError()

    async def generate(
        self,
        prompt: str,
        *,
        response_model: type[OutputT],
        correlation_id: str | None = None,
    ) -> LLMResult[OutputT]:
        """Return a response validated against `response_model`.

        Prompt and response bodies, credentials, endpoint URLs, and raw
        transport exceptions are never logged or included in raised errors.
        """

        headers = {
            "Authorization": f"Bearer {self.settings.api_key.get_secret_value()}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if correlation_id and _CORRELATION_ID.fullmatch(correlation_id):
            headers["X-Correlation-ID"] = correlation_id

        payload = {
            "model": self.settings.model,
            "messages": [{"role": "user", "content": prompt}],
            "response_format": {"type": "json_object"},
        }

        try:
            async with httpx.AsyncClient(
                transport=self._transport,
                timeout=self.settings.request_timeout_seconds,
            ) as client:
                response = await client.post(
                    self.settings.api_endpoint,
                    headers=headers,
                    json=payload,
                )
        except httpx.TimeoutException:
            self._log_failure("provider_timeout")
            raise LLMProviderTimeoutError() from None
        except httpx.InvalidURL:
            self._log_failure("provider_configuration_error")
            raise LLMProviderConfigurationError() from None
        except httpx.RequestError:
            self._log_failure("provider_connection_error")
            raise LLMProviderConnectionError() from None

        if not 200 <= response.status_code < 300:
            self._log_failure("provider_http_error", status_code=response.status_code)
            raise LLMProviderHTTPError(response.status_code)

        try:
            body = response.json()
            content = body["choices"][0]["message"]["content"]
            if not isinstance(content, str):
                raise ValueError("Expected textual message content")
            output = self._parse_output(response_model, content)
        except Exception:
            # Do not retain provider payloads or validation details: they can
            # contain prompts, assessment data, or provider-generated content.
            self._log_failure("provider_response_error")
            raise LLMProviderResponseError() from None

        logger.info(
            "LLM provider request succeeded",
            extra={
                "llm_provider": self.settings.provider,
                "llm_model": self.settings.model,
                "outcome": "success",
            },
        )
        return LLMResult(
            output=output,
            provider=self.settings.provider,
            model=self.settings.model,
        )

    @staticmethod
    def _parse_output(response_model: type[OutputT], content: str) -> OutputT:
        # Pydantic v2 and v1 are both supported by the project's FastAPI range.
        validate_json = getattr(response_model, "model_validate_json", None)
        if validate_json is not None:
            return validate_json(content)
        return response_model.parse_raw(content)

    def _log_failure(self, error_code: str, *, status_code: int | None = None) -> None:
        details: dict[str, str | int] = {
            "llm_provider": self.settings.provider,
            "llm_model": self.settings.model,
            "error_code": error_code,
            "outcome": "failure",
        }
        if status_code is not None:
            details["http_status"] = status_code
        logger.warning("LLM provider request failed", extra=details)
