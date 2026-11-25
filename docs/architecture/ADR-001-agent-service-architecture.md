# ADR-001: Independent Agent Service Architecture

## Status

Accepted. The team has approved retaining the existing independently deployed FastAPI Agent Service at `agents/agent_service/`. This ADR records that decision; it does not assign an approval date, meeting, or individual approver.

## Context and problem

The application needs a bounded AI integration boundary while keeping assessment workflows independent of an external AI provider. The repository currently contains a separate FastAPI Agent Service with a health endpoint, backend integration placeholders, PostgreSQL models for attempts, events, and recording metadata, and Docker Compose definitions for separate frontend, backend, agent-service, and PostgreSQL services. The AI workflows described below are architectural scope for the MVP, not implemented features.

The repository does not contain the Persian PRD PDF or another source defining the full text of AI-FR-01 through AI-FR-05 or DD-21 through DD-23. The requirement IDs and scope summarized here come from the approved architecture task for this issue. Their exact wording and detailed mapping to each DD cannot be verified from the repository.

## Decision

Retain one independently deployed FastAPI Agent Service as the AI integration boundary. The Backend application communicates with this separately deployed service over its API. The LLM Provider is accessed only through the Agent Service.

The Agent Service will contain exactly two bounded, independently testable AI workflows:

1. Attempt Event Summary (AI-FR-01).
2. Natural-Language HR Reporting (AI-FR-04).

These are approved MVP boundaries, not implementation claims.

## Responsibilities

### Frontend

- Communicates only with the Backend.
- Never calls the Agent Service or LLM Provider directly.

### Backend

- Owns all PostgreSQL access.
- Handles authentication and authorization.
- Retrieves attempt events and classifies HR natural-language queries.
- Performs deterministic calculations and owns application-level workflow orchestration.
- Calls the Agent Service through its API, sending only data permitted by the boundaries below.

### Agent Service

- Remains an independent FastAPI service.
- Owns shared LLM provider integration, prompt execution, and AI output handling.
- Implements only the two bounded workflows listed in this ADR.
- Does not connect directly to PostgreSQL, perform authorization, or perform numerical analytics.
- Does not become a general-purpose chatbot or autonomous multi-agent system.

### LLM Provider

- Is accessed exclusively through the Agent Service.
- Is never called directly by the Frontend or Backend.

## Communication flow

Requests flow as follows:

```text
Frontend → Backend → Agent Service → LLM Provider
```

Responses return through the same chain:

```text
LLM Provider → Agent Service → Backend → Frontend
```

## Permitted data boundaries

### AI-FR-01: Attempt Event Summary

The Backend may send only the actual structured events belonging to the authorized attempt. Permitted fields are event type, start time, and duration when measurable.

The request must not include videos, images, question text, answer keys, or candidate answers. The model must not invent events, speculate about causes, or accuse a candidate of cheating. Authorization and attempt selection remain Backend responsibilities.

### AI-FR-04: Natural-Language HR Reporting

The Backend classifies the query and computes exact results. The Agent Service receives only the permitted aggregated results and the reporting context needed to express those results.

Only these four report categories are supported:

1. Attempt counts by status.
2. Average, minimum, and maximum score for one exam, excluding cancelled and not-started attempts.
3. Attempts with the most events.
4. Attempts with incomplete recordings.

Unsupported questions must not produce invented numbers or records. Numerical results and record selection are computed by the Backend.

## Failure isolation and AI unavailability

Failure of an AI workflow, the Agent Service, or an external LLM Provider must not interrupt core assessment functionality. Exam creation and execution, answer saving, recording, scoring, raw event review, and Excel export must remain usable without an external AI provider.

The Backend must treat AI features as optional capabilities and handle Agent Service/provider failures without making those core functions unavailable.

## Scope restrictions

The MVP does not include:

- Cheating detection.
- Autonomous recruitment or candidate suitability decisions.
- Question generation or improvement.
- Facial recognition.
- Video or image analysis.
- Candidate guidance.
- Additional AI services or autonomous agents.

## Consequences and trade-offs

- A separate deployable service gives the AI workflows an explicit API boundary and keeps provider-specific integration outside the Backend.
- The Backend remains the source of truth for access control, database queries, deterministic calculations, and assessment workflows.
- Separate deployment adds a network boundary and another service to operate; API failures and timeouts must be handled without blocking core assessment use.
- Restricting inputs and report categories reduces exposure of candidate data and limits unsupported AI output.
- The repository currently provides only a health-check placeholder, so both approved AI workflows and the necessary failure handling remain future implementation work.
- Current Compose wiring does not fully reflect the approved communication and availability boundaries; see the implementation discrepancies below.

## Current implementation discrepancies

Observed in the repository at the time this ADR was written:

- Both `docker-compose.yml` and `docker-compose.prod.yml` pass `AGENT_SERVICE_URL` to the Frontend, although the approved boundary says the Frontend communicates only with the Backend.
- Both Compose files make the Frontend depend on Agent Service health. Both also make Backend startup depend on Agent Service health. The Backend dependency can prevent core Backend availability when the Agent Service is unhealthy, contrary to the required failure isolation.
- `README.md` says the Frontend homepage displays all three service states, which may expose a direct Frontend-to-Agent health-check path and should be checked during a later implementation review.
- `agents/agent_service/app/main.py` contains only a health endpoint. Backend agent integration modules and routes are placeholders. No AI workflow is implemented.

These are recorded for follow-up; this issue changes architecture documentation only.

## References

- Product requirements: AI-FR-01 through AI-FR-05 (full PRD text was not present in the repository during inspection).
- Design decisions: DD-21 through DD-23 (source text was not present in the repository during inspection).
- Issue #20: “Approve and Document the MVP AI Service Architecture.”
- Repository implementation reviewed: `README.md`, `agents/README.md`, `agents/agent_service/app/main.py`, Backend agent integration placeholders, and both Docker Compose files.
