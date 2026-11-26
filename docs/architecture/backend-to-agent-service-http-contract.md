# Backend-to-Agent Service HTTP Contract

## Purpose and scope

This document defines the proposed HTTP boundary between the Backend and the
independent FastAPI Agent Service for the two approved workflows:

1. Attempt Event Summary (AI-FR-01).
2. Natural-Language HR Reporting (AI-FR-04).

The endpoint paths and JSON examples below describe the contract to implement.
They are not claims that workflow routes or handlers are currently available.
The Agent Service currently exposes only `GET /health`.

This document does not add a workflow, change a schema, or move Backend
responsibilities into the Agent Service. The existing Pydantic contracts remain
the source of truth for request and response fields.

## References

- [ADR-001: Independent Agent Service Architecture](ADR-001-agent-service-architecture.md)
- [Agent Service Internal Architecture](agent-service-internal-architecture.md)
- Issue #32: Attempt Event Summary schemas in
  `agents/agent_service/app/schemas/attempt_event_summary.py`
- Issue #43: Natural-Language HR Reporting schemas in
  `agents/agent_service/app/schemas/hr_reporting.py`
- Issue #25: shared error response and correlation handling in
  `agents/agent_service/app/core/errors.py`,
  `agents/agent_service/app/core/correlation.py`, and
  `agents/agent_service/app/main.py`
- Issue #27: service-to-service authentication decision (pending)

## Endpoints

| Workflow | Method and path | Existing schema contract |
| --- | --- | --- |
| Attempt Event Summary | `POST /api/v1/workflows/attempt-event-summary` | `AttemptEventSummaryInput` → `AttemptEventSummaryOutput` |
| Natural-Language HR Reporting | `POST /api/v1/workflows/hr-reporting` | `NaturalLanguageReportingInput` → `NaturalLanguageReportingOutput` |

Both request and successful response bodies are JSON. FastAPI request validation
must happen before the selected workflow handler runs. The response must match
the corresponding existing output schema. Do not define duplicate HTTP-specific
schemas for these contracts.

## Attempt Event Summary (AI-FR-01)

The request uses `AttemptEventSummaryInput`. It contains only the recorded event
fields allowed by Issue #32: the exact approved `event_type`, server-recorded
`occurred_at` timestamp, and optional integer `duration_seconds`.

Example request:

```json
{
  "events": [
    {
      "event_type": "TabHidden",
      "occurred_at": "2026-11-25T10:15:30Z",
      "duration_seconds": 4
    },
    {
      "event_type": "TabVisible",
      "occurred_at": "2026-11-25T10:15:34Z",
      "duration_seconds": 0
    }
  ]
}
```

The Issue #32 schema accepts exactly these 12 case-sensitive event types:
`TabHidden`, `CameraStopped`, `ScreenShareStopped`, `CopyAttempt`,
`PasteAttempt`, `Reentered`, `ConcurrentSessionBlocked`, `Idle`,
`NetworkDisconnected`, `NetworkRestored`, `RecordingGap`, and `TabVisible`.
`TabVisible` and `Reentered` are distinct. Timestamps are timezone-aware, and
duration is expressed in integer seconds or `null` when unavailable.

The response uses `AttemptEventSummaryOutput` and returns the outcome, Persian
summary when applicable, and source events. Before sending the request, the
Backend must sort events by `occurred_at` in ascending chronological order. The
Agent must preserve the received event order and event values in its output;
output events must retain those values and that order.

Successful response example:

```json
{
  "status": "success",
  "summary": "در ساعت ۱۰:۱۵:۳۰ رویداد TabHidden و در ساعت ۱۰:۱۵:۳۴ رویداد TabVisible ثبت شد.",
  "events": [
    {
      "event_type": "TabHidden",
      "occurred_at": "2026-11-25T10:15:30Z",
      "duration_seconds": 4
    },
    {
      "event_type": "TabVisible",
      "occurred_at": "2026-11-25T10:15:34Z",
      "duration_seconds": 0
    }
  ]
}
```

For an empty event list, the request is:

```json
{"events": []}
```

Empty event-list response example:

```json
{
  "status": "empty",
  "summary": "هیچ رخدادی ثبت نشده است",
  "events": []
}
```

An insufficient-data input can contain an event whose duration was not
measurable:

```json
{
  "events": [
    {
      "event_type": "TabHidden",
      "occurred_at": "2026-11-25T10:15:30Z",
      "duration_seconds": null
    }
  ]
}
```

Insufficient source-data response example:

```json
{
  "status": "insufficient_data",
  "summary": null,
  "events": [
    {
      "event_type": "TabHidden",
      "occurred_at": "2026-11-25T10:15:30Z",
      "duration_seconds": null
    }
  ]
}
```

An empty event list and insufficient source data are valid workflow outcomes.
They are not provider or service errors.

## Natural-Language HR Reporting (AI-FR-04)

The request uses `NaturalLanguageReportingInput`, a discriminated union with
exactly four categories and category-specific Backend-computed results:

- `attempt_counts_by_status`
- `exam_score_statistics`
- `attempts_with_highest_event_count`
- `recording_completeness`

Example request for counts by status:

```json
{
  "category": "attempt_counts_by_status",
  "result": {
    "state": "available",
    "data": {
      "status_counts": [
        {"status": "Not Started", "count": 0},
        {"status": "In Progress", "count": 1},
        {"status": "Submitted", "count": 2},
        {"status": "Timed Out", "count": 3},
        {"status": "Interrupted", "count": 4},
        {"status": "Cancelled", "count": 5}
      ]
    }
  }
}
```

