"""ORM model for persistent assessment-retention processing state."""

from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any

from sqlalchemy import BigInteger, CheckConstraint, DateTime, Enum as SAEnum, ForeignKey, Index, Integer, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base

if TYPE_CHECKING:
    from app.models.exam import Exam


class RetentionProcessingStatus(str, Enum):
    """Allowed states for retention processing."""

    PENDING = "Pending"
    IN_PROGRESS = "In Progress"
    COMPLETED = "Completed"
    FAILED = "Failed"


class AssessmentRetentionProcessing(Base):
    """One resumable retention-processing state record for an exam.

    ``attempt_count`` counts retention-processing executions or retries; it
    does not represent the candidate's number of assessment attempts.
    Failure diagnostics must contain operational information only and must
    exclude candidate PII, answers, question content, authentication
    secrets, and recording content.
    """

    __tablename__ = "assessment_retention_processing"
    __table_args__ = (
        CheckConstraint("attempt_count >= 0", name="ck_retention_attempt_count_non_negative"),
        CheckConstraint(
            "processing_completed_at IS NULL OR processing_started_at IS NULL "
            "OR processing_completed_at >= processing_started_at",
            name="ck_retention_processing_timestamp_order",
        ),
        CheckConstraint(
            "(status = 'Pending' AND attempt_count = 0 AND processing_started_at IS NULL "
            "AND processing_completed_at IS NULL AND failure_category IS NULL AND failure_diagnostics IS NULL "
            "AND lease_owner IS NULL AND lease_expires_at IS NULL AND heartbeat_at IS NULL) "
            "OR (status = 'In Progress' AND attempt_count >= 1 AND processing_started_at IS NOT NULL "
            "AND processing_completed_at IS NULL AND failure_category IS NULL AND failure_diagnostics IS NULL "
            "AND lease_owner IS NOT NULL AND lease_expires_at IS NOT NULL AND heartbeat_at IS NOT NULL) "
            "OR (status = 'Completed' AND attempt_count >= 1 AND processing_started_at IS NOT NULL "
            "AND processing_completed_at IS NOT NULL AND failure_category IS NULL AND failure_diagnostics IS NULL "
            "AND lease_owner IS NULL AND lease_expires_at IS NULL AND heartbeat_at IS NULL) "
            "OR (status = 'Failed' AND attempt_count >= 1 AND processing_started_at IS NOT NULL "
            "AND processing_completed_at IS NOT NULL AND failure_category IS NOT NULL "
            "AND lease_owner IS NULL AND lease_expires_at IS NULL AND heartbeat_at IS NULL)",
            name="ck_retention_status_consistency",
        ),
        CheckConstraint(
            "(lease_owner IS NULL AND lease_expires_at IS NULL AND heartbeat_at IS NULL) "
            "OR (lease_owner IS NOT NULL AND lease_expires_at IS NOT NULL AND heartbeat_at IS NOT NULL)",
            name="ck_retention_lease_fields_consistency",
        ),
        Index("ix_retention_processing_status", "status"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    exam_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("exams.id"), nullable=False, unique=True)
    status: Mapped[RetentionProcessingStatus] = mapped_column(
        SAEnum(
            RetentionProcessingStatus,
            name="retention_processing_status",
            native_enum=False,
            values_callable=lambda enum_type: [member.value for member in enum_type],
        ),
        nullable=False,
        default=RetentionProcessingStatus.PENDING,
        server_default=text("'Pending'"),
    )
    processing_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    processing_completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))
    failure_category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    failure_diagnostics: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    last_successful_stage: Mapped[str | None] = mapped_column(String(100), nullable=True)
    lease_owner: Mapped[str | None] = mapped_column(String(255), nullable=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    exam: Mapped["Exam"] = relationship(back_populates="retention_processing")
