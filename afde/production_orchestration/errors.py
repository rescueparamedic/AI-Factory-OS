"""Errors for the production Planner-to-Runtime orchestration boundary."""


class ProductionOrchestrationError(RuntimeError):
    """Base error for invalid orchestration composition or contracts."""


class InvalidProductionOrchestrationRequestError(
    ProductionOrchestrationError, ValueError
):
    """Raised when governed orchestration input is malformed."""


class InvalidProductionOrchestrationResultError(
    ProductionOrchestrationError, ValueError
):
    """Raised when an orchestration result is internally inconsistent."""
