"""ORM model for an activity or state-related event in an assessment attempt."""

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base

if TYPE_CHECKING:
    from app.models.assessment_attempt import AssessmentAttempt


class AttemptEvent(Base):
    """Extensible event record associated with one assessment attempt."""

    __tablename__ = "attempt_events"
    __table_args__ = (
        Index("ix_attempt_events_attempt_occurred_at", "attempt_id", "occurred_at"),
        Index("ix_attempt_events_event_type", "event_type"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    attempt_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("assessment_attempts.id"),
        nullable=False,
    )
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    event_metadata: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)

    attempt: Mapped["AssessmentAttempt"] = relationship(back_populates="events")
