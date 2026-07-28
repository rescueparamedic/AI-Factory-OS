"""Typed failures for production adapter instance creation."""


class ProductionAdapterCreationError(RuntimeError):
    """Base error for the non-executable adapter creation boundary."""


class InvalidProductionAdapterCreationContextError(
    ProductionAdapterCreationError,
    ValueError,
):
    """Raised when caller-supplied creation context is malformed."""


class InvalidProductionAdapterFactoryError(
    ProductionAdapterCreationError,
    TypeError,
):
    """Raised when a supplied factory violates the factory contract."""


class ProductionAdapterFactoryNotFoundError(
    ProductionAdapterCreationError,
    LookupError,
):
    """Raised when no exact factory is registered for an adapter."""


class DuplicateProductionAdapterFactoryError(
    ProductionAdapterCreationError,
    ValueError,
):
    """Raised when multiple factories declare one adapter identity."""


class ProductionAdapterCreationIdentityMismatchError(
    ProductionAdapterCreationError,
    ValueError,
):
    """Raised when creation identities do not match the descriptor."""


class AdapterUnavailableForCreationError(
    ProductionAdapterCreationError,
):
    """Raised when descriptor availability prohibits creation."""


class CredentialNotReadyForCreationError(
    ProductionAdapterCreationError,
):
    """Raised when declared credential readiness prohibits creation."""


class ProductionAdapterFactoryCreationError(
    ProductionAdapterCreationError,
):
    """Raised when a factory cannot produce an instance."""


class InvalidProductionAdapterInstanceError(
    ProductionAdapterCreationError,
    TypeError,
):
    """Raised when a factory returns an invalid instance contract."""


class InvalidProductionAdapterCreationResultError(
    ProductionAdapterCreationError,
    ValueError,
):
    """Raised when a creation result violates immutable invariants."""
