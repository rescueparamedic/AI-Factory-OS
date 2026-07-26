from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from afde.execution_path import ExecutionPathRequest, ExecutionPathService
from afde.knowledge import KnowledgeFoundationProvider
from afde.operational_adapter_registry import OperationalAdapterRegistry
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
    DuplicateAdapterIdentityError,
    ExecutionContract,
    InvalidToolAdapterCatalogError,
    PrivacyClassification,
    RuntimeCompatibility,
    ToolAdapterCatalog,
    ToolAdapterDescriptor,
)
from afde.tool_selection import (
    ToolAdapterSelectionRequest,
    ToolAdapterSelectionService,
    ToolAdapterSelectionStatus,
)


ROOT = Path(__file__).resolve().parents[1]
CAPABILITY_ID = "CAP-KNOW-0001"


def _descriptor(
    adapter_id="adapter.local",
    capability_id=CAPABILITY_ID,
):
    return ToolAdapterDescriptor(
        adapter_id=adapter_id,
        display_name=f"Adapter {adapter_id}",
        version="1.0.0",
        supported_capability_ids=(capability_id,),
        availability=AdapterAvailability.AVAILABLE,
        runtime_compatibility=RuntimeCompatibility.COMPATIBLE,
        execution_contract=ExecutionContract.CONTROLLED_RUNTIME,
        privacy_classification=PrivacyClassification.LOCAL,
        cost_classification=CostClassification.NO_COST,
        credentials_required=False,
        description="Explicit test registration metadata.",
        metadata_references=(
            "tests/test_operational_adapter_registry.py",
        ),
    )


def _resolution():
    return CapabilityResolver(
        KnowledgeFoundationProvider(ROOT)
    ).resolve(CapabilityRequirement(capability_id=CAPABILITY_ID))


def test_empty_registrations_produce_valid_empty_snapshot_and_catalog():
    registry = OperationalAdapterRegistry(())

    assert registry.snapshot.adapters == ()
    assert registry.snapshot.capability_mappings == ()
    assert registry.project_catalog().list_adapters() == ()
    assert registry.project_catalog() is registry.project_catalog()


def test_single_registration_is_snapshotted_and_projected():
    descriptor = _descriptor()
    registry = OperationalAdapterRegistry([descriptor])

    assert registry.snapshot.adapters == (descriptor,)
    assert registry.project_catalog().get_adapter(
        descriptor.adapter_id
    ) is descriptor
    assert isinstance(registry.project_catalog(), ToolAdapterCatalog)


def test_multiple_registrations_are_input_order_independent():
    alpha = _descriptor("adapter.alpha", CAPABILITY_ID)
    zeta = _descriptor("adapter.zeta", "CAP-RESOLVER-0001")

    first = OperationalAdapterRegistry([zeta, alpha])
    second = OperationalAdapterRegistry([alpha, zeta])

    assert first.snapshot == second.snapshot
    assert tuple(
        item.adapter_id for item in first.snapshot.adapters
    ) == ("adapter.alpha", "adapter.zeta")
    assert first.project_catalog().snapshot == (
        second.project_catalog().snapshot
    )


def test_snapshot_is_immutable_and_defensively_captures_input():
    registrations = [_descriptor()]
    registry = OperationalAdapterRegistry(registrations)
    registrations.clear()

    assert len(registry.snapshot.adapters) == 1
    assert isinstance(registry.snapshot.adapters, tuple)
    with pytest.raises(FrozenInstanceError):
        registry.snapshot.adapters = ()


def test_duplicate_adapter_identity_fails_closed():
    descriptor = _descriptor()

    with pytest.raises(
        DuplicateAdapterIdentityError,
        match="duplicate adapter identities",
    ):
        OperationalAdapterRegistry((descriptor, descriptor))


def test_invalid_capability_mapping_fails_closed():
    descriptor = _descriptor()
    object.__setattr__(
        descriptor,
        "supported_capability_ids",
        ("invalid-capability",),
    )

    with pytest.raises(
        InvalidToolAdapterCatalogError,
        match="invalid capability_id",
    ):
        OperationalAdapterRegistry((descriptor,))


@pytest.mark.parametrize("registrations", [None, (object(),)])
def test_invalid_registration_source_fails_closed(registrations):
    with pytest.raises(InvalidToolAdapterCatalogError):
        OperationalAdapterRegistry(registrations)


def test_projected_catalog_preserves_existing_downstream_contracts():
    registry = OperationalAdapterRegistry((_descriptor(),))
    catalog = registry.project_catalog()
    resolution = _resolution()

    selection = ToolAdapterSelectionService(catalog).select(
        ToolAdapterSelectionRequest(resolution)
    )
    assert selection.selection_status is (
        ToolAdapterSelectionStatus.SELECTED
    )

    path = ExecutionPathService(catalog).build(
        ExecutionPathRequest(selection)
    )
    policy = RuntimeIntegrationPolicy(
        projection_version="1.0.0",
        required_runtime_compatibility=RuntimeCompatibility.COMPATIBLE,
        required_execution_contract=ExecutionContract.CONTROLLED_RUNTIME,
    )
    projection = RuntimeIntegrationService(policy).project(
        RuntimeIntegrationRequest(path)
    ).projection
    result = ToolAdapterContractService(catalog).bind(
        ToolAdapterRequest(projection)
    )

    assert result.status is ToolAdapterContractStatus.VALIDATED
    assert result.adapter_id == "adapter.local"
    assert result.capability_id == CAPABILITY_ID
    assert result.runtime_allowed is False
    assert result.execution_allowed is False
