from dataclasses import FrozenInstanceError, dataclass, replace
from pathlib import Path

import pytest

import afde
import afde.production_adapter_runtime_startup_integration as startup_package
from afde.knowledge import KnowledgeFoundationProvider
from afde.production_adapter_creation import (
    ProductionAdapterConfigurationKey,
    ProductionAdapterConfigurationMetadata,
    ProductionAdapterInstance,
)
from afde.production_adapter_credential_readiness import (
    CredentialReadinessEvidence,
    CredentialReadinessEvidenceSource,
)
from afde.production_adapter_invocation import InvocationTargetResult
from afde.production_adapter_runtime_startup_integration import (
    InvalidProductionAdapterRuntimeStartupCompositionError,
    InvalidProductionAdapterRuntimeStartupRequestError,
    ProductionAdapterRuntimeStartupIdentityMismatchError,
    ProductionAdapterRuntimeStartupPrerequisiteError,
    build_production_adapter_runtime_startup_composition,
)
from afde.runtime_integration import RuntimeIntegrationPolicy
from afde.tool_catalog import (
    AdapterAvailability,
    CostClassification,
    ExecutionContract,
    PrivacyClassification,
    RuntimeCompatibility,
    ToolAdapterDescriptor,
)


ROOT = Path(__file__).resolve().parents[1]
ADAPTER_ID = "adapter.startup_fixture"


def _descriptor(**overrides):
    values = {
        "adapter_id": ADAPTER_ID,
        "display_name": "Startup Fixture",
        "version": "1.0.0",
        "supported_capability_ids": ("CAP-STARTUPFIXTURE-0001",),
        "availability": AdapterAvailability.AVAILABLE,
        "runtime_compatibility": RuntimeCompatibility.COMPATIBLE,
        "execution_contract": ExecutionContract.CONTROLLED_RUNTIME,
        "privacy_classification": PrivacyClassification.LOCAL,
        "cost_classification": CostClassification.NO_COST,
        "credentials_required": True,
        "description": "Startup integration metadata fixture.",
        "metadata_references": ("fixture:startup",),
    }
    values.update(overrides)
    return ToolAdapterDescriptor(**values)


@dataclass(frozen=True)
class FakeEntryPoint:
    name: str
    value: str
    descriptor: ToolAdapterDescriptor

    def load(self):
        return self.descriptor


class FakeDiscoverySource:
    def __init__(self, descriptor):
        self.descriptor = descriptor
        self.groups = []

    def entry_points(self, group):
        self.groups.append(group)
        return (FakeEntryPoint("startup", "fake:startup", self.descriptor),)


class FakeFactory:
    def __init__(self, adapter_id=ADAPTER_ID):
        self.adapter_id = adapter_id
        self.contexts = []

    def create(self, context):
        self.contexts.append(context)
        return ProductionAdapterInstance(
            adapter_id=context.adapter_id,
            creation_metadata_references=("CREATION-REFERENCE-STARTUP-001",),
        )


class FakeInvocationTarget:
    def __init__(self, adapter_id=ADAPTER_ID):
        self.adapter_id = adapter_id
        self.requests = []

    def invoke(self, request):
        self.requests.append(request)
        return InvocationTargetResult(
            adapter_id=self.adapter_id,
            result_metadata_references=(
                "INVOCATION-RESULT-REFERENCE-STARTUP-001",
            ),
        )


def _evidence(adapter_id=ADAPTER_ID, ready=True):
    return CredentialReadinessEvidence(
        adapter_id=adapter_id,
        ready=ready,
        evidence_reference="CRED-EVIDENCE-STARTUP-001",
        source=CredentialReadinessEvidenceSource.CALLER_ASSERTION,
    )


def _configuration():
    return (
        ProductionAdapterConfigurationMetadata(
            key=ProductionAdapterConfigurationKey.DEPLOYMENT_REFERENCE,
            reference="CONFIG-REFERENCE-STARTUP-DEPLOYMENT",
        ),
        ProductionAdapterConfigurationMetadata(
            key=ProductionAdapterConfigurationKey.PROFILE_REFERENCE,
            reference="CONFIG-REFERENCE-STARTUP-PROFILE",
        ),
    )


def _policy():
    return RuntimeIntegrationPolicy(
        projection_version="1.0.0",
        required_runtime_compatibility=RuntimeCompatibility.COMPATIBLE,
        required_execution_contract=ExecutionContract.CONTROLLED_RUNTIME,
    )


