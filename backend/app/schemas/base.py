"""Local strict Pydantic v2 base for backend API contracts."""

from pydantic import BaseModel, ConfigDict


class StrictModel(BaseModel):
    """Reject unknown fields and non-finite numbers at the API boundary.

    This is intentionally local to the backend. It replaces the older shared
    ``okala_ai.contract.StrictModel`` without importing that package, whose
    event and HR-reporting contracts overlap with the current agent service.
    """

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
