from dataclasses import dataclass
from inspect import signature

import pytest

from afde.knowledge import CapabilityContext, CapabilityRegistryEntry
from afde.production_adapter_discovery import (
    build_discovered_production_adapter_registry,
)
from afde.production_adapter_registration import (
    build_production_adapter_registry,
)
from afde.production_composition import build_production_composition
from afde.runtime_integration import RuntimeIntegrationPolicy
from afde.tool_catalog import (
    AdapterAvailability,
    AmbiguousCapabilityMappingError,
    CostClassification,
    DuplicateAdapterIdentityError,
    ExecutionContract,
    PrivacyClassification,
    RuntimeCompatibility,
    ToolAdapterCatalog,
    ToolAdapterDescriptor,
)


def _descriptor(
    adapter_id="adapter.discovered",
    capability_id="CAP-DISCOVERED-0001",
):
    return ToolAdapterDescriptor(
        adapter_id=adapter_id,
        display_name="Discovered Adapter",
        version="1.0.0",
        supported_capability_ids=(capability_id,),
        availability=AdapterAvailability.AVAILABLE,
        runtime_compatibility=RuntimeCompatibility.COMPATIBLE,
        execution_contract=ExecutionContract.CONTROLLED_RUNTIME,
        privacy_classification=PrivacyClassification.LOCAL,
        cost_classification=CostClassification.NO_COST,
        credentials_required=False,
        description="Discovered metadata only.",
    )


@dataclass(frozen=True)
class FakeEntryPoint:
    name: str
    value: str
    descriptor: ToolAdapterDescriptor

    def load(self):
        return self.descriptor


class FakeDiscoverySource:
    def __init__(self, descriptors):
        self._entry_points = tuple(
            FakeEntryPoint(
                descriptor.adapter_id,
                f"fake:{descriptor.adapter_id}",
                descriptor,
            )
            for descriptor in descriptors
        )

    def entry_points(self, group):
        assert group == "ai_factory_os.tool_adapters"
        return self._entry_points


class GuardedKnowledgeProvider:
    def __init__(self):
        self.calls = []
        self.capability = CapabilityRegistryEntry(
            capability_id="CAP-DISCOVERED-0001",
            name="Discovered Fixture",
            description="Composition compatibility fixture.",
            owner="AI Factory OS Architecture",
            scope="architecture.production_adapter_discovery",
            status="implemented",
            maturity="M3",
            implementation_status="implemented",
            required_knowledge=(),
            required_capabilities=(),
            tool_dependencies=(),
            adapter_dependencies=(),
            runtime_dependencies=(),
            implementation_references=(),
            validation_evidence=(),
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
        raise AssertionError("Knowledge behavior must not be called")

    def get_document(self, document_id):
        raise AssertionError("Document behavior must not be called")

    def reference_priority(self, scope=None):
        self.calls.append(("reference_priority", scope))
        return ("constitutional",)


def _policy():
    return RuntimeIntegrationPolicy(
        projection_version="1.0.0",
        required_runtime_compatibility=RuntimeCompatibility.COMPATIBLE,
        required_execution_contract=ExecutionContract.CONTROLLED_RUNTIME,
    )


def test_registry_merges_static_and_discovered_descriptors_in_existing_catalog():
    discovered = _descriptor()
    registry = build_discovered_production_adapter_registry(
        source=FakeDiscoverySource((discovered,))
    )

    assert isinstance(registry.project_catalog(), ToolAdapterCatalog)
    assert tuple(
        descriptor.adapter_id for descriptor in registry.snapshot.adapters
    ) == (
        "adapter.codex_automation_bridge",
        "adapter.discovered",
    )
    assert (
        registry.project_catalog().get_adapter("adapter.discovered")
        is discovered
    )


def test_existing_catalog_rejects_duplicate_identity_after_merge():
    duplicate = _descriptor(
        adapter_id="adapter.codex_automation_bridge",
    )

    with pytest.raises(DuplicateAdapterIdentityError):
        build_discovered_production_adapter_registry(
            source=FakeDiscoverySource((duplicate,))
        )


def test_existing_catalog_rejects_ambiguous_capability_after_merge():
    ambiguous = _descriptor(
        capability_id="CAP-TOOLADAPTER-CONTRACT-0001",
    )

    with pytest.raises(AmbiguousCapabilityMappingError):
        build_discovered_production_adapter_registry(
            source=FakeDiscoverySource((ambiguous,))
        )


def test_discovered_registry_remains_composition_compatible_and_non_executable():
    registry = build_discovered_production_adapter_registry(
        source=FakeDiscoverySource((_descriptor(),))
    )
    provider = GuardedKnowledgeProvider()
    catalog = registry.project_catalog()

    composition = build_production_composition(
        knowledge_provider=provider,
        adapter_registry=registry,
        runtime_policy=_policy(),
    )

    assert composition.tool_adapter_catalog is catalog
    assert composition.tool_adapter_selection._candidate_source is catalog
    assert composition.execution_path._catalog is catalog
    assert composition.tool_adapter_contract._lookup is catalog
    assert composition.runtime_allowed is False
    assert composition.execution_allowed is False
    assert provider.calls == []


def test_existing_builder_signatures_and_static_result_are_unchanged():
    assert str(signature(build_production_adapter_registry)) == (
        "() -> 'OperationalAdapterRegistry'"
    )
    assert str(signature(build_production_composition)) == (
        "(*, knowledge_provider: 'KnowledgeProvider', "
        "adapter_registry: 'OperationalAdapterRegistry', "
        "runtime_policy: 'RuntimeIntegrationPolicy') "
        "-> 'NonExecutableComposition'"
    )
    assert tuple(
        descriptor.adapter_id
        for descriptor in build_production_adapter_registry().snapshot.adapters
    ) == ("adapter.codex_automation_bridge",)
