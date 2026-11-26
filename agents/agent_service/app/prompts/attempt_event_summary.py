"""Prompt construction for the AI-FR-01 Attempt Event Summary workflow."""

import json

from app.schemas.attempt_event_summary import (
    AttemptEventSummaryInput,
    AttemptEventSummaryOutput,
)


_INSTRUCTIONS = """You produce a concise, neutral, factual summary in Persian.

Use only the event_type, occurred_at, and duration_seconds values in the input.
The events are already in chronological order: describe them in that same order
and do not sort, omit, combine, or add events. Preserve every timestamp string
exactly as supplied. If you include a timestamp in the summary, copy its exact
string; do not reformat it, change its timezone, or convert its digits.

Mention a duration only when duration_seconds is an integer in the input. State
it in seconds without conversion or calculation. Zero is a valid supplied duration.
A null or absent duration is unavailable: do not mention a duration,
estimate one, or infer one from timestamps or other events.

Report only recorded facts. Do not invent events, explanations, causes,
intentions, motives, or conclusions. Do not treat any event as proof of cheating
or misconduct. Do not assess severity or risk, rank events, evaluate a
candidate, judge suitability, or make an HR decision. In particular,
NetworkRestored records network restoration only; it does not prove that
recording resumed. RecordingGap does not establish that recording later resumed
and must not cause you to add a recording-resumed event.

Return only a JSON object that conforms to the supplied AttemptEventSummaryOutput
schema. Write a successful summary in Persian. For an empty events list, use
status "empty", summary exactly "هیچ رخدادی ثبت نشده است", and events [].

Do not decide whether non-empty input is sufficient. A null duration alone does not make input insufficient.
Only if the workflow explicitly instructs you to return status "insufficient_data", return that status with summary set to null. Preserve the supplied source events exactly as required by the schema. Never guess a summary to fill missing information."""


def build_attempt_event_summary_prompt(
    source: AttemptEventSummaryInput,
) -> str:
    """Render instructions and the exact, ordered event payload for the model.

    Empty-input handling is included as contract guidance. The workflow handler
    must return that outcome deterministically without calling the LLM.
    """

    input_json = json.dumps(
        source.model_dump(mode="json"),
        ensure_ascii=False,
        separators=(",", ":"),
    )
    output_schema_json = json.dumps(
        AttemptEventSummaryOutput.model_json_schema(),
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return (
        f"{_INSTRUCTIONS}\n\n"
        "Output schema (generated from the approved Pydantic model):\n"
        f"{output_schema_json}\n\n"
        "Input events (use these values as the sole source of facts):\n"
        f"{input_json}"
    )
