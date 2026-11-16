# AGENTS.md — Instructions for Coding Agents

These instructions apply to Codex and other coding agents working in this repository.

The agent is an implementation assistant. It must work within the assigned GitHub issue, the approved product specification, the existing repository architecture, and the developer's authorization.

## 1. Mandatory reading before implementation

Before changing code, read:

1. `docs/SPEC.md` — product scope, requirements, architecture, and constraints.
2. The complete GitHub issue assigned to the current task, including its description, acceptance criteria, dependencies, and relevant discussion.
3. Relevant source code, tests, models, schemas, services, API routes, migrations, configuration, and documentation.
4. The current Git branch and working-tree status.

Check related issues and dependencies when available. If the issue cannot be accessed, ask the developer to provide its complete content; do not guess.

Do not assume an open issue means its functionality is absent. Inspect the repository first.

## 2. Source-of-truth rules

Use the documents for their intended purposes:

- `docs/SPEC.md` defines the product and technical baseline.
- GitHub Issues define individual implementation tasks and acceptance criteria.
- This `AGENTS.md` defines agent operating rules.
- `docs/DEVELOPMENT_WORKFLOW.md` defines team collaboration.

GitHub Issues are the project's implementation work breakdown. Work only on the assigned issue unless the developer explicitly authorizes additional scope.

If an issue conflicts with the specification, existing approved architecture, or another issue, stop before making the conflicting decision. Explain the conflict and request clarification. Do not silently redefine requirements.

Distinguish confirmed requirements from assumptions and open decisions in `docs/SPEC.md`.

## 3. Scope control

- Implement only what is necessary for the assigned issue and its acceptance criteria.
- Do not implement unrelated issues.
- Do not perform opportunistic refactoring.
- Do not add features because they seem useful.
- Do not duplicate functionality that already exists.
- Do not change public API contracts, shared schemas, or business behavior without a task-based reason.
- Do not change product scope or architecture without approval.
- Preserve unrelated user and teammate changes.

If a prerequisite is missing, determine whether it is genuinely blocking. Report the dependency and evidence rather than implementing a substitute without authorization.

## 4. Repository inspection

Before coding:

- Identify the relevant application entry points and module boundaries.
- Follow existing naming, import, configuration, error-handling, and test conventions.
- Inspect related implementations before creating new ones.
- Identify shared files that another developer may be changing.
- Check the working tree before editing.
- Avoid broad file moves or directory restructuring.

The actual repository structure takes precedence over conceptual directory examples in older documentation.

## 5. Backend engineering rules

For backend changes:

- Use the existing FastAPI application patterns.
- Use Pydantic schemas for request/response validation where appropriate.
- Use SQLAlchemy according to the repository's established version and conventions.
- Keep API transport concerns separate from business logic.
- Put reusable business rules in appropriate services/modules rather than unnecessarily in route handlers.
- Enforce authorization on the backend.
- Use transactions for operations requiring atomicity.
- Handle errors explicitly and consistently.
- Preserve deterministic grading.
- Treat the server as authoritative for examination timing, attempt status, submission, and official results.
- Avoid leaking internal exception details, credentials, or sensitive data in API responses.

Do not add a new framework, dependency, architectural layer, or abstraction without demonstrating why it is needed for the assigned issue.

## 6. Frontend engineering rules

For frontend changes:

- Use the existing Next.js, React, and TypeScript conventions.
- Reuse existing components, hooks, API clients, and styling patterns where appropriate.
- Keep types accurate; do not hide errors with broad `any` types or unsafe casts.
- Validate user input at the appropriate boundary.
- Present understandable loading, empty, success, and error states where relevant.
- Keep API communication separate from presentation where the existing architecture supports it.
- Do not redesign unrelated screens.
- Never treat frontend state as authoritative for authorization, official scores, examination timing, or final attempt state.

## 7. Database and migration rules

- Inspect existing models and migrations before changing the schema.
- Use Alembic migrations for schema changes.
- Do not manually change a production database schema.
- Preserve foreign-key and referential integrity.
- Add suitable constraints and indexes where required by the task.
- Consider existing data and migration upgrade behavior.
- Do not create duplicate or conflicting migrations.
- Coordinate with the developer when a change touches shared models or migration files.
- Do not run destructive database commands against shared, production, or unknown databases.
- Never commit real candidate data.

If migration history or database state is unclear, inspect and report before applying changes.

## 8. Examination and grading rules

