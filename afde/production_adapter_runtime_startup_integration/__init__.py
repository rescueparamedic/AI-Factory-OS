"""Package-scoped non-executable production adapter startup composition."""

from .errors import (
    InvalidProductionAdapterRuntimeStartupCompositionError,
    InvalidProductionAdapterRuntimeStartupRequestError,
    ProductionAdapterRuntimeStartupIdentityMismatchError,
    ProductionAdapterRuntimeStartupIntegrationError,
    ProductionAdapterRuntimeStartupPrerequisiteError,
)
from .factory import build_production_adapter_runtime_startup_composition
from .credential_projection import (
    adapt_credential_readiness_to_runtime_prerequisite_satisfaction,
)
from .models import ProductionAdapterRuntimeStartupComposition

__all__ = [
    "InvalidProductionAdapterRuntimeStartupCompositionError",
    "InvalidProductionAdapterRuntimeStartupRequestError",
    "ProductionAdapterRuntimeStartupComposition",
    "ProductionAdapterRuntimeStartupIdentityMismatchError",
    "ProductionAdapterRuntimeStartupIntegrationError",
    "ProductionAdapterRuntimeStartupPrerequisiteError",
    "adapt_credential_readiness_to_runtime_prerequisite_satisfaction",
    "build_production_adapter_runtime_startup_composition",
]
