"""Typed failures for non-executable production adapter startup assembly."""


class ProductionAdapterRuntimeStartupIntegrationError(RuntimeError):
    """Base error for the package-scoped startup composition boundary."""


class InvalidProductionAdapterRuntimeStartupRequestError(
    ProductionAdapterRuntimeStartupIntegrationError,
    TypeError,
):
    """Raised when a caller-supplied startup dependency is malformed."""


class ProductionAdapterRuntimeStartupIdentityMismatchError(
    ProductionAdapterRuntimeStartupIntegrationError,
    ValueError,
):
    """Raised when any startup dependency declares another adapter identity."""


class ProductionAdapterRuntimeStartupPrerequisiteError(
    ProductionAdapterRuntimeStartupIntegrationError,
):
    """Raised when availability or credential readiness is not sufficient."""


class InvalidProductionAdapterRuntimeStartupCompositionError(
    ProductionAdapterRuntimeStartupIntegrationError,
    ValueError,
):
    """Raised when the immutable startup result violates its invariants."""
