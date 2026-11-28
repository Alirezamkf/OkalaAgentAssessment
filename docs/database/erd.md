# OkalaAgentAssessment Database ERD

This ERD is generated from the current SQLAlchemy ORM metadata and the current Alembic baseline migration. The live PostgreSQL schema was not verified reliably in this run, so this document must be treated as an ORM/migration representation rather than a confirmed live-schema dump.

## Mermaid Entity Relationship Diagram

```mermaid
erDiagram
    HR_USERS {
        BIGINT id PK "NOT NULL"
        VARCHAR100 username UK "NOT NULL"
        VARCHAR255 password_hash "NOT NULL"
        VARCHAR100 first_name "NOT NULL"
        VARCHAR100 last_name "NOT NULL"
        VARCHAR150 position "NOT NULL"
        VARCHAR500 profile_image_reference "NULL"
    }

    HR_USER_ROLES {
        BIGINT hr_user_id PK,FK "NOT NULL; ON DELETE CASCADE"
        VARCHAR20 role "NOT NULL; HR or HRAdmin or HRManagement"
    }

    EXAM_TEMPLATES {
        BIGINT id PK "NOT NULL"
        VARCHAR200 name "NOT NULL"
        TEXT description "NULL"
        BIGINT created_by_hr_user_id FK "NOT NULL"
        TIMESTAMPTZ created_at "NOT NULL; now()"
        TIMESTAMPTZ updated_at "NOT NULL; now()"
    }

    EXAM_TEMPLATE_QUESTIONS {
        BIGINT id PK "NOT NULL"
        BIGINT exam_template_id FK "NOT NULL"
        TEXT question_text "NOT NULL"
        INTEGER position "NOT NULL"
        INTEGER score "NOT NULL"
        VARCHAR500 image_reference "NULL"
        TIMESTAMPTZ created_at "NOT NULL; now()"
        TIMESTAMPTZ updated_at "NOT NULL; now()"
    }

    EXAM_TEMPLATE_QUESTION_OPTIONS {
        BIGINT id PK "NOT NULL"
        BIGINT exam_template_question_id FK "NOT NULL"
        TEXT option_text "NOT NULL"
        INTEGER position "NOT NULL"
        BOOLEAN is_correct "NOT NULL; false"
        TIMESTAMPTZ created_at "NOT NULL; now()"
        TIMESTAMPTZ updated_at "NOT NULL; now()"
    }

    EXAMS {
        BIGINT id PK "NOT NULL"
        VARCHAR200 name UK "NOT NULL"
        BIGINT exam_template_id FK "NULL"
        VARCHAR status "NOT NULL; Created"
        INTEGER duration_minutes "NOT NULL; 25"
        TIMESTAMPTZ available_from "NOT NULL"
        TIMESTAMPTZ available_until "NOT NULL"
        BIGINT created_by_hr_user_id FK "NOT NULL"
    }

    EXAM_QUESTIONS {
        BIGINT id PK "NOT NULL"
        BIGINT exam_id FK "NOT NULL"
        TEXT text "NOT NULL"
        INTEGER score "NOT NULL"
        VARCHAR500 image_reference "NULL"
    }

    EXAM_QUESTION_OPTIONS {
        BIGINT id PK "NOT NULL"
        BIGINT exam_question_id FK "NOT NULL"
        TEXT text "NOT NULL"
        BOOLEAN is_correct "NOT NULL; false"
        INTEGER position "NOT NULL"
    }

    CANDIDATES {
        BIGINT id PK "NOT NULL"
        VARCHAR100 first_name "NOT NULL"
        VARCHAR100 last_name "NOT NULL"
        VARCHAR320 email "NULL"
        VARCHAR50 phone "NULL"
    }

    EXAM_INVITATIONS {
        BIGINT id PK "NOT NULL"
        BIGINT candidate_id FK "NOT NULL"
        BIGINT exam_id FK "NOT NULL"
        VARCHAR64 token_hash UK "NOT NULL"
        VARCHAR status "NOT NULL; Pending"
        TIMESTAMPTZ created_at "NOT NULL"
        TIMESTAMPTZ expires_at "NOT NULL"
        INTEGER failed_identity_attempts "NOT NULL; 0"
        TIMESTAMPTZ identity_locked_until "NULL"
    }

    EXAM_INVITATION_QUESTIONS {
        BIGINT id PK "NOT NULL"
        BIGINT exam_invitation_id FK "NOT NULL"
        BIGINT exam_question_id FK "NOT NULL"
        BIGINT exam_id FK "NOT NULL"
    }

    ASSESSMENT_ATTEMPTS {
        BIGINT id PK "NOT NULL"
        BIGINT exam_id FK "NOT NULL"
        BIGINT candidate_id FK "NOT NULL"
        BIGINT exam_invitation_id FK "NOT NULL"
        VARCHAR status "NOT NULL; Not Started"
        TIMESTAMPTZ created_at "NOT NULL; now()"
        TIMESTAMPTZ started_at "NULL"
        TIMESTAMPTZ completed_at "NULL"
        TIMESTAMPTZ deadline_at "NOT NULL; no default"
        INTEGER current_question_position "NULL"
        NUMERIC102 official_score "NULL"
        NUMERIC102 max_score "NULL"
        VARCHAR hr_decision "NOT NULL; Unset"
        BIGINT hr_decided_by_id FK "NULL"
        TIMESTAMPTZ hr_decision_updated_at "NULL"
    }

    ATTEMPT_QUESTION_ORDERS {
        BIGINT id PK "NOT NULL"
        BIGINT attempt_id FK "NOT NULL"
        BIGINT exam_invitation_id FK "NOT NULL"
        BIGINT exam_question_id FK "NOT NULL"
        INTEGER position "NOT NULL"
    }

    CANDIDATE_ANSWERS {
        BIGINT id PK "NOT NULL"
        BIGINT attempt_id FK "NOT NULL"
        BIGINT exam_question_id FK "NOT NULL"
        BIGINT selected_option_id FK "NULL"
        TIMESTAMPTZ submitted_at "NULL"
    }

    CANDIDATE_CONSENTS {
        BIGINT id PK "NOT NULL"
        BIGINT exam_invitation_id FK_UK "NOT NULL"
        TIMESTAMPTZ accepted_at "NOT NULL; now()"
    }

    ATTEMPT_EVENTS {
        BIGINT id PK "NOT NULL"
        BIGINT attempt_id FK "NOT NULL"
        ATTEMPT_EVENT_TYPE event_type "NOT NULL"
        TIMESTAMPTZ occurred_at "NOT NULL; now()"
        INTEGER duration_seconds "NULL"
        JSONB event_metadata "NOT NULL; {}"
    }

    RECORDING_METADATA {
        BIGINT id PK "NOT NULL"
        BIGINT attempt_id FK "NOT NULL"
        VARCHAR50 source "NOT NULL"
        VARCHAR50 status "NOT NULL"
        TIMESTAMPTZ started_at "NULL"
        TIMESTAMPTZ ended_at "NULL"
        BIGINT file_size_bytes "NULL"
        VARCHAR100 media_type "NULL"
        VARCHAR1024 storage_reference "NULL"
    }

    ASSESSMENT_RETENTION_PROCESSING {
        BIGINT id PK "NOT NULL"
        BIGINT exam_id FK_UK "NOT NULL"
        VARCHAR status "NOT NULL; Pending"
        TIMESTAMPTZ processing_started_at "NULL"
        TIMESTAMPTZ processing_completed_at "NULL"
        INTEGER attempt_count "NOT NULL; 0"
        VARCHAR100 failure_category "NULL"
        JSONB failure_diagnostics "NULL"
        VARCHAR100 last_successful_stage "NULL"
        VARCHAR255 lease_owner "NULL"
        TIMESTAMPTZ lease_expires_at "NULL"
        TIMESTAMPTZ heartbeat_at "NULL"
    }

    ALEMBIC_VERSION {
        VARCHAR32 version_num PK "NOT NULL"
    }

    HR_USERS ||--o| HR_USER_ROLES : has_authoritative_role

    HR_USERS ||--o{ EXAM_TEMPLATES : creates
    HR_USERS ||--o{ EXAMS : creates
    HR_USERS o|--o{ ASSESSMENT_ATTEMPTS : decides

    EXAM_TEMPLATES ||--o{ EXAM_TEMPLATE_QUESTIONS : contains
    EXAM_TEMPLATE_QUESTIONS ||--o{ EXAM_TEMPLATE_QUESTION_OPTIONS : provides
    EXAM_TEMPLATES ||--o{ EXAMS : source_for

    EXAMS ||--o{ EXAM_QUESTIONS : owns_snapshot
    EXAM_QUESTIONS ||--o{ EXAM_QUESTION_OPTIONS : provides
    EXAMS ||--o{ EXAM_INVITATIONS : assigned_to
    EXAMS ||--o{ ASSESSMENT_ATTEMPTS : attempted
    EXAMS ||--o| ASSESSMENT_RETENTION_PROCESSING : has_processing_state

    CANDIDATES ||--o{ EXAM_INVITATIONS : receives
    CANDIDATES ||--o{ ASSESSMENT_ATTEMPTS : participates

    EXAM_INVITATIONS ||--o| CANDIDATE_CONSENTS : records
    EXAM_INVITATIONS ||--o| ASSESSMENT_ATTEMPTS : has_attempt
    EXAM_INVITATIONS ||--o{ EXAM_INVITATION_QUESTIONS : selects
    EXAM_INVITATION_QUESTIONS }o--|| EXAM_QUESTIONS : selects_snapshot

    ASSESSMENT_ATTEMPTS ||--o{ ATTEMPT_QUESTION_ORDERS : has_question_order
    ASSESSMENT_ATTEMPTS ||--o{ CANDIDATE_ANSWERS : contains
    ASSESSMENT_ATTEMPTS ||--o{ ATTEMPT_EVENTS : logs
    ASSESSMENT_ATTEMPTS ||--o{ RECORDING_METADATA : has_recordings

    ATTEMPT_QUESTION_ORDERS }o--|| EXAM_QUESTIONS : orders
    CANDIDATE_ANSWERS }o--|| EXAM_QUESTIONS : answers
    CANDIDATE_ANSWERS }o--|| ATTEMPT_QUESTION_ORDERS : uses_attempt_question
    CANDIDATE_ANSWERS }o--o| EXAM_QUESTION_OPTIONS : selects_option
```

