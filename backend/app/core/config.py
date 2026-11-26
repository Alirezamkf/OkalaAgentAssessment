import os
from typing import Mapping

from pydantic import SecretStr


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
