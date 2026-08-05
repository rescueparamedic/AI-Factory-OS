"""Typed failures for the Production Adapter Runtime event stream boundary."""


class ProductionAdapterRuntimeEventStreamError(RuntimeError):
    """Base error for package-scoped Runtime event stream validation."""


class InvalidProductionAdapterRuntimeEventStreamRequestError(
    ProductionAdapterRuntimeEventStreamError,
    TypeError,
):
    """Raised when a Runtime event stream request is invalid."""


class InvalidProductionAdapterRuntimeEventStreamResultError(
    ProductionAdapterRuntimeEventStreamError,
    ValueError,
):
    """Raised when a Runtime event stream result is inconsistent."""
