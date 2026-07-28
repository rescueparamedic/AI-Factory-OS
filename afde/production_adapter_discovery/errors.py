"""Typed failures for production Tool Adapter metadata discovery."""


class ProductionAdapterDiscoveryError(RuntimeError):
    """Base error for the production discovery boundary."""


class DiscoverySourceError(ProductionAdapterDiscoveryError):
    """Raised when the configured discovery source cannot be enumerated."""


class EntryPointLoadError(ProductionAdapterDiscoveryError):
    """Raised when one Tool Adapter descriptor entry point cannot be loaded."""


class EntryPointTypeError(ProductionAdapterDiscoveryError, TypeError):
    """Raised when an entry point does not return a ToolAdapterDescriptor."""
