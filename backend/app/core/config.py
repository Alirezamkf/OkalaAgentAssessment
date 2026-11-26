import os
import math
from typing import Mapping

from pydantic import SecretStr


DEFAULT_AGENT_SERVICE_CONNECT_TIMEOUT_SECONDS = 5.0
DEFAULT_AGENT_SERVICE_REQUEST_TIMEOUT_SECONDS = 35.0


def load_agent_service_shared_secret(
    environ: Mapping[str, str] | None = None,
) -> SecretStr | None:
    source = os.environ if environ is None else environ
    value = source.get("AGENT_SERVICE_SHARED_SECRET", "").strip()
    return SecretStr(value) if value else None


class Settings:
    environment: str = os.getenv("ENVIRONMENT", "development")
    frontend_origins: list[str] = [
        origin.strip()
        for origin in os.getenv("FRONTEND_URL", "http://localhost:3000").split(",")
        if origin.strip()
    ]
    database_url: str = os.getenv("DATABASE_URL", "").strip()
    if not database_url:
        raise RuntimeError("DATABASE_URL is required")
    agent_service_url: str = os.getenv("AGENT_SERVICE_URL", "http://localhost:8001")
    agent_service_shared_secret: SecretStr | None = load_agent_service_shared_secret()
    # Iran is the project's configured default region; override for another deployment.
    candidate_phone_region: str | None = os.getenv("CANDIDATE_PHONE_REGION", "IR") or None


settings = Settings()


def load_agent_service_timeouts(
    environ: Mapping[str, str] | None = None,
) -> tuple[float, float]:
    """Load positive Agent Service connect and request timeouts in seconds.

    Validation happens when the Agent client is constructed, not while the
    Backend starts, so unrelated Backend routes remain available if these
    optional integration settings are malformed.
    """

    source = os.environ if environ is None else environ
    values: list[float] = []
    for name, default in (
        (
            "AGENT_SERVICE_CONNECT_TIMEOUT_SECONDS",
            DEFAULT_AGENT_SERVICE_CONNECT_TIMEOUT_SECONDS,
        ),
        (
            "AGENT_SERVICE_REQUEST_TIMEOUT_SECONDS",
            DEFAULT_AGENT_SERVICE_REQUEST_TIMEOUT_SECONDS,
        ),
    ):
        try:
            value = float(source.get(name, str(default)))
        except (TypeError, ValueError):
            raise ValueError(f"{name} must be a positive number") from None
        if not math.isfinite(value) or value <= 0:
            raise ValueError(f"{name} must be a positive number")
        values.append(value)
    return values[0], values[1]
