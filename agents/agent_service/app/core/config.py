"""Centralized, secret-safe configuration for Agent Service LLM usage."""

from functools import lru_cache
import os
import re
from typing import Mapping
from urllib.parse import urlsplit

from pydantic import BaseModel, Field, SecretStr, ValidationError, validator


class LLMConfigurationError(ValueError):
    """Safe configuration error containing field names, never setting values."""

    def __init__(self, fields: tuple[str, ...]) -> None:
        self.fields = fields
        super().__init__(f"Invalid LLM configuration for fields: {', '.join(fields)}")


class LLMSettings(BaseModel):
    """Shared settings consumed by both Agent Service workflows."""

    provider: str = Field(..., min_length=1, max_length=64)
    model: str = Field(..., min_length=1, max_length=200)
    api_endpoint: str | None = Field(default=None, max_length=2048)
    api_key: SecretStr
    request_timeout_seconds: float = Field(default=30.0, gt=0, le=300)

    class Config:
        extra = "forbid"
        allow_mutation = False
        anystr_strip_whitespace = True

    @validator("provider")
    def validate_provider_identifier(cls, value: str) -> str:
        if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9._-]*", value):
            raise ValueError("must be a provider identifier")
        return value

    @validator("api_endpoint")
    def validate_api_endpoint(cls, value: str | None) -> str | None:
        if value is None or not value:
            return None
        try:
            parsed = urlsplit(value)
            valid = parsed.scheme in {"http", "https"} and bool(parsed.hostname)
            # Do not allow credentials to be embedded in a URL, where they could
            # accidentally appear in diagnostics or logs.
            valid = valid and parsed.username is None and parsed.password is None
            _ = parsed.port  # Force validation of malformed port values.
        except ValueError:
            valid = False
        if not valid:
            raise ValueError("must be an HTTP(S) URL without embedded credentials")
        return value

    @validator("api_key")
    def validate_api_key(cls, value: SecretStr) -> SecretStr:
        if not value.get_secret_value().strip():
            raise ValueError("must not be empty")
        return value


def load_llm_settings(environ: Mapping[str, str] | None = None) -> LLMSettings:
    """Read and validate LLM settings without exposing invalid values."""

    source = os.environ if environ is None else environ
    endpoint = source.get("LLM_API_ENDPOINT", "").strip() or None
    values = {
        "provider": source.get("LLM_PROVIDER"),
        "model": source.get("LLM_MODEL"),
        "api_endpoint": endpoint,
        "api_key": source.get("LLM_API_KEY"),
        "request_timeout_seconds": source.get("LLM_REQUEST_TIMEOUT_SECONDS", "30"),
    }
    try:
        return LLMSettings(**values)
    except ValidationError as exc:
        # Pydantic's formatted errors can include rejected input. Only retain
        # field names so credentials or other environment values cannot leak.
        fields = tuple(sorted({str(error["loc"][0]) for error in exc.errors()}))
        raise LLMConfigurationError(fields) from None


@lru_cache(maxsize=1)
def get_llm_settings() -> LLMSettings:
    """Return the process-wide settings instance shared by workflow handlers."""

    return load_llm_settings()
