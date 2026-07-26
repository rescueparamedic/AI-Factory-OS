import pytest

import afde
import afde.production_composition as production_package
from afde.execution_path import ExecutionPathService
from afde.knowledge import CapabilityContext, CapabilityRegistryEntry
from afde.non_executable_composition import NonExecutableComposition
from afde.operational_adapter_registry import OperationalAdapterRegistry
from afde.planner_resolution import PlannerResolutionService
from afde.production_composition import build_production_composition
from afde.resolver import CapabilityResolver
from afde.runtime_integration import (
    RuntimeIntegrationPolicy,
    RuntimeIntegrationService,
)
from afde.tool_adapter_contract import ToolAdapterContractService
from afde.tool_catalog import (
    AdapterAvailability,
    CostClassification,
    ExecutionContract,
    PrivacyClassification,
    RuntimeCompatibility,
    ToolAdapterDescriptor,
)
from afde.tool_selection import ToolAdapterSelectionService


CAPABILITY_ID = "CAP-KNOW-0001"


class FakeKnowledgeProvider:
    def __init__(self):
        self.calls = []
        self.capability = CapabilityRegistryEntry(
            capability_id=CAPABILITY_ID,
            name="Knowledge Foundation",
            description="In-memory production composition fixture.",
            owner="AI Factory OS Architecture",
            scope="architecture.knowledge_foundation",
            status="implemented",
            maturity="M3",
            implementation_status="implemented",
            required_knowledge=(),
            required_capabilities=(),
            tool_dependencies=(),
            adapter_dependencies=(),
            runtime_dependencies=(),
            implementation_references=("afde/knowledge/",),
            validation_evidence=("in-memory test",),
            known_gaps=(),
            source_documents=(),
            supersedes=(),
        )

    def get_capability(self, capability_id):
        self.calls.append(("get_capability", capability_id))
        return self.capability

    def capability_context(self, capability_id, scope=None):
        self.calls.append(("capability_context", capability_id, scope))
        return CapabilityContext(
            capability=self.capability,
            required_knowledge=(),
            source_documents=(),
            authority=(),
            status=self.capability.status,
            scope=scope or self.capability.scope,
            reference_priority=("constitutional",),
            gaps=(),
        )

    def gaps(self, capability_id, scope=None):
        self.calls.append(("gaps", capability_id, scope))
        return ()

    def get_knowledge(self, knowledge_id):
        raise AssertionError("no Knowledge lookup is expected")

    def get_document(self, document_id):
        raise AssertionError("no Document lookup is expected")

    def reference_priority(self, scope=None):
        self.calls.append(("reference_priority", scope))
        return ("constitutional",)


def _descriptor():
    return ToolAdapterDescriptor(
        adapter_id="adapter.production",
        display_name="Production Metadata Fixture",
        version="1.0.0",
        supported_capability_ids=(CAPABILITY_ID,),
        availability=AdapterAvailability.AVAILABLE,
        runtime_compatibility=RuntimeCompatibility.COMPATIBLE,
        execution_contract=ExecutionContract.CONTROLLED_RUNTIME,
        privacy_classification=PrivacyClassification.LOCAL,
        cost_classification=CostClassification.NO_COST,
        credentials_required=False,
        description="Non-executable registration metadata.",
        metadata_references=("DOC-COMPOSITION-0001",),
    )


def _policy():
    return RuntimeIntegrationPolicy(
        projection_version="1.0.0",
        required_runtime_compatibility=RuntimeCompatibility.COMPATIBLE,
        required_execution_contract=ExecutionContract.CONTROLLED_RUNTIME,
    )


def _composition(provider=None, registry=None, policy=None):
    return build_production_composition(
        knowledge_provider=provider or FakeKnowledgeProvider(),
        adapter_registry=(
            OperationalAdapterRegistry((_descriptor(),))
            if registry is None
            else registry
        ),
        runtime_policy=policy or _policy(),
    )


def test_builder_reuses_existing_container_services_and_registry_catalog():
    registry = OperationalAdapterRegistry((_descriptor(),))

    composition = _composition(registry=registry)

    assert isinstance(composition, NonExecutableComposition)
    assert isinstance(composition.capability_resolver, CapabilityResolver)
    assert isinstance(composition.planner_resolution, PlannerResolutionService)
    assert isinstance(
        composition.tool_adapter_selection,
        ToolAdapterSelectionService,
    )
    assert isinstance(composition.execution_path, ExecutionPathService)
    assert isinstance(
        composition.runtime_integration,
        RuntimeIntegrationService,
    )
    assert isinstance(
        composition.tool_adapter_contract,
        ToolAdapterContractService,
    )
    catalog = registry.project_catalog()
    assert composition.tool_adapter_catalog is catalog
    assert composition.tool_adapter_selection._candidate_source is catalog
    assert composition.execution_path._catalog is catalog
    assert composition.tool_adapter_contract._lookup is catalog


def test_empty_registry_produces_valid_non_executable_composition():
    composition = _composition(registry=OperationalAdapterRegistry(()))

    assert composition.tool_adapter_catalog.list_adapters() == ()
    assert composition.runtime_allowed is False
    assert composition.execution_allowed is False
    for name in (
        "run",
        "execute",
        "invoke",
        "dispatch",
        "start",
        "resume",
        "recover",
        "cancel",
    ):
        assert not hasattr(composition, name)


def test_builder_only_constructs_and_does_not_call_provider_behavior():
    provider = FakeKnowledgeProvider()

    _composition(provider=provider)

    assert provider.calls == []


@pytest.mark.parametrize(
    "overrides, message",
    [
        (
            {"provider": object()},
            "knowledge_provider must implement",
        ),
        (
            {"registry": object()},
            "adapter_registry must be",
        ),
        (
            {"policy": object()},
            "runtime_policy must be",
        ),
    ],
)
def test_invalid_dependencies_fail_closed(overrides, message):
    values = {
        "provider": FakeKnowledgeProvider(),
        "registry": OperationalAdapterRegistry((_descriptor(),)),
        "policy": _policy(),
    }
    values.update(overrides)

    with pytest.raises(TypeError, match=message):
        build_production_composition(
            knowledge_provider=values["provider"],
            adapter_registry=values["registry"],
            runtime_policy=values["policy"],
        )


def test_public_contract_is_additive_and_package_scoped():
    assert production_package.__all__ == [
        "build_production_composition",
    ]
    assert not hasattr(afde, "build_production_composition")
