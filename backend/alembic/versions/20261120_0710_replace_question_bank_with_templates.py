"""Create the complete initial Okala Agent Assessment PostgreSQL schema."""

from alembic import op
import sqlalchemy as sa


revision = "20261120_0710"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # One complete initial PostgreSQL schema is created at this revision.

    op.create_table(
        "hr_users",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("username", sa.String(length=100), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("first_name", sa.String(length=100), nullable=False),
        sa.Column("last_name", sa.String(length=100), nullable=False),
        sa.Column("position", sa.String(length=150), nullable=False),
        sa.Column("profile_image_reference", sa.String(length=500), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "exam_templates",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_by_hr_user_id", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("length(name) >= 1", name="ck_exam_templates_name_not_empty"),
        sa.ForeignKeyConstraint(["created_by_hr_user_id"], ["hr_users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_exam_templates_created_by_hr_user_id", "exam_templates", ["created_by_hr_user_id"], unique=False)

    op.create_table(
        "exam_template_questions",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("exam_template_id", sa.BigInteger(), nullable=False),
        sa.Column("question_text", sa.Text(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("image_reference", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("position >= 1", name="ck_exam_template_questions_position_positive"),
        sa.CheckConstraint("score > 0", name="ck_exam_template_questions_score_positive"),
        sa.ForeignKeyConstraint(["exam_template_id"], ["exam_templates.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("exam_template_id", "position", name="uq_exam_template_questions_template_position"),
    )
    op.create_index("ix_exam_template_questions_exam_template_id", "exam_template_questions", ["exam_template_id"], unique=False)

    op.create_table(
        "exam_template_question_options",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("exam_template_question_id", sa.BigInteger(), nullable=False),
        sa.Column("option_text", sa.Text(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("is_correct", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("position >= 1", name="ck_exam_template_question_options_position_positive"),
        sa.ForeignKeyConstraint(["exam_template_question_id"], ["exam_template_questions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("exam_template_question_id", "position", name="uq_exam_template_question_options_question_position"),
    )
    op.create_index(
        "uq_exam_template_question_options_one_correct",
        "exam_template_question_options",
        ["exam_template_question_id"],
        unique=True,
        postgresql_where=sa.text("is_correct = true"),
    )

    op.create_table(
        "exams",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("exam_template_id", sa.BigInteger(), nullable=True),
        sa.Column("status", sa.Enum("Created", "Published", "Cancelled", name="exam_status", native_enum=False), nullable=False, server_default=sa.text("'Created'")),
        sa.Column("duration_minutes", sa.Integer(), nullable=False),
        sa.Column("available_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("available_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by_hr_user_id", sa.BigInteger(), nullable=False),
        sa.CheckConstraint("length(trim(name)) >= 1", name="ck_exams_name_not_empty"),
        sa.CheckConstraint("duration_minutes >= 20 AND duration_minutes <= 25", name="ck_exams_duration_minutes_range"),
        sa.CheckConstraint("available_until > available_from", name="ck_exams_availability_order"),
        sa.ForeignKeyConstraint(["exam_template_id"], ["exam_templates.id"]),
        sa.ForeignKeyConstraint(["created_by_hr_user_id"], ["hr_users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", name="uq_exams_name"),
    )
    op.create_index("ix_exams_exam_template_id", "exams", ["exam_template_id"], unique=False)

    op.create_table(
        "exam_questions",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("exam_id", sa.BigInteger(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("image_reference", sa.String(length=500), nullable=True),
        sa.CheckConstraint("score > 0", name="ck_exam_questions_score_positive"),
        sa.ForeignKeyConstraint(["exam_id"], ["exams.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id", "exam_id", name="uq_exam_questions_id_exam"),
    )

    op.create_table(
        "exam_question_options",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("exam_question_id", sa.BigInteger(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("is_correct", sa.Boolean(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.CheckConstraint("position >= 1", name="ck_exam_question_options_position_positive"),
        sa.ForeignKeyConstraint(["exam_question_id"], ["exam_questions.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("exam_question_id", "position", name="uq_exam_question_options_question_position"),
        sa.UniqueConstraint("id", "exam_question_id", name="uq_exam_question_options_id_question"),
    )
    op.create_index(
        "uq_exam_question_options_one_correct",
        "exam_question_options",
        ["exam_question_id"],
        unique=True,
        postgresql_where=sa.text("is_correct = true"),
    )

    op.create_table(
        "candidates",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("first_name", sa.String(length=100), nullable=False),
        sa.Column("last_name", sa.String(length=100), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=True),
        sa.Column("phone", sa.String(length=50), nullable=True),
        sa.CheckConstraint("length(trim(first_name)) >= 1", name="ck_candidates_first_name_not_empty"),
        sa.CheckConstraint("length(trim(last_name)) >= 1", name="ck_candidates_last_name_not_empty"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_candidates_email", "candidates", ["email"], unique=False)
    op.create_index("ix_candidates_phone", "candidates", ["phone"], unique=False)

    op.create_table(
        "exam_invitations",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("candidate_id", sa.BigInteger(), nullable=False),
        sa.Column("exam_id", sa.BigInteger(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("status", sa.Enum("Pending", "Accepted", "Expired", "Cancelled", name="invitation_status", native_enum=False), nullable=False, server_default=sa.text("'Pending'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("failed_identity_attempts", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("identity_locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("failed_identity_attempts >= 0", name="ck_exam_invitations_failed_identity_attempts_non_negative"),
        sa.ForeignKeyConstraint(["candidate_id"], ["candidates.id"]),
        sa.ForeignKeyConstraint(["exam_id"], ["exams.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id", "candidate_id", "exam_id", name="uq_invitation_identity"),
        sa.UniqueConstraint("id", "exam_id", name="uq_invitation_id_exam"),
    )
    op.create_index("uq_exam_invitations_token_hash", "exam_invitations", ["token_hash"], unique=True)

    op.create_table(
        "exam_invitation_questions",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("exam_invitation_id", sa.BigInteger(), nullable=False),
        sa.Column("exam_question_id", sa.BigInteger(), nullable=False),
        sa.Column("exam_id", sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(["exam_invitation_id", "exam_id"], ["exam_invitations.id", "exam_invitations.exam_id"], name="fk_invitation_questions_invitation_exam"),
        sa.ForeignKeyConstraint(["exam_question_id", "exam_id"], ["exam_questions.id", "exam_questions.exam_id"], name="fk_invitation_questions_exam_question_exam"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("exam_invitation_id", "exam_question_id", name="uq_invitation_questions_invitation_question"),
    )
    op.create_index("ix_invitation_questions_exam_question_id", "exam_invitation_questions", ["exam_question_id"], unique=False)

    op.create_table(
        "assessment_attempts",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("exam_id", sa.BigInteger(), nullable=False),
        sa.Column("candidate_id", sa.BigInteger(), nullable=False),
        sa.Column("exam_invitation_id", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.Enum("Not Started", "In Progress", "Submitted", "Timed Out", "Interrupted", "Cancelled", name="attempt_status", native_enum=False), nullable=False, server_default=sa.text("'Not Started'")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deadline_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("current_question_position", sa.Integer(), nullable=True),
        sa.Column("official_score", sa.Numeric(10, 2), nullable=True),
        sa.Column("max_score", sa.Numeric(10, 2), nullable=True),
        sa.Column("hr_decision", sa.Enum("Unset", "Accepted", "Rejected", "Needs Review", name="hr_decision", native_enum=False), nullable=False, server_default=sa.text("'Unset'")),
        sa.Column("hr_decided_by_id", sa.BigInteger(), nullable=True),
        sa.Column("hr_decision_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["exam_invitation_id", "candidate_id", "exam_id"], ["exam_invitations.id", "exam_invitations.candidate_id", "exam_invitations.exam_id"], name="fk_attempt_invitation_identity"),
        sa.ForeignKeyConstraint(["exam_id"], ["exams.id"]),
        sa.ForeignKeyConstraint(["candidate_id"], ["candidates.id"]),
        sa.ForeignKeyConstraint(["hr_decided_by_id"], ["hr_users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("exam_invitation_id", name="uq_assessment_attempts_invitation_id"),
        sa.UniqueConstraint("id", "exam_invitation_id", name="uq_assessment_attempts_id_invitation"),
        sa.CheckConstraint("current_question_position IS NULL OR current_question_position >= 1", name="ck_assessment_attempts_current_position_positive"),
        sa.CheckConstraint("(hr_decision = 'Unset' AND hr_decided_by_id IS NULL AND hr_decision_updated_at IS NULL) OR (hr_decision <> 'Unset' AND hr_decided_by_id IS NOT NULL AND hr_decision_updated_at IS NOT NULL)", name="ck_assessment_attempts_hr_decision_consistency"),
    )
    op.create_index("ix_assessment_attempts_exam_id", "assessment_attempts", ["exam_id"], unique=False)
    op.create_index("ix_assessment_attempts_candidate_id", "assessment_attempts", ["candidate_id"], unique=False)
    op.create_index("ix_assessment_attempts_status", "assessment_attempts", ["status"], unique=False)

    op.create_table(
        "attempt_question_orders",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("attempt_id", sa.BigInteger(), nullable=False),
        sa.Column("exam_invitation_id", sa.BigInteger(), nullable=False),
        sa.Column("exam_question_id", sa.BigInteger(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.CheckConstraint("position >= 1", name="ck_attempt_question_orders_position_positive"),
        sa.ForeignKeyConstraint(["attempt_id", "exam_invitation_id"], ["assessment_attempts.id", "assessment_attempts.exam_invitation_id"], name="fk_attempt_question_orders_attempt_invitation"),
        sa.ForeignKeyConstraint(["exam_invitation_id", "exam_question_id"], ["exam_invitation_questions.exam_invitation_id", "exam_invitation_questions.exam_question_id"], name="fk_attempt_question_orders_selected_exam_question"),
        sa.ForeignKeyConstraint(["exam_question_id"], ["exam_questions.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("attempt_id", "position", name="uq_attempt_question_orders_attempt_position"),
        sa.UniqueConstraint("attempt_id", "exam_question_id", name="uq_attempt_question_orders_attempt_question"),
    )
    op.create_index("ix_attempt_question_orders_exam_question_id", "attempt_question_orders", ["exam_question_id"], unique=False)

    op.create_table(
        "candidate_answers",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("attempt_id", sa.BigInteger(), nullable=False),
        sa.Column("exam_question_id", sa.BigInteger(), nullable=False),
        sa.Column("selected_option_id", sa.BigInteger(), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["attempt_id", "exam_question_id"], ["attempt_question_orders.attempt_id", "attempt_question_orders.exam_question_id"], name="fk_candidate_answers_attempt_question_order"),
        sa.ForeignKeyConstraint(["selected_option_id", "exam_question_id"], ["exam_question_options.id", "exam_question_options.exam_question_id"], name="fk_candidate_answers_selected_option_exam_question"),
        sa.ForeignKeyConstraint(["attempt_id"], ["assessment_attempts.id"]),
        sa.ForeignKeyConstraint(["exam_question_id"], ["exam_questions.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("attempt_id", "exam_question_id", name="uq_candidate_answers_attempt_question"),
    )
    op.create_index("ix_candidate_answers_exam_question_id", "candidate_answers", ["exam_question_id"], unique=False)
    op.create_index("ix_candidate_answers_selected_option_id", "candidate_answers", ["selected_option_id"], unique=False)

    op.create_table(
        "candidate_consents",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("exam_invitation_id", sa.BigInteger(), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["exam_invitation_id"], ["exam_invitations.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("exam_invitation_id", name="uq_candidate_consents_exam_invitation_id"),
    )

    op.execute("CREATE TYPE attempt_event_type AS ENUM ('TabHidden', 'CameraStopped', 'ScreenShareStopped', 'CopyAttempt', 'PasteAttempt', 'Reentered', 'ConcurrentSessionBlocked', 'Idle', 'NetworkDisconnected', 'NetworkRestored', 'RecordingGap')")
    op.create_table(
        "attempt_events",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("attempt_id", sa.BigInteger(), nullable=False),
        sa.Column("event_type", sa.dialects.postgresql.ENUM("TabHidden", "CameraStopped", "ScreenShareStopped", "CopyAttempt", "PasteAttempt", "Reentered", "ConcurrentSessionBlocked", "Idle", "NetworkDisconnected", "NetworkRestored", "RecordingGap", name="attempt_event_type", create_type=False), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("duration_seconds", sa.Integer(), nullable=True),
        sa.Column("event_metadata", sa.dialects.postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.CheckConstraint("duration_seconds IS NULL OR duration_seconds >= 0", name="ck_attempt_events_duration_seconds_non_negative"),
        sa.ForeignKeyConstraint(["attempt_id"], ["assessment_attempts.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_attempt_events_attempt_occurred_at", "attempt_events", ["attempt_id", "occurred_at"], unique=False)
    op.create_index("ix_attempt_events_event_type", "attempt_events", ["event_type"], unique=False)

    op.create_table(
        "recording_metadata",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("attempt_id", sa.BigInteger(), nullable=False),
        sa.Column("source", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("file_size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("media_type", sa.String(length=100), nullable=True),
        sa.Column("storage_reference", sa.String(length=1024), nullable=True),
        sa.CheckConstraint("file_size_bytes IS NULL OR file_size_bytes >= 0", name="ck_recording_metadata_file_size_non_negative"),
        sa.CheckConstraint("ended_at IS NULL OR started_at IS NULL OR ended_at >= started_at", name="ck_recording_metadata_timestamp_order"),
        sa.CheckConstraint("source IN ('webcam', 'screen')", name="ck_recording_metadata_source_allowed"),
        sa.ForeignKeyConstraint(["attempt_id"], ["assessment_attempts.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("attempt_id", "source", name="uq_recording_metadata_attempt_source"),
    )
    op.create_index("ix_recording_metadata_attempt_id", "recording_metadata", ["attempt_id"], unique=False)
    op.create_index("ix_recording_metadata_source", "recording_metadata", ["source"], unique=False)
    op.create_index("ix_recording_metadata_status", "recording_metadata", ["status"], unique=False)

    op.create_table(
        "assessment_retention_processing",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("exam_id", sa.BigInteger(), nullable=False, unique=True),
        sa.Column("status", sa.Enum("Pending", "In Progress", "Completed", "Failed", name="retention_processing_status", native_enum=False), nullable=False, server_default=sa.text("'Pending'")),
        sa.Column("processing_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("processing_completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("failure_category", sa.String(length=100), nullable=True),
        sa.Column("failure_diagnostics", sa.dialects.postgresql.JSONB(), nullable=True),
        sa.Column("last_successful_stage", sa.String(length=100), nullable=True),
        sa.Column("lease_owner", sa.String(length=255), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("attempt_count >= 0", name="ck_retention_attempt_count_non_negative"),
        sa.CheckConstraint("processing_completed_at IS NULL OR processing_started_at IS NULL OR processing_completed_at >= processing_started_at", name="ck_retention_processing_timestamp_order"),
        sa.CheckConstraint("(status = 'Pending' AND attempt_count = 0 AND processing_started_at IS NULL AND processing_completed_at IS NULL AND failure_category IS NULL AND failure_diagnostics IS NULL AND lease_owner IS NULL AND lease_expires_at IS NULL AND heartbeat_at IS NULL) OR (status = 'In Progress' AND attempt_count >= 1 AND processing_started_at IS NOT NULL AND processing_completed_at IS NULL AND failure_category IS NULL AND failure_diagnostics IS NULL AND lease_owner IS NOT NULL AND lease_expires_at IS NOT NULL AND heartbeat_at IS NOT NULL) OR (status = 'Completed' AND attempt_count >= 1 AND processing_started_at IS NOT NULL AND processing_completed_at IS NOT NULL AND failure_category IS NULL AND failure_diagnostics IS NULL AND lease_owner IS NULL AND lease_expires_at IS NULL AND heartbeat_at IS NULL) OR (status = 'Failed' AND attempt_count >= 1 AND processing_started_at IS NOT NULL AND processing_completed_at IS NOT NULL AND failure_category IS NOT NULL AND lease_owner IS NULL AND lease_expires_at IS NULL AND heartbeat_at IS NULL)", name="ck_retention_status_consistency"),
        sa.CheckConstraint("(lease_owner IS NULL AND lease_expires_at IS NULL AND heartbeat_at IS NULL) OR (lease_owner IS NOT NULL AND lease_expires_at IS NOT NULL AND heartbeat_at IS NOT NULL)", name="ck_retention_lease_fields_consistency"),
        sa.ForeignKeyConstraint(["exam_id"], ["exams.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_retention_processing_status", "assessment_retention_processing", ["status"], unique=False)


def downgrade() -> None:
    # Reverse dependency order; no legacy bank tables are recreated.
    op.drop_index("ix_retention_processing_status", table_name="assessment_retention_processing")
    op.drop_table("assessment_retention_processing")

    op.drop_index("ix_recording_metadata_status", table_name="recording_metadata")
    op.drop_index("ix_recording_metadata_source", table_name="recording_metadata")
    op.drop_index("ix_recording_metadata_attempt_id", table_name="recording_metadata")
    op.drop_table("recording_metadata")

    op.drop_index("ix_attempt_events_event_type", table_name="attempt_events")
    op.drop_index("ix_attempt_events_attempt_occurred_at", table_name="attempt_events")
    op.drop_table("attempt_events")
    op.execute("DROP TYPE IF EXISTS attempt_event_type")

    op.drop_index("ix_candidate_answers_selected_option_id", table_name="candidate_answers")
    op.drop_index("ix_candidate_answers_exam_question_id", table_name="candidate_answers")
    op.drop_table("candidate_answers")

    op.drop_table("candidate_consents")

    op.drop_index("ix_attempt_question_orders_exam_question_id", table_name="attempt_question_orders")
    op.drop_table("attempt_question_orders")

    op.drop_index("ix_assessment_attempts_status", table_name="assessment_attempts")
    op.drop_index("ix_assessment_attempts_candidate_id", table_name="assessment_attempts")
    op.drop_index("ix_assessment_attempts_exam_id", table_name="assessment_attempts")
    op.drop_table("assessment_attempts")

    op.drop_index("ix_invitation_questions_exam_question_id", table_name="exam_invitation_questions")
    op.drop_table("exam_invitation_questions")

    op.drop_index("uq_exam_invitations_token_hash", table_name="exam_invitations")
    op.drop_table("exam_invitations")

    op.drop_index("ix_candidates_phone", table_name="candidates")
    op.drop_index("ix_candidates_email", table_name="candidates")
    op.drop_table("candidates")

    op.drop_index("uq_exam_question_options_one_correct", table_name="exam_question_options")
    op.drop_table("exam_question_options")
    op.drop_table("exam_questions")

    op.drop_index("ix_exams_exam_template_id", table_name="exams")
    op.drop_table("exams")

    op.drop_index("uq_exam_template_question_options_one_correct", table_name="exam_template_question_options")
    op.drop_table("exam_template_question_options")

    op.drop_index("ix_exam_template_questions_exam_template_id", table_name="exam_template_questions")
    op.drop_table("exam_template_questions")

    op.drop_index("ix_exam_templates_created_by_hr_user_id", table_name="exam_templates")
    op.drop_table("exam_templates")

    op.drop_table("hr_users")
