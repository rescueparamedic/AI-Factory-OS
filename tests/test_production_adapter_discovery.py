from dataclasses import dataclass

import pytest

import afde
import afde.production_adapter_discovery as discovery_package
from afde.production_adapter_discovery import (
    ENTRY_POINT_GROUP,
    DiscoverySourceError,
    EntryPointLoadError,
    EntryPointTypeError,
    ImportlibMetadataDiscoverySource,
    discover_production_adapter_descriptors,
)
from afde.tool_catalog import (
    AdapterAvailability,
    CostClassification,
    ExecutionContract,
    PrivacyClassification,
    RuntimeCompatibility,
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
        description="Fake entry-point descriptor metadata.",
        metadata_references=("fake-distribution",),
    )


@dataclass(frozen=True)
class FakeEntryPoint:
    name: str
    value: str
    result: object = None
    failure: Exception | None = None

    def load(self):
        if self.failure is not None:
            raise self.failure
        return self.result


class FakeDiscoverySource:
    def __init__(self, entry_points=(), failure=None):
        self._entry_points = tuple(entry_points)
        self._failure = failure
        self.groups = []

    def entry_points(self, group):
        self.groups.append(group)
        if self._failure is not None:
            raise self._failure
        return self._entry_points


def test_fake_source_is_injected_and_entry_points_are_deterministic():
    alpha = _descriptor("adapter.alpha", "CAP-ALPHA-0001")
    zeta = _descriptor("adapter.zeta", "CAP-ZETA-0001")
    source = FakeDiscoverySource((
        FakeEntryPoint("zeta", "package:zeta", zeta),
        FakeEntryPoint("alpha", "package:alpha", alpha),
    ))

    result = discover_production_adapter_descriptors(source=source)

    assert source.groups == [ENTRY_POINT_GROUP]
    assert result == (alpha, zeta)


def test_empty_fake_source_requires_no_installed_package():
    source = FakeDiscoverySource()

    assert discover_production_adapter_descriptors(source=source) == ()
    assert source.groups == ["ai_factory_os.tool_adapters"]


def test_standard_library_source_queries_only_the_exact_group(monkeypatch):
    descriptor = _descriptor()
    entry_point = FakeEntryPoint(
        "discovered",
        "package:descriptor",
        descriptor,
    )
    calls = []

    def fake_entry_points(**kwargs):
        calls.append(kwargs)
        return (entry_point,)

    monkeypatch.setattr(
        "afde.production_adapter_discovery.discovery.metadata.entry_points",
        fake_entry_points,
    )

    source = ImportlibMetadataDiscoverySource()
    assert source.entry_points(ENTRY_POINT_GROUP) == (entry_point,)
    assert calls == [{"group": ENTRY_POINT_GROUP}]


def test_source_enumeration_failure_is_typed_and_fail_closed():
    source = FakeDiscoverySource(failure=RuntimeError("broken metadata"))

    with pytest.raises(DiscoverySourceError) as failure:
        discover_production_adapter_descriptors(source=source)

    assert isinstance(failure.value.__cause__, RuntimeError)


def test_entry_point_load_failure_is_typed_and_fail_closed():
    source = FakeDiscoverySource((
        FakeEntryPoint(
            "broken",
            "package:descriptor",
            failure=ImportError("cannot import descriptor"),
        ),
    ))

    with pytest.raises(EntryPointLoadError, match="broken") as failure:
        discover_production_adapter_descriptors(source=source)

    assert isinstance(failure.value.__cause__, ImportError)


@pytest.mark.parametrize("invalid", [None, object(), (_descriptor(),)])
def test_entry_point_must_return_one_descriptor(invalid):
    source = FakeDiscoverySource((
        FakeEntryPoint("invalid", "package:value", invalid),
    ))

    with pytest.raises(EntryPointTypeError, match="exactly one"):
        discover_production_adapter_descriptors(source=source)


def test_public_contract_is_additive_and_package_scoped():
    assert discovery_package.__all__ == [
        "DiscoverySourceError",
        "ENTRY_POINT_GROUP",
        "EntryPointLoadError",
        "EntryPointTypeError",
        "ImportlibMetadataDiscoverySource",
        "ProductionAdapterDiscoveryError",
        "ProductionAdapterDiscoverySource",
        "ProductionAdapterEntryPoint",
        "build_discovered_production_adapter_registry",
        "discover_production_adapter_descriptors",
    ]
    assert not hasattr(afde, "discover_production_adapter_descriptors")
    assert not hasattr(
        afde,
        "build_discovered_production_adapter_registry",
    )
