import json
from urllib.parse import urlsplit
from typing import Protocol

import httpx
from pydantic import BaseModel, ConfigDict, StrictInt

from app.config import Settings


class ProviderUnavailable(Exception):
    pass


class Provider(Protocol):
    async def choose(self, choices: list[str]) -> int: ...


class Choice(BaseModel):
    model_config = ConfigDict(extra="forbid")
    choice: StrictInt


class OpenAICompatibleProvider:
    def __init__(self, settings: Settings):
        self.settings = settings

    async def choose(self, choices: list[str]) -> int:
        if not self.settings.api_key or not self.settings.model:
            raise ProviderUnavailable()
        url = urlsplit(self.settings.provider_url)
        if url.scheme != "https" or not url.hostname or url.username or url.password:
            raise ProviderUnavailable()
        try:
            async with httpx.AsyncClient(timeout=self.settings.timeout, follow_redirects=False) as client:
                response = await client.post(self.settings.provider_url,
                    headers={"Authorization": f"Bearer {self.settings.api_key}"},
                    json={"model": self.settings.model, "temperature": 0,
                          "max_tokens": 30, "response_format": {"type": "json_object"},
                          "messages": [{"role": "system", "content": "Select the clearest concise Persian phrasing. Return only JSON {\"choice\": integer}, indexing from zero. Do not add facts."},
                                       {"role": "user", "content": json.dumps(choices, ensure_ascii=False)}]})
                response.raise_for_status()
                if len(response.content) > 32768:
                    raise ValueError()
                body = response.json()
                content = body["choices"][0]["message"]["content"]
                if not isinstance(content, str) or len(content.encode("utf-8")) > 4096:
                    raise ValueError()
                choice = Choice.model_validate_json(content).choice
                if not 0 <= choice < len(choices):
                    raise ValueError()
                return choice
        except (httpx.HTTPError, ValueError, KeyError, IndexError, TypeError):
            # Never forward provider bodies, exception strings, or credentials.
            raise ProviderUnavailable() from None
