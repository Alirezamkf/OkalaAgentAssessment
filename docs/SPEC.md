# Okala Examination System — Product and Technical Specification

**Project:** AI-Powered Internship Aptitude Assessment Platform with Remote Proctoring
**Product:** Okala Examination System
**Specification version:** 1.1
**Status:** Shared project baseline
**Architecture:** Modular monolithic application
**Backend:** Python / FastAPI
**Frontend:** Next.js / React / TypeScript
**Database:** PostgreSQL
**Team:** Three developers collaborating through GitHub Issues

---

## 1. Purpose, scope, and authority

### 1.1 Purpose

This document defines the product scope, functional requirements, architectural principles, technical constraints, security and privacy expectations, and business rules for the Okala Examination System MVP.

It is the shared product and technical baseline for all three developers and their coding agents.

### 1.2 Project work breakdown

The project implementation is organized through the **198 GitHub Issues established for the repository**. Individual issues describe implementation tasks, dependencies, deliverables, and acceptance criteria.

The documents have distinct responsibilities:

- **`docs/SPEC.md`** defines what the product is intended to do and the approved product and architecture constraints.
- **GitHub Issues** define the individual implementation tasks and their acceptance criteria.
- **`AGENTS.md`** defines mandatory operating instructions for coding agents.
- **`docs/DEVELOPMENT_WORKFLOW.md`** defines how the three developers coordinate their work.

GitHub Issues are the implementation work breakdown. This specification does not prescribe a separate implementation schedule or task hierarchy.

An issue must be interpreted consistently with this specification. If an issue, the current implementation, and this specification appear to conflict, the developer must raise the conflict for team resolution rather than silently changing product behavior.

### 1.3 Status and interpretation

This document preserves the original project requirements while clarifying their organization. A statement marked as an open decision, proposal, or assumption is not an approved requirement until the team confirms it.

The specification is not a substitute for reading the assigned GitHub issue, inspecting the repository, or checking dependencies.

---

## 2. Product overview

### 2.1 Overview

The Okala Examination System is an online internship aptitude assessment platform intended to support the recruitment and evaluation of internship candidates.

The platform enables HR administrators to create and manage assessments, register candidates, distribute individual examination links, conduct timed online examinations, collect recording evidence, monitor observable browser events, calculate examination scores, and review candidate performance.

The system also provides two controlled AI-assisted capabilities for HR administrators:

1. **AI Event Summary:** Generates Persian-language summaries of actual recorded proctoring events.
2. **Natural Language HR Reporting:** Allows authorized HR administrators to ask supported questions about assessment statistics in natural language.

The platform is intended to provide structured assessment workflows, reliable examination execution, recording integrity, transparent evidence collection, and human-controlled recruitment decisions.

### 2.2 Objectives

The system is intended to:

- Provide a secure HR administration interface.
- Support examination creation and configuration.
- Support multiple-choice questions and answer keys.
- Register candidates and generate unique examination links.
- Provide secure candidate examination access.
- Support timed examinations.
- Save candidate answers automatically.
- Record webcam and shared-screen video with candidate consent.
- Capture observable browser and examination events.
- Support interrupted recording recovery.
- Calculate examination scores deterministically.
- Provide authorized HR access to assessment results and recording evidence.
- Export assessment results to Excel.
- Provide the two controlled AI-powered HR assistance capabilities described in this document.
- Preserve human responsibility for recruitment decisions.

### 2.3 Product boundaries

The MVP is an assessment and evidence-support platform. It is not an autonomous recruitment decision system and does not automatically determine whether a candidate cheated.

The initial architecture is modular monolithic. Modules should have clear responsibilities and boundaries without requiring independently deployed microservices for the MVP.

---

## 3. Users, roles, and access boundaries

### 3.1 HR Administrator

HR administrators manage assessment and recruitment workflows. Their responsibilities include:

