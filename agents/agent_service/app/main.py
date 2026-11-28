import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.api.v1.workflows import router as protected_workflow_router
from app.core.correlation import (
    CORRELATION_ID_HEADER,
    correlation_id_fingerprint,
    new_correlation_id,
    request_correlation_id,
    is_valid_correlation_id,
)
from app.core.errors import AgentServiceError, ErrorDetail, ErrorResponse


logger = logging.getLogger(__name__)

app = FastAPI(title="Okala Generic Agent Service", version="1.0.0")


def _error_response(
    *,
    status_code: int,
    code: str,
    message: str,
    correlation_id: str,
    response_headers: dict[str, str] | None = None,
) -> JSONResponse:
    body = ErrorResponse(
        error=ErrorDetail(code=code, message=message),
        correlation_id=correlation_id,
    )
    headers = {CORRELATION_ID_HEADER: correlation_id}
    if response_headers:
        headers.update(response_headers)
    return JSONResponse(
        status_code=status_code,
        content=body.model_dump(),
        headers=headers,
    )


@app.middleware("http")
async def correlation_id_middleware(request: Request, call_next):
    supplied = request.headers.get(CORRELATION_ID_HEADER)
    correlation_id = supplied if is_valid_correlation_id(supplied) else new_correlation_id()
    request.state.correlation_id = correlation_id
    response = await call_next(request)
    response.headers[CORRELATION_ID_HEADER] = correlation_id
    return response


@app.exception_handler(AgentServiceError)
async def handle_agent_service_error(
    request: Request, exc: AgentServiceError
) -> JSONResponse:
    correlation_id = request_correlation_id(request)
    logger.warning(
        "Agent Service request failed",
        extra={
            "error_code": exc.code,
            "http_status": exc.http_status_code,
            "correlation_fingerprint": correlation_id_fingerprint(correlation_id),
            "outcome": "failure",
        },
    )
    return _error_response(
        status_code=exc.http_status_code,
        code=exc.code,
        message=exc.public_message,
        correlation_id=correlation_id,
        response_headers=getattr(exc, "response_headers", None),
    )


@app.exception_handler(RequestValidationError)
async def handle_request_validation_error(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    # Pydantic details may contain submitted assessment values; never return
    # or log them from the centralized API error handler.
    correlation_id = request_correlation_id(request)
    logger.info(
        "Agent Service rejected an invalid request",
        extra={
            "error_code": "request_validation_error",
            "correlation_fingerprint": correlation_id_fingerprint(correlation_id),
            "outcome": "failure",
        },
    )
    return _error_response(
        status_code=422,
        code="request_validation_error",
        message="Request validation failed.",
        correlation_id=correlation_id,
    )


@app.exception_handler(Exception)
async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
    correlation_id = request_correlation_id(request)
    # Avoid exception text and tracebacks here; either may include prompts,
    # provider response content, credentials, or assessment data.
    logger.error(
        "Unexpected Agent Service failure",
        extra={
            "error_code": "internal_error",
            "exception_type": type(exc).__name__,
            "correlation_fingerprint": correlation_id_fingerprint(correlation_id),
            "outcome": "failure",
        },
    )
    return _error_response(
        status_code=500,
        code="internal_error",
        message="An internal error occurred.",
        correlation_id=correlation_id,
    )


app.include_router(protected_workflow_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "healthy", "service": "agent"}
