"""Protected route group reserved for the approved AI workflow endpoints."""

from fastapi import APIRouter, Depends

from app.core.authentication import require_backend_service_auth


def create_protected_workflow_router() -> APIRouter:
    """Create the single route group for all authenticated workflow endpoints."""

    return APIRouter(
        prefix="/api/v1/workflows",
        dependencies=[Depends(require_backend_service_auth)],
    )


router = create_protected_workflow_router()
