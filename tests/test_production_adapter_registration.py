from dataclasses import FrozenInstanceError

import pytest

import afde
import afde.production_adapter_registration as registration_package
from afde.knowledge import CapabilityContext, CapabilityRegistryEntry
from afde.operational_adapter_registry import OperationalAdapterRegistry
from afde.production_adapter_registration import (
    build_production_adapter_registry,
)
from afde.production_composition import build_production_composition
from afde.runtime_integration import RuntimeIntegrationPolicy
from afde.tool_catalog import (
    AdapterAvailability,
    CostClassification,
    ExecutionContract,
    PrivacyClassification,
    RuntimeCompatibility,
)


CAPABILITY_ID = "CAP-TOOLADAPTER-CONTRACT-0001"
METADATA_REFERENCES = (
    "real_worker_runtime/automation_bridge.py",
    "real_worker_runtime/tool_actions.py",
    "docs/reports/AFDE_3_2_CODEX_AUTOMATION_BRIDGE_REPORT.md",
)


class GuardedKnowledgeProvider:
    def __init__(self):
        self.calls = []
        self.capability = CapabilityRegistryEntry(
            capability_id=CAPABILITY_ID,
            name="Tool Adapter Execution Contract",
            description="Production registration composition fixture.",
            owner="AI Factory OS Architecture",
            scope="architecture.tool_adapter_contract",
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


def test_registers_exactly_one_complete_static_descriptor():
    registry = build_production_adapter_registry()

    assert isinstance(registry, OperationalAdapterRegistry)
    assert len(registry.snapshot.adapters) == 1
    descriptor = registry.snapshot.adapters[0]
    assert descriptor.adapter_id == "adapter.codex_automation_bridge"
    assert descriptor.display_name == "Codex Automation Bridge"
    assert descriptor.version == "1.0.0"
    assert descriptor.supported_capability_ids == (CAPABILITY_ID,)
    assert descriptor.availability is AdapterAvailability.AVAILABLE
    assert (
        descriptor.runtime_compatibility
        is RuntimeCompatibility.COMPATIBLE
    )
    assert (
        descriptor.execution_contract
        is ExecutionContract.CONTROLLED_RUNTIME
    )
    assert (
        descriptor.privacy_classification
        is PrivacyClassification.EXTERNAL
    )
    assert descriptor.cost_classification is CostClassification.NO_COST
    assert descriptor.credentials_required is True
    assert descriptor.description == (
        "Static production registration metadata for the existing "
        "Codex Automation Bridge."
    )
    assert descriptor.metadata_references == METADATA_REFERENCES


def test_each_call_is_independent_with_equal_immutable_snapshot():
    first = build_production_adapter_registry()
    second = build_production_adapter_registry()

    assert first is not second
    assert first.project_catalog() is not second.project_catalog()
    assert first.snapshot == second.snapshot
    assert first.snapshot is first.project_catalog().snapshot
    with pytest.raises(FrozenInstanceError):
        first.snapshot.adapters = ()


def test_registry_preserves_catalog_identity_and_composition_compatibility():
    registry = build_production_adapter_registry()
    provider = GuardedKnowledgeProvider()
    catalog = registry.project_catalog()

    composition = build_production_composition(
        knowledge_provider=provider,
        adapter_registry=registry,
        runtime_policy=_policy(),
    )

    assert registry.project_catalog() is catalog
    assert composition.tool_adapter_catalog is catalog
    assert composition.tool_adapter_selection._candidate_source is catalog
    assert composition.execution_path._catalog is catalog
    assert composition.tool_adapter_contract._lookup is catalog
    assert composition.runtime_allowed is False
    assert composition.execution_allowed is False
    assert provider.calls == []


def test_public_contract_is_additive_and_package_scoped():
    assert registration_package.__all__ == [
        "build_production_adapter_registry",
    ]
    assert not hasattr(afde, "build_production_adapter_registry")
