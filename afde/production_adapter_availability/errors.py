"""Typed failures for production Tool Adapter availability metadata."""


class ProductionAdapterAvailabilityError(RuntimeError):
    """Base error for production adapter availability assessment."""


class InvalidAvailabilityDescriptorError(
    ProductionAdapterAvailabilityError,
    TypeError,
):
    """Raised when assessment receives an invalid descriptor."""


class InvalidAvailabilityResultError(
    ProductionAdapterAvailabilityError,
    ValueError,
):
    """Raised when an availability result conflicts with its descriptor."""
