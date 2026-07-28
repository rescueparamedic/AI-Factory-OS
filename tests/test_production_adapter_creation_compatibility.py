from dataclasses import dataclass
from inspect import Parameter, signature
from pathlib import Path

from afde.execution_path import ExecutionPathRequest, ExecutionPathService
from afde.knowledge import KnowledgeFoundationProvider
from afde.production_adapter_availability import (
    ProductionAdapterAvailabilityService,
)
from afde.production_adapter_creation import (
    ProductionAdapterCreationContext,
    ProductionAdapterCreationService,
    ProductionAdapterInstance,
)
from afde.production_adapter_credential_readiness import (
    CredentialReadinessEvidence,
    CredentialReadinessEvidenceSource,
    ProductionAdapterCredentialReadinessService,
)
from afde.production_adapter_discovery import (
    build_discovered_production_adapter_registry,
)
from afde.production_adapter_registration import (
    build_production_adapter_registry,
)
from afde.production_composition import build_production_composition
from afde.resolver import CapabilityRequirement, CapabilityResolver
from afde.runtime_integration import (
    RuntimeIntegrationPolicy,
    RuntimeIntegrationRequest,
    RuntimeIntegrationService,
    RuntimeProjection,
)
from afde.tool_adapter_contract import (
    ToolAdapterBinding,
    ToolAdapterContractService,
    ToolAdapterContractStatus,
    ToolAdapterRequest,
)
from afde.tool_catalog import (
    AdapterAvailability,
    CostClassification,
    ExecutionContract,
    PrivacyClassification,
    RuntimeCompatibility,
    ToolAdapterDescriptor,
)
from afde.tool_selection import (
    ToolAdapterSelectionRequest,
    ToolAdapterSelectionService,
)


ROOT = Path(__file__).resolve().parents[1]
CAPABILITY_ID = "CAP-KNOW-0001"


def _descriptor(*, credentials_required=False):
    return ToolAdapterDescriptor(
        adapter_id="adapter.creation_compatible",
        display_name="Creation Compatible",
        version="1.0.0",
        supported_capability_ids=(CAPABILITY_ID,),
        availability=AdapterAvailability.AVAILABLE,
        runtime_compatibility=RuntimeCompatibility.COMPATIBLE,
        execution_contract=ExecutionContract.CONTROLLED_RUNTIME,
        privacy_classification=PrivacyClassification.LOCAL,
        cost_classification=CostClassification.NO_COST,
        credentials_required=credentials_required,
        description="Creation compatibility fixture.",
        metadata_references=("fixture:creation-compatibility",),
    )


@dataclass(frozen=True)
class FakeEntryPoint:
    name: str
    value: str
    descriptor: ToolAdapterDescriptor

    def load(self):
        return self.descriptor


class FakeDiscoverySource:
    def __init__(self, descriptor):
        self.entry_point = FakeEntryPoint(
            descriptor.adapter_id,
            "fake:creation_descriptor",
            descriptor,
        )

    def entry_points(self, group):
        assert group == "ai_factory_os.tool_adapters"
        return (self.entry_point,)


class FakeFactory:
    def __init__(self, adapter_id):
        self.adapter_id = adapter_id

    def create(self, context):
        return ProductionAdapterInstance(
            adapter_id=context.adapter_id,
            creation_metadata_references=(
                "CREATION-REFERENCE-COMPAT-001",
            ),
        )


def _policy():
    return RuntimeIntegrationPolicy(
        projection_version="1.0.0",
        required_runtime_compatibility=RuntimeCompatibility.COMPATIBLE,
        required_execution_contract=ExecutionContract.CONTROLLED_RUNTIME,
    )


