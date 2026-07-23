"""Read-only AFDE Knowledge Foundation Provider."""

from .errors import (
    KnowledgeFoundationError,
    RegistryLoadError,
    RegistryLookupError,
    RegistryNotFoundError,
    RegistryPathError,
    RegistryValidationError,
)
from .loader import DEFAULT_REGISTRY_PATH, KnowledgeRegistryLoader
from .models import (
    CapabilityContext,
    CapabilityRegistryEntry,
    DocumentRegistryEntry,
    KnowledgeFoundationSnapshot,
    KnowledgeGap,
    KnowledgeRegistryEntry,
)
from .provider import KnowledgeFoundationProvider
from .validator import KnowledgeRegistryValidator

__all__ = [
    "CapabilityContext",
    "CapabilityRegistryEntry",
    "DEFAULT_REGISTRY_PATH",
    "DocumentRegistryEntry",
    "KnowledgeFoundationError",
    "KnowledgeFoundationProvider",
    "KnowledgeFoundationSnapshot",
    "KnowledgeGap",
    "KnowledgeRegistryEntry",
    "KnowledgeRegistryLoader",
    "KnowledgeRegistryValidator",
    "RegistryLoadError",
    "RegistryLookupError",
    "RegistryNotFoundError",
    "RegistryPathError",
    "RegistryValidationError",
]
