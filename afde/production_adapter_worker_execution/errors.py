"""Typed validation failures for the Production Adapter Worker boundary."""


class ProductionAdapterWorkerExecutionError(RuntimeError):
    """Base error for package-scoped Worker execution validation."""


class InvalidProductionAdapterWorkerExecutionRequestError(
    ProductionAdapterWorkerExecutionError,
    TypeError,
):
    """Raised when the Worker execution request contract is invalid."""


class InvalidProductionAdapterWorkerExecutionResultError(
    ProductionAdapterWorkerExecutionError,
    ValueError,
):
    """Raised when the Worker execution result contract is inconsistent."""


class ProductionAdapterWorkerExecutionIdentityMismatchError(
    ProductionAdapterWorkerExecutionError,
    ValueError,
):
    """Raised when Worker or Runtime result identities conflict."""