- Secure authentication.
- Creating and editing examinations.
- Managing questions and answer keys.
- Configuring examination duration and access windows.
- Registering candidates.
- Generating individual examination links.
- Publishing and cancelling examinations.
- Monitoring candidate examination attempts.
- Reviewing recording evidence.
- Reviewing observable event logs.
- Viewing calculated examination results.
- Requesting AI-generated event summaries.
- Asking supported natural-language reporting questions.
- Recording recruitment decisions.
- Exporting assessment results.

HR access to candidate information, examination records, results, and recordings must be authorized by the backend.

### 3.2 Candidate

Candidates participate through individual examination links. The candidate workflow may include:

- Opening a personal examination link.
- Completing the configured identity-verification process.
- Reviewing recording and privacy information.
- Providing or rejecting recording consent.
- Checking webcam and screen-sharing permissions.
- Starting an examination when eligible.
- Answering examination questions.
- Viewing remaining examination time.
- Having answers saved automatically.
- Submitting the examination.
- Recovering an interrupted session when permitted.
- Viewing examination completion status.

A candidate must not gain access to:

- Correct answer keys.
- Other candidates' information or examination attempts.
- Other candidates' recordings.
- HR-only reports or decisions.
- Internal grading configuration.
- Unauthorized examination results.

Candidate-facing responses must expose only the information needed for the candidate's own permitted workflow.

---

## 4. Functional requirements

The identifiers below preserve the original specification's requirement labels. GitHub Issues may split, combine, or implement these requirements across multiple tasks; the identifiers do not replace issue acceptance criteria.

### 4.1 HR administration

| ID | Feature | Requirement |
|---|---|---|
| F01 | HR Authentication | HR users can authenticate securely. |
| F02 | Exam Creation | Authorized HR users can create an assessment. |
| F03 | Question Management | Authorized HR users can create and manage multiple-choice questions. |
| F04 | Answer Key Management | Authorized HR users can define correct answers and scores. |
| F05 | Exam Configuration | HR users can configure examination duration and access windows. |
| F06 | Candidate Management | HR users can register and manage candidate records. |
| F07 | Unique Exam Links | The system can generate an individual examination link for each assigned candidate. |
| F08 | Exam Publication | Authorized HR users can publish and cancel examinations. |
| F09 | Candidate Monitoring | HR users can review examination-attempt status. |
| F10 | Recording Review | Authorized HR users can review available candidate recordings. |
| F11 | Event Review | HR users can view persisted browser/proctoring events. |
| F12 | HR Decision | HR users can record a recruitment decision, such as accept, reject, or request review, subject to the approved decision workflow. |
| F13 | Excel Export | Authorized HR users can download assessment results in Excel format. |

### 4.2 Candidate features

| ID | Feature | Requirement |
|---|---|---|
| F14 | Secure Exam Access | A candidate can open their own personal examination link. |
| F15 | Identity Verification | The system performs the configured verification of the registered candidate's email/phone or other approved identity mechanism. Exact policy remains subject to the relevant open decision. |
| F16 | Consent Management | The candidate can accept or reject recording consent before recording-dependent examination activity. |
| F17 | Equipment Check | The candidate can check webcam and screen-sharing permissions. |
| F18 | Exam Participation | The candidate can answer the questions made available for their examination. |
| F19 | Countdown Timer | Remaining time is determined by the server; the interface displays it to the candidate. |
| F20 | Automatic Answer Saving | Candidate answer changes are saved automatically and reliably. |
| F21 | Exam Submission | The candidate can submit the examination according to the backend-controlled lifecycle. |
| F22 | Reconnection | An interrupted session can resume only under the approved recovery conditions. |
| F23 | Exam Completion | The candidate can see completion status without disclosure of answer keys or unauthorized scores. |

### 4.3 Remote proctoring and observable events

