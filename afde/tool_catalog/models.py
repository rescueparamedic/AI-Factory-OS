"""Immutable Tool Adapter Catalog metadata and projections."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import re

from afde.tool_selection import (
    InvalidAdapterCandidateError,
    ToolAdapterCandidate,
)

from .errors import (
    InvalidToolAdapterCatalogError,
    InvalidToolAdapterDescriptorError,
)


CAPABILITY_ID_PATTERN = re.compile(
    r"^CAP-[A-Z0-9]+(?:-[A-Z0-9]+)*-[0-9]{4}$"
)
VERSION_PATTERN = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")


class AdapterAvailability(str, Enum):
    """Whether an adapter may be projected for selection."""

    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"


class RuntimeCompatibility(str, Enum):
    """Whether compatibility with the governed Runtime is established."""

    COMPATIBLE = "compatible"
    INCOMPATIBLE = "incompatible"
    UNVERIFIED = "unverified"


class ExecutionContract(str, Enum):
    """Declared execution boundary; it grants no execution authority."""

    CONTROLLED_RUNTIME = "controlled_runtime"
    NOT_DECLARED = "not_declared"


class PrivacyClassification(str, Enum):
    """Small discovery classification for expected data locality."""

    LOCAL = "local"
    EXTERNAL = "external"


class CostClassification(str, Enum):
    """Small discovery classification for expected adapter cost."""

    NO_COST = "no_cost"
    VARIABLE = "variable"


@dataclass(frozen=True)
class ToolAdapterDescriptor:
    """Governed discovery metadata for one adapter identity."""

    adapter_id: str
    display_name: str
    version: str
    supported_capability_ids: tuple[str, ...]
    availability: AdapterAvailability
    runtime_compatibility: RuntimeCompatibility
    execution_contract: ExecutionContract
    privacy_classification: PrivacyClassification
    cost_classification: CostClassification
    credentials_required: bool
    description: str
    metadata_references: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        try:
            candidate = ToolAdapterCandidate(
                adapter_id=self.adapter_id,
                capability_ids=self.supported_capability_ids,
            )
        except InvalidAdapterCandidateError as exc:
            raise InvalidToolAdapterDescriptorError(str(exc)) from exc
        display_name = _text(self.display_name, "display_name")
        description = _text(self.description, "description")
        if (
            not isinstance(self.version, str)
            or not VERSION_PATTERN.fullmatch(self.version)
        ):
            raise InvalidToolAdapterDescriptorError(
                f"invalid version: {self.version!r}"
            )
        _enum(self.availability, AdapterAvailability, "availability")
        _enum(
            self.runtime_compatibility,
            RuntimeCompatibility,
            "runtime_compatibility",
        )
        _enum(
            self.execution_contract,
            ExecutionContract,
            "execution_contract",
        )
        _enum(
            self.privacy_classification,
            PrivacyClassification,
            "privacy_classification",
        )
        _enum(
            self.cost_classification,
            CostClassification,
            "cost_classification",
        )
        if not isinstance(self.credentials_required, bool):
            raise InvalidToolAdapterDescriptorError(
                "credentials_required must be a boolean"
            )
        references = _references(self.metadata_references)
        object.__setattr__(self, "adapter_id", candidate.adapter_id)
        object.__setattr__(
            self,
            "supported_capability_ids",
            candidate.capability_ids,
        )
        object.__setattr__(self, "display_name", display_name)
        object.__setattr__(self, "description", description)
        object.__setattr__(self, "metadata_references", references)

    @property
    def selectable(self) -> bool:
        """Return the fail-closed projection eligibility state."""

        return (
            self.availability is AdapterAvailability.AVAILABLE
            and self.runtime_compatibility
            is RuntimeCompatibility.COMPATIBLE
            and self.execution_contract
            is ExecutionContract.CONTROLLED_RUNTIME
        )

    def to_candidate(self) -> ToolAdapterCandidate:
        """Project only identity and exact mappings for Tool Selection."""

        return ToolAdapterCandidate(
            adapter_id=self.adapter_id,
            capability_ids=self.supported_capability_ids,
        )


@dataclass(frozen=True)
class CapabilityAdapterMapping:
    """Immutable exact Capability-to-adapter discovery mapping."""

    capability_id: str
    adapter_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if (
            not isinstance(self.capability_id, str)
            or not CAPABILITY_ID_PATTERN.fullmatch(self.capability_id)
        ):
            raise InvalidToolAdapterCatalogError(
                f"invalid capability_id: {self.capability_id!r}"
            )
        if (
            isinstance(self.adapter_ids, (str, bytes))
            or not isinstance(self.adapter_ids, tuple)
            or not self.adapter_ids
            or any(
                not isinstance(item, str)
                or not item
                or item != item.strip()
                for item in self.adapter_ids
            )
        ):
            raise InvalidToolAdapterCatalogError(
                "adapter_ids must be a non-empty tuple of identities"
            )
        if len(self.adapter_ids) != len(set(self.adapter_ids)):
            raise InvalidToolAdapterCatalogError(
                "adapter_ids contains duplicate identities"
            )
        if self.adapter_ids != tuple(sorted(self.adapter_ids)):
            raise InvalidToolAdapterCatalogError(
                "adapter_ids must use deterministic identity ordering"
            )
        object.__setattr__(self, "adapter_ids", tuple(self.adapter_ids))


@dataclass(frozen=True)
class ToolAdapterCatalogSnapshot:
    """Read-only deterministic projection of the complete Catalog."""

    adapters: tuple[ToolAdapterDescriptor, ...]
    capability_mappings: tuple[CapabilityAdapterMapping, ...]
    trace: tuple[str, ...]

    def __post_init__(self) -> None:
        for field_name in ("adapters", "capability_mappings", "trace"):
            object.__setattr__(
                self, field_name, tuple(getattr(self, field_name)),
            )
        if any(
            not isinstance(item, ToolAdapterDescriptor)
            for item in self.adapters
        ):
            raise InvalidToolAdapterCatalogError(
                "snapshot contains an invalid adapter descriptor"
            )
        if any(
            not isinstance(item, CapabilityAdapterMapping)
            for item in self.capability_mappings
        ):
            raise InvalidToolAdapterCatalogError(
                "snapshot contains an invalid capability mapping"
            )
        identities = tuple(item.adapter_id for item in self.adapters)
        capability_ids = tuple(
            item.capability_id for item in self.capability_mappings
        )
        if (
            len(identities) != len(set(identities))
            or identities != tuple(sorted(identities))
        ):
            raise InvalidToolAdapterCatalogError(
                "snapshot adapter identities must be unique and ordered"
            )
        if (
            len(capability_ids) != len(set(capability_ids))
            or capability_ids != tuple(sorted(capability_ids))
        ):
            raise InvalidToolAdapterCatalogError(
                "snapshot capability mappings must be unique and ordered"
            )
        expected: dict[str, list[str]] = {}
        for adapter in self.adapters:
            for capability_id in adapter.supported_capability_ids:
                expected.setdefault(capability_id, []).append(
                    adapter.adapter_id
                )
        expected_mappings = tuple(
            (
                capability_id,
                tuple(sorted(adapter_ids)),
            )
            for capability_id, adapter_ids in sorted(expected.items())
        )
        actual_mappings = tuple(
            (item.capability_id, item.adapter_ids)
            for item in self.capability_mappings
        )
        if actual_mappings != expected_mappings:
            raise InvalidToolAdapterCatalogError(
                "snapshot capability mappings do not match descriptors"
            )
        if any(
            not isinstance(item, str) or not item
            for item in self.trace
        ):
            raise InvalidToolAdapterCatalogError(
                "snapshot trace must contain non-empty strings"
            )


def _text(value: str, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise InvalidToolAdapterDescriptorError(
            f"{field_name} must be a non-empty string"
        )
    return value.strip()


def _enum(value: object, enum_type: type[Enum], field_name: str) -> None:
    if not isinstance(value, enum_type):
        raise InvalidToolAdapterDescriptorError(
            f"invalid {field_name}: {value!r}"
        )


def _references(values: tuple[str, ...]) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)) or not isinstance(values, tuple):
        raise InvalidToolAdapterDescriptorError(
            "metadata_references must be a tuple"
        )
    normalized = tuple(
        _text(value, "metadata reference") for value in values
    )
    if len(normalized) != len(set(normalized)):
        raise InvalidToolAdapterDescriptorError(
            "metadata_references contains duplicate values"
        )
    return normalized
