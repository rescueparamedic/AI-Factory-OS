"""Immutable input and output models for Capability Resolver."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import re
from types import MappingProxyType
from typing import Any, Mapping

from afde.knowledge import (
    CapabilityRegistryEntry,
    DocumentRegistryEntry,
    KnowledgeGap,
    KnowledgeRegistryEntry,
)

from .errors import InvalidCapabilityRequirementError


CAPABILITY_ID_PATTERN = re.compile(
    r"^CAP-[A-Z0-9]+(?:-[A-Z0-9]+)*-[0-9]{4}$"
)
KNOWLEDGE_ID_PATTERN = re.compile(r"^KNW-[A-Z0-9]+-[0-9]{4}$")
MATURITY_LEVELS = ("M0", "M1", "M2", "M3", "M4", "M5", "M6")


class ResolutionStatus(str, Enum):
    """Governed outcomes for one deterministic resolution."""

    RESOLVED = "resolved"
    UNRESOLVED = "unresolved"
    BLOCKED = "blocked"
    DECISION_REQUIRED = "decision_required"


@dataclass(frozen=True)
class CapabilityRequirement:
    """Structured Planner output accepted by the MVP resolver."""

    capability_id: str | None = None
    requested_scope: str | None = None
    minimum_maturity: str | None = None
    require_operational: bool = False
    required_knowledge_ids: tuple[str, ...] = ()
    constraints: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        capability_id = _optional_text(self.capability_id, "capability_id")
        if capability_id is None:
            raise InvalidCapabilityRequirementError(
                "capability_id is required for MVP resolution"
            )
        if not CAPABILITY_ID_PATTERN.fullmatch(capability_id):
            raise InvalidCapabilityRequirementError(
                f"invalid capability_id: {capability_id}"
            )
        requested_scope = _optional_text(
            self.requested_scope, "requested_scope",
        )
        minimum_maturity = _optional_text(
            self.minimum_maturity, "minimum_maturity",
        )
        if (
            minimum_maturity is not None
            and minimum_maturity not in MATURITY_LEVELS
        ):
            raise InvalidCapabilityRequirementError(
                f"invalid minimum_maturity: {minimum_maturity}"
            )
        if not isinstance(self.require_operational, bool):
            raise InvalidCapabilityRequirementError(
                "require_operational must be a boolean"
            )
        required_knowledge_ids = _identifier_tuple(
            self.required_knowledge_ids,
            KNOWLEDGE_ID_PATTERN,
            "required_knowledge_ids",
        )
        if not isinstance(self.constraints, Mapping):
            raise InvalidCapabilityRequirementError(
                "constraints must be a mapping"
            )
        constraints: dict[str, Any] = {}
        for key, value in self.constraints.items():
            if not isinstance(key, str) or not key.strip():
                raise InvalidCapabilityRequirementError(
                    "constraint keys must be non-empty strings"
                )
            constraints[key.strip()] = _freeze(value)

        object.__setattr__(self, "capability_id", capability_id)
        object.__setattr__(self, "requested_scope", requested_scope)
        object.__setattr__(self, "minimum_maturity", minimum_maturity)
        object.__setattr__(
            self, "required_knowledge_ids", required_knowledge_ids,
        )
        object.__setattr__(
            self, "constraints", MappingProxyType(constraints),
        )


@dataclass(frozen=True)
class CapabilityResolutionResult:
    """Read-only explanation of a resolver decision."""

    requirement: CapabilityRequirement
    capability: CapabilityRegistryEntry | None
    resolution_status: ResolutionStatus
    eligible: bool
    matched_scope: str | None
    required_knowledge: tuple[KnowledgeRegistryEntry, ...]
    required_capabilities: tuple[CapabilityRegistryEntry, ...]
    source_documents: tuple[DocumentRegistryEntry, ...]
    reference_priority: tuple[str, ...]
    gaps: tuple[KnowledgeGap, ...]
    rejection_reasons: tuple[str, ...]
    decision_required: bool
    trace: tuple[str, ...]

    def __post_init__(self) -> None:
        for field_name in (
            "required_knowledge",
            "required_capabilities",
            "source_documents",
            "reference_priority",
            "gaps",
            "rejection_reasons",
            "trace",
        ):
            object.__setattr__(self, field_name, tuple(getattr(self, field_name)))


def _optional_text(value: str | None, field_name: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise InvalidCapabilityRequirementError(
            f"{field_name} must be a non-empty string"
        )
    return value.strip()


def _identifier_tuple(
    values: tuple[str, ...],
    pattern: re.Pattern[str],
    field_name: str,
) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)) or not isinstance(values, tuple):
        raise InvalidCapabilityRequirementError(
            f"{field_name} must be a tuple"
        )
    normalized: list[str] = []
    for value in values:
        if not isinstance(value, str) or not pattern.fullmatch(value):
            raise InvalidCapabilityRequirementError(
                f"{field_name} contains an invalid identifier: {value!r}"
            )
        normalized.append(value)
    if len(normalized) != len(set(normalized)):
        raise InvalidCapabilityRequirementError(
            f"{field_name} contains duplicate identifiers"
        )
    return tuple(normalized)


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType(
            {str(key): _freeze(item) for key, item in value.items()}
        )
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    if isinstance(value, set):
        return frozenset(_freeze(item) for item in value)
    return value
