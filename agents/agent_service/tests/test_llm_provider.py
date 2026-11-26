import asyncio
import json
import logging

import httpx
import pytest
from pydantic import BaseModel, SecretStr

from app.core.config import LLMSettings
from app.integrations.llm.errors import (
    LLMProviderConnectionError,
    LLMProviderHTTPError,
    LLMProviderResponseError,
    LLMProviderTimeoutError,
)
from app.integrations.llm.provider_adapter import OpenAICompatibleProvider


class Summary(BaseModel):
    summary: str


def settings(
    *, endpoint: str = "https://llm.example.test/v1/chat/completions"
) -> LLMSettings:
    return LLMSettings(
        provider="compatible-test-provider",
        model="test-model",
        api_endpoint=endpoint,
        api_key=SecretStr("placeholder-secret"),
        request_timeout_seconds=7,
    )


def provider_response(content: str, *, status_code: int = 200) -> httpx.Response:
    return httpx.Response(
        status_code,
        json={"choices": [{"message": {"content": content}}]},
    )


def test_sends_configured_request_and_parses_typed_response(
    caplog: pytest.LogCaptureFixture,
) -> None:
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["authorization"] = request.headers["Authorization"]
        seen["correlation_id"] = request.headers.get("X-Correlation-ID")
        seen["timeout"] = request.extensions["timeout"]
        seen["body"] = json.loads(request.content)
        return provider_response('{"summary":"A concise summary."}')

    caplog.set_level(logging.INFO)
    result = asyncio.run(
        OpenAICompatibleProvider(
            settings(), transport=httpx.MockTransport(handler)
        ).generate(
            "safe test prompt",
            response_model=Summary,
            correlation_id="request-123",
        )
    )

    assert seen["url"] == "https://llm.example.test/v1/chat/completions"
    assert seen["authorization"] == "Bearer placeholder-secret"
    assert seen["correlation_id"] == "request-123"
    assert seen["timeout"]["read"] == 7
    assert seen["body"] == {
        "model": "test-model",
        "messages": [{"role": "user", "content": "safe test prompt"}],
        "response_format": {"type": "json_object"},
    }
    assert result.output == Summary(summary="A concise summary.")
    assert result.provider == "compatible-test-provider"
    assert result.model == "test-model"
    assert "placeholder-secret" not in caplog.text
    assert "safe test prompt" not in caplog.text
    assert any(
        getattr(record, "correlation_id", None) == "request-123"
        for record in caplog.records
    )


def test_maps_timeout_to_safe_error(caplog: pytest.LogCaptureFixture) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("sensitive transport details", request=request)

    caplog.set_level(logging.WARNING)
    with pytest.raises(LLMProviderTimeoutError) as error:
        asyncio.run(
            OpenAICompatibleProvider(
                settings(), transport=httpx.MockTransport(handler)
            ).generate(
                "assessment prompt",
                response_model=Summary,
            )
        )

    assert str(error.value) == LLMProviderTimeoutError.message
    assert "placeholder-secret" not in caplog.text
    assert "assessment prompt" not in caplog.text
    assert "sensitive transport details" not in caplog.text


def test_maps_connection_failure_to_safe_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("sensitive connection details", request=request)

    with pytest.raises(LLMProviderConnectionError) as error:
        asyncio.run(
            OpenAICompatibleProvider(
                settings(), transport=httpx.MockTransport(handler)
            ).generate("prompt", response_model=Summary)
        )

    assert str(error.value) == LLMProviderConnectionError.message
    assert "sensitive connection details" not in str(error.value)
    assert "placeholder-secret" not in str(error.value)


def test_http_error_does_not_expose_provider_body_or_prompt(
    caplog: pytest.LogCaptureFixture,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            429,
            text="placeholder-secret assessment data provider internals",
        )

    caplog.set_level(logging.WARNING)
    with pytest.raises(LLMProviderHTTPError) as error:
        asyncio.run(
            OpenAICompatibleProvider(
                settings(), transport=httpx.MockTransport(handler)
            ).generate("assessment prompt", response_model=Summary)
        )

    assert error.value.status_code == 429
    for sensitive_value in (
        "placeholder-secret",
        "assessment data",
        "provider internals",
        "assessment prompt",
    ):
        assert sensitive_value not in str(error.value)
        assert sensitive_value not in caplog.text


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(200, text="not-json"),
        httpx.Response(200, json={"choices": []}),
        provider_response("not-json"),
        provider_response('{"unexpected":"shape"}'),
    ],
)
def test_rejects_malformed_provider_responses_safely(
    response: httpx.Response, caplog: pytest.LogCaptureFixture
) -> None:
    response_content = response.content.decode("utf-8", errors="replace")

    def handler(request: httpx.Request) -> httpx.Response:
        return response

    caplog.set_level(logging.WARNING)
    with pytest.raises(LLMProviderResponseError) as error:
        asyncio.run(
            OpenAICompatibleProvider(
                settings(), transport=httpx.MockTransport(handler)
            ).generate("assessment prompt", response_model=Summary)
        )

    assert str(error.value) == LLMProviderResponseError.message
    assert response_content not in str(error.value)
    assert response_content not in caplog.text
    assert "assessment prompt" not in caplog.text
    assert "placeholder-secret" not in caplog.text
