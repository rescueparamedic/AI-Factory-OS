"""Typed failures for the Production Adapter Runtime event collection boundary."""


class ProductionAdapterRuntimeEventCollectionError(RuntimeError):
    """Base error for package-scoped Runtime event collection validation."""


class InvalidProductionAdapterRuntimeEventError(
    ProductionAdapterRuntimeEventCollectionError,
    ValueError,
):
    """Raised when one caller-supplied Runtime event is invalid."""


class InvalidProductionAdapterRuntimeEventCollectionRequestError(
    ProductionAdapterRuntimeEventCollectionError,
    TypeError,
):
    """Raised when a Runtime event collection request is invalid."""


class InvalidProductionAdapterRuntimeEventCollectionResultError(
    ProductionAdapterRuntimeEventCollectionError,
    ValueError,
):
    """Raised when a Runtime event collection result is inconsistent."""