def test_creation_reuses_existing_binding_without_changing_upstream_contracts():
    descriptor = _descriptor()
    registry = build_discovered_production_adapter_registry(
        source=FakeDiscoverySource(descriptor)
    )
    catalog = registry.project_catalog()
    before = registry.snapshot
    resolution = CapabilityResolver(
        KnowledgeFoundationProvider(ROOT)
    ).resolve(CapabilityRequirement(capability_id=CAPABILITY_ID))
    selection = ToolAdapterSelectionService(catalog).select(
        ToolAdapterSelectionRequest(resolution)
    )
    path = ExecutionPathService(catalog).build(
        ExecutionPathRequest(selection)
    )
    runtime = RuntimeIntegrationService(_policy()).project(
        RuntimeIntegrationRequest(path)
    )
    contract = ToolAdapterContractService(catalog).bind(
        ToolAdapterRequest(runtime.projection)
    )
    availability = ProductionAdapterAvailabilityService().assess(descriptor)
    readiness = ProductionAdapterCredentialReadinessService().assess(
        descriptor
    )
    context = ProductionAdapterCreationContext(
        adapter_id=descriptor.adapter_id,
        descriptor=descriptor,
        availability=availability,
        credential_readiness=readiness,
        binding=contract.binding,
    )

    result = ProductionAdapterCreationService((
        FakeFactory(descriptor.adapter_id),
    )).create(context)

    assert registry.snapshot is before
    assert registry.project_catalog() is catalog
    assert catalog.get_adapter(descriptor.adapter_id) is descriptor
    assert isinstance(runtime.projection, RuntimeProjection)
    assert contract.status is ToolAdapterContractStatus.VALIDATED
    assert isinstance(contract.binding, ToolAdapterBinding)
    assert context.binding is contract.binding
    assert result.instance.adapter_id == descriptor.adapter_id
    assert result.runtime_allowed is False
    assert result.execution_allowed is False
    assert runtime.runtime_allowed is False
    assert runtime.execution_allowed is False


def test_required_ready_creation_does_not_change_existing_prerequisite_path():
    descriptor = _descriptor(credentials_required=True)
    registry = build_discovered_production_adapter_registry(
        source=FakeDiscoverySource(descriptor)
    )
    catalog = registry.project_catalog()
    availability = ProductionAdapterAvailabilityService().assess(descriptor)
    readiness = ProductionAdapterCredentialReadinessService().assess(
        descriptor,
        CredentialReadinessEvidence(
            adapter_id=descriptor.adapter_id,
            ready=True,
            evidence_reference="CRED-EVIDENCE-CREATION-COMPAT-001",
            source=CredentialReadinessEvidenceSource.CALLER_ASSERTION,
        ),
    )
    context = ProductionAdapterCreationContext(
        adapter_id=descriptor.adapter_id,
        descriptor=descriptor,
        availability=availability,
        credential_readiness=readiness,
    )

    result = ProductionAdapterCreationService((
        FakeFactory(descriptor.adapter_id),
    )).create(context)

    resolution = CapabilityResolver(
        KnowledgeFoundationProvider(ROOT)
    ).resolve(CapabilityRequirement(capability_id=CAPABILITY_ID))
    selection = ToolAdapterSelectionService(catalog).select(
        ToolAdapterSelectionRequest(resolution)
    )
    path = ExecutionPathService(catalog).build(
        ExecutionPathRequest(selection)
    )
    runtime = RuntimeIntegrationService(_policy()).project(
        RuntimeIntegrationRequest(path)
    )

    assert result.instance.adapter_id == descriptor.adapter_id
    assert path.runtime_handoff_ready is False
    assert runtime.projection is None
    assert runtime.runtime_allowed is False
    assert runtime.execution_allowed is False


def test_static_registration_remains_metadata_only_and_unchanged():
    registry = build_production_adapter_registry()
    before = registry.snapshot
    descriptor = before.adapters[0]

    assert descriptor.adapter_id == "adapter.codex_automation_bridge"
    assert registry.snapshot is before
    assert registry.project_catalog().get_adapter(
        descriptor.adapter_id
    ) is descriptor


def test_existing_builder_signatures_are_unchanged():
    assert tuple(signature(build_production_adapter_registry).parameters) == ()
    discovered = signature(
        build_discovered_production_adapter_registry
    ).parameters
    assert tuple(discovered) == ("source",)
    assert discovered["source"].kind is Parameter.KEYWORD_ONLY
    assert discovered["source"].default is None
    composition = signature(build_production_composition).parameters
    assert tuple(composition) == (
        "knowledge_provider",
        "adapter_registry",
        "runtime_policy",
    )
    assert all(
        item.kind is Parameter.KEYWORD_ONLY
        for item in composition.values()
    )
