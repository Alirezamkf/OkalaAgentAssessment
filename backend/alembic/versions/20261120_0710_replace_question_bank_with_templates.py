"""Replace the shared question bank with reusable exam templates."""

from alembic import op
import sqlalchemy as sa


revision = "20261120_0710"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
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
    op.create_index(
        "ix_exam_templates_created_by_hr_user_id",
        "exam_templates",
        ["created_by_hr_user_id"],
        unique=False,
    )

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
    op.create_index(
        "ix_exam_template_questions_exam_template_id",
        "exam_template_questions",
        ["exam_template_id"],
        unique=False,
    )

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
        sa.UniqueConstraint(
            "exam_template_question_id",
            "position",
            name="uq_exam_template_question_options_question_position",
        ),
    )
    op.create_index(
        "uq_exam_template_question_options_one_correct",
        "exam_template_question_options",
        ["exam_template_question_id"],
        unique=True,
        postgresql_where=sa.text("is_correct = true"),
    )

    # Existing exams remain independent and receive nullable compatibility fields.
    op.add_column("exams", sa.Column("name", sa.String(length=200), nullable=True))
    op.add_column("exams", sa.Column("exam_template_id", sa.BigInteger(), nullable=True))
    op.create_index("ix_exams_exam_template_id", "exams", ["exam_template_id"], unique=False)
    op.create_foreign_key(
        "fk_exams_exam_template_id",
        "exams",
        "exam_templates",
        ["exam_template_id"],
        ["id"],
    )

    # Drop the shared bank only after the template tables and exam compatibility columns exist.
    op.drop_table("question_set_items")
    op.drop_table("question_options")
    op.drop_table("question_sets")
    op.drop_table("questions")


def downgrade() -> None:
    op.create_table(
        "questions",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("image_reference", sa.String(length=500), nullable=True),
        sa.CheckConstraint("score > 0", name="ck_questions_score_positive"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "question_options",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("question_id", sa.BigInteger(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("is_correct", sa.Boolean(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.CheckConstraint("position >= 1", name="ck_question_options_position_positive"),
        sa.ForeignKeyConstraint(["question_id"], ["questions.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("question_id", "position", name="uq_question_options_question_position"),
        sa.UniqueConstraint("id", "question_id", name="uq_question_options_id_question"),
    )
    op.create_index(
        "uq_question_options_one_correct",
        "question_options",
        ["question_id"],
        unique=True,
        postgresql_where=sa.text("is_correct = true"),
    )
    op.create_table(
        "question_sets",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_by_hr_user_id", sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(["created_by_hr_user_id"], ["hr_users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "question_set_items",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("question_set_id", sa.BigInteger(), nullable=False),
        sa.Column("question_id", sa.BigInteger(), nullable=False),
        sa.Column("score", sa.Integer(), nullable=True),
        sa.CheckConstraint("score IS NULL OR score > 0", name="ck_question_set_items_score_positive"),
        sa.ForeignKeyConstraint(["question_set_id"], ["question_sets.id"]),
        sa.ForeignKeyConstraint(["question_id"], ["questions.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("question_set_id", "question_id", name="uq_question_set_items_set_question"),
    )
    op.create_index("ix_question_set_items_question_set_id", "question_set_items", ["question_set_id"], unique=False)
    op.create_index("ix_question_set_items_question_id", "question_set_items", ["question_id"], unique=False)

    op.drop_constraint("fk_exams_exam_template_id", "exams", type_="foreignkey")
    op.drop_index("ix_exams_exam_template_id", table_name="exams")
    op.drop_column("exams", "exam_template_id")
    op.drop_column("exams", "name")

    op.drop_index("uq_exam_template_question_options_one_correct", table_name="exam_template_question_options")
    op.drop_table("exam_template_question_options")
    op.drop_index("ix_exam_template_questions_exam_template_id", table_name="exam_template_questions")
    op.drop_table("exam_template_questions")
    op.drop_index("ix_exam_templates_created_by_hr_user_id", table_name="exam_templates")
    op.drop_table("exam_templates")
