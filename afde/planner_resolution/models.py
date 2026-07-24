"""Immutable contracts for Planner-to-Resolver integration."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass
from enum import Enum
from types import MappingProxyType
from typing import Any, Mapping

from afde.knowledge import KnowledgeGap
from afde.resolver import CapabilityRequirement, CapabilityResolutionResult

from .errors import InvalidPlannerResolutionRequestError


class IntegrationStatus(str, Enum):
    """Bounded projection of the Resolver's governed status."""

    RESOLVED = "resolved"
    UNRESOLVED = "unresolved"
    BLOCKED = "blocked"
    DECISION_REQUIRED = "decision_required"


@dataclass(frozen=True)
class PlannerCapabilityResolutionRequest:
    """Structured Planner context plus an explicit capability requirement."""

    planning_result: Any
    capability_requirement: CapabilityRequirement | None = None
    capability_id: str | None = None
    requested_scope: str | None = None
    minimum_maturity: str | None = None
    require_operational: bool = False
    constraints: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.planning_result is None:
            raise InvalidPlannerResolutionRequestError(
                "planning_result is required"
            )
        if (
            self.capability_requirement is not None
            and not isinstance(
                self.capability_requirement, CapabilityRequirement,
            )
        ):
            raise InvalidPlannerResolutionRequestError(
                "capability_requirement must be a CapabilityRequirement"
            )
        if not isinstance(self.require_operational, bool):
            raise InvalidPlannerResolutionRequestError(
                "require_operational must be a boolean"
            )
        if not isinstance(self.constraints, Mapping):
            raise InvalidPlannerResolutionRequestError(
                "constraints must be a mapping"
            )
        inline_values = (
            self.capability_id,
            self.requested_scope,
            self.minimum_maturity,
        )
        if self.capability_requirement is not None and (
            any(value is not None for value in inline_values)
            or self.require_operational
            or self.constraints
        ):
            raise InvalidPlannerResolutionRequestError(
                "explicit requirement and inline requirement fields "
                "cannot be combined"
            )
        object.__setattr__(
            self, "planning_result", _freeze_planning_result(
                self.planning_result
            ),
        )
        object.__setattr__(
            self, "constraints", _freeze_mapping(self.constraints),
        )


@dataclass(frozen=True)
class PlannerCapabilityResolutionResult:
    """Read-only integration result; it never grants runtime execution."""

    planner_context: Any
    capability_requirement: CapabilityRequirement
    capability_resolution_result: CapabilityResolutionResult
    integration_status: IntegrationStatus
    decision_required: bool
    gaps: tuple[KnowledgeGap, ...]
    ordered_rationale: tuple[str, ...]
    runtime_allowed: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "planner_context", _freeze_planning_result(
                self.planner_context
            ),
        )
        object.__setattr__(self, "gaps", tuple(self.gaps))
        object.__setattr__(
            self, "ordered_rationale", tuple(self.ordered_rationale),
        )
        if self.runtime_allowed:
            raise InvalidPlannerResolutionRequestError(
                "planner resolution cannot allow runtime execution"
            )


def _freeze_planning_result(value: Any) -> Any:
    if is_dataclass(value) and not isinstance(value, type):
        value = asdict(value)
    elif hasattr(value, "to_dict") and callable(value.to_dict):
        value = value.to_dict()
    if not isinstance(value, Mapping):
        raise InvalidPlannerResolutionRequestError(
            "planning_result must be structured as a mapping"
        )
    return _freeze(value)


def _freeze_mapping(value: Mapping[str, Any]) -> Mapping[str, Any]:
    result: dict[str, Any] = {}
    for key, item in value.items():
        if not isinstance(key, str) or not key.strip():
            raise InvalidPlannerResolutionRequestError(
                "constraint keys must be non-empty strings"
            )
        result[key.strip()] = _freeze(item)
    return MappingProxyType(result)


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({
            str(key): _freeze(item) for key, item in value.items()
        })
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    if isinstance(value, set):
        return frozenset(_freeze(item) for item in value)
    return value