def _build(*, descriptor=None, factory=None, target=None, evidence=None):
    descriptor = descriptor or _descriptor()
    factory = factory or FakeFactory(descriptor.adapter_id)
    target = target or FakeInvocationTarget(descriptor.adapter_id)
    evidence = _evidence(descriptor.adapter_id) if evidence is None else evidence
    result = build_production_adapter_runtime_startup_composition(
        knowledge_provider=KnowledgeFoundationProvider(ROOT),
        runtime_policy=_policy(),
        adapter_id=descriptor.adapter_id,
        discovery_source=FakeDiscoverySource(descriptor),
        factory=factory,
        credential_readiness_evidence=evidence,
        configuration_metadata=_configuration(),
        invocation_target=target,
    )
    return result, factory, target


def test_startup_composes_existing_capabilities_without_creation_or_invocation():
    result, factory, target = _build()

    catalog = result.adapter_registry.project_catalog()
    assert result.production_composition.tool_adapter_catalog is catalog
    assert catalog.get_adapter(ADAPTER_ID) is result.descriptor
    assert result.availability.descriptor is result.descriptor
    assert result.credential_readiness.descriptor is result.descriptor
    assert result.creation_context.descriptor is result.descriptor
    assert result.creation_context.configuration_metadata == _configuration()
    assert result.creation_service.factory_ids == (ADAPTER_ID,)
    assert result.factory is factory
    assert result.invocation_target is target
    assert factory.contexts == []
    assert target.requests == []
    assert result.runtime_allowed is False
    assert result.execution_allowed is False


def test_startup_result_is_immutable_and_denies_authority():
    result, _, _ = _build()

    with pytest.raises(FrozenInstanceError):
        result.adapter_id = "adapter.changed"
    with pytest.raises(InvalidProductionAdapterRuntimeStartupCompositionError):
        replace(result, runtime_allowed=True)
    with pytest.raises(InvalidProductionAdapterRuntimeStartupCompositionError):
        replace(result, execution_allowed=True)


@pytest.mark.parametrize("dependency", [None, object()])
def test_malformed_factory_or_target_fails_closed(dependency):
    descriptor = _descriptor()
    common = {
        "knowledge_provider": KnowledgeFoundationProvider(ROOT),
        "runtime_policy": _policy(),
        "adapter_id": ADAPTER_ID,
        "discovery_source": FakeDiscoverySource(descriptor),
        "credential_readiness_evidence": _evidence(),
        "configuration_metadata": _configuration(),
    }
    with pytest.raises(InvalidProductionAdapterRuntimeStartupRequestError):
        build_production_adapter_runtime_startup_composition(
            **common,
            factory=dependency,
            invocation_target=FakeInvocationTarget(),
        )
    with pytest.raises(InvalidProductionAdapterRuntimeStartupRequestError):
        build_production_adapter_runtime_startup_composition(
            **common,
            factory=FakeFactory(),
            invocation_target=dependency,
        )


def test_identity_mismatch_fails_before_factory_or_target_behavior():
    factory = FakeFactory("adapter.other")
    target = FakeInvocationTarget()

    with pytest.raises(ProductionAdapterRuntimeStartupIdentityMismatchError):
        _build(factory=factory, target=target)

    assert factory.contexts == []
    assert target.requests == []


def test_unavailable_and_not_ready_prerequisites_fail_closed():
    unavailable = _descriptor(availability=AdapterAvailability.UNAVAILABLE)
    with pytest.raises(ProductionAdapterRuntimeStartupPrerequisiteError):
        _build(descriptor=unavailable)

    factory = FakeFactory()
    target = FakeInvocationTarget()
    with pytest.raises(ProductionAdapterRuntimeStartupPrerequisiteError):
        _build(factory=factory, target=target, evidence=_evidence(ready=False))
    assert factory.contexts == []
    assert target.requests == []


def test_public_contract_is_additive_and_package_scoped():
    assert not hasattr(afde, "ProductionAdapterRuntimeStartupComposition")
    assert not hasattr(afde, "build_production_adapter_runtime_startup_composition")
    assert startup_package.__all__ == [
        "InvalidProductionAdapterRuntimeStartupCompositionError",
        "InvalidProductionAdapterRuntimeStartupRequestError",
        "ProductionAdapterRuntimeStartupComposition",
        "ProductionAdapterRuntimeStartupIdentityMismatchError",
        "ProductionAdapterRuntimeStartupIntegrationError",
        "ProductionAdapterRuntimeStartupPrerequisiteError",
        "build_production_adapter_runtime_startup_composition",
    ]
