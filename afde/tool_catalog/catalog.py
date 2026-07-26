"""Deterministic in-memory Tool Adapter Catalog."""
from __future__ import annotations

from collections.abc import Iterable
from types import MappingProxyType

from afde.tool_selection import ToolAdapterCandidate

from .errors import (
    AdapterNotFoundError,
    AmbiguousCapabilityMappingError,
    DuplicateAdapterIdentityError,
    InvalidToolAdapterCatalogError,
)
from .models import (
    CAPABILITY_ID_PATTERN,
    CapabilityAdapterMapping,
    ToolAdapterCatalogSnapshot,
    ToolAdapterDescriptor,
)


class ToolAdapterCatalog:
    """Single read-only source of adapter discovery metadata."""

    def __init__(
        self, descriptors: Iterable[ToolAdapterDescriptor],
    ) -> None:
        try:
            snapshot = tuple(descriptors)
        except Exception as exc:
            raise InvalidToolAdapterCatalogError(
                "descriptors must be an iterable"
            ) from exc
        if any(
            not isinstance(item, ToolAdapterDescriptor)
            for item in snapshot
        ):
            raise InvalidToolAdapterCatalogError(
                "Catalog contains malformed adapter metadata"
            )
        ordered = tuple(sorted(
            snapshot, key=lambda item: item.adapter_id,
        ))
        identities = tuple(item.adapter_id for item in ordered)
        if len(identities) != len(set(identities)):
            raise DuplicateAdapterIdentityError(
                "Catalog contains duplicate adapter identities"
            )

        mappings = self._mappings(ordered)
        candidates = tuple(
            item.to_candidate() for item in ordered if item.selectable
        )
        self._reject_ambiguous_candidates(candidates)
        by_adapter_id = {
            item.adapter_id: item for item in ordered
        }
        by_capability_id = {
            mapping.capability_id: tuple(
                by_adapter_id[adapter_id]
                for adapter_id in mapping.adapter_ids
            )
            for mapping in mappings
        }
        self._by_adapter_id = MappingProxyType(by_adapter_id)
        self._by_capability_id = MappingProxyType(by_capability_id)
        self._candidates = candidates
        self._snapshot = ToolAdapterCatalogSnapshot(
            adapters=ordered,
            capability_mappings=mappings,
            trace=(
                f"01.descriptors.snapshot:{len(ordered)}",
                "02.identities.unique",
                f"03.capabilities.mapped:{len(mappings)}",
                f"04.candidates.selectable:{len(candidates)}",
                "05.catalog.ready",
            ),
        )

    @property
    def snapshot(self) -> ToolAdapterCatalogSnapshot:
        """Return the immutable Catalog projection."""

        return self._snapshot

    def get_adapter(self, adapter_id: str) -> ToolAdapterDescriptor:
        """Return one exact adapter identity."""

        identity = self._adapter_query(adapter_id)
        try:
            return self._by_adapter_id[identity]
        except KeyError as exc:
            raise AdapterNotFoundError(
                f"adapter is not cataloged: {identity}"
            ) from exc

    def adapters_for_capability(
        self, capability_id: str,
    ) -> tuple[ToolAdapterDescriptor, ...]:
        """Return every descriptor with one exact Capability ID mapping."""

        identifier = self._capability_query(capability_id)
        return self._by_capability_id.get(identifier, ())

    def list_candidates(self) -> tuple[ToolAdapterCandidate, ...]:
        """Project selectable descriptors for AdapterCandidateSource."""

        return self._candidates

    def list_adapters(self) -> tuple[ToolAdapterDescriptor, ...]:
        """Return the immutable deterministic descriptor snapshot."""

        return self._snapshot.adapters

    @staticmethod
    def _mappings(
        descriptors: tuple[ToolAdapterDescriptor, ...],
    ) -> tuple[CapabilityAdapterMapping, ...]:
        mapped: dict[str, list[str]] = {}
        for descriptor in descriptors:
            for capability_id in descriptor.supported_capability_ids:
                mapped.setdefault(capability_id, []).append(
                    descriptor.adapter_id
                )
        return tuple(
            CapabilityAdapterMapping(
                capability_id=capability_id,
                adapter_ids=tuple(sorted(mapped[capability_id])),
            )
            for capability_id in sorted(mapped)
        )

    @staticmethod
    def _reject_ambiguous_candidates(
        candidates: tuple[ToolAdapterCandidate, ...],
    ) -> None:
        owners: dict[str, list[str]] = {}
        for candidate in candidates:
            for capability_id in candidate.capability_ids:
                owners.setdefault(capability_id, []).append(
                    candidate.adapter_id
                )
        ambiguous = tuple(
            (
                capability_id,
                tuple(sorted(adapter_ids)),
            )
            for capability_id, adapter_ids in sorted(owners.items())
            if len(adapter_ids) > 1
        )
        if ambiguous:
            capability_id, adapter_ids = ambiguous[0]
            raise AmbiguousCapabilityMappingError(
                "multiple selectable adapters map exact capability "
                f"{capability_id}: {','.join(adapter_ids)}"
            )

    @staticmethod
    def _adapter_query(adapter_id: str) -> str:
        if (
            not isinstance(adapter_id, str)
            or not adapter_id
            or adapter_id != adapter_id.strip()
        ):
            raise InvalidToolAdapterCatalogError(
                "adapter_id query must be an exact non-empty identity"
            )
        return adapter_id

    @staticmethod
    def _capability_query(capability_id: str) -> str:
        if (
            not isinstance(capability_id, str)
            or not CAPABILITY_ID_PATTERN.fullmatch(capability_id)
        ):
            raise InvalidToolAdapterCatalogError(
                f"invalid capability_id query: {capability_id!r}"
            )
        return capability_id
