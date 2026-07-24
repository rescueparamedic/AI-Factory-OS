from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from afde.knowledge import KnowledgeFoundationProvider
from afde.resolver import CapabilityRequirement, CapabilityResolver
from afde.tool_catalog import (
    AdapterAvailability,
    AdapterNotFoundError,
    AmbiguousCapabilityMappingError,
    CapabilityAdapterMapping,
    CostClassification,
    DuplicateAdapterIdentityError,
    ExecutionContract,
    InvalidToolAdapterCatalogError,
    InvalidToolAdapterDescriptorError,
    PrivacyClassification,
    RuntimeCompatibility,
    ToolAdapterCatalog,
    ToolAdapterCatalogSnapshot,
    ToolAdapterDescriptor,
)
from afde.tool_selection import (
    ToolAdapterCandidate,
    ToolAdapterSelectionRequest,
    ToolAdapterSelectionService,
    ToolAdapterSelectionStatus,
)


ROOT = Path(__file__).resolve().parents[1]
CAPABILITY_ID = "CAP-KNOW-0001"


def _descriptor(
    adapter_id="adapter.local",
    *capability_ids,
    **overrides,
):
    values = {
        "adapter_id": adapter_id,
        "display_name": "Local Test Adapter",
        "version": "1.0.0",
        "supported_capability_ids": capability_ids or (CAPABILITY_ID,),
        "availability": AdapterAvailability.AVAILABLE,
        "runtime_compatibility": RuntimeCompatibility.COMPATIBLE,
        "execution_contract": ExecutionContract.CONTROLLED_RUNTIME,
        "privacy_classification": PrivacyClassification.LOCAL,
        "cost_classification": CostClassification.NO_COST,
        "credentials_required": False,
        "description": "Test-only governed discovery metadata.",
        "metadata_references": ("tests/test_tool_adapter_catalog.py",),
    }
    values.update(overrides)
    return ToolAdapterDescriptor(**values)


def _resolved(capability_id=CAPABILITY_ID):
    return CapabilityResolver(
        KnowledgeFoundationProvider(ROOT)
    ).resolve(CapabilityRequirement(capability_id=capability_id))


def test_descriptor_metadata_is_valid_normalized_and_immutable():
    descriptor = _descriptor(
        " adapter.local ",
        metadata_references=(" reference-a ",),
    )

    assert descriptor.adapter_id == "adapter.local"
    assert descriptor.display_name == "Local Test Adapter"
    assert descriptor.version == "1.0.0"
    assert descriptor.supported_capability_ids == (CAPABILITY_ID,)
    assert descriptor.metadata_references == ("reference-a",)
    assert descriptor.selectable is True
    with pytest.raises(FrozenInstanceError):
        descriptor.version = "2.0.0"


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("adapter_id", " ", "invalid adapter_id"),
        ("version", "v1", "invalid version"),
        (
            "supported_capability_ids",
            ("invalid",),
            "invalid capability",
        ),
        (
            "supported_capability_ids",
            (),
            "non-empty tuple",
        ),
        (
            "supported_capability_ids",
            (CAPABILITY_ID, CAPABILITY_ID),
            "duplicate identifiers",
        ),
        ("availability", "available", "invalid availability"),
        (
            "runtime_compatibility",
            "compatible",
            "invalid runtime_compatibility",
        ),
        (
            "execution_contract",
            "controlled_runtime",
            "invalid execution_contract",
        ),
        (
            "privacy_classification",
            "local",
            "invalid privacy_classification",
        ),
        (
            "cost_classification",
            "no_cost",
            "invalid cost_classification",
        ),
        (
            "credentials_required",
            "no",
            "credentials_required must be a boolean",
        ),
    ],
)
def test_invalid_descriptor_metadata_fails_closed(field, value, message):
    with pytest.raises(InvalidToolAdapterDescriptorError, match=message):
        _descriptor(**{field: value})


def test_catalog_snapshots_input_and_orders_adapters_and_mappings():
    descriptors = [
        _descriptor("adapter.zeta", "CAP-RESOLVER-0001"),
        _descriptor("adapter.alpha", CAPABILITY_ID),
    ]
    catalog = ToolAdapterCatalog(descriptors)
    descriptors.clear()

    assert tuple(
        item.adapter_id for item in catalog.snapshot.adapters
    ) == ("adapter.alpha", "adapter.zeta")
    assert tuple(
        item.capability_id
        for item in catalog.snapshot.capability_mappings
    ) == (CAPABILITY_ID, "CAP-RESOLVER-0001")
    assert catalog.snapshot.trace == (
        "01.descriptors.snapshot:2",
        "02.identities.unique",
        "03.capabilities.mapped:2",
        "04.candidates.selectable:2",
        "05.catalog.ready",
    )
    assert isinstance(catalog.snapshot.adapters, tuple)
    assert isinstance(catalog.snapshot.capability_mappings, tuple)
    with pytest.raises(FrozenInstanceError):
        catalog.snapshot.adapters = ()
    with pytest.raises(
        InvalidToolAdapterCatalogError, match="unique and ordered",
    ):
        ToolAdapterCatalogSnapshot(
            adapters=(
                _descriptor("adapter.zeta", "CAP-RESOLVER-0001"),
                _descriptor("adapter.alpha", CAPABILITY_ID),
            ),
            capability_mappings=(),
            trace=("01.invalid",),
        )


