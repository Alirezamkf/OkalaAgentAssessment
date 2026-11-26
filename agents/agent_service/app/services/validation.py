"""Shared validation boundary for the two approved Agent workflows.

This module adapts the existing workflow schemas and semantic validators. It
does not duplicate their contract rules or perform workflow execution.
"""

from typing import Any

from pydantic import ValidationError

from app.core.errors import AgentServiceError
from app.schemas.attempt_event_summary import (
    AttemptEventSummaryInput,
    AttemptEventSummaryOutput,
    AttemptEventSummaryOutputValidationError,
    validate_attempt_event_summary_output,
)
from app.schemas.hr_reporting import (
    NaturalLanguageReportingInput,
    NaturalLanguageReportingOutput,
    ReportingOutputValidationError,
    validate_natural_language_reporting_output,
)


class WorkflowValidationError(AgentServiceError):
    """Safe base error for invalid workflow input or output."""

    code = "workflow_validation_error"
    message = "Workflow data failed validation."
    public_message = "Workflow data is invalid."
    http_status_code = 422

    def __init__(self) -> None:
        super().__init__(self.message)


class WorkflowInputValidationError(WorkflowValidationError):
    """Raised when a request payload does not match its input schema."""

    code = "workflow_input_invalid"
    message = "Workflow input is invalid."
    public_message = "Workflow input is invalid."
    http_status_code = 422


class WorkflowOutputValidationError(WorkflowValidationError):
    """Raised when model output fails schema or source-dependent validation."""

    code = "workflow_output_invalid"
    message = "Workflow output is invalid."
    public_message = "The AI provider returned an unusable result."
    http_status_code = 502


def validate_attempt_event_summary_input(
    payload: AttemptEventSummaryInput | dict[str, Any],
) -> AttemptEventSummaryInput:
    """Validate untrusted request data before an AI-FR-01 handler is called."""

    try:
        return AttemptEventSummaryInput.model_validate(payload)
    except ValidationError:
        raise WorkflowInputValidationError() from None


def validate_attempt_event_summary_result(
    output: AttemptEventSummaryOutput | dict[str, Any],
    source: AttemptEventSummaryInput,
) -> AttemptEventSummaryOutput:
    """Validate model output shape and its exact source-event correspondence."""

    try:
        return validate_attempt_event_summary_output(output, source)
    except (ValidationError, AttemptEventSummaryOutputValidationError):
        raise WorkflowOutputValidationError() from None


def validate_hr_reporting_input(
    payload: NaturalLanguageReportingInput | dict[str, Any],
) -> NaturalLanguageReportingInput:
    """Validate Backend-prepared AI-FR-04 data before handler execution."""

    try:
        return NaturalLanguageReportingInput.model_validate(payload)
    except ValidationError:
        raise WorkflowInputValidationError() from None


def validate_hr_reporting_result(
    output: NaturalLanguageReportingOutput | dict[str, Any],
    source: NaturalLanguageReportingInput,
) -> NaturalLanguageReportingOutput:
    """Validate model output against its schema and supplied Backend results."""

    try:
        return validate_natural_language_reporting_output(output, source)
    except (ValidationError, ReportingOutputValidationError):
        raise WorkflowOutputValidationError() from None
