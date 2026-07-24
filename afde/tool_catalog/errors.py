"""Domain errors for the read-only Tool Adapter Catalog."""


class ToolAdapterCatalogError(RuntimeError):
    """Base error for Catalog validation and lookup failures."""


class InvalidToolAdapterDescriptorError(
    ToolAdapterCatalogError, ValueError,
):
    """Raised when adapter discovery metadata is invalid."""


class InvalidToolAdapterCatalogError(
    ToolAdapterCatalogError, ValueError,
):
    """Raised when a Catalog snapshot or query is invalid."""


class DuplicateAdapterIdentityError(InvalidToolAdapterCatalogError):
    """Raised when the Catalog contains a repeated adapter identity."""


class AmbiguousCapabilityMappingError(InvalidToolAdapterCatalogError):
    """Raised when multiple selectable adapters own one Capability ID."""


class AdapterNotFoundError(ToolAdapterCatalogError, LookupError):
    """Raised when an exact adapter identity is not cataloged."""