def test_capability_mapping_is_immutable_and_deterministically_ordered():
    mapping = CapabilityAdapterMapping(
        capability_id=CAPABILITY_ID,
        adapter_ids=("adapter.alpha", "adapter.zeta"),
    )

    assert mapping.adapter_ids == ("adapter.alpha", "adapter.zeta")
    with pytest.raises(FrozenInstanceError):
        mapping.adapter_ids = ()
    with pytest.raises(
        InvalidToolAdapterCatalogError, match="deterministic",
    ):
        CapabilityAdapterMapping(
            capability_id=CAPABILITY_ID,
            adapter_ids=("adapter.zeta", "adapter.alpha"),
        )


def test_exact_adapter_and_capability_lookups_are_stable_and_read_only():
    alpha = _descriptor("adapter.alpha")
    catalog = ToolAdapterCatalog([alpha])

    assert catalog.get_adapter("adapter.alpha") is alpha
    assert catalog.get_adapter("adapter.alpha") is alpha
    assert catalog.adapters_for_capability(CAPABILITY_ID) == (alpha,)
    assert catalog.adapters_for_capability(CAPABILITY_ID) == (alpha,)
    assert catalog.adapters_for_capability("CAP-RESOLVER-0001") == ()
    with pytest.raises(AdapterNotFoundError):
        catalog.get_adapter("adapter")
    with pytest.raises(InvalidToolAdapterCatalogError):
        catalog.get_adapter(" adapter.alpha ")
    with pytest.raises(InvalidToolAdapterCatalogError):
        catalog.adapters_for_capability("CAP-KNOW")


def test_catalog_does_not_fuzzy_or_semantically_match():
    catalog = ToolAdapterCatalog([_descriptor("image.generator")])

    with pytest.raises(AdapterNotFoundError):
        catalog.get_adapter("image")
    assert catalog.adapters_for_capability("CAP-KNOW-9999") == ()


def test_duplicate_identity_and_selectable_mapping_ambiguity_fail_closed():
    descriptor = _descriptor()
    with pytest.raises(DuplicateAdapterIdentityError, match="duplicate"):
        ToolAdapterCatalog([descriptor, descriptor])
    with pytest.raises(
        AmbiguousCapabilityMappingError,
        match="adapter.alpha,adapter.zeta",
    ):
        ToolAdapterCatalog([
            _descriptor("adapter.zeta"),
            _descriptor("adapter.alpha"),
        ])


@pytest.mark.parametrize(
    "overrides",
    [
        {"availability": AdapterAvailability.UNAVAILABLE},
        {"runtime_compatibility": RuntimeCompatibility.INCOMPATIBLE},
        {"runtime_compatibility": RuntimeCompatibility.UNVERIFIED},
        {"execution_contract": ExecutionContract.NOT_DECLARED},
    ],
)
def test_non_selectable_metadata_remains_discoverable_but_not_projected(
    overrides,
):
    descriptor = _descriptor(**overrides)
    catalog = ToolAdapterCatalog([descriptor])

    assert catalog.get_adapter(descriptor.adapter_id) is descriptor
    assert catalog.adapters_for_capability(CAPABILITY_ID) == (descriptor,)
    assert catalog.list_candidates() == ()


def test_one_selectable_and_one_unavailable_mapping_is_not_ambiguous():
    available = _descriptor("adapter.available")
    unavailable = _descriptor(
        "adapter.unavailable",
        availability=AdapterAvailability.UNAVAILABLE,
    )
    catalog = ToolAdapterCatalog([unavailable, available])

    assert tuple(
        item.adapter_id
        for item in catalog.adapters_for_capability(CAPABILITY_ID)
    ) == ("adapter.available", "adapter.unavailable")
    assert catalog.list_candidates() == (
        ToolAdapterCandidate("adapter.available", (CAPABILITY_ID,)),
    )


def test_empty_catalog_is_valid_and_deterministic():
    catalog = ToolAdapterCatalog(())

    assert catalog.snapshot.adapters == ()
    assert catalog.snapshot.capability_mappings == ()
    assert catalog.list_candidates() == ()
    assert catalog.adapters_for_capability(CAPABILITY_ID) == ()
    assert catalog.snapshot is catalog.snapshot


def test_malformed_catalog_input_fails_closed():
    with pytest.raises(InvalidToolAdapterCatalogError, match="iterable"):
        ToolAdapterCatalog(None)
    with pytest.raises(InvalidToolAdapterCatalogError, match="malformed"):
        ToolAdapterCatalog([object()])


def test_catalog_candidate_projection_integrates_with_selection():
    catalog = ToolAdapterCatalog([_descriptor()])
    request = ToolAdapterSelectionRequest(_resolved())
    service = ToolAdapterSelectionService(catalog)

    first = service.select(request)
    second = service.select(request)

    assert first == second
    assert first.selection_status is ToolAdapterSelectionStatus.SELECTED
    assert first.selected_adapter == ToolAdapterCandidate(
        "adapter.local", (CAPABILITY_ID,),
    )
    assert first.runtime_allowed is False
    assert first.execution_allowed is False


def test_selection_rejects_unavailable_or_unsupported_catalog_entries():
    unavailable = ToolAdapterCatalog([
        _descriptor(availability=AdapterAvailability.UNAVAILABLE),
    ])
    unsupported = ToolAdapterCatalog([
        _descriptor("adapter.other", "CAP-RESOLVER-0001"),
    ])
    request = ToolAdapterSelectionRequest(_resolved())

    for catalog in (unavailable, unsupported):
        result = ToolAdapterSelectionService(catalog).select(request)
        assert result.selection_status is (
            ToolAdapterSelectionStatus.NO_SELECTION
        )
        assert result.selected_adapter is None
        assert result.runtime_allowed is False
        assert result.execution_allowed is False
