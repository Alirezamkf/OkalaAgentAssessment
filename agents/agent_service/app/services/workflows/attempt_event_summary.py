"""Application service for the AI-FR-01 Attempt Event Summary workflow."""

import logging
import time
from datetime import datetime, timezone

from app.core.correlation import correlation_id_fingerprint
from app.core.errors import AgentServiceError
from app.integrations.llm.protocol import LLMProvider
from app.prompts.attempt_event_summary import build_attempt_event_summary_prompt
from app.schemas.attempt_event_summary import (
    AttemptEventSummaryInput,
    AttemptEventSummaryOutput,
    AttemptEventSummaryStatus,
)
from app.services.validation import validate_attempt_event_summary_result


logger = logging.getLogger(__name__)


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

    started_at = datetime.now(timezone.utc).isoformat()
    start_clock = time.perf_counter()
    log_context: dict[str, str] = {"operation": "attempt_event_summary"}
    fingerprint = correlation_id_fingerprint(correlation_id)
    if fingerprint is not None:
        log_context["correlation_fingerprint"] = fingerprint
    logger.info(
        "Agent workflow started",
        extra={**log_context, "started_at": started_at},
    )

    try:
        if len(source.events) < 2:
            output = _deterministic_outcome(source)
        else:
            prompt = build_attempt_event_summary_prompt(source)
            result = await provider.generate(
                prompt,
                response_model=AttemptEventSummaryOutput,
                correlation_id=correlation_id,
            )
            output = validate_attempt_event_summary_result(result.output, source)
    except Exception as exc:
        failure_category = (
            exc.code if isinstance(exc, AgentServiceError) else "workflow_error"
        )
        logger.warning(
            "Agent workflow completed",
            extra={
                **log_context,
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "duration_ms": (time.perf_counter() - start_clock) * 1000,
                "outcome": "failure",
                "failure_category": failure_category,
            },
        )
        raise

    logger.info(
        "Agent workflow completed",
        extra={
            **log_context,
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "duration_ms": (time.perf_counter() - start_clock) * 1000,
            "outcome": "success",
            "workflow_status": output.status.value,
        },
    )
    return output