The category-specific result fields and validation rules are defined only in
Issue #43's schema. In particular, the Backend supplies all calculations;
zero counts can be available results; and the three recording states
(`Complete`, `No Recording`, and `Incomplete`) stay distinct.

Successful response example:

```json
{
  "category": "attempt_counts_by_status",
  "result_state": "available",
  "explanation": "مقادیر ثبت‌شده به‌ترتیب وضعیت‌ها عبارت‌اند از ۰، ۱، ۲، ۳، ۴ و ۵."
}
```

Empty score-result request example:

```json
{
  "category": "exam_score_statistics",
  "result": {
    "state": "empty",
    "eligible_finalized_score_count": 0
  }
}
```

Corresponding empty response example:

```json
{
  "category": "exam_score_statistics",
  "result_state": "empty",
  "explanation": "برای این گزارش نتیجه‌ای در دسترس نیست."
}
```

An empty result must not be given fabricated numerical values. The successful
output schema has only `available` and `empty` result states; it has no
`unavailable` value.

## AI/provider unavailability and errors

AI/provider unavailability is an HTTP error response, never a successful
workflow outcome. The Issue #25 envelope is:

```json
{
  "error": {
    "code": "provider_connection_error",
    "message": "The AI provider is temporarily unavailable."
  },
  "correlation_id": "request-123"
}
```

The implemented mappings are:

| Condition | HTTP status | Error code |
| --- | ---: | --- |
| FastAPI request schema validation failure | 422 | `request_validation_error` |
| Shared workflow input validation failure | 422 | `workflow_input_invalid` |
| Generic workflow validation failure | 422 | `workflow_validation_error` |
| Agent Service LLM configuration is invalid | 503 | `llm_configuration_error` |
| Provider configuration failure | 503 | `provider_configuration_error` |
| Provider connection failure / unavailable | 503 | `provider_connection_error` |
| Generic provider failure | 503 | `provider_error` |
| Provider request timeout | 504 | `provider_timeout` |
| Provider rejection or unsuccessful HTTP response | 502 | `provider_http_error` |
| Malformed or unusable provider response | 502 | `provider_response_error` |
| Workflow output fails schema or source-dependent validation | 502 | `workflow_output_invalid` |
| Generic Agent Service application error | 500 | `agent_service_error` |
| Unexpected internal failure | 500 | `internal_error` |

The public message and error code are stable and safe. The envelope does not
include validation details, provider response bodies, raw transport details,
credentials, prompts, or assessment data. Provider-specific upstream HTTP
status is not part of the public error response.

## Correlation ID

The request header is `X-Correlation-ID`. A value matching
`[A-Za-z0-9._:-]{1,128}` is accepted. If it is absent or invalid, the Agent
Service generates a UUID-based ID. The chosen ID is returned in both the
`X-Correlation-ID` response header and is available for logging and
workflow-level correlation. Error responses also include it in the envelope's
`correlation_id`; successful response bodies remain unchanged to match their
existing schemas. The ID is metadata only; it must not carry user or assessment
data.

## Responsibilities and data boundaries

### Backend

- Authenticates and authorizes the user and decides whether the request is
  allowed.
- Retrieves events and selects the authorized attempt for AI-FR-01.
- Classifies the HR request, retrieves permitted data, and computes every
  AI-FR-04 result.
- Sends only the matching structured schema input and handles Agent Service
  errors without making core assessment functions depend on AI availability.

### Agent Service

- Validates the request against the matching existing Pydantic input schema.
- Runs only the selected approved workflow, calls the configured LLM through
  its shared provider integration, and validates output before responding.
- Does not access the Backend database, authorize users, retrieve records,
  classify the HR query, or calculate report values.

### Data that must not be sent

Do not forward candidate answers, answer keys, question text, exam content,
video, images, or unnecessary candidate identifiers/personal information.
For AI-FR-01, send only the approved event fields; do not add attempt IDs or
unrelated metadata. For AI-FR-04, send only the selected category and its
Backend-computed structured result; do not send the raw natural-language HR
query or raw events when the category requires aggregates. These restrictions
apply to both Agent input and LLM prompt data.

## Authentication and timeout configuration

The Backend owns user authentication and authorization under ADR-001. The
service-to-service authentication mechanism for Backend-to-Agent requests is
pending Issue #27. This contract does not select a token type, header, or
credential format; those details must be added after Issue #27 is decided.

Agent Service's `LLM_REQUEST_TIMEOUT_SECONDS` configures the Agent-to-LLM
request. It defaults to 30 seconds and is validated as greater than zero and
no more than 300 seconds. It is not the Backend-to-Agent HTTP timeout. The
Backend transport timeout is not defined in the inspected sources and remains
open; no value is specified here.

## Open decisions and assumptions

1. **Backend-to-Agent authentication:** pending Issue #27; the mechanism and
   wire details are not finalized here.
2. **Backend-to-Agent timeout:** no transport timeout value was found in the
   inspected configuration or contract documents.
3. **Successful HTTP status:** `200 OK` is a proposal for successful workflow
   responses, pending approval. No successful status code is specified by the
   existing schemas or architecture documents.
4. **Endpoint implementation:** both workflow paths are proposed by the
   internal architecture and are not currently implemented; only the health
   endpoint exists today.
5. **Provider timeout coordination:** the Backend timeout should be decided
   with the Agent-to-LLM timeout and request overhead in mind, but no ordering
   or numeric margin is approved by the inspected sources.

