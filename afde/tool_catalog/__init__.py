"""Governed read-only Tool Adapter Catalog foundation."""

from .catalog import ToolAdapterCatalog
from .errors import (
    AdapterNotFoundError,
    AmbiguousCapabilityMappingError,
    DuplicateAdapterIdentityError,
    InvalidToolAdapterCatalogError,
    InvalidToolAdapterDescriptorError,
    ToolAdapterCatalogError,
)
from .models import (
    AdapterAvailability,
    CapabilityAdapterMapping,
    CostClassification,
    ExecutionContract,
    PrivacyClassification,
    RuntimeCompatibility,
    ToolAdapterCatalogSnapshot,
    ToolAdapterDescriptor,
)

__all__ = [
    "AdapterAvailability",
    "AdapterNotFoundError",
    "AmbiguousCapabilityMappingError",
    "CapabilityAdapterMapping",
    "CostClassification",
    "DuplicateAdapterIdentityError",
    "ExecutionContract",
    "InvalidToolAdapterCatalogError",
    "InvalidToolAdapterDescriptorError",
    "PrivacyClassification",
    "RuntimeCompatibility",
    "ToolAdapterCatalog",
    "ToolAdapterCatalogError",
    "ToolAdapterCatalogSnapshot",
    "ToolAdapterDescriptor",
]