## A. Database Overview

The database is organized around reusable Exam Templates, actual Exam snapshot questions, Candidate identities, Exam Invitations, Assessment Attempts, candidate answers, recording data, events, and retention processing. `alembic_version` is migration metadata, not an application entity.

## B. Table Descriptions

### `hr_users`
Stores HR accounts and the existing HR decision user relationship. The current model exposes `id`, `username`, `password_hash`, `first_name`, `last_name`, `position`, and `profile_image_reference`. The approved relationship to Exam and ExamTemplate creators is one-way; this table does not expose reverse template/exam collections.

### `hr_user_roles`
Stores the single authoritative HR application role for one HR account. `hr_user_id` is both the primary key and a foreign key to `hr_users.id` with `ON DELETE CASCADE`, so an account has at most one effective role and the assignment disappears with the account. The role column accepts exactly `HR`, `HRAdmin`, and `HRManagement`, enforced by a check constraint and a non-native SQLAlchemy enum. This table is separate because the approved `hr_users` table must retain exactly its seven columns. Technical Support identities are not stored here.

### `exam_templates`
Stores reusable Exam definitions. It belongs to one HR owner and contains ordered template questions.

### `exam_template_questions`
Stores ordered questions inside a template. The unique `(exam_template_id, position)` prevents duplicate positions. Questions are copied into actual Exam snapshots rather than shared directly.

