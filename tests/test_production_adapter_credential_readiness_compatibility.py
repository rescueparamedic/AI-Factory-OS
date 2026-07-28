from dataclasses import dataclass
from inspect import Parameter, signature
from pathlib import Path

from afde.execution_path import (
    ExecutionPathRequest,
    ExecutionPathService,
    ExecutionPathStatus,
    RuntimeHandoffProjection,
)
from afde.knowledge import KnowledgeFoundationProvider
from afde.production_adapter_availability import (
    ProductionAdapterAvailabilityService,
)
from afde.production_adapter_credential_readiness import (
    CredentialReadinessEvidence,
    CredentialReadinessEvidenceSource,
    CredentialReadinessStatus,
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
    RuntimeIntegrationStatus,
    RuntimeProjection,
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


def _descriptor(*, credentials_required):
    return ToolAdapterDescriptor(
        adapter_id="adapter.readiness_compatible",
        display_name="Readiness Compatible",
        version="1.0.0",
        supported_capability_ids=(CAPABILITY_ID,),
        availability=AdapterAvailability.AVAILABLE,
        runtime_compatibility=RuntimeCompatibility.COMPATIBLE,
        execution_contract=ExecutionContract.CONTROLLED_RUNTIME,
        privacy_classification=PrivacyClassification.LOCAL,
        cost_classification=CostClassification.NO_COST,
        credentials_required=credentials_required,
        description="Readiness compatibility fixture.",
        metadata_references=("fixture:readiness-compatibility",),
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
        self._entry_point = FakeEntryPoint(
            name=descriptor.adapter_id,
            value="fake:readiness_descriptor",
            descriptor=descriptor,
        )

    def entry_points(self, group):
        assert group == "ai_factory_os.tool_adapters"
        return (self._entry_point,)


def _registry(descriptor):
    return build_discovered_production_adapter_registry(
        source=FakeDiscoverySource(descriptor)
    )


def _path(catalog):
    resolution = CapabilityResolver(
        KnowledgeFoundationProvider(ROOT)
    ).resolve(CapabilityRequirement(capability_id=CAPABILITY_ID))
    selection = ToolAdapterSelectionService(catalog).select(
        ToolAdapterSelectionRequest(resolution)
    )
    return ExecutionPathService(catalog).build(
        ExecutionPathRequest(selection)
    )


def _policy():
    return RuntimeIntegrationPolicy(
        projection_version="1.0.0",
        required_runtime_compatibility=RuntimeCompatibility.COMPATIBLE,
        required_execution_contract=ExecutionContract.CONTROLLED_RUNTIME,
    )


def test_discovery_registry_catalog_and_availability_remain_unchanged():
    descriptor = _descriptor(credentials_required=True)
    registry = _registry(descriptor)
    catalog = registry.project_catalog()
    before = registry.snapshot
    registered = catalog.get_adapter(descriptor.adapter_id)

    availability = ProductionAdapterAvailabilityService().assess(registered)
    readiness = ProductionAdapterCredentialReadinessService().assess(
        registered,
        CredentialReadinessEvidence(
            adapter_id=descriptor.adapter_id,
            ready=True,
            evidence_reference="CRED-EVIDENCE-COMPAT-001",
            source=(
                CredentialReadinessEvidenceSource
                .GOVERNED_RECORD_REFERENCE
            ),
        ),
    )

    assert registered is descriptor
    assert registry.snapshot is before
    assert registry.project_catalog() is catalog
    assert availability.available is True
    assert readiness.status is CredentialReadinessStatus.READY
    assert readiness.descriptor is descriptor


def test_not_required_preserves_existing_execution_and_runtime_projection():
    descriptor = _descriptor(credentials_required=False)
    registry = _registry(descriptor)
    catalog = registry.project_catalog()
    readiness = ProductionAdapterCredentialReadinessService().assess(
        catalog.get_adapter(descriptor.adapter_id)
    )

    path = _path(catalog)
    runtime = RuntimeIntegrationService(_policy()).project(
        RuntimeIntegrationRequest(path)
    )

    assert readiness.status is CredentialReadinessStatus.NOT_REQUIRED
    assert path.status is ExecutionPathStatus.CONSTRUCTED
    assert isinstance(path.steps[0], RuntimeHandoffProjection)
    assert path.steps[0].credentials_required is False
    assert path.runtime_allowed is False
    assert path.execution_allowed is False
    assert runtime.status is RuntimeIntegrationStatus.READY
    assert isinstance(runtime.projection, RuntimeProjection)
    assert runtime.projection.credentials_required is False
    assert runtime.projection.runtime_allowed is False
    assert runtime.projection.execution_allowed is False


def test_ready_assessment_does_not_override_existing_prerequisite_path():
    descriptor = _descriptor(credentials_required=True)
    registry = _registry(descriptor)
    catalog = registry.project_catalog()
    readiness = ProductionAdapterCredentialReadinessService().assess(
        catalog.get_adapter(descriptor.adapter_id),
        CredentialReadinessEvidence(
            adapter_id=descriptor.adapter_id,
            ready=True,
            evidence_reference="CRED-EVIDENCE-PATH-001",
            source=CredentialReadinessEvidenceSource.CALLER_ASSERTION,
        ),
    )

    path = _path(catalog)
    runtime = RuntimeIntegrationService(_policy()).project(
        RuntimeIntegrationRequest(path)
    )

    assert readiness.status is CredentialReadinessStatus.READY
    assert path.status is ExecutionPathStatus.PREREQUISITES_REQUIRED
    assert isinstance(path.steps[0], RuntimeHandoffProjection)
    assert path.steps[0].credentials_required is True
    assert path.runtime_handoff_ready is False
    assert runtime.status is RuntimeIntegrationStatus.BLOCKED
    assert runtime.projection is None
    assert runtime.runtime_allowed is False
    assert runtime.execution_allowed is False


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
        parameter.kind is Parameter.KEYWORD_ONLY
        for parameter in composition.values()
    )
