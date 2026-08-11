"""Typed failures for production Planner-to-Worker dispatch."""


class ProductionPlannerWorkerDispatchError(RuntimeError):
    """Base error for the production dispatch boundary."""


class InvalidProductionPlannerWorkerDispatchRequestError(
    ProductionPlannerWorkerDispatchError,
    ValueError,
):
    """Raised when top-level Worker dispatch input is malformed."""


class InvalidProductionPlannerWorkerDispatchResultError(
    ProductionPlannerWorkerDispatchError,
    ValueError,
):
    """Raised when a dispatch outcome is internally inconsistent."""
