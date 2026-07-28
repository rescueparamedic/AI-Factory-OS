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
    ProductionAdapterCredentialReadinessService,
)
from afde.production_adapter_discovery import (
    build_discovered_production_adapter_registry,
)
from afde.production_adapter_invocation import (
    InvocationRequest,
    InvocationService,
    InvocationTargetResult,
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
)
from afde.tool_adapter_contract import (
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


def _descriptor():
    return ToolAdapterDescriptor(
        adapter_id="adapter.invocation_compatible",
        display_name="Invocation Compatible",
        version="1.0.0",
        supported_capability_ids=(CAPABILITY_ID,),
        availability=AdapterAvailability.AVAILABLE,
        runtime_compatibility=RuntimeCompatibility.COMPATIBLE,
        execution_contract=ExecutionContract.CONTROLLED_RUNTIME,
        privacy_classification=PrivacyClassification.LOCAL,
        cost_classification=CostClassification.NO_COST,
        credentials_required=False,
        description="Invocation compatibility fixture.",
        metadata_references=("fixture:invocation-compatibility",),
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
            "fake:invocation_descriptor",
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
                "CREATION-REFERENCE-INVOCATION-COMPAT-001",
            ),
        )


class FakeInvocationTarget:
    def __init__(self, adapter_id):
        self.adapter_id = adapter_id

    def invoke(self, request):
        return InvocationTargetResult(
            adapter_id=request.adapter_id,
            result_metadata_references=(
                "INVOCATION-RESULT-REFERENCE-COMPAT-001",
            ),
        )


def _policy():
    return RuntimeIntegrationPolicy(
        projection_version="1.0.0",
        required_runtime_compatibility=RuntimeCompatibility.COMPATIBLE,
        required_execution_contract=ExecutionContract.CONTROLLED_RUNTIME,
    )


def test_invocation_reuses_full_existing_metadata_chain_unchanged():
    descriptor = _descriptor()
    registry = build_discovered_production_adapter_registry(
        source=FakeDiscoverySource(descriptor)
    )
    catalog = registry.project_catalog()
    snapshot = registry.snapshot
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
    tool_request = ToolAdapterRequest(runtime.projection)
    contract = ToolAdapterContractService(catalog).bind(tool_request)
    availability = ProductionAdapterAvailabilityService().assess(
        descriptor
    )
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
    creation = ProductionAdapterCreationService((
        FakeFactory(descriptor.adapter_id),
    )).create(context)
    request = InvocationRequest(
        adapter_id=descriptor.adapter_id,
        descriptor=descriptor,
        creation_result=creation,
        instance=creation.instance,
        tool_adapter_request=tool_request,
        binding=contract.binding,
        availability=availability,
        credential_readiness=readiness,
    )

    result = InvocationService().invoke(
        request,
        FakeInvocationTarget(descriptor.adapter_id),
    )

    assert registry.snapshot is snapshot
    assert registry.project_catalog() is catalog
    assert catalog.get_adapter(descriptor.adapter_id) is descriptor
    assert contract.status is ToolAdapterContractStatus.VALIDATED
    assert request.binding is contract.binding
    assert request.instance is creation.instance
    assert result.request is request
    assert result.runtime_allowed is False
    assert result.execution_allowed is False
    assert runtime.runtime_allowed is False
    assert runtime.execution_allowed is False


def test_static_registration_and_builder_contracts_remain_unchanged():
    registry = build_production_adapter_registry()
    snapshot = registry.snapshot

    assert registry.snapshot is snapshot
    assert registry.project_catalog().list_adapters() == snapshot.adapters
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
