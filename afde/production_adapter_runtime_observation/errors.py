"""Typed failures for the Production Adapter Runtime observation boundary."""


class ProductionAdapterRuntimeObservationError(RuntimeError):
    """Base error for package-scoped Runtime observation validation."""


class InvalidProductionAdapterRuntimeObservationIdentityError(
    ProductionAdapterRuntimeObservationError,
    ValueError,
):
    """Raised when an observation identity is malformed."""


class InvalidProductionAdapterRuntimeObservationSourceError(
    ProductionAdapterRuntimeObservationError,
    TypeError,
):
    """Raised when the observed execution contract is invalid."""


class InvalidProductionAdapterRuntimeObservationResultError(
    ProductionAdapterRuntimeObservationError,
    ValueError,
):
    """Raised when an observation result is inconsistent."""


class ProductionAdapterRuntimeObservationIdentityMismatchError(
    ProductionAdapterRuntimeObservationError,
    ValueError,
):
    """Raised when observation and execution identities conflict."""
