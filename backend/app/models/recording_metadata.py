"""ORM model for provider-independent recording metadata."""

from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, CheckConstraint, DateTime, Enum as SAEnum, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base

if TYPE_CHECKING:
    from app.models.assessment_attempt import AssessmentAttempt


class RecordingMetadata(Base):
    """Metadata and storage reference for one recording of an attempt.

    The model stores no recording bytes and does not select or depend on a
    storage provider. Status values are a strict recording lifecycle contract.
    """

    __tablename__ = "recording_metadata"
    __table_args__ = (
        CheckConstraint(
            "file_size_bytes IS NULL OR file_size_bytes >= 0",
            name="ck_recording_metadata_file_size_non_negative",
        ),
        CheckConstraint(
            "ended_at IS NULL OR started_at IS NULL OR ended_at >= started_at",
            name="ck_recording_metadata_timestamp_order",
        ),
        CheckConstraint(
            "source IN ('webcam', 'screen')",
            name="ck_recording_metadata_source_allowed",
        ),
        CheckConstraint(
            "status IN ('Pending', 'Starting', 'Recording', 'Interrupted', 'Failed', 'Completed')",
            name="ck_recording_metadata_status_allowed",
        ),
        UniqueConstraint(
            "attempt_id",
            "source",
            name="uq_recording_metadata_attempt_source",
        ),
        Index("ix_recording_metadata_attempt_id", "attempt_id"),
        Index("ix_recording_metadata_source", "source"),
        Index("ix_recording_metadata_status", "status"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    attempt_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("assessment_attempts.id"),
        nullable=False,
    )
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped["RecordingStatus"] = mapped_column(
        SAEnum(RecordingStatus, name="recording_status", native_enum=False,
               validate_strings=True, values_callable=lambda enum_type: [member.value for member in enum_type]),
        nullable=False,
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    file_size_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    media_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    storage_reference: Mapped[str | None] = mapped_column(String(1024), nullable=True)

    attempt: Mapped["AssessmentAttempt"] = relationship(back_populates="recordings")
