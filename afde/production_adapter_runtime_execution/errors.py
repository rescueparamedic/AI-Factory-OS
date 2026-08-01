"""Typed failures for the production adapter Runtime execution boundary."""


class ProductionAdapterRuntimeExecutionError(RuntimeError):
    """Base error for package-scoped Runtime adapter execution."""


class InvalidProductionAdapterRuntimeExecutionAuthorityError(
    ProductionAdapterRuntimeExecutionError,
    ValueError,
):
    """Raised when Runtime authority is malformed or not execution-scoped."""


class InvalidProductionAdapterRuntimeExecutionRequestError(
    ProductionAdapterRuntimeExecutionError,
    TypeError,
):
    """Raised when an execution request violates the package contract."""


class ProductionAdapterRuntimeExecutionIdentityMismatchError(
    ProductionAdapterRuntimeExecutionError,
    ValueError,
):
    """Raised when an authority or request identity chain conflicts."""


class ProductionAdapterRuntimeExecutionAuthorityReuseError(
    ProductionAdapterRuntimeExecutionError,
):
    """Raised when an already-consumed Runtime authority is reused."""


class ProductionAdapterRuntimeCreationCallError(
    ProductionAdapterRuntimeExecutionError,
):
    """Raised when the reused production adapter creation boundary fails."""


class ProductionAdapterRuntimeInvocationCallError(
    ProductionAdapterRuntimeExecutionError,
):
    """Raised when the reused production adapter invocation boundary fails."""


class InvalidProductionAdapterRuntimeExecutionResultError(
    ProductionAdapterRuntimeExecutionError,
    ValueError,
):
    """Raised when the immutable execution result is inconsistent."""
