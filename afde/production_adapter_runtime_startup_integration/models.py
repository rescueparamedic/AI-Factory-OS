"""Immutable result for non-executable production adapter startup assembly."""
from __future__ import annotations

from dataclasses import dataclass

from afde.non_executable_composition import NonExecutableComposition
from afde.operational_adapter_registry import OperationalAdapterRegistry
from afde.production_adapter_availability import (
    ProductionAdapterAvailabilityResult,
)
from afde.production_adapter_creation import (
    ProductionAdapterCreationContext,
    ProductionAdapterCreationService,
    ProductionAdapterFactory,
)
from afde.production_adapter_credential_readiness import (
    CredentialReadinessStatus,
    ProductionAdapterCredentialReadinessResult,
)
from afde.production_adapter_invocation import InvocationService, InvocationTarget
from afde.tool_catalog import ToolAdapterDescriptor

from .errors import InvalidProductionAdapterRuntimeStartupCompositionError


@dataclass(frozen=True)
class ProductionAdapterRuntimeStartupComposition:
    """Validated startup dependency graph with no Runtime or execution authority."""

    adapter_id: str
    adapter_registry: OperationalAdapterRegistry
    production_composition: NonExecutableComposition
    descriptor: ToolAdapterDescriptor
    availability: ProductionAdapterAvailabilityResult
    credential_readiness: ProductionAdapterCredentialReadinessResult
    creation_context: ProductionAdapterCreationContext
    creation_service: ProductionAdapterCreationService
    factory: ProductionAdapterFactory
    invocation_service: InvocationService
    invocation_target: InvocationTarget
    trace: tuple[str, ...]
    runtime_allowed: bool = False
    execution_allowed: bool = False

    def __post_init__(self) -> None:
        error = InvalidProductionAdapterRuntimeStartupCompositionError
        exact_types = (
            ("adapter_registry", self.adapter_registry, OperationalAdapterRegistry),
            (
                "production_composition",
                self.production_composition,
                NonExecutableComposition,
            ),
            ("descriptor", self.descriptor, ToolAdapterDescriptor),
            (
                "availability",
                self.availability,
                ProductionAdapterAvailabilityResult,
            ),
            (
                "credential_readiness",
                self.credential_readiness,
                ProductionAdapterCredentialReadinessResult,
            ),
            (
                "creation_context",
                self.creation_context,
                ProductionAdapterCreationContext,
            ),
            (
                "creation_service",
                self.creation_service,
                ProductionAdapterCreationService,
            ),
            ("invocation_service", self.invocation_service, InvocationService),
        )
        for name, value, expected in exact_types:
            if type(value) is not expected:
                raise error(f"{name} contract type is invalid")

        if (
            not isinstance(self.adapter_id, str)
            or not self.adapter_id
            or self.adapter_id != self.adapter_id.strip()
        ):
            raise error("adapter_id must be an exact non-empty identity")

        catalog = self.adapter_registry.project_catalog()
        try:
            catalog_descriptor = catalog.get_adapter(self.adapter_id)
            factory_adapter_id = getattr(self.factory, "adapter_id")
            target_adapter_id = getattr(self.invocation_target, "adapter_id")
            target_invoke = getattr(self.invocation_target, "invoke")
        except Exception as exc:
            raise error("startup dependency identity could not be inspected") from exc

        if (
            self.production_composition.tool_adapter_catalog is not catalog
            or catalog_descriptor is not self.descriptor
            or self.availability.descriptor is not self.descriptor
            or self.credential_readiness.descriptor is not self.descriptor
            or self.creation_context.descriptor is not self.descriptor
            or self.creation_context.availability is not self.availability
            or self.creation_context.credential_readiness
            is not self.credential_readiness
        ):
            raise error("startup objects conflict with the Registry identity chain")
        if (
            self.adapter_id != self.descriptor.adapter_id
            or self.adapter_id != self.credential_readiness.adapter_id
            or self.adapter_id != self.creation_context.adapter_id
            or self.creation_service.factory_ids != (self.adapter_id,)
            or factory_adapter_id != self.adapter_id
            or target_adapter_id != self.adapter_id
            or not callable(target_invoke)
        ):
            raise error("startup adapter identities conflict")
        expected_readiness = (
            CredentialReadinessStatus.READY
            if self.descriptor.credentials_required
            else CredentialReadinessStatus.NOT_REQUIRED
        )
        if (
            not self.availability.available
            or self.credential_readiness.status is not expected_readiness
        ):
            raise error("startup prerequisites are not satisfied")
        if isinstance(self.trace, (str, bytes)):
            raise error("trace must be a tuple of non-empty strings")
        try:
            trace = tuple(self.trace)
        except TypeError as exc:
            raise error("trace must be a tuple of non-empty strings") from exc
        if not trace or any(not isinstance(item, str) or not item for item in trace):
            raise error("trace must be a tuple of non-empty strings")
        authority = (
            self.runtime_allowed,
            self.execution_allowed,
            self.production_composition.runtime_allowed,
            self.production_composition.execution_allowed,
            self.availability.runtime_allowed,
            self.availability.execution_allowed,
            self.credential_readiness.runtime_allowed,
            self.credential_readiness.execution_allowed,
            self.creation_context.runtime_allowed,
            self.creation_context.execution_allowed,
        )
        if any(value is not False for value in authority):
            raise error(
                "startup composition cannot grant Runtime or execution authority"
            )
        object.__setattr__(self, "trace", trace)
