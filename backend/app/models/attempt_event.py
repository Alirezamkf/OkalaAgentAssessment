"""ORM model for an activity or state-related event in an assessment attempt."""

from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any

from sqlalchemy import BigInteger, CheckConstraint, DateTime, Enum as SAEnum, ForeignKey, Index, Integer, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base

if TYPE_CHECKING:
    from app.models.assessment_attempt import AssessmentAttempt


class AttemptEventType(str, Enum):
    """Allowed activity event types persisted for assessment attempts."""

    TAB_HIDDEN = "TabHidden"
    CAMERA_STOPPED = "CameraStopped"
    SCREEN_SHARE_STOPPED = "ScreenShareStopped"
    COPY_ATTEMPT = "CopyAttempt"
    PASTE_ATTEMPT = "PasteAttempt"
    REENTERED = "Reentered"
    CONCURRENT_SESSION_BLOCKED = "ConcurrentSessionBlocked"
    IDLE = "Idle"
    NETWORK_DISCONNECTED = "NetworkDisconnected"
    NETWORK_RESTORED = "NetworkRestored"
    RECORDING_GAP = "RecordingGap"


class AttemptEvent(Base):
    """Extensible event record associated with one assessment attempt."""

    __tablename__ = "attempt_events"
    __table_args__ = (
        CheckConstraint(
            "duration_seconds IS NULL OR duration_seconds >= 0",
            name="ck_attempt_events_duration_seconds_non_negative",
        ),
        Index("ix_attempt_events_attempt_occurred_at", "attempt_id", "occurred_at"),
        Index("ix_attempt_events_event_type", "event_type"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    attempt_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("assessment_attempts.id"),
        nullable=False,
    )
    # PostgreSQL-native Enum keeps event_type restricted to the approved 11 values.
    event_type: Mapped[AttemptEventType] = mapped_column(
        SAEnum(
            AttemptEventType,
            name="attempt_event_type",
            native_enum=True,
            validate_strings=True,
        ),
        nullable=False,
    )
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    # Duration is independent of occurred_at and remains NULL when not measurable.
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    event_metadata: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)

    attempt: Mapped["AssessmentAttempt"] = relationship(back_populates="events")