| ID | Feature | Requirement |
|---|---|---|
| F24 | Webcam Recording | Record the candidate's webcam after the required permission and consent. |
| F25 | Screen Recording | Record the candidate's shared screen after the required permission and consent. |
| F26 | Event Detection | Persist supported observable browser and examination events. |
| F27 | Tab Switching Detection | Record supported page/tab visibility changes. |
| F28 | Copy/Paste Events | Record observable copy/paste actions where browser capabilities permit. |
| F29 | Idle Event Logging | Record configured inactivity events. |
| F30 | Recording Interruption | Detect and represent recording interruptions. |
| F31 | Recording Recovery | Support recovery within the currently specified 120-second window, subject to confirmation of the exact policy. |
| F32 | Recording Integrity | Preserve and validate recording chunks before treating a recording as successfully published. |
| F33 | Incomplete Recording Status | Represent incomplete recordings accurately so HR is not misled about recording completeness. |

The system records observable evidence. It does **not** automatically determine that a candidate cheated, committed misconduct, or deserves a particular recruitment outcome. Browser event collection is limited by actual browser capabilities and permissions; the product must not claim to observe activity that it cannot reliably observe.

### 4.4 AI capabilities

Only two AI capabilities are in the specified MVP scope:

| ID | Feature | Requirement |
|---|---|---|
| AI-01 | AI Event Summary | Generate a Persian-language summary of actual events belonging to an individual examination attempt. |
| AI-04 | Natural Language HR Reporting | Answer supported HR questions using backend-calculated assessment statistics. |

Detailed behavior and restrictions are defined in Section 10.

---

## 5. Non-functional requirements

### 5.1 Security

- Every protected backend operation must enforce authentication and authorization.
- Candidate-specific examination links must use secure, unpredictable tokens.
- Sensitive information must not be exposed through public or candidate-facing APIs.
- Recording files must not be publicly accessible.
- HR access to recordings and candidate records must be authorized.
- Secrets and credentials must be supplied through environment configuration or an approved secret-management mechanism.
- API inputs must be validated.
- Database access must use safe parameterized or ORM mechanisms.
- Sensitive information must not be written unnecessarily to application logs.
- Authorization must be enforced by the backend, not merely by hiding frontend controls.

### 5.2 Reliability

- Candidate answers must be saved reliably.
- Examination timing must be controlled by the server.
- Recording uploads must support chunked transfer.
- Recording interruptions must be represented accurately.
- Recovery must follow the approved recovery window and rules.
- Invalid or incomplete recording chunks must not be represented as successfully published.
- Failure of an AI service must not prevent core examination functionality.
- Persisted examination data must remain consistent through retries and recoverable failures.

### 5.3 Maintainability

- Code must be organized into modules with clear responsibilities.
- Business logic must not be unnecessarily duplicated.
- API contracts and non-obvious business rules must be documented.
- Database schema changes must use migrations.
- Tests must be maintained with implementation code.
- Architectural decisions and material deviations must be documented.
- Existing repository conventions should be followed unless an approved change is made.

### 5.4 Privacy

- Recording requires explicit candidate consent.
- Recording and personal-data handling must follow applicable privacy requirements.
- Only necessary information should be collected and processed.
- AI requests must contain only information permitted for the relevant AI feature.
- Candidate video, screen recordings, question text, answer keys, and candidate answers must not be sent to the LLM for the two MVP AI features.
- Access to recordings and candidate data must be limited to authorized users and legitimate workflows.

### 5.5 Performance

- Examination interfaces should remain responsive during an active attempt.
- Answer-saving requests should be lightweight and reliable.
- Recording uploads should use chunks rather than requiring one large upload.
- Database operations should avoid unnecessary repeated queries.
- AI requests should use bounded inputs, appropriate timeouts, and controlled failure handling.

---

## 6. System architecture

### 6.1 Architectural style

The specified architecture is a **modular monolithic application**.

This means:

- The primary backend is an integrated FastAPI application.
- Backend source code is organized into functional modules.
- Each module has clear responsibilities and boundaries.
- Modules communicate through internal application interfaces.
- The MVP does not require independently deployed microservices.
- Future architectural evolution requires a reasoned team decision.

The frontend and backend are separate application components within the overall product.

If the current repository contains additional processes, containers, or services, their actual responsibilities must be understood and documented accurately. Their presence alone does not authorize an architectural redesign.

