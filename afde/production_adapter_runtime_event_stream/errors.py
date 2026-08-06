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


class InvalidProductionAdapterRuntimeEventStreamTransitionError(
    ProductionAdapterRuntimeEventStreamError,
):
    """Raised when a stream lifecycle operation is invalid for its state."""


class InvalidProductionAdapterRuntimeEventStreamEventError(
    ProductionAdapterRuntimeEventStreamError,
    TypeError,
):
    """Raised when an appended value is not one exact Runtime event."""


class InvalidProductionAdapterRuntimeEventStreamTimestampError(
    ProductionAdapterRuntimeEventStreamError,
    ValueError,
):
    """Raised when a lifecycle timestamp or ordering invariant is invalid."""
