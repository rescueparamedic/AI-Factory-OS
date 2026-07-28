"""Typed failures for the package-scoped adapter invocation contract."""


class ProductionAdapterInvocationError(RuntimeError):
    """Base error for the non-Runtime invocation boundary."""


class InvalidInvocationRequestError(
    ProductionAdapterInvocationError,
    TypeError,
):
    """Raised when an invocation request violates its immutable contract."""


class InvalidInvocationTargetError(
    ProductionAdapterInvocationError,
    TypeError,
):
    """Raised when a caller-supplied target violates the target protocol."""


class ProductionAdapterInvocationIdentityMismatchError(
    ProductionAdapterInvocationError,
    ValueError,
):
    """Raised when any invocation identity in the chain disagrees."""


class AdapterUnavailableForInvocationError(
    ProductionAdapterInvocationError,
):
    """Raised when descriptor metadata does not declare availability."""


class CredentialNotReadyForInvocationError(
    ProductionAdapterInvocationError,
):
    """Raised when required caller readiness metadata is not ready."""


class InvocationAuthorityViolationError(
    ProductionAdapterInvocationError,
):
    """Raised when Runtime or execution authority is asserted."""


class InvocationTargetCallError(
    ProductionAdapterInvocationError,
):
    """Raised when a caller-supplied target raises internally."""


class InvalidInvocationTargetResultError(
    ProductionAdapterInvocationError,
    TypeError,
):
    """Raised when a target returns an invalid result contract."""


class InvalidInvocationResultError(
    ProductionAdapterInvocationError,
    ValueError,
):
    """Raised when the service result violates immutable invariants."""