### 6.2 Technology baseline

| Layer | Technology | Responsibility |
|---|---|---|
| Frontend | Next.js / React | User interfaces |
| Frontend language | TypeScript | Type-safe frontend development |
| Backend language | Python | Business logic |
| Backend framework | FastAPI | API and backend services |
| Database | PostgreSQL | Structured application data |
| ORM | SQLAlchemy | Database interaction |
| Migrations | Alembic | Database schema evolution |
| Browser recording | MediaRecorder API | Webcam recording |
| Screen capture | Screen Capture API (`getDisplayMedia`) | Shared-screen recording |
| Excel generation | Pandas / OpenPyXL | Excel exports |
| AI integration | LLM API | The two approved AI capabilities |
| Containerization | Docker | Application packaging |
| Local orchestration | Docker Compose | Local application environment |

The exact LLM provider and model are not fixed by this specification. Model selection must be based on evaluation against the requirements in Section 10.5.

The repository's actual dependency versions and configuration are implementation facts and should be inspected rather than guessed.

### 6.3 Frontend responsibilities

The frontend provides the HR and candidate experiences.

**HR Dashboard areas:**

- Login.
- Examination management.
- Question management.
- Candidate management.
- Examination monitoring.
- Recording review.
- Event review.
- Results and reporting.
- AI-assisted reporting.
- HR decisions.

**Candidate Portal areas:**

- Personal examination access.
- Identity verification.
- Consent information and handling.
- Equipment checks.
- Examination interface.
- Remaining-time display.
- Answer interaction and submission.
- Completion status.

**Browser recording responsibilities:**

- Request and handle webcam permission.
- Request and handle screen-sharing permission.
- Initialize browser recording.
- Generate recording chunks.
- Upload chunks.
- Detect client-side recording interruptions where possible.
- Participate in the approved recovery workflow.

The frontend is not authoritative for authorization, examination timing, final attempt status, or official scores.

### 6.4 Backend responsibilities

The backend is authoritative for:

- Authentication and authorization.
- Examination business rules.
- Question and answer management.
- Candidate registration and assignment.
- Examination-link generation and validation.
- Examination lifecycle and state transitions.
- Server-controlled timing.
- Candidate answer persistence.
- Submission.
- Deterministic grading.
- Recording upload processing.
- Recording recovery and publication.
- Event persistence.
- Recording metadata and completeness status.
- Excel generation.
- AI request preparation, access control, and orchestration.

Business logic should reside in appropriate services/modules rather than being concentrated in API route handlers.

### 6.5 Data and storage responsibilities

PostgreSQL stores structured application data and authoritative metadata.

Video recording files and chunks are stored separately in private file or object storage. The database stores their metadata, relationships, status, and storage references as appropriate; large video binaries should not be placed in ordinary relational records.

Storage access must be mediated by backend authorization. Private storage references or filesystem paths must not be exposed as public access mechanisms.

### 6.6 AI integration boundary

AI integrations are backend-controlled. The LLM must not directly control examination state, grading, candidate ranking, or HR decisions.

The backend prepares permitted inputs, performs calculations where required, validates results, applies authorization, and handles provider failures.

---

## 7. Core application modules

The following are logical module responsibilities. They do not mandate a particular directory layout. Developers must follow the actual repository structure and avoid unnecessary restructuring.

### 7.1 Authentication

Responsibilities:

- HR login.
- Credential verification.
- Session or token lifecycle.
- Authorization.
- Protected API access.

### 7.2 Examination management

Responsibilities:

- Create and edit examinations.
- Configure duration and access windows.
- Publish examinations.
- Cancel examinations.
- Enforce examination-management permissions.

### 7.3 Question management

Responsibilities:

- Store and manage questions.
- Store answer options.
- Store correct answers and score values.
- Validate question configuration.
- Prevent answer-key disclosure to candidates.

### 7.4 Candidate management

Responsibilities:

- Store candidate information.
- Register candidates.
- Assign candidates to examinations.
- Generate individual examination links.
- Manage candidate examination access.