- The backend is authoritative for examination state and timing.
- Enforce valid attempt-state transitions.
- Persist candidate answers reliably.
- Do not expose answer keys or restricted question content to candidates.
- Do not calculate official scores in the frontend.
- Grading must remain deterministic.
- Do not recalculate or overwrite persisted official results unless the assigned issue explicitly requires an approved behavior.
- Do not invent lifecycle states, transitions, scoring rules, or recovery behavior.

## 9. Recording, proctoring, and privacy rules

- Recording files must remain in private storage.
- Enforce authorization for recording and event access.
- Validate recording chunks and their association with the correct attempt/recording.
- Do not mark incomplete or invalid recording data as successfully published.
- Keep recording metadata distinct from the actual video files.
- Do not expose private storage paths or unrestricted object references.
- Do not log video content, credentials, tokens, or unnecessary candidate personal information.
- Respect candidate consent and the configured permission flow.
- Do not add microphone recording.
- Do not invent retention periods or recording state transitions.
- Record only events the application can actually observe.
- Do not implement automated cheating judgments, face recognition, YOLO, or computer-vision misconduct detection.

## 10. AI restrictions

The specified MVP has exactly two AI capabilities:

1. AI-01 — AI Event Summary.
2. AI-04 — Natural Language HR Reporting.

For AI-related tasks:

- Keep AI calls backend-controlled.
- Apply authorization before retrieving or preparing inputs.
- Bound and validate inputs and outputs.
- Preserve source records and calculated results.
- Handle provider errors and timeouts safely.
- Do not allow the LLM to execute arbitrary SQL.
- Do not let the LLM invent statistics or events.
- Do not send candidate video, screen recordings, question text, answer keys, or candidate answers to the LLM for these MVP features.
- Do not implement LLM grading, candidate scoring, candidate ranking, cheating judgments, or recruitment decisions.
- Do not assume a provider/model is approved unless the team has selected it.

AI failure must not interrupt core examination functionality.

## 11. Security and configuration

- Never hard-code credentials, tokens, API keys, or secrets.
- Do not print secrets in logs or final reports.
- Use the repository's environment/configuration conventions.
- Update example configuration with placeholders only.
- Validate untrusted input.
- Enforce authorization at the backend boundary.
- Apply safe upload and file handling.
- Avoid exposing stack traces or internal implementation details to end users.
- Do not weaken security checks to make tests pass.

## 12. Testing and verification

For every behavior change:

1. Add or update relevant tests.
2. Run focused tests for the changed behavior.
3. Run broader relevant tests when practical.
4. Run configured formatting, linting, and type checks where applicable.
5. Test migrations when the schema changes.
6. Inspect the final diff for unrelated or accidental changes.

Report exact commands and actual results. Never claim a test passed if it was not run. Distinguish failures introduced by the change from pre-existing failures or environment limitations.

Do not modify or delete tests merely to make an implementation pass unless the test itself is demonstrably incorrect and the developer has authorized the correction.

## 13. Git and external-action restrictions

Unless the developer explicitly authorizes the action:

- Do not commit.
- Do not push.
- Do not merge.
- Do not force-push.
- Do not reset, clean, or delete branches.
- Do not discard user changes.
- Do not modify GitHub issues, labels, assignments, milestones, or project settings.
- Do not change repository permissions or secrets.
- Do not run destructive database or storage operations.

Before switching branches or applying changes, inspect `git status` and preserve all existing work.

## 14. When to stop and ask

Stop and report when:

- The assigned issue is unavailable or ambiguous in a way that affects implementation.
- A required prerequisite is missing.
- The issue conflicts with `docs/SPEC.md`.
- A proposed change would alter a shared contract or architecture without approval.
- The working tree contains changes that could be overwritten.
- The operation could destroy data or affect a shared/production environment.
- Required credentials, services, or test infrastructure are unavailable and cannot safely be bypassed.

Do not ask for approval for every routine, reversible implementation step. Use reasonable engineering judgment within the assigned scope and these restrictions.

## 15. Required completion report

At the end of the task, report:

1. **Issue:** issue number and title.
2. **Implementation:** concise summary of behavior implemented.
3. **Files changed:** list and purpose.
4. **Acceptance criteria:** how each was addressed.
5. **Tests:** exact commands and results.
6. **Migrations:** migration files and validation, if applicable.
7. **Limitations:** known gaps or environment blockers.
8. **Open questions:** anything requiring team decision.
9. **Git state:** current branch and working-tree status.
10. **Scope confirmation:** any deviations from the issue or specification.

Do not claim completion if acceptance criteria remain unmet or required verification was not performed.