### `exam_template_question_options`
Stores template question options with position and correctness. The partial unique index permits only one correct option; option count validation remains Backend responsibility.

### `exams`
Stores actual scheduled exams, independent of template records after creation. `exam_template_id` is nullable for migration compatibility. `name` is required, non-empty, and globally unique in the ORM/migration design. `duration_minutes` is constrained to 20–25.

### `exam_questions`
Stores the independent Exam-specific snapshot copy of question text, score, and image reference. It has no FK to template questions.

### `exam_question_options`
Stores the independent snapshot options for an ExamQuestion. It has no FK to template options.

### `candidates`
Stores a reusable global Candidate identity. Email and phone are nullable to support anonymization; historical Attempt rows retain the Candidate FK.

### `exam_invitations`
Links one Candidate to one Exam and stores secure token hash, invitation status, expiration, and identity lockout state. Multiple invitations may exist for the same Candidate and Exam.

### `exam_invitation_questions`
Join table linking one invitation to selected Exam snapshot questions. The composite FK ensures the Invitation and ExamQuestion belong to the same Exam.

### `assessment_attempts`
Stores one attempt for an invitation, its lifecycle, timing, current position, scores, and latest HR decision. `exam_invitation_id` is unique, so one invitation supports at most one Attempt.

### `attempt_question_orders`
Stores the persisted presentation order for snapshot questions assigned to an Attempt. Composite FKs ensure the attempt and selected question belong to their invitation and Exam snapshot.