### 7.5 Assessment engine

Responsibilities:

- Deliver permitted examination content.
- Manage examination attempts.
- Enforce server-side timing.
- Persist candidate answers.
- Handle submission.
- Enforce valid lifecycle transitions.

### 7.6 Grading

Responsibilities:

- Retrieve submitted answers.
- Compare answers with authoritative answer keys.
- Calculate official scores deterministically.
- Persist official results.

Grading must not use an LLM. The frontend must not calculate authoritative scores.

### 7.7 Reporting and Excel export

Responsibilities:

- Retrieve authorized assessment results.
- Generate Excel reports.
- Provide authorized downloads.
- Ensure report contents are consistent with persisted authoritative data.

### 7.8 HR decisions

Responsibilities:

- Record HR decisions associated with the relevant candidate/attempt context.
- Preserve the decision information required by the approved workflow.
- Enforce HR authorization.

The exact decision-history model and workflow must follow the approved issue requirements and team decisions; this specification does not prescribe an unapproved schema.

### 7.9 Audit and events

Responsibilities:

- Persist supported observable browser events.
- Record relevant examination lifecycle events.
- Preserve event timestamps and relevant metadata.
- Provide authorized event retrieval.
- Preserve original event records independently of AI summaries.

### 7.10 Remote proctoring

Responsibilities include browser capture, chunk upload, storage, interruption handling, recovery, validation, publication, completeness status, and authorized review. Details are in Section 8.

### 7.11 AI

Responsibilities are limited to AI-01 Event Summary and AI-04 Natural Language HR Reporting as defined in Section 10.

---

## 8. Remote proctoring and recording

### 8.1 Webcam recording

The browser captures webcam video using the MediaRecorder API after the candidate has been informed and has granted the required permission and consent.

### 8.2 Screen recording

The browser captures the candidate's selected/shared screen using browser screen-capture capabilities after the required permission and consent.

### 8.3 Recording chunks and upload

Recording data is uploaded in chunks. The backend must validate upload context and chunk metadata, associate chunks with the correct attempt/recording, and handle retries or interruptions consistently.

The implementation must not treat receipt of one chunk as proof that the complete recording is valid or published.

### 8.4 Storage

Recording files and chunks reside in private file/object storage. PostgreSQL stores metadata and references. Recording access must be authorized by the backend.

### 8.5 Interruption and recovery

The system must represent recording interruptions and support the specified recovery behavior. The original specification identifies a 120-second recovery window; the exact start/end conditions, retry semantics, and interaction with attempt state must be confirmed against approved task requirements and team decisions before implementation where ambiguity exists.

### 8.6 Validation and publication

Recording chunks must be validated before a recording is marked successfully published. Invalid, missing, or incomplete chunks must not be silently treated as complete. Recording completeness and publication status must accurately reflect persisted evidence.

### 8.7 Observable event collection

The specified examples include:

- Tab/page visibility changes.
- Observable copy/paste actions.
- Inactivity events.
- Recording interruptions.
- Relevant examination lifecycle events.

Only events the application can actually observe should be recorded. Event metadata and timestamps should be preserved sufficiently for authorized review.

### 8.8 HR review

Authorized HR users may review available recordings and event records. The interface must distinguish complete, incomplete, interrupted, unavailable, and published states according to the implemented approved status model.

### 8.9 Explicit limitations

The MVP does not include:

- Microphone recording.
- Face recognition.
- Facial identity matching.
- YOLO-based detection.
- Computer-vision-based cheating detection.
- Automatic cheating or misconduct judgments.

The platform supplies evidence for human review; it does not make automated misconduct determinations.

---

## 9. Data model and database principles

### 9.1 Logical entities

The original logical data concepts include:

1. `HRUser`
2. `Candidate`
3. `Exam`
4. `Question`
5. `QuestionOption`
6. `ExamQuestion`
7. `CandidateExamAssignment`
8. `ExamAttempt`
9. `CandidateAnswer`
10. `ExamResult`
11. `HRDecision`
12. `ProctoringEvent`
13. `Recording`
14. `RecordingChunk`
15. `AISummary`
16. `AIReportRequest`

