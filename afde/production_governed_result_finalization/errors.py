"""Typed failures for governed Production result finalization."""


class ProductionGovernedResultFinalizationError(RuntimeError):
    """Base error for predictable finalization failures."""


class InvalidProductionGovernedResultFinalizationRequestError(
    ProductionGovernedResultFinalizationError,
):
    """The supported top-level request or generated identity is invalid."""
