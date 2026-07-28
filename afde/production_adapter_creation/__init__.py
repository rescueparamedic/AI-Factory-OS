"""Explicit non-executable production adapter creation foundation."""

from .errors import (
    AdapterUnavailableForCreationError,
    CredentialNotReadyForCreationError,
    DuplicateProductionAdapterFactoryError,
    InvalidProductionAdapterCreationContextError,
    InvalidProductionAdapterCreationResultError,
    InvalidProductionAdapterFactoryError,
    InvalidProductionAdapterInstanceError,
    ProductionAdapterCreationError,
    ProductionAdapterCreationIdentityMismatchError,
    ProductionAdapterFactoryCreationError,
    ProductionAdapterFactoryNotFoundError,
)
from .models import (
    ProductionAdapterConfigurationKey,
    ProductionAdapterConfigurationMetadata,
    ProductionAdapterCreationContext,
    ProductionAdapterCreationResult,
    ProductionAdapterFactory,
    ProductionAdapterInstance,
)
from .service import ProductionAdapterCreationService

__all__ = [
    "AdapterUnavailableForCreationError",
    "CredentialNotReadyForCreationError",
    "DuplicateProductionAdapterFactoryError",
    "InvalidProductionAdapterCreationContextError",
    "InvalidProductionAdapterCreationResultError",
    "InvalidProductionAdapterFactoryError",
    "InvalidProductionAdapterInstanceError",
    "ProductionAdapterConfigurationKey",
    "ProductionAdapterConfigurationMetadata",
    "ProductionAdapterCreationContext",
    "ProductionAdapterCreationError",
    "ProductionAdapterCreationIdentityMismatchError",
    "ProductionAdapterCreationResult",
    "ProductionAdapterCreationService",
    "ProductionAdapterFactory",
    "ProductionAdapterFactoryCreationError",
    "ProductionAdapterFactoryNotFoundError",
    "ProductionAdapterInstance",
]
