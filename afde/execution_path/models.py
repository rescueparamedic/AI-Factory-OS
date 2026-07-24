"""Immutable contracts for a non-executable Execution Path."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import re

from afde.resolver import ResolutionStatus
from afde.tool_catalog import (
    AdapterAvailability,
    CostClassification,
    ExecutionContract,
    PrivacyClassification,
    RuntimeCompatibility,
)
from afde.tool_selection import (
    ToolAdapterCandidate,
    ToolAdapterSelectionResult,
)

from .errors import (
    InvalidExecutionPathMetadataError,
    InvalidExecutionPathRequestError,
)


CAPABILITY_ID_PATTERN = re.compile(r"^CAP-[A-Z0-9]+-[0-9]{4}$")
PATH_ID_PATTERN = re.compile(r"^EXECPATH-[A-F0-9]{16}$")
VERSION_PATTERN = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")


class ExecutionPathStatus(str, Enum):
    """Governed structural outcomes; none grant execution authority."""

    CONSTRUCTED = "constructed"
    PREREQUISITES_REQUIRED = "prerequisites_required"
    BLOCKED = "blocked"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True)
class ExecutionPathRequest:
    """One immutable Tool Selection result accepted for path construction."""

    selection_result: ToolAdapterSelectionResult

    def __post_init__(self) -> None:
        if not isinstance(
            self.selection_result, ToolAdapterSelectionResult,
        ):
            raise InvalidExecutionPathRequestError(
                "selection_result must be a ToolAdapterSelectionResult"
            )


@dataclass(frozen=True)
class RuntimeHandoffProjection:
    """Read-only structural handoff metadata; never executable authority."""

    sequence: int
    adapter_id: str
    capability_id: str
    adapter_version: str
    availability: AdapterAvailability
    runtime_compatibility: RuntimeCompatibility
    execution_contract: ExecutionContract
    privacy_classification: PrivacyClassification
    cost_classification: CostClassification
    credentials_required: bool
    metadata_references: tuple[str, ...]
    handoff_ready: bool
    runtime_allowed: bool = False
    execution_allowed: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.sequence, int) or self.sequence < 1:
            raise InvalidExecutionPathMetadataError(
                "sequence must be a positive integer"
            )
        try:
            candidate = ToolAdapterCandidate(
                adapter_id=self.adapter_id,
                capability_ids=(self.capability_id,),
            )
        except Exception as exc:
            raise InvalidExecutionPathMetadataError(
                "handoff adapter or Capability identity is invalid"
            ) from exc
        if (
            not isinstance(self.adapter_version, str)
            or not VERSION_PATTERN.fullmatch(self.adapter_version)
        ):
            raise InvalidExecutionPathMetadataError(
                f"invalid adapter_version: {self.adapter_version!r}"
            )
        for field_name, value, enum_type in (
            ("availability", self.availability, AdapterAvailability),
            (
                "runtime_compatibility",
                self.runtime_compatibility,
                RuntimeCompatibility,
            ),
            (
                "execution_contract",
                self.execution_contract,
                ExecutionContract,
            ),
            (
                "privacy_classification",
                self.privacy_classification,
                PrivacyClassification,
            ),
            (
                "cost_classification",
                self.cost_classification,
                CostClassification,
            ),
        ):
            if not isinstance(value, enum_type):
                raise InvalidExecutionPathMetadataError(
                    f"invalid {field_name}: {value!r}"
                )
        if not isinstance(self.credentials_required, bool):
            raise InvalidExecutionPathMetadataError(
                "credentials_required must be a boolean"
            )
        references = _strings(
            self.metadata_references, "metadata_references",
        )
        expected_ready = (
            self.availability is AdapterAvailability.AVAILABLE
            and self.runtime_compatibility
            is RuntimeCompatibility.COMPATIBLE
            and self.execution_contract
            is ExecutionContract.CONTROLLED_RUNTIME
            and not self.credentials_required
        )
        if not isinstance(self.handoff_ready, bool):
            raise InvalidExecutionPathMetadataError(
                "handoff_ready must be a boolean"
            )
        if self.handoff_ready != expected_ready:
            raise InvalidExecutionPathMetadataError(
                "handoff_ready conflicts with Catalog metadata"
            )
        _prohibit_authority(
            self.runtime_allowed, self.execution_allowed,
        )
        object.__setattr__(self, "adapter_id", candidate.adapter_id)
        object.__setattr__(
            self, "capability_id", candidate.capability_ids[0],
        )
        object.__setattr__(self, "metadata_references", references)


@dataclass(frozen=True)
class ExecutionPathResult:
    """Immutable path construction outcome with preserved upstream context."""

    status: ExecutionPathStatus
    path_id: str | None
    path_constructed: bool
    runtime_handoff_ready: bool
    adapter_id: str | None
    capability_id: str
    steps: tuple[RuntimeHandoffProjection, ...]
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
    blocked_reasons: tuple[str, ...]
    trace: tuple[str, ...]
    runtime_allowed: bool = False
    execution_allowed: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.status, ExecutionPathStatus):
            raise InvalidExecutionPathRequestError(
                "status is invalid"
            )
        if (
            not isinstance(self.capability_id, str)
            or not CAPABILITY_ID_PATTERN.fullmatch(self.capability_id)
        ):
            raise InvalidExecutionPathRequestError(
                "capability_id is invalid"
            )
        if not isinstance(self.resolver_status, ResolutionStatus):
            raise InvalidExecutionPathRequestError(
                "resolver_status is invalid"
            )
        for field_name in (
            "path_constructed",
            "runtime_handoff_ready",
            "eligible",
            "decision_required",
        ):
            if not isinstance(getattr(self, field_name), bool):
                raise InvalidExecutionPathRequestError(
                    f"{field_name} must be a boolean"
                )
        for field_name in (
            "steps",
            "gaps",
            "source_documents",
        ):
            object.__setattr__(
                self, field_name, tuple(getattr(self, field_name)),
            )
        for field_name in (
            "rejection_reasons",
            "reference_priority",
            "ordered_rationale",
            "resolver_trace",
            "selection_rationale",
            "selection_trace",
            "blocked_reasons",
            "trace",
        ):
            object.__setattr__(
                self,
                field_name,
                _snapshot_strings(getattr(self, field_name), field_name),
            )
        if any(
            not isinstance(step, RuntimeHandoffProjection)
            for step in self.steps
        ):
            raise InvalidExecutionPathRequestError(
                "steps contains an invalid handoff projection"
            )
        if tuple(step.sequence for step in self.steps) != tuple(
            range(1, len(self.steps) + 1)
        ):
            raise InvalidExecutionPathRequestError(
                "steps must use stable consecutive ordering"
            )
        constructed_status = self.status in (
            ExecutionPathStatus.CONSTRUCTED,
            ExecutionPathStatus.PREREQUISITES_REQUIRED,
        )
        if (
            self.path_constructed != constructed_status
            or self.path_constructed != bool(self.steps)
            or self.path_constructed
            != (
                isinstance(self.path_id, str)
                and bool(PATH_ID_PATTERN.fullmatch(self.path_id))
            )
        ):
            raise InvalidExecutionPathRequestError(
                "path construction fields are inconsistent"
            )
        if self.path_constructed:
            first = self.steps[0]
            if (
                self.adapter_id != first.adapter_id
                or self.capability_id != first.capability_id
                or self.resolver_status is not ResolutionStatus.RESOLVED
                or not self.eligible
                or self.decision_required
            ):
                raise InvalidExecutionPathRequestError(
                    "constructed path conflicts with upstream state"
                )
        elif self.adapter_id is not None:
            raise InvalidExecutionPathRequestError(
                "blocked path cannot identify a handoff adapter"
            )
        expected_handoff = (
            self.status is ExecutionPathStatus.CONSTRUCTED
            and len(self.steps) == 1
            and self.steps[0].handoff_ready
        )
        if self.runtime_handoff_ready != expected_handoff:
            raise InvalidExecutionPathRequestError(
                "runtime_handoff_ready is inconsistent"
            )
        if (
            self.status is ExecutionPathStatus.CONSTRUCTED
            and self.blocked_reasons
        ):
            raise InvalidExecutionPathRequestError(
                "constructed path cannot contain blocked reasons"
            )
        if (
            self.status is not ExecutionPathStatus.CONSTRUCTED
            and not self.blocked_reasons
        ):
            raise InvalidExecutionPathRequestError(
                "non-ready path requires blocked reasons"
            )
        _prohibit_authority(
            self.runtime_allowed, self.execution_allowed,
        )


def _strings(values: tuple[str, ...], field_name: str) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)) or not isinstance(values, tuple):
        raise InvalidExecutionPathMetadataError(
            f"{field_name} must be a tuple"
        )
    if any(
        not isinstance(item, str) or not item.strip()
        for item in values
    ):
        raise InvalidExecutionPathMetadataError(
            f"{field_name} contains an invalid value"
        )
    normalized = tuple(item.strip() for item in values)
    if len(normalized) != len(set(normalized)):
        raise InvalidExecutionPathMetadataError(
            f"{field_name} contains duplicate values"
        )
    return normalized


def _snapshot_strings(
    values: object, field_name: str,
) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)):
        raise InvalidExecutionPathRequestError(
            f"{field_name} must be a sequence of strings"
        )
    try:
        snapshot = tuple(values)
    except TypeError as exc:
        raise InvalidExecutionPathRequestError(
            f"{field_name} must be a sequence of strings"
        ) from exc
    if any(
        not isinstance(item, str) or not item
        for item in snapshot
    ):
        raise InvalidExecutionPathRequestError(
            f"{field_name} contains an invalid value"
        )
    return snapshot


def _prohibit_authority(
    runtime_allowed: bool, execution_allowed: bool,
) -> None:
    if not isinstance(runtime_allowed, bool) or runtime_allowed:
        raise InvalidExecutionPathRequestError(
            "Execution Path cannot allow Runtime"
        )
    if not isinstance(execution_allowed, bool) or execution_allowed:
        raise InvalidExecutionPathRequestError(
            "Execution Path cannot allow execution"
        )
