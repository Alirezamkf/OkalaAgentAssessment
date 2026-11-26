import pytest
from pydantic import SecretStr

from app.core.config import (
    LLMConfigurationError,
    get_llm_settings,
    load_llm_settings,
)


def valid_environment(**overrides: str) -> dict[str, str]:
    values = {
        "LLM_PROVIDER": "example-provider",
        "LLM_MODEL": "example-model-v1",
        "LLM_API_KEY": "test-placeholder-secret",
        "LLM_REQUEST_TIMEOUT_SECONDS": "45",
    }
    values.update(overrides)
    return values


def test_loads_valid_configuration_and_masks_credential() -> None:
    settings = load_llm_settings(
        valid_environment(LLM_API_ENDPOINT="https://llm.example.test/v1")
    )

    assert settings.provider == "example-provider"
    assert settings.model == "example-model-v1"
    assert settings.api_endpoint == "https://llm.example.test/v1"
    assert settings.api_key == SecretStr("test-placeholder-secret")
    assert settings.request_timeout_seconds == 45
    assert "test-placeholder-secret" not in str(settings)
    assert "test-placeholder-secret" not in repr(settings)


def test_endpoint_is_optional_and_timeout_has_safe_default() -> None:
    settings = load_llm_settings(valid_environment())

    assert settings.api_endpoint is None
    assert settings.request_timeout_seconds == 30


def test_missing_required_settings_report_only_field_names() -> None:
    with pytest.raises(LLMConfigurationError) as error:
        load_llm_settings({})

    assert error.value.fields == ("api_key", "model", "provider")
    assert "LLM_API_KEY" not in str(error.value)


@pytest.mark.parametrize(
    "overrides",
    [
        {"LLM_PROVIDER": "bad provider name"},
        {"LLM_API_ENDPOINT": "file:///etc/passwd"},
        {"LLM_API_ENDPOINT": "https://user:secret@llm.example.test/v1"},
        {"LLM_REQUEST_TIMEOUT_SECONDS": "0"},
        {"LLM_REQUEST_TIMEOUT_SECONDS": "not-a-number"},
        {"LLM_API_KEY": "   "},
    ],
)
def test_invalid_settings_raise_safe_error(overrides: dict[str, str]) -> None:
    secret = "test-placeholder-secret"
    with pytest.raises(LLMConfigurationError) as error:
        load_llm_settings(valid_environment(**overrides))

    assert error.value.fields
    assert secret not in str(error.value)
    assert "secret" not in str(error.value)


def test_cached_settings_are_shared_and_do_not_log_credentials(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    get_llm_settings.cache_clear()
    for name, value in valid_environment().items():
        monkeypatch.setenv(name, value)

    first = get_llm_settings()
    second = get_llm_settings()

    assert first is second
    assert "test-placeholder-secret" not in caplog.text
    get_llm_settings.cache_clear()