### `candidate_answers`
Stores one answer per Attempt and ExamQuestion. It links the selected option to the matching ExamQuestion snapshot and the AttemptQuestionOrder.

### `candidate_consents`
Stores only positive consent acceptance timestamp for an Invitation. Existence means consent was accepted. `exam_invitation_id` is unique.

### `attempt_events`
Stores server-timestamped Attempt activity. `duration_seconds` is nullable and non-negative if present. `event_metadata` is JSONB and defaults to `{}`.

### `recording_metadata`
Stores final provider-independent metadata for webcam and screen recordings. `(attempt_id, source)` is unique, with source constrained to `webcam` or `screen`.

### `assessment_retention_processing`
Stores persistent retention processing state and worker lease state for exactly one Exam. `attempt_count` is retention execution/retry count, not Candidate Attempt count.

### `alembic_version`
Migration metadata table maintained by Alembic. It is not an application entity.

## C. Relationship Details

- `hr_users (1) ---- (N) exam_templates`
- `hr_users (1) ---- (N) exams`
- `hr_users (1) ---- (N) assessment_attempts` only for optional HR decisions
- `exam_templates (1) ---- (N) exam_template_questions`
- `exam_template_questions (1) ---- (N) exam_template_question_options`
- `exam_templates (1) ---- (N) exams`
- `exams (1) ---- (N) exam_questions`
- `exam_questions (1) ---- (N) exam_question_options`
- `exams (1) ---- (N) exam_invitations`
- `candidates (1) ---- (N) exam_invitations`
- `exam_invitations (1) ---- (1) candidate_consents`
- `exam_invitations (1) ---- (1) assessment_attempts`
- `exam_invitations (1) ---- (N) exam_invitation_questions`
- `exam_invitation_questions (N) ---- (1) exam_questions`
- `exams (1) ---- (N) assessment_attempts`
- `candidates (1) ---- (N) assessment_attempts`
- `exams (1) ---- (1) assessment_retention_processing`
- `assessment_attempts (1) ---- (N) attempt_question_orders`
- `assessment_attempts (1) ---- (N) candidate_answers`
- `assessment_attempts (1) ---- (N) attempt_events`
- `assessment_attempts (1) ---- (N) recording_metadata`
- `attempt_question_orders (1) ---- (N) candidate_answers`
- `exam_questions (1) ---- (N) candidate_answers`
- `exam_question_options (1) ---- (N) candidate_answers`

CandidateConsent has no direct foreign key to AssessmentAttempt; it is reached through ExamInvitation, and each Invitation also has at most one Attempt.

## D. Constraints and Indexes

### Primary and unique constraints

- Every application table has a `BIGINT` primary key. Most use a column named `id`; `hr_user_roles` uses `hr_user_id`.
- `hr_users.username` is unique and NOT NULL.
- `hr_user_roles.hr_user_id` is the primary key and a foreign key to `hr_users.id`, allowing at most one effective role per HR account.
- `exams.name` is unique and NOT NULL.
- `exam_template_questions` has unique `(exam_template_id, position)`.
- `exam_template_question_options` has unique `(exam_template_question_id, position)`.
- `exam_question_options` has unique `(exam_question_id, position)` and `(id, exam_question_id)`.
- `exam_invitations.token_hash` is unique.
- `exam_invitation_questions` has unique `(exam_invitation_id, exam_question_id)`.
- `assessment_attempts.exam_invitation_id` is unique.
- `attempt_question_orders` has unique `(attempt_id, position)` and `(attempt_id, exam_question_id)`.
- `candidate_answers` has unique `(attempt_id, exam_question_id)`.
- `candidate_consents.exam_invitation_id` is unique.
- `recording_metadata` has unique `(attempt_id, source)`.
- `assessment_retention_processing.exam_id` is unique.

