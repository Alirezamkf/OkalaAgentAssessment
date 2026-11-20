"""Pydantic schemas for attempt event input and output contracts."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.attempt_event import AttemptEventType


class AttemptEventCreate(BaseModel):
    """Optional duration contract for creating an assessment attempt event."""

    event_type: AttemptEventType
    occurred_at: datetime | None = None
    duration_seconds: int | None = Field(default=None, ge=0)
    event_metadata: dict[str, Any] = Field(default_factory=dict)


class AttemptEventResponse(BaseModel):
    """Serialized attempt event representation."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    attempt_id: int
    event_type: AttemptEventType
    occurred_at: datetime
    duration_seconds: int | None
    event_metadata: dict[str, Any]
