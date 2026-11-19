import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    internal_secret: str = ""
    api_key: str = ""
    model: str = ""
    provider_url: str = "https://api.openai.com/v1/chat/completions"
    timeout: float = 8

    @classmethod
    def from_env(cls):
        return cls(os.getenv("AGENT_INTERNAL_SECRET", ""), os.getenv("LLM_API_KEY", ""),
                   os.getenv("LLM_MODEL", ""), os.getenv("LLM_PROVIDER_URL", cls.provider_url),
                   max(1, min(20, float(os.getenv("LLM_TIMEOUT_SECONDS", "8")))))