These are conceptual entities, not a final database schema. The exact table names, fields, relationships, constraints, indexes, and persistence strategy must follow approved implementation decisions, existing repository conventions, and relevant GitHub issues.

Do not infer a final schema from this list alone.

### 9.2 Integrity principles

- Use primary keys and foreign keys where appropriate.
- Enforce appropriate uniqueness constraints.
- Validate relationships between candidates, examinations, assignments, and attempts.
- Prevent unauthorized access to another candidate's records.
- Preserve the relationship between recording chunks and their recording/attempt context.
- Use database transactions for operations requiring atomicity.
- Maintain migration history.
- Avoid silently overwriting important examination records.
- Use constraints and indexes appropriate to access patterns and integrity requirements.
- Never use manual production schema changes as a substitute for migrations.

### 9.3 Attempt lifecycle

Examination attempts must have explicit persisted states. The backend must enforce valid transitions and reject invalid transitions.

The original specification does not provide a complete, approved transition table. Developers must use the relevant approved GitHub issues and team decisions to establish exact states, transitions, and edge cases. Do not invent lifecycle transitions.

### 9.4 Recording lifecycle

The original specification identifies these recording concepts/states:

- Recording requested.
- Recording started.
- Recording in progress.
- Recording interrupted.
- Recording recovering.
- Recording completed.
- Recording incomplete.
- Recording published.
- Recording unavailable.

The exact enum, transition rules, and relationships between upload reservations, chunks, recovery, completeness, and publication must be established by approved implementation requirements. Do not collapse distinct concepts or invent transitions.

### 9.5 Database changes

All database schema changes must be represented by the repository's migration system, using Alembic where applicable. Migrations must be reviewed and tested, especially when multiple developers work on related models or shared schema.

---

## 10. AI capabilities and restrictions

### 10.1 Approved scope

Only the following two AI capabilities are included in the specified MVP:

1. AI-01: AI Event Summary.
2. AI-04: Natural Language HR Reporting.

No additional AI feature may be introduced without an agreed specification change.

### 10.2 AI-01 — AI Event Summary

**Purpose:** Provide HR with a readable Persian summary of actual recorded events belonging to one examination attempt.

**Permitted input may include:**

- Event records belonging to the relevant attempt.
- Event type.
- Event start time.
- Event duration, where available.
- Other approved, non-content event metadata needed to explain the event.

**Processing:**

1. The backend retrieves the relevant persisted event records.
2. The backend checks authorization and filters/prepares permitted metadata.
3. The LLM receives only the permitted event information.
4. The LLM generates a Persian, time-oriented summary.
5. HR can compare the summary with the original event log.

**Output:** A human-readable Persian event summary.

**Restrictions:**

- The model must not invent events or facts.
- The model must not claim that a candidate cheated.
- The model must not assign misconduct labels.
- The model must not determine candidate competence.
- The model must not score or rank candidates.
- The summary must not replace the original event log.
- Original events must remain available if AI generation fails.
- Candidate video, screen recordings, question text, answer keys, and candidate answers must not be sent to the LLM for this feature.

### 10.3 AI-04 — Natural Language HR Reporting

**Purpose:** Allow an authorized HR administrator to ask supported questions about assessment statistics in natural language.

**Examples from the original specification:**

- How many candidates completed the examination?
- What is the average examination score?
- How many candidates have incomplete recordings?
- What is the distribution of candidate scores?

**Processing:**

1. The backend receives the HR question and verifies authorization.
2. The backend identifies whether the question maps to a supported reporting category.
3. The backend calculates the required statistics using SQL and/or Python.
4. The backend prepares a structured result.
5. The LLM converts the structured result into a Persian natural-language explanation.
6. The backend returns the response to HR.

**Restrictions:**

