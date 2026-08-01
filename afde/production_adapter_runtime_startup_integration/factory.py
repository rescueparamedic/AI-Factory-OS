"""Application-startup composition root for production adapter capabilities."""
from __future__ import annotations

from collections.abc import Iterable

from afde.production_adapter_availability import (
    ProductionAdapterAvailabilityService,
)
from afde.production_adapter_creation import (
    ProductionAdapterConfigurationMetadata,
    ProductionAdapterCreationContext,
    ProductionAdapterCreationService,
    ProductionAdapterFactory,
)
from afde.production_adapter_credential_readiness import (
    CredentialReadinessEvidence,
    CredentialReadinessStatus,
    ProductionAdapterCredentialReadinessService,
)
from afde.production_adapter_discovery import (
    ProductionAdapterDiscoverySource,
    build_discovered_production_adapter_registry,
)
from afde.production_adapter_invocation import InvocationService, InvocationTarget
from afde.production_composition import build_production_composition
from afde.resolver import KnowledgeProvider
from afde.runtime_integration import RuntimeIntegrationPolicy

from .errors import (
    InvalidProductionAdapterRuntimeStartupRequestError,
    ProductionAdapterRuntimeStartupIdentityMismatchError,
    ProductionAdapterRuntimeStartupPrerequisiteError,
)
from .models import ProductionAdapterRuntimeStartupComposition


def build_production_adapter_runtime_startup_composition(
    *,
    knowledge_provider: KnowledgeProvider,
    runtime_policy: RuntimeIntegrationPolicy,
    adapter_id: str,
    discovery_source: ProductionAdapterDiscoverySource,
    factory: ProductionAdapterFactory,
    credential_readiness_evidence: CredentialReadinessEvidence | None,
    configuration_metadata: Iterable[ProductionAdapterConfigurationMetadata],
    invocation_target: InvocationTarget,
) -> ProductionAdapterRuntimeStartupComposition:
    """Assemble and validate startup dependencies without creating or invoking."""

    if (
        not isinstance(adapter_id, str)
        or not adapter_id
        or adapter_id != adapter_id.strip()
    ):
        raise InvalidProductionAdapterRuntimeStartupRequestError(
            "adapter_id must be an exact non-empty identity"
        )
    if discovery_source is None:
        raise InvalidProductionAdapterRuntimeStartupRequestError(
            "discovery_source must be supplied explicitly"
        )
    if credential_readiness_evidence is not None and type(
        credential_readiness_evidence
    ) is not CredentialReadinessEvidence:
        raise InvalidProductionAdapterRuntimeStartupRequestError(
            "credential_readiness_evidence must use the existing contract or None"
        )

    factory_adapter_id = _dependency_identity(factory, "factory", "create")
    target_adapter_id = _dependency_identity(
        invocation_target,
        "invocation_target",
        "invoke",
    )
    evidence_adapter_id = (
        credential_readiness_evidence.adapter_id
        if credential_readiness_evidence is not None
        else adapter_id
    )
    if any(
        identity != adapter_id
        for identity in (
            factory_adapter_id,
            target_adapter_id,
            evidence_adapter_id,
        )
    ):
        raise ProductionAdapterRuntimeStartupIdentityMismatchError(
            "factory, evidence, target, and requested adapter identities must agree"
        )

    adapter_registry = build_discovered_production_adapter_registry(
        source=discovery_source
    )
    production_composition = build_production_composition(
        knowledge_provider=knowledge_provider,
        adapter_registry=adapter_registry,
        runtime_policy=runtime_policy,
    )
    descriptor = production_composition.tool_adapter_catalog.get_adapter(adapter_id)
    availability = ProductionAdapterAvailabilityService().assess(descriptor)
    credential_readiness = ProductionAdapterCredentialReadinessService().assess(
        descriptor,
        credential_readiness_evidence,
    )
    expected_readiness = (
        CredentialReadinessStatus.READY
        if descriptor.credentials_required
        else CredentialReadinessStatus.NOT_REQUIRED
    )
    if not availability.available:
        raise ProductionAdapterRuntimeStartupPrerequisiteError(
            "adapter availability does not permit startup composition"
        )
    if credential_readiness.status is not expected_readiness:
        raise ProductionAdapterRuntimeStartupPrerequisiteError(
            "credential readiness does not permit startup composition"
        )

    creation_service = ProductionAdapterCreationService((factory,))
    creation_context = ProductionAdapterCreationContext(
        adapter_id=adapter_id,
        descriptor=descriptor,
        availability=availability,
        credential_readiness=credential_readiness,
        configuration_metadata=configuration_metadata,
        binding=None,
        runtime_allowed=False,
        execution_allowed=False,
    )
    invocation_service = InvocationService()
    return ProductionAdapterRuntimeStartupComposition(
        adapter_id=adapter_id,
        adapter_registry=adapter_registry,
        production_composition=production_composition,
        descriptor=descriptor,
        availability=availability,
        credential_readiness=credential_readiness,
        creation_context=creation_context,
        creation_service=creation_service,
        factory=factory,
        invocation_service=invocation_service,
        invocation_target=invocation_target,
        trace=(
            f"01.discovery.registry.ready:{adapter_id}",
            "02.production.composition.ready",
            "03.descriptor.identity.validated",
            "04.availability.accepted",
            "05.credential_readiness.accepted",
            "06.creation.dependencies.assembled",
            "07.invocation.dependencies.assembled",
            "08.adapter.creation.not_called",
            "09.adapter.invocation.not_called",
            "10.authority.denied",
        ),
        runtime_allowed=False,
        execution_allowed=False,
    )


def _dependency_identity(dependency: object, name: str, method: str) -> str:
    try:
        adapter_id = getattr(dependency, "adapter_id")
        behavior = getattr(dependency, method)
    except Exception as exc:
        raise InvalidProductionAdapterRuntimeStartupRequestError(
            f"{name} contract could not be inspected"
        ) from exc
    if (
        not isinstance(adapter_id, str)
        or not adapter_id
        or adapter_id != adapter_id.strip()
        or not callable(behavior)
    ):
        raise InvalidProductionAdapterRuntimeStartupRequestError(
            f"{name} must declare an exact adapter identity and {method}"
        )
    return adapter_id
