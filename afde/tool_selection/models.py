"""Immutable contracts for deterministic Tool Adapter selection."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import re

from afde.planner_resolution import PlannerCapabilityResolutionResult
from afde.resolver import CapabilityResolutionResult, ResolutionStatus

from .errors import (
    InvalidAdapterCandidateError,
    InvalidToolAdapterSelectionRequestError,
)


CAPABILITY_ID_PATTERN = re.compile(r"^CAP-[A-Z0-9]+-[0-9]{4}$")


class ToolAdapterSelectionStatus(str, Enum):
    """Governed outcomes for one selection decision."""

    SELECTED = "selected"
    NO_SELECTION = "no_selection"
    BLOCKED = "blocked"


@dataclass(frozen=True)
class ToolAdapterCandidate:
    """Read-only projection of adapter identity and supported capabilities."""

    adapter_id: str
    capability_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if (
            not isinstance(self.adapter_id, str)
            or not self.adapter_id.strip()
        ):
            raise InvalidAdapterCandidateError(
                f"invalid adapter_id: {self.adapter_id!r}"
            )
        if (
            isinstance(self.capability_ids, (str, bytes))
            or not isinstance(self.capability_ids, tuple)
            or not self.capability_ids
        ):
            raise InvalidAdapterCandidateError(
                "capability_ids must be a non-empty tuple"
            )
        if any(
            not isinstance(item, str)
            or not CAPABILITY_ID_PATTERN.fullmatch(item)
            for item in self.capability_ids
        ):
            raise InvalidAdapterCandidateError(
                "capability_ids contains an invalid capability identifier"
            )
        if len(self.capability_ids) != len(set(self.capability_ids)):
            raise InvalidAdapterCandidateError(
                "capability_ids contains duplicate identifiers"
            )
        object.__setattr__(
            self, "capability_ids", tuple(self.capability_ids),
        )
        object.__setattr__(self, "adapter_id", self.adapter_id.strip())


@dataclass(frozen=True)
class ToolAdapterSelectionRequest:
    """One immutable Resolver or Planner Resolution selection input."""

    resolution_result: (
        CapabilityResolutionResult | PlannerCapabilityResolutionResult
    )

    def __post_init__(self) -> None:
        if not isinstance(
            self.resolution_result,
            (CapabilityResolutionResult, PlannerCapabilityResolutionResult),
        ):
            raise InvalidToolAdapterSelectionRequestError(
                "resolution_result must be a CapabilityResolutionResult "
                "or PlannerCapabilityResolutionResult"
            )


@dataclass(frozen=True)
class ToolAdapterSelectionResult:
    """Read-only selection result that never grants execution."""

    selection_status: ToolAdapterSelectionStatus
    capability_id: str
    selected_adapter: ToolAdapterCandidate | None
    resolver_status: ResolutionStatus
    eligible: bool
    decision_required: bool
    gaps: tuple[object, ...]
    rejection_reasons: tuple[str, ...]
    source_documents: tuple[object, ...]
    reference_priority: tuple[str, ...]
    ordered_rationale: tuple[str, ...]
    resolver_trace: tuple[str, ...]
    selection_rationale: tuple[str, ...]
    selection_trace: tuple[str, ...]
    runtime_allowed: bool = False
    execution_allowed: bool = False

    def __post_init__(self) -> None:
        if not isinstance(
            self.selection_status, ToolAdapterSelectionStatus,
        ):
            raise InvalidToolAdapterSelectionRequestError(
                "selection_status is invalid"
            )
        if (
            not isinstance(self.capability_id, str)
            or not CAPABILITY_ID_PATTERN.fullmatch(self.capability_id)
        ):
            raise InvalidToolAdapterSelectionRequestError(
                "capability_id is invalid"
            )
        if not isinstance(self.resolver_status, ResolutionStatus):
            raise InvalidToolAdapterSelectionRequestError(
                "resolver_status is invalid"
            )
        if not isinstance(self.eligible, bool):
            raise InvalidToolAdapterSelectionRequestError(
                "eligible must be a boolean"
            )
        if not isinstance(self.decision_required, bool):
            raise InvalidToolAdapterSelectionRequestError(
                "decision_required must be a boolean"
            )
        selected = (
            self.selection_status is ToolAdapterSelectionStatus.SELECTED
        )
        if selected != isinstance(
            self.selected_adapter, ToolAdapterCandidate,
        ):
            raise InvalidToolAdapterSelectionRequestError(
                "selected_adapter is inconsistent with selection_status"
            )
        for field_name in (
            "gaps",
            "rejection_reasons",
            "source_documents",
            "reference_priority",
            "ordered_rationale",
            "resolver_trace",
            "selection_rationale",
            "selection_trace",
        ):
            object.__setattr__(
                self, field_name, tuple(getattr(self, field_name)),
            )
        if not isinstance(self.runtime_allowed, bool):
            raise InvalidToolAdapterSelectionRequestError(
                "runtime_allowed must be a boolean"
            )
        if self.runtime_allowed:
            raise InvalidToolAdapterSelectionRequestError(
                "Tool Adapter selection cannot allow Runtime"
            )
        if not isinstance(self.execution_allowed, bool):
            raise InvalidToolAdapterSelectionRequestError(
                "execution_allowed must be a boolean"
            )
        if self.execution_allowed:
            raise InvalidToolAdapterSelectionRequestError(
                "Tool Adapter selection cannot allow execution"
            )