- Statistical calculations are performed by the backend, not invented by the LLM.
- The LLM must not execute arbitrary SQL.
- Unsupported questions must be handled safely.
- Responses must be grounded in calculated results.
- Unauthorized candidate information must not be exposed.
- The LLM must not make recruitment decisions.
- Candidate video, screen recordings, question text, answer keys, and candidate answers must not be sent to the LLM for this feature.

### 10.4 AI failure handling

If an AI provider is unavailable or returns an invalid response:

- Core examination functionality must continue.
- Original event logs must remain accessible.
- Persisted results must remain accessible.
- The AI operation must return a controlled failure.
- AI failure must not be treated as examination failure.
- The system must not fabricate a successful summary or report.

### 10.5 Model/provider evaluation

The provider and model are not predetermined. Potential model families mentioned in the original project context include GPT, Qwen, and DeepSeek, but none is selected by this specification.

Evaluation criteria include:

- Persian language quality.
- Factual accuracy.
- Faithfulness to supplied information.
- Instruction following.
- Latency.
- Cost.
- Reliability.
- Privacy and data-handling suitability.

A model must not be treated as approved merely because it is available or inexpensive.

---

## 11. Security, privacy, and operational requirements

1. Never commit API keys, passwords, tokens, or other secrets.
2. Use local environment configuration and maintain placeholder examples such as `.env.example`.
3. Never commit real candidate personal information or recordings.
4. Keep recording files in private storage.
5. Enforce backend authorization for every protected operation.
6. Validate uploaded recording chunks and their association with the correct attempt.
7. Validate API inputs.
8. Use migrations for database schema changes.
9. Avoid logging unnecessary sensitive information.
10. Do not trust frontend values for official scores, timing, permissions, or final attempt status.
11. Validate important state changes on the server.
12. Apply appropriate file-size and upload limits.
13. Use safe error handling.
14. Do not expose stack traces, credentials, or private storage details in production responses.
15. Document security-sensitive decisions.
16. Respect candidate consent and applicable privacy requirements.
17. Do not send restricted candidate content to the LLM for the two MVP AI capabilities.

This specification does not claim a particular legal certification or define a recording retention period.

---

## 12. Assumptions and open decisions

The following decision identifiers are retained from the original specification. Their exact resolution must be verified with the project decision-makers and relevant issue descriptions.

| ID | Topic | Status in this specification |
|---|---|---|
| DD-04 | Examination recovery behavior | Requires confirmation of exact policy and edge cases. |
| DD-07 | Candidate identity verification | Requires confirmation of the approved method and rules. |
| DD-08 | Microphone recording | Microphone recording is not part of the current scope. |
| DD-09 | Recording retention | Retention period and deletion policy require confirmation. |
| DD-10 | Recording access and permissions | Detailed access policy requires confirmation. |
| DD-14 | Examination state rules | Exact states and transitions require confirmation. |
| DD-15 | Candidate access restrictions | Detailed policy requires confirmation; baseline restrictions are in Section 3. |
| DD-16 | Event definitions | Exact event catalogue and semantics require confirmation. |
| DD-17 | HR decision workflow | Detailed decision workflow and persistence behavior require confirmation. |
| DD-18 | AI reporting categories | Supported categories require confirmation and controlled definition. |
| DD-19 | AI model/provider | Provider and model selection require evaluation and approval. |

Additional points from the original specification:

- **Five failed identity-verification attempts followed by a 15-minute lockout:** proposed rule; do not implement as approved until confirmed.
- **120-second recording recovery window:** stated in the original specification. Confirm exact semantics and whether it remains the approved rule before relying on ambiguous edge cases.
- **Recording:** webcam and screen, not microphone.
- **Initial question type:** multiple choice.
- **AI reporting:** limited to supported assessment statistics.

When an open decision affects an assigned task, the developer must check the issue and seek clarification rather than silently selecting a behavior.

---

## 13. Repository and implementation conventions

The original specification proposed a frontend/backend/docs-oriented repository layout. That proposal is conceptual, not a mandate to reorganize the current repository.

The current repository structure is the implementation reference. Developers and coding agents must inspect it before adding files, moving modules, or changing architecture.

