"""HTTP endpoint for the AI-FR-01 Attempt Event Summary workflow."""

from typing import TypeVar

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from app.core.correlation import request_correlation_id
from app.integrations.llm.provider_adapter import OpenAICompatibleProvider
from app.integrations.llm.protocol import LLMProvider, LLMResult
from app.schemas.attempt_event_summary import (
    AttemptEventSummaryInput,
    AttemptEventSummaryOutput,
)
from app.services.workflows.attempt_event_summary import (
    handle_attempt_event_summary,
)


router = APIRouter()
OutputT = TypeVar("OutputT", bound=BaseModel)


class _ConfiguredLLMProvider:
    """Load configured provider settings only when generation is requested."""

    async def generate(
        self,
        prompt: str,
        *,
        response_model: type[OutputT],
        correlation_id: str | None = None,
    ) -> LLMResult[OutputT]:
        provider = OpenAICompatibleProvider()
        return await provider.generate(
            prompt,
            response_model=response_model,
            correlation_id=correlation_id,
        )


def get_llm_provider() -> LLMProvider:
    """Return a provider that loads centralized settings on first generation."""

    return _ConfiguredLLMProvider()


@router.post(
    "/attempt-event-summary",
    response_model=AttemptEventSummaryOutput,
)
async def attempt_event_summary(
    payload: AttemptEventSummaryInput,
    request: Request,
    provider: LLMProvider = Depends(get_llm_provider),
) -> AttemptEventSummaryOutput:
    """Validate and delegate an event summary request to its workflow handler."""

    return await handle_attempt_event_summary(
        payload,
        provider=provider,
        correlation_id=request_correlation_id(request),
    )
