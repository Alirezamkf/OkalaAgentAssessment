"""Provider-independent contract shared by Agent Service workflows."""

from dataclasses import dataclass
from typing import Generic, Protocol, TypeVar

from pydantic import BaseModel


OutputT = TypeVar("OutputT", bound=BaseModel)


@dataclass(frozen=True)
class LLMResult(Generic[OutputT]):
    """A validated model output with safe provider and model metadata."""

    output: OutputT
    provider: str
    model: str


class LLMProvider(Protocol):
    """Minimal interface for typed, provider-independent LLM requests."""

    async def generate(
        self,
        prompt: str,
        *,
        response_model: type[OutputT],
        correlation_id: str | None = None,
    ) -> LLMResult[OutputT]: ...
