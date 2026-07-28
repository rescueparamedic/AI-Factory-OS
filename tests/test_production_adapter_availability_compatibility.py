from dataclasses import dataclass
from pathlib import Path

from afde.execution_path import ExecutionPathRequest, ExecutionPathService
from afde.knowledge import KnowledgeFoundationProvider
from afde.operational_adapter_registry import OperationalAdapterRegistry
from afde.production_adapter_availability import (
    ProductionAdapterAvailabilityService,
)
from afde.production_adapter_discovery import (
    build_discovered_production_adapter_registry,
)
from afde.resolver import CapabilityRequirement, CapabilityResolver
from afde.runtime_integration import (
    RuntimeIntegrationPolicy,
    RuntimeIntegrationRequest,
    RuntimeIntegrationService,
    RuntimeProjection,
)
from afde.tool_catalog import (
    AdapterAvailability,
    CostClassification,
    ExecutionContract,
    PrivacyClassification,
    RuntimeCompatibility,
    ToolAdapterCatalog,
    ToolAdapterDescriptor,
)
from afde.tool_selection import (
    ToolAdapterSelectionRequest,
    ToolAdapterSelectionService,
)


CAPABILITY_ID = "CAP-KNOW-0001"
ROOT = Path(__file__).resolve().parents[1]


def _descriptor():
    return ToolAdapterDescriptor(
        adapter_id="adapter.availability_compatible",
        display_name="Availability Compatible",
        version="1.0.0",
        supported_capability_ids=(CAPABILITY_ID,),
        availability=AdapterAvailability.AVAILABLE,
        runtime_compatibility=RuntimeCompatibility.COMPATIBLE,
        execution_contract=ExecutionContract.CONTROLLED_RUNTIME,
        privacy_classification=PrivacyClassification.LOCAL,
        cost_classification=CostClassification.NO_COST,
        credentials_required=False,
        description="Availability compatibility fixture.",
        metadata_references=("fixture:availability-compatibility",),
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
            value="fake:availability_descriptor",
            descriptor=descriptor,
        )

    def entry_points(self, group):
        assert group == "ai_factory_os.tool_adapters"
        return (self._entry_point,)


def _policy():
    return RuntimeIntegrationPolicy(
        projection_version="1.0.0",
        required_runtime_compatibility=RuntimeCompatibility.COMPATIBLE,
        required_execution_contract=ExecutionContract.CONTROLLED_RUNTIME,
    )


def test_discovery_registry_and_catalog_supply_the_exact_descriptor():
    descriptor = _descriptor()
    registry = build_discovered_production_adapter_registry(
        source=FakeDiscoverySource(descriptor)
    )
    catalog = registry.project_catalog()
    registered = catalog.get_adapter(descriptor.adapter_id)

    result = ProductionAdapterAvailabilityService().assess(registered)

    assert isinstance(registry, OperationalAdapterRegistry)
    assert isinstance(catalog, ToolAdapterCatalog)
    assert registry.project_catalog() is catalog
    assert registered is descriptor
    assert result.descriptor is descriptor
    assert result.availability is AdapterAvailability.AVAILABLE
    assert result.available is True


def test_assessment_does_not_change_execution_path_or_runtime_projection():
    descriptor = _descriptor()
    registry = build_discovered_production_adapter_registry(
        source=FakeDiscoverySource(descriptor)
    )
    catalog = registry.project_catalog()
    assessment = ProductionAdapterAvailabilityService().assess(
        catalog.get_adapter(descriptor.adapter_id)
    )

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

    assert path.adapter_id == descriptor.adapter_id
    assert path.runtime_allowed is False
    assert path.execution_allowed is False
    assert isinstance(runtime.projection, RuntimeProjection)
    assert runtime.projection.adapter_id == descriptor.adapter_id
    assert runtime.projection.availability is assessment.availability
    assert runtime.projection.runtime_allowed is False
    assert runtime.projection.execution_allowed is False
    assert runtime.runtime_allowed is False
    assert runtime.execution_allowed is False


def test_registry_catalog_descriptor_and_runtime_contracts_are_unchanged():
    descriptor = _descriptor()
    registry = OperationalAdapterRegistry((descriptor,))
    catalog = registry.project_catalog()
    before = registry.snapshot

    result = ProductionAdapterAvailabilityService().assess(
        catalog.get_adapter(descriptor.adapter_id)
    )

    assert registry.snapshot is before
    assert registry.project_catalog() is catalog
    assert catalog.get_adapter(descriptor.adapter_id) is descriptor
    assert result.runtime_allowed is False
    assert result.execution_allowed is False
