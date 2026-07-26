from dataclasses import FrozenInstanceError, replace

import pytest

import afde
import afde.non_executable_composition as composition_package
from afde.execution_path import (
    ExecutionPathRequest,
    ExecutionPathService,
)
from afde.knowledge import CapabilityContext, CapabilityRegistryEntry
from afde.non_executable_composition import (
    NonExecutableComposition,
    build_non_executable_composition,
)
from afde.planner_resolution import (
    PlannerCapabilityResolutionRequest,
    PlannerResolutionService,
)
from afde.resolver import CapabilityRequirement, CapabilityResolver
from afde.runtime_integration import (
    RuntimeIntegrationPolicy,
    RuntimeIntegrationRequest,
    RuntimeIntegrationService,
)
from afde.tool_adapter_contract import (
    ToolAdapterContractService,
    ToolAdapterRequest,
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


class FakeKnowledgeProvider:
    def __init__(self):
        self.calls = []
        self.capability = CapabilityRegistryEntry(
            capability_id=CAPABILITY_ID,
            name="Knowledge Foundation",
            description="In-memory capability for composition tests.",
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
        assert capability_id == CAPABILITY_ID
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
        adapter_id="adapter.local",
        display_name="Local Adapter",
        version="1.2.3",
        supported_capability_ids=(CAPABILITY_ID,),
        availability=AdapterAvailability.AVAILABLE,
        runtime_compatibility=RuntimeCompatibility.COMPATIBLE,
        execution_contract=ExecutionContract.CONTROLLED_RUNTIME,
        privacy_classification=PrivacyClassification.LOCAL,
        cost_classification=CostClassification.NO_COST,
        credentials_required=False,
        description="In-memory adapter descriptor.",
        metadata_references=("DOC-TCAT-0001",),
    )


def _policy():
    return RuntimeIntegrationPolicy(
        projection_version="1.0.0",
        required_runtime_compatibility=RuntimeCompatibility.COMPATIBLE,
        required_execution_contract=ExecutionContract.CONTROLLED_RUNTIME,
    )


def _composition(provider=None, descriptors=None, policy=None):
    return build_non_executable_composition(
        knowledge_provider=provider or FakeKnowledgeProvider(),
        adapter_descriptors=(
            [_descriptor()] if descriptors is None else descriptors
        ),
        runtime_policy=policy or _policy(),
    )


def test_builder_constructs_exact_existing_services_and_shared_catalog():
    composition = _composition()

    assert isinstance(composition, NonExecutableComposition)
    assert isinstance(composition.capability_resolver, CapabilityResolver)
    assert isinstance(composition.planner_resolution, PlannerResolutionService)
    assert isinstance(composition.tool_adapter_catalog, ToolAdapterCatalog)
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
    catalog = composition.tool_adapter_catalog
    assert composition.tool_adapter_selection._candidate_source is catalog
    assert composition.execution_path._catalog is catalog
    assert composition.tool_adapter_contract._lookup is catalog


def test_composition_is_frozen_non_executable_and_denies_authority():
    composition = _composition()

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
    with pytest.raises(FrozenInstanceError):
        composition.runtime_allowed = True
    with pytest.raises(ValueError, match="cannot allow Runtime"):
        replace(composition, runtime_allowed=True)
    with pytest.raises(ValueError, match="cannot allow execution"):
        replace(composition, execution_allowed=True)


def test_public_exports_are_additive_and_limited_to_two_contracts():
    assert composition_package.__all__ == [
        "NonExecutableComposition",
        "build_non_executable_composition",
    ]
    assert not hasattr(afde, "NonExecutableComposition")
    assert not hasattr(afde, "build_non_executable_composition")


def test_builder_only_constructs_and_does_not_call_provider_behavior():
    provider = FakeKnowledgeProvider()

    _composition(provider=provider)

    assert provider.calls == []


@pytest.mark.parametrize(
    "overrides, error",
    [
        ({"provider": object()}, TypeError),
        ({"descriptors": None}, ValueError),
        ({"descriptors": [object()]}, ValueError),
        ({"policy": object()}, TypeError),
    ],
)
def test_invalid_dependencies_fail_closed(overrides, error):
    values = {
        "provider": FakeKnowledgeProvider(),
        "descriptors": [_descriptor()],
        "policy": _policy(),
    }
    values.update(overrides)

    with pytest.raises(error):
        build_non_executable_composition(
            knowledge_provider=values["provider"],
            adapter_descriptors=values["descriptors"],
            runtime_policy=values["policy"],
        )


def test_existing_public_contracts_form_deterministic_manual_chain():
    provider = FakeKnowledgeProvider()
    composition = _composition(provider=provider)
    planner_request = PlannerCapabilityResolutionRequest(
        planning_result={"plan_id": "PLAN-1", "goal": "Validate composition"},
        capability_requirement=CapabilityRequirement(
            capability_id=CAPABILITY_ID,
            minimum_maturity="M3",
        ),
    )

    def project():
        planner_result = composition.planner_resolution.resolve(
            planner_request
        )
        selection = composition.tool_adapter_selection.select(
            ToolAdapterSelectionRequest(planner_result)
        )
        path = composition.execution_path.build(
            ExecutionPathRequest(selection)
        )
        runtime = composition.runtime_integration.project(
            RuntimeIntegrationRequest(path)
        )
        contract = composition.tool_adapter_contract.bind(
            ToolAdapterRequest(runtime.projection)
        )
        return planner_result, selection, path, runtime, contract

    first = project()
    second = project()

    assert first == second
    _, selection, path, runtime, contract = first
    assert selection.selected_adapter.adapter_id == path.adapter_id
    assert path.path_id == runtime.path_id == contract.path_id
    assert selection.capability_id == contract.capability_id
    assert selection.selected_adapter.adapter_id == contract.adapter_id
    for result in (selection, path, runtime, contract):
        assert result.runtime_allowed is False
        assert result.execution_allowed is False