### Check constraints

- `hr_user_roles.role` is one of `HR`, `HRAdmin`, or `HRManagement`.
- Exam template name is non-empty.
- Template question position is positive and score is positive.
- Template and exam option positions are positive.
- Exam duration is 20–25 and availability end follows start.
- Exam name is non-empty.
- Candidate first and last names are non-empty.
- Invitation failed attempts are non-negative.
- Attempt current position is positive when present.
- HR decision fields are consistent with `Unset` and non-unset decisions.
- AttemptEvent duration is `NULL` or non-negative.
- Recording file size is non-negative.
- Recording end time is not before start time.
- Recording source is only `webcam` or `screen`.
- Retention attempts and timestamps/lease fields obey the status consistency constraints.

### Partial indexes

- One correct template option per template question.
- One correct exam snapshot option per ExamQuestion.

### Ordinary indexes

- Foreign-key indexes are present for invitation, attempt, candidate, exam, question, answer, source and status lookup paths.
- AttemptEvent has attempt/timestamp and event-type indexes.
- Retention processing has a status index.

## E. HR Role Persistence

HR roles are stored in `hr_user_roles`, not in `hr_users`, because the approved HRUser table has exactly seven columns and a role column is forbidden. The three approved values are `HR`, `HRAdmin`, and `HRManagement`. `hr_user_id` is both primary key and foreign key, so there is exactly one authoritative effective role per HR account and no competing role source.

The backend resolves a role through `app.services.hr_role_resolution.resolve_hr_role`, which reads the persisted assignment for the account. It never accepts a role from a request body, query parameter, header, or client state. A missing assignment raises `HRRoleNotAssignedError`, an unknown account raises `HRUserNotFoundError`, and an unsupported stored value raises `HRRoleInvalidError`. There is no default role and no implicit `HR` fallback: resolution fails closed. `assign_hr_role` is the backend-only write path and rejects anything that is not an approved `HRRole` member.

Initial `HRManagement` provisioning remains an outstanding acceptance criterion for issue #249. The repository has no approved password-hashing mechanism and no administrative provisioning procedure, and this issue does not add one. No public endpoint, application endpoint, or insecure script creates or promotes an HRManagement account. A separate approved issue must define secure password hashing and the administrative/database procedure that creates the HRUser and its HRManagement assignment atomically. Until then the initial HRManagement account cannot be provisioned by this codebase.

Migration and rollback: revision `20261128_0700` follows `20261120_0710`. `upgrade()` creates only `hr_user_roles` with its primary key, foreign key, and check constraint. It does not alter `hr_users`, delete account data, or invent roles for existing accounts. `downgrade()` drops only `hr_user_roles`. Run migrations with `alembic upgrade head` and roll back one revision with `alembic downgrade 20261120_0710`. Focused tests verify upgrade and downgrade against an isolated SQLite database. The actual Alembic CLI upgrade and downgrade were also verified against a disposable PostgreSQL 18 database in a temporary container. No development or production database was used.

## F. Design Notes

- Template questions and options are copied into independent Exam snapshot tables.
- Invitation selections and Attempt presentation order are separate concepts.
- Candidate and HR identity rows are preserved for historical references.
- The Candidate contact CheckConstraint is omitted to allow anonymized Candidate rows.
- Network event types do not themselves create recording pause state.
- RecordingMetadata stores final recording metadata without temporary segments.
- `AttemptRecordingPause` is not currently registered in ORM metadata and is therefore excluded.
- `alembic_version` is migration metadata and is omitted from application relationships.


## G. Schema Verification

- PostgreSQL database name: `okala_assessment` as configured for Docker/local setup.
- Latest Alembic revision in this branch: `20261128_0700_add_hr_user_roles.py` (`20261128_0700`). The development database's applied revision is environment-dependent.
- Application tables: 18 (excluding `alembic_version`).
- PostgreSQL migration verification: upgrade and downgrade were tested against a disposable PostgreSQL 18 container. The configured development database was not inspected or modified.
- `alembic_version` is a migration metadata table outside the application-table count.
- The ERD reflects the ORM metadata and migration structure represented in this branch.