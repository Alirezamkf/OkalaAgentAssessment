# Agent Service Internal Architecture

## Status and scope

This document proposes the internal module boundaries for the independent FastAPI Agent Service approved by [ADR-001](ADR-001-agent-service-architecture.md). It is an architecture design only: the workflows, provider integration, schemas, and error handling described here are not implemented by this document.

The service contains exactly two workflow handlers:

1. Attempt Event Summary (AI-FR-01).
2. Natural-Language HR Reporting (AI-FR-04).

It does not define a general-purpose chat interface, additional agents, or autonomous workflows.

## Current repository state

`agents/agent_service/app/main.py` currently creates the FastAPI app and exposes only `GET /health`. The existing `app/api`, `app/core`, `app/schemas`, and `app/services` directories contain only `.gitkeep` files. The only Agent Service test checks the health response. Its requirements currently include FastAPI and Uvicorn; no provider SDK or Pydantic-specific dependency is declared. FastAPI already depends on Pydantic, so request and response models can use the Pydantic version supplied by the installed FastAPI dependency.

The Backend's `app/api/v1/agent.py`, `app/integrations/agents/agent_client.py`, and `agent_config.py` are placeholders. Backend tests use `pytest` and FastAPI `TestClient`; the Agent Service health test uses the same pattern. There is no existing application logging or correlation-ID convention in either service.

## Proposed module structure

This is a target layout for later implementation. It reuses the existing Agent Service package directories and adds only module groupings needed for the approved boundaries.

```text
agents/agent_service/app/
├── main.py
├── api/
│   └── v1/
│       ├── attempt_event_summary.py
│       └── hr_reporting.py
├── core/
│   ├── config.py
│   ├── correlation.py
│   ├── errors.py
│   └── logging.py
├── integrations/
│   └── llm/
│       ├── protocol.py
│       └── provider_adapter.py
├── prompts/
│   ├── attempt_event_summary.py
│   └── hr_reporting.py
├── schemas/
│   ├── common.py
│   ├── attempt_event_summary.py
│   └── hr_reporting.py
└── services/
    └── workflows/
        ├── attempt_event_summary.py
        └── hr_reporting.py
```

The two modules under `services/workflows` are the only workflow handlers. The two API modules are transport adapters; the two prompt modules hold prompt construction/templates for their corresponding workflow. No directories or files need to be created until implementation begins.

## Module responsibilities and interfaces

### HTTP application and routes

- `main.py` creates the FastAPI application, registers the health and versioned workflow routes, installs correlation-ID middleware, and registers service-level exception handlers. It must not implement either workflow.
- `api/v1/attempt_event_summary.py` exposes `POST /api/v1/workflows/attempt-event-summary`. It accepts `AttemptEventSummaryRequest`, obtains the workflow and provider through application dependencies, calls the handler, and returns `AttemptEventSummaryResponse`.
- `api/v1/hr_reporting.py` exposes `POST /api/v1/workflows/hr-reporting`. It accepts `HRReportingRequest`, obtains the workflow and provider through application dependencies, calls the handler, and returns `HRReportingResponse`.

Routes perform only HTTP concerns: parsing and schema validation, dependency resolution, passing the correlation ID, and translating service errors to the documented HTTP error envelope. They do not build prompts, call provider SDKs, query data, calculate report values, or apply workflow rules. Backend remains responsible for authentication/authorization and for deciding which request to send.

### Workflow handlers

Each handler is a plain application service. It accepts validated data and an injected provider port; it has no dependency on FastAPI, `Request`, response objects, or a concrete provider SDK.

```python
async def handle(
    request: AttemptEventSummaryRequest,
    *,
    provider: LLMProvider,
    correlation_id: str,
) -> AttemptEventSummaryResponse: ...

async def handle(
    request: HRReportingRequest,
    *,
    provider: LLMProvider,
    correlation_id: str,
) -> HRReportingResponse: ...
```

Both functions may validate workflow-specific invariants, build their own prompt through the matching prompt module, invoke the shared provider port, validate the returned model, and raise typed service errors. They must not retrieve records, authorize users, classify the original HR query, or calculate/select numerical results. The HR handler receives only the Backend-classified reporting context and its permitted precomputed aggregate data.

### Shared provider boundary

- `integrations/llm/protocol.py` defines the provider-independent interface, for example `LLMProvider.generate(prompt, *, response_model, correlation_id)`. The result must be parsed/validated as the requested Pydantic response model.
- `integrations/llm/provider_adapter.py` implements that interface for the configured provider. Provider SDK types, credentials, transport, retries/timeouts, and provider-specific response parsing stay inside this adapter. The choice of concrete provider is configuration-driven and is not part of workflow code.
- Both handlers receive the same provider interface through dependency injection. A test can substitute a small fake provider without network access or provider credentials.

The interface is a design contract, not an implemented provider or a commitment to add a provider SDK in this issue.

### Configuration, prompts, schemas, and validation

- `core/config.py` owns typed service configuration: provider selection/settings supplied through environment variables, request timeout, and other operational limits. Secrets are not logged. Defaults and required values should be explicit; configuration validation should fail at startup for invalid settings.
- `prompts/attempt_event_summary.py` and `prompts/hr_reporting.py` own only the prompt templates/builders for their respective workflow. They accept typed, already-permitted inputs and do not retrieve or enrich data.
- `schemas/common.py` contains shared response/error metadata models only when genuinely shared.
- `schemas/attempt_event_summary.py` defines the request and response models for AI-FR-01. The request permits only structured authorized-attempt events with event type, start time, and measurable duration; it excludes video, images, question text, answer keys, and candidate answers. The response is a factual summary grounded in supplied events and must not invent events, causes, or cheating accusations.
- `schemas/hr_reporting.py` defines the request and response models for AI-FR-04. The request contains the Backend-classified supported report category, precomputed results, and the minimum reporting context. It does not carry raw database records or ask the Agent Service to calculate or select results. The supported categories are exactly those listed in ADR-001.
- Request models reject unknown fields (`extra="forbid"`) and apply type, size, and range constraints. The HTTP boundary validates incoming JSON; the provider adapter/workflow validates generated content against the explicit response model before it can be returned. Invalid model output is a service failure, not a successful response.

The exact field names and product-specific limits should be finalized from the full PRD when available; the PRD text was not present during this design review.

### Errors, correlation, and logs

- `core/errors.py` defines typed, provider-neutral errors such as provider unavailable, provider timeout, and invalid provider output. It contains no HTTP or SDK-specific behavior.
- `main.py` maps typed service errors to a stable JSON error envelope containing a safe error code, public message, and correlation ID. Suggested mappings are 503 for unavailable provider, 504 for provider timeout, and 502 for malformed provider output. Internal exception details and provider responses are not returned to callers. Framework request-validation failures remain 422 responses and use the same envelope where practical.
- `core/correlation.py` reads a valid incoming `X-Correlation-ID` or creates a UUID, places it in request context, includes it in success/error responses, and passes it to the handler and provider adapter. Reject or replace invalid/oversized values; do not trust arbitrary header contents as log structure.
- `core/logging.py` configures structured logs. Each workflow/provider log event should include correlation ID, workflow name, stage, outcome, and elapsed time where available. Do not log prompts, raw event payloads, candidate data, HR query content, provider credentials, or full provider responses. Use stable error codes for failures.

Provider failures are isolated to the optional AI request. The Backend can report that the AI capability is unavailable while retaining normal assessment functionality, as required by ADR-001. The Agent Service does not retry indefinitely or turn a failed provider call into invented output.

## Request flow

```text
Backend
  → FastAPI route (parse request, resolve dependencies, attach correlation ID)
  → one of the two workflow handlers (workflow-specific prompt and orchestration)
  → shared LLMProvider interface
  → configured provider adapter
  → response-model validation
  → route response or centralized safe error mapping
```

The route selects one handler based on its endpoint; it does not dispatch to a generic agent. Both workflows use the same provider boundary, while keeping their prompts, schemas, and handler logic separate.

## Dependency boundaries

Allowed direction is from HTTP routes to workflow services, and from workflow services to schemas, prompt builders, core configuration/error contracts, and the provider interface. The concrete provider adapter implements the provider interface and may depend on the chosen provider SDK. `main.py` wires the concrete adapter and workflow dependencies.

No Agent Service module may import Backend packages, Backend database sessions, Backend ORM models, SQLAlchemy for application data, PostgreSQL clients, or database repositories. No provider-specific SDK may be imported by a route, schema, prompt module, or workflow handler. The Backend alone retrieves and authorizes source data, classifies HR requests, and computes/selects every numeric result and report record.

## Testing strategy

- Keep the two workflow handlers independently testable as plain async functions. Pass a fake `LLMProvider` that records the prompt and returns a controlled Pydantic-compatible result; assert prompt inputs, output validation, and typed error behavior without an HTTP server or network.
- Test each schema's accepted fields, forbidden extra fields, and relevant limits independently.
- Use FastAPI `TestClient` for route tests, overriding provider/workflow dependencies with fakes. Check status codes, response schemas, correlation-ID propagation, and safe error envelopes.
- Retain the existing health endpoint test. No real provider credentials or external calls are needed for the unit and route test suites.

These are proposed tests; this architecture-only issue does not add tests or claim the workflows are implemented.

## ADR-001 consistency and known gaps

This design keeps exactly the two AI-FR-01 and AI-FR-04 workflows and preserves the ADR's boundaries: Backend-owned data and deterministic work, Agent Service as the only LLM integration boundary, no direct database access, bounded permitted inputs, and optional AI failure handling. It introduces no new service or autonomous agent.

The current application has only the health endpoint and no workflow routes, handlers, schemas, prompts, provider interface, configuration, structured logging, or correlation middleware. Those are design gaps to address in a later implementation issue. This document does not change the existing application or Docker Compose configuration. The Compose dependencies noted in ADR-001 remain a separate availability discrepancy and are not addressed here.
