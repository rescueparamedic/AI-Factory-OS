"""Deterministic, read-only Tool Adapter selection policy."""
from __future__ import annotations

from typing import Iterable, Protocol

from afde.planner_resolution import (
    IntegrationStatus,
    PlannerCapabilityResolutionResult,
)
from afde.resolver import (
    CapabilityRequirement,
    CapabilityResolutionResult,
    ResolutionStatus,
)

from .errors import (
    AdapterCandidateSourceError,
    InvalidAdapterCandidateError,
    InvalidToolAdapterSelectionRequestError,
)
from .models import (
    ToolAdapterCandidate,
    ToolAdapterSelectionRequest,
    ToolAdapterSelectionResult,
    ToolAdapterSelectionStatus,
)


class AdapterCandidateSource(Protocol):
    """Minimal injected source for an authoritative candidate snapshot."""

    def list_candidates(self) -> Iterable[ToolAdapterCandidate]: ...


class ToolAdapterSelectionService:
    """Select one exact adapter identity without invoking the adapter."""

    def __init__(self, candidate_source: AdapterCandidateSource) -> None:
        if not callable(getattr(candidate_source, "list_candidates", None)):
            raise TypeError(
                "candidate_source must provide list_candidates()"
            )
        self._candidate_source = candidate_source

    def select(
        self, request: ToolAdapterSelectionRequest,
    ) -> ToolAdapterSelectionResult:
        if not isinstance(request, ToolAdapterSelectionRequest):
            raise InvalidToolAdapterSelectionRequestError(
                "request must be a ToolAdapterSelectionRequest"
            )
        resolution, ordered_rationale = self._resolution(request)
        self._validate_resolution(resolution)
        capability_id = resolution.requirement.capability_id
        assert capability_id is not None

        if (
            resolution.resolution_status is not ResolutionStatus.RESOLVED
            or not resolution.eligible
        ):
            reason = (
                "selection blocked because Resolver status is "
                f"{resolution.resolution_status.value}"
            )
            return self._result(
                resolution,
                ordered_rationale,
                ToolAdapterSelectionStatus.BLOCKED,
                None,
                (reason,),
                (
                    "01.resolution.rejected:"
                    f"{resolution.resolution_status.value}",
                    "04.selection.blocked",
                ),
            )

        candidates = self._candidate_snapshot()
        ordered_candidates = tuple(sorted(
            candidates, key=lambda item: item.adapter_id,
        ))
        matches = tuple(
            item for item in ordered_candidates
            if capability_id in item.capability_ids
        )
        prefix = (
            "01.resolution.accepted:resolved",
            f"02.candidates.snapshot:{len(ordered_candidates)}",
            f"03.capability.exact_matches:{len(matches)}",
        )
        if not matches:
            return self._result(
                resolution,
                ordered_rationale,
                ToolAdapterSelectionStatus.NO_SELECTION,
                None,
                (f"no adapter supports exact capability {capability_id}",),
                prefix + ("04.selection.none",),
            )
        if len(matches) > 1:
            identities = ",".join(item.adapter_id for item in matches)
            return self._result(
                resolution,
                ordered_rationale,
                ToolAdapterSelectionStatus.BLOCKED,
                None,
                (
                    "multiple authoritative adapters support exact "
                    f"capability {capability_id}: {identities}",
                ),
                prefix + ("04.selection.ambiguous",),
            )
        selected = matches[0]
        return self._result(
            resolution,
            ordered_rationale,
            ToolAdapterSelectionStatus.SELECTED,
            selected,
            (
                f"selected {selected.adapter_id} by exact capability "
                f"match on {capability_id}",
            ),
            prefix + (f"04.selection.selected:{selected.adapter_id}",),
        )

    def _candidate_snapshot(self) -> tuple[ToolAdapterCandidate, ...]:
        try:
            candidates = tuple(self._candidate_source.list_candidates())
        except (TypeError, ValueError) as exc:
            raise AdapterCandidateSourceError(
                "candidate source returned an invalid collection"
            ) from exc
        except Exception as exc:
            raise AdapterCandidateSourceError(
                "candidate source failed"
            ) from exc
        if any(
            not isinstance(item, ToolAdapterCandidate)
            for item in candidates
        ):
            raise InvalidAdapterCandidateError(
                "candidate source returned invalid adapter metadata"
            )
        identities = tuple(item.adapter_id for item in candidates)
        if len(identities) != len(set(identities)):
            raise InvalidAdapterCandidateError(
                "candidate source returned duplicate adapter identities"
            )
        return candidates

    @staticmethod
    def _resolution(
        request: ToolAdapterSelectionRequest,
    ) -> tuple[CapabilityResolutionResult, tuple[str, ...]]:
        value = request.resolution_result
        if isinstance(value, PlannerCapabilityResolutionResult):
            resolution = value.capability_resolution_result
            if (
                not isinstance(value.integration_status, IntegrationStatus)
                or not isinstance(resolution, CapabilityResolutionResult)
                or value.integration_status.value
                != resolution.resolution_status.value
                or value.capability_requirement != resolution.requirement
                or value.decision_required != resolution.decision_required
                or value.gaps != resolution.gaps
                or value.runtime_allowed
            ):
                raise InvalidToolAdapterSelectionRequestError(
                    "Planner Resolution result is inconsistent"
                )
            return resolution, value.ordered_rationale
        return value, tuple(value.trace)

    @staticmethod
    def _validate_resolution(
        resolution: CapabilityResolutionResult,
    ) -> None:
        if (
            not isinstance(resolution.requirement, CapabilityRequirement)
            or not isinstance(
                resolution.requirement.capability_id, str,
            )
            or not isinstance(
                resolution.resolution_status, ResolutionStatus,
            )
            or not isinstance(resolution.eligible, bool)
            or not isinstance(resolution.decision_required, bool)
        ):
            raise InvalidToolAdapterSelectionRequestError(
                "Resolver result contains invalid structured fields"
            )
        resolved = resolution.resolution_status is ResolutionStatus.RESOLVED
        if (
            resolution.eligible != resolved
            or resolution.decision_required
            != (
                resolution.resolution_status
                is ResolutionStatus.DECISION_REQUIRED
            )
            or (
                resolved
                and (
                    resolution.capability is None
                    or resolution.capability.capability_id
                    != resolution.requirement.capability_id
                )
            )
        ):
            raise InvalidToolAdapterSelectionRequestError(
                "Resolver result is inconsistent"
            )

    @staticmethod
    def _result(
        resolution: CapabilityResolutionResult,
        ordered_rationale: tuple[str, ...],
        status: ToolAdapterSelectionStatus,
        selected: ToolAdapterCandidate | None,
        selection_rationale: tuple[str, ...],
        selection_trace: tuple[str, ...],
    ) -> ToolAdapterSelectionResult:
        capability_id = resolution.requirement.capability_id
        assert capability_id is not None
        return ToolAdapterSelectionResult(
            selection_status=status,
            capability_id=capability_id,
            selected_adapter=selected,
            resolver_status=resolution.resolution_status,
            eligible=resolution.eligible,
            decision_required=resolution.decision_required,
            gaps=resolution.gaps,
            rejection_reasons=resolution.rejection_reasons,
            source_documents=resolution.source_documents,
            reference_priority=resolution.reference_priority,
            ordered_rationale=ordered_rationale,
            resolver_trace=resolution.trace,
            selection_rationale=selection_rationale,
            selection_trace=selection_trace,
            runtime_allowed=False,
            execution_allowed=False,
        )
