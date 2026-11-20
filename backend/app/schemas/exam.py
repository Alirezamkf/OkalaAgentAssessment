"""Pydantic contracts for actual exam naming."""

from pydantic import BaseModel, ConfigDict, Field


class ExamCreateResponse(BaseModel):
    """Exam creation response that exposes the backend-selected final name."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str = Field(min_length=1, max_length=200)