General module concepts include frontend features for authentication, examinations, questions, candidates, assessment, proctoring, results, and reporting; and backend responsibilities for API routes, configuration, database access, models, schemas, business services, tests, and migrations.

Do not create duplicate structures or reorganize working code solely to match a proposed diagram.

---

## 14. Coding and engineering standards

### 14.1 General

- Follow this specification as the shared product baseline.
- Do not independently redefine product scope.
- Do not introduce new features without agreement.
- Do not replace the selected architectural style without agreement.
- Keep modules focused on their responsibilities.
- Prefer readable, maintainable code.
- Avoid unnecessary abstractions and duplicate implementations.
- Use meaningful names.
- Handle errors explicitly.
- Document non-obvious business rules.

### 14.2 Backend

- Use FastAPI for backend APIs.
- Use SQLAlchemy for database access.
- Use Alembic for database migrations.
- Separate API routes, schemas, models, and business logic according to repository conventions.
- Validate requests and responses.
- Use transactions when operations require atomicity.
- Enforce authorization on the backend.
- Keep grading deterministic.
- Do not put all business logic in route handlers.

### 14.3 Frontend

- Use Next.js and TypeScript.
- Use reusable components and existing UI conventions.
- Keep API communication separate from UI components where practical.
- Validate user input.
- Display understandable error messages.
- Do not treat frontend state as authoritative for security-sensitive operations.
- Do not calculate authoritative scores in the browser.
- Do not rely on browser timers as the authoritative examination clock.

### 14.4 Database

- All schema changes require migrations.
- Do not manually modify production database schemas.
- Avoid unnecessary denormalization.
- Use appropriate constraints and indexes.
- Preserve referential integrity.
- Never commit real candidate data.

### 14.5 Testing

Testing must be appropriate to the task and risk. Depending on the change, use:

- Unit tests for business logic.
- API tests for backend endpoints.
- Database tests for persistence and constraints.
- Integration tests for cross-module workflows.
- Frontend tests for critical interactions.
- Security tests for protected operations.

A feature is not complete merely because its interface exists or the application starts successfully.

---

## 15. Definition of Done

A GitHub task is ready for completion when:

- Its issue scope and acceptance criteria are satisfied.
- The implementation follows the project architecture and coding standards.
- Relevant tests exist and have been run.
- Test results and any failures are reported accurately.
- Existing functionality has not been unintentionally broken.
- Database migrations are included and tested where needed.
- API contracts or relevant documentation are updated where applicable.
- Security and authorization have been considered.
- The implementation has been reviewed through the team's agreed process.
- Deviations, limitations, and unresolved questions are documented.
- The issue and pull request are updated according to the team workflow.

The completion criteria are applied to individual GitHub tasks, not to a separate implementation schedule or task hierarchy.

---

## 16. Out of scope for the MVP

Unless formally approved as future scope, the following are excluded:

- Automated cheating detection.
- Face recognition.
- Facial identity matching using computer vision.
- YOLO-based detection.
- AI-based candidate scoring.
- AI-based candidate ranking.
- AI-based recruitment decisions.
- Multi-agent recruitment workflows.
- An independently deployed microservices architecture as the MVP architecture.
- LLM-based grading.
- Automatic judgment of candidate behavior.
- Microphone recording.

The platform provides assessment information and evidence for HR review. Final recruitment decisions remain human-controlled.

---

## 17. Final architectural principles

The Okala Examination System is to be developed as a maintainable, secure modular monolithic application.

The backend controls business logic, examination state, timing, grading, data access, recording management, and AI integration.

The frontend provides the HR and candidate experiences and manages browser capabilities such as webcam and screen recording.

PostgreSQL stores structured application data. Private file/object storage holds recording files and chunks.

AI is limited to two controlled capabilities:

1. AI Event Summary.
2. Natural Language HR Reporting.

AI does not grade, rank, judge candidate behavior, or make recruitment decisions.

The three developers and their coding agents share this specification as the product and technical baseline and use the repository's GitHub Issues for implementation work.
