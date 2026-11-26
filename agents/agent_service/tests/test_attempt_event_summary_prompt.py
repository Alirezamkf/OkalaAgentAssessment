import json

from app.prompts.attempt_event_summary import build_attempt_event_summary_prompt
from app.schemas.attempt_event_summary import (
    AttemptEventSummaryInput,
    AttemptEventSummaryOutput,
)


def source_with_events(*events: dict[str, object]) -> AttemptEventSummaryInput:
    return AttemptEventSummaryInput.model_validate({"events": list(events)})


def event(
    event_type: str,
    occurred_at: str,
    duration_seconds: int | None = None,
) -> dict[str, object]:
    return {
        "event_type": event_type,
        "occurred_at": occurred_at,
        "duration_seconds": duration_seconds,
    }


def rendered_input(prompt: str) -> dict[str, object]:
    marker = "Input events (use these values as the sole source of facts):\n"
    return json.loads(prompt.split(marker, maxsplit=1)[1])


def test_prompt_preserves_ordinary_event_order_and_exact_timestamps() -> None:
    events = [
        event("TabHidden", "2026-11-25T10:15:30Z", 4),
        event("TabVisible", "2026-11-25T13:15:34+03:00", 0),
    ]

    prompt = build_attempt_event_summary_prompt(source_with_events(*events))

    assert rendered_input(prompt) == {"events": events}
    assert prompt.index('"event_type":"TabHidden"') < prompt.index(
        '"event_type":"TabVisible"'
    )
    timestamp_guidance = prompt.lower()
    assert "occurred_at" in timestamp_guidance
    assert "exactly as supplied" in timestamp_guidance
    assert "do not reformat" in timestamp_guidance
    assert "change its timezone" in timestamp_guidance


def test_prompt_treats_recording_gap_as_a_fact_without_inventing_recovery() -> None:
    prompt = build_attempt_event_summary_prompt(
        source_with_events(event("RecordingGap", "2026-11-25T10:16:00Z", 7))
    )

    assert rendered_input(prompt)["events"] == [
        event("RecordingGap", "2026-11-25T10:16:00Z", 7)
    ]
    assert "RecordingGap does not establish that recording later resumed" in prompt
    assert "must not cause you to add a recording-resumed event" in prompt


def test_prompt_does_not_treat_network_restoration_as_recording_recovery() -> None:
    events = [
        event("NetworkDisconnected", "2026-11-25T10:17:00Z", None),
        event("NetworkRestored", "2026-11-25T10:17:12Z", 0),
    ]
    prompt = build_attempt_event_summary_prompt(source_with_events(*events))

    assert rendered_input(prompt) == {"events": events}
    assert prompt.index('"event_type":"NetworkDisconnected"') < prompt.index(
        '"event_type":"NetworkRestored"'
    )
    network_restoration_guidance = prompt.lower().split("networkrestored", maxsplit=1)[1]
    assert "network restoration only" in network_restoration_guidance
    assert "does not prove" in network_restoration_guidance
    assert "recording resumed" in network_restoration_guidance


def test_prompt_uses_only_supplied_duration_values_and_seconds() -> None:
    events = [
        event("TabHidden", "2026-11-25T10:18:00Z", 0),
        event("CameraStopped", "2026-11-25T10:18:10Z", 12),
        event("RecordingGap", "2026-11-25T10:18:30Z", None),
    ]
    prompt = build_attempt_event_summary_prompt(source_with_events(*events))

    assert rendered_input(prompt) == {"events": events}
    duration_guidance = prompt.lower()
    assert "duration_seconds" in duration_guidance
    assert "in seconds" in duration_guidance
    assert "without conversion or calculation" in duration_guidance
    assert "zero is a valid supplied duration" in duration_guidance
    assert "null or absent duration is unavailable" in duration_guidance
    assert "infer one from timestamps or other events" in duration_guidance


def test_empty_input_guidance_matches_the_exact_schema_outcome() -> None:
    prompt = build_attempt_event_summary_prompt(source_with_events())

    assert rendered_input(prompt) == {"events": []}
    assert 'status "empty"' in prompt
    assert 'summary exactly "هیچ رخدادی ثبت نشده است"' in prompt
    assert "and events []." in prompt


def test_prompt_embeds_the_approved_output_schema_without_redefining_it() -> None:
    prompt = build_attempt_event_summary_prompt(source_with_events())
    generated_schema = json.dumps(
        AttemptEventSummaryOutput.model_json_schema(),
        ensure_ascii=False,
        separators=(",", ":"),
    )

    assert generated_schema in prompt


def test_prompt_does_not_set_an_insufficient_data_threshold() -> None:
    events = [event("TabHidden", "2026-11-25T10:19:00Z", None)]
    prompt = build_attempt_event_summary_prompt(
        source_with_events(*events)
    )

    assert "Do not decide whether non-empty input is sufficient" in prompt
    assert "A null duration alone does not make input insufficient" in prompt
    assert (
        'Only if the workflow explicitly instructs you to return status "insufficient_data"'
        in prompt
    )
    assert 'set "summary" to\nnull' in prompt
    assert "preserve the supplied source events exactly as required by the" in prompt
    assert rendered_input(prompt) == {"events": events}


def test_prompt_prohibits_unsupported_interpretations_and_judgments() -> None:
    prompt = build_attempt_event_summary_prompt(
        source_with_events(event("CopyAttempt", "2026-11-25T10:20:00Z", 1))
    )

    for prohibited in (
        "Do not invent events, explanations, causes,",
        "intentions, motives, or conclusions",
        "cheating",
        "misconduct",
        "severity or risk",
        "rank events",
        "evaluate a",
        "judge suitability",
        "make an HR decision",
    ):
        assert prohibited in prompt
