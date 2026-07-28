"""Entry-point metadata discovery for production Tool Adapter descriptors."""
from __future__ import annotations

from importlib import metadata

from afde.operational_adapter_registry import OperationalAdapterRegistry
from afde.production_adapter_registration import (
    build_production_adapter_registry,
)
from afde.tool_catalog import ToolAdapterDescriptor

from .errors import (
    DiscoverySourceError,
    EntryPointLoadError,
    EntryPointTypeError,
)
from .models import (
    ProductionAdapterDiscoverySource,
    ProductionAdapterEntryPoint,
)


ENTRY_POINT_GROUP = "ai_factory_os.tool_adapters"


class ImportlibMetadataDiscoverySource:
    """Standard-library source for installed entry-point metadata."""

    def entry_points(
        self,
        group: str,
    ) -> tuple[ProductionAdapterEntryPoint, ...]:
        """Return entry points registered for one exact group."""

        return tuple(metadata.entry_points(group=group))


def discover_production_adapter_descriptors(
    *,
    source: ProductionAdapterDiscoverySource | None = None,
) -> tuple[ToolAdapterDescriptor, ...]:
    """Load exactly one descriptor value from every discovered entry point."""

    selected_source = (
        ImportlibMetadataDiscoverySource()
        if source is None
        else source
    )
    try:
        entry_points = tuple(selected_source.entry_points(ENTRY_POINT_GROUP))
        metadata_entries = tuple(
            (
                entry_point.name,
                entry_point.value,
                entry_point,
            )
            for entry_point in entry_points
        )
        ordered = tuple(sorted(
            metadata_entries,
            key=lambda item: item[:2],
        ))
    except Exception as exc:
        raise DiscoverySourceError(
            "production adapter discovery source could not be enumerated"
        ) from exc

    descriptors = []
    for entry_point_name, _, entry_point in ordered:
        try:
            discovered = entry_point.load()
        except Exception as exc:
            raise EntryPointLoadError(
                "production adapter entry point failed to load: "
                f"{entry_point_name}"
            ) from exc
        if type(discovered) is not ToolAdapterDescriptor:
            raise EntryPointTypeError(
                "production adapter entry point must return exactly one "
                f"ToolAdapterDescriptor: {entry_point_name}"
            )
        descriptors.append(discovered)
    return tuple(descriptors)


def build_discovered_production_adapter_registry(
    *,
    source: ProductionAdapterDiscoverySource | None = None,
) -> OperationalAdapterRegistry:
    """Merge static and discovered metadata into the existing Registry."""

    static_descriptors = (
        build_production_adapter_registry().snapshot.adapters
    )
    discovered_descriptors = discover_production_adapter_descriptors(
        source=source
    )
    return OperationalAdapterRegistry(
        static_descriptors + discovered_descriptors
    )
