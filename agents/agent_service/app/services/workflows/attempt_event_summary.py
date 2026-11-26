"""Application service for the AI-FR-01 Attempt Event Summary workflow."""

from app.integrations.llm.protocol import LLMProvider
from app.prompts.attempt_event_summary import build_attempt_event_summary_prompt
from app.schemas.attempt_event_summary import (
    AttemptEventSummaryInput,
    AttemptEventSummaryOutput,
    AttemptEventSummaryStatus,
)
from app.services.validation import validate_attempt_event_summary_result


def _deterministic_outcome(
    source: AttemptEventSummaryInput,
) -> AttemptEventSummaryOutput:
    if not source.events:
        return AttemptEventSummaryOutput(
            status=AttemptEventSummaryStatus.EMPTY,
            summary="هیچ رخدادی ثبت نشده است",
            events=[],
        )

    return AttemptEventSummaryOutput(
        status=AttemptEventSummaryStatus.INSUFFICIENT_DATA,
        summary=None,
        events=list(source.events),
    )


async def handle_attempt_event_summary(
    source: AttemptEventSummaryInput,
    *,
    provider: LLMProvider,
    correlation_id: str,
) -> AttemptEventSummaryOutput:
    """Summarize a validated event list using the shared LLM provider."""

    if len(source.events) < 2:
        return _deterministic_outcome(source)

    prompt = build_attempt_event_summary_prompt(source)
    result = await provider.generate(
        prompt,
        response_model=AttemptEventSummaryOutput,
        correlation_id=correlation_id,
    )
    return validate_attempt_event_summary_result(result.output, source)
