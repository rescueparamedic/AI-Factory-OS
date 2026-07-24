"""Deterministic construction of a non-executable Execution Path."""
from __future__ import annotations

from hashlib import sha256
from typing import Protocol

from afde.resolver import ResolutionStatus
from afde.tool_catalog import (
    AdapterAvailability,
    AdapterNotFoundError,
    ExecutionContract,
    RuntimeCompatibility,
    ToolAdapterCatalogError,
    ToolAdapterDescriptor,
)
from afde.tool_selection import (
    ToolAdapterCandidate,
    ToolAdapterSelectionResult,
    ToolAdapterSelectionStatus,
)

from .errors import (
    ExecutionPathSourceError,
    InvalidExecutionPathMetadataError,
    InvalidExecutionPathRequestError,
)
from .models import (
    ExecutionPathRequest,
    ExecutionPathResult,
    ExecutionPathStatus,
    RuntimeHandoffProjection,
)


class AdapterMetadataSource(Protocol):
    """Exact read-only Catalog behavior required by the path service."""

    def get_adapter(self, adapter_id: str) -> ToolAdapterDescriptor: ...


class ExecutionPathService:
    """Build one structural Runtime handoff route without execution."""

    def __init__(self, catalog: AdapterMetadataSource) -> None:
        if not callable(getattr(catalog, "get_adapter", None)):
            raise TypeError(
                "catalog must provide get_adapter(adapter_id)"
            )
        self._catalog = catalog

    def build(
        self, request: ExecutionPathRequest,
    ) -> ExecutionPathResult:
        if not isinstance(request, ExecutionPathRequest):
            raise InvalidExecutionPathRequestError(
                "request must be an ExecutionPathRequest"
            )
        selection = request.selection_result
        self._validate_selection_projection(selection)
        if selection.selection_status is not (
            ToolAdapterSelectionStatus.SELECTED
        ):
            status = (
                ExecutionPathStatus.UNAVAILABLE
                if selection.selection_status
                is ToolAdapterSelectionStatus.NO_SELECTION
                else ExecutionPathStatus.BLOCKED
            )
            reason = (
                "execution path requires one successful Tool Adapter "
                f"selection; received {selection.selection_status.value}"
            )
            return self._blocked(
                selection,
                status,
                (reason,),
                (
                    "01.selection.rejected:"
                    f"{selection.selection_status.value}",
                    f"05.path.{status.value}",
                ),
            )
        if (
            selection.resolver_status is not ResolutionStatus.RESOLVED
            or not selection.eligible
            or selection.decision_required
        ):
            reason = (
                "execution path requires resolved eligible Resolver state "
                "without a pending decision"
            )
            return self._blocked(
                selection,
                ExecutionPathStatus.BLOCKED,
                (reason,),
                (
                    "01.selection.accepted:selected",
                    "02.resolver.rejected",
                    "05.path.blocked",
                ),
            )

        candidate = selection.selected_adapter
        if candidate is None:
            raise InvalidExecutionPathMetadataError(
                "selected adapter identity is missing"
            )
        try:
            descriptor = self._catalog.get_adapter(candidate.adapter_id)
        except AdapterNotFoundError:
            return self._blocked(
                selection,
                ExecutionPathStatus.UNAVAILABLE,
                (
                    "selected adapter is not available in the Catalog: "
                    f"{candidate.adapter_id}",
                ),
                (
                    "01.selection.accepted:selected",
                    f"02.catalog.adapter.not_found:{candidate.adapter_id}",
                    "05.path.unavailable",
                ),
            )
        except ToolAdapterCatalogError as exc:
            raise ExecutionPathSourceError(
                "Catalog metadata source failed"
            ) from exc
        except Exception as exc:
            raise ExecutionPathSourceError(
                "Catalog metadata source returned an unexpected failure"
            ) from exc
        if not isinstance(descriptor, ToolAdapterDescriptor):
            raise InvalidExecutionPathMetadataError(
                "Catalog returned invalid adapter metadata"
            )
        conflict = self._metadata_conflict(selection, descriptor)
        if conflict is not None:
            return self._blocked(
                selection,
                ExecutionPathStatus.BLOCKED,
                (conflict,),
                (
                    "01.selection.accepted:selected",
                    f"02.catalog.adapter.found:{descriptor.adapter_id}",
                    "03.catalog.metadata.conflict",
                    "05.path.blocked",
                ),
            )
        if descriptor.availability is not AdapterAvailability.AVAILABLE:
            return self._metadata_blocked(
                selection,
                descriptor,
                ExecutionPathStatus.UNAVAILABLE,
                "selected adapter is unavailable",
                "availability",
            )
        if (
            descriptor.runtime_compatibility
            is not RuntimeCompatibility.COMPATIBLE
        ):
            return self._metadata_blocked(
                selection,
                descriptor,
                ExecutionPathStatus.BLOCKED,
                "selected adapter is not Runtime-compatible",
                "runtime_compatibility",
            )
        if (
            descriptor.execution_contract
            is not ExecutionContract.CONTROLLED_RUNTIME
        ):
            return self._metadata_blocked(
                selection,
                descriptor,
                ExecutionPathStatus.BLOCKED,
                "selected adapter has no supported execution contract",
                "execution_contract",
            )

        handoff_ready = not descriptor.credentials_required
        step = RuntimeHandoffProjection(
            sequence=1,
            adapter_id=descriptor.adapter_id,
            capability_id=selection.capability_id,
            adapter_version=descriptor.version,
            availability=descriptor.availability,
            runtime_compatibility=descriptor.runtime_compatibility,
            execution_contract=descriptor.execution_contract,
            privacy_classification=descriptor.privacy_classification,
            cost_classification=descriptor.cost_classification,
            credentials_required=descriptor.credentials_required,
            metadata_references=descriptor.metadata_references,
            handoff_ready=handoff_ready,
            runtime_allowed=False,
            execution_allowed=False,
        )
        path_id = self._path_id(step)
        if descriptor.credentials_required:
            status = ExecutionPathStatus.PREREQUISITES_REQUIRED
            blocked_reasons = (
                "credentials are required; retrieval and authorization "
                "remain outside Execution Path",
            )
            readiness_trace = "04.handoff.prerequisites_required:credentials"
        else:
            status = ExecutionPathStatus.CONSTRUCTED
            blocked_reasons = ()
            readiness_trace = "04.handoff.ready"
        return self._result(
            selection=selection,
            status=status,
            path_id=path_id,
            adapter_id=descriptor.adapter_id,
            steps=(step,),
            blocked_reasons=blocked_reasons,
            trace=(
                "01.selection.accepted:selected",
                f"02.catalog.adapter.found:{descriptor.adapter_id}",
                "03.catalog.metadata.validated",
                readiness_trace,
                f"05.path.{status.value}:{path_id}",
            ),
        )

    @staticmethod
    def _validate_selection_projection(
        selection: ToolAdapterSelectionResult,
    ) -> None:
        if not isinstance(selection, ToolAdapterSelectionResult):
            raise InvalidExecutionPathRequestError(
                "selection_result is invalid"
            )
        if selection.runtime_allowed or selection.execution_allowed:
            raise InvalidExecutionPathRequestError(
                "Tool Selection cannot grant execution authority"
            )
        if (
            not isinstance(
                selection.selection_status, ToolAdapterSelectionStatus,
            )
            or not isinstance(selection.resolver_status, ResolutionStatus)
            or not isinstance(selection.eligible, bool)
            or not isinstance(selection.decision_required, bool)
        ):
            raise InvalidExecutionPathRequestError(
                "Tool Selection projection contains invalid state"
            )
        if (
            selection.selection_status
            is ToolAdapterSelectionStatus.SELECTED
        ):
            candidate = selection.selected_adapter
            if candidate is None:
                raise InvalidExecutionPathMetadataError(
                    "selected adapter identity is missing"
                )
            try:
                validated = ToolAdapterCandidate(
                    candidate.adapter_id, candidate.capability_ids,
                )
                ToolAdapterCandidate(
                    validated.adapter_id, (selection.capability_id,),
                )
            except Exception as exc:
                raise InvalidExecutionPathMetadataError(
                    "selected adapter or Capability identity is invalid"
                ) from exc

    @staticmethod
    def _metadata_conflict(
        selection: ToolAdapterSelectionResult,
        descriptor: ToolAdapterDescriptor,
    ) -> str | None:
        candidate = selection.selected_adapter
        assert candidate is not None
        if descriptor.adapter_id != candidate.adapter_id:
            return "Catalog adapter identity conflicts with Tool Selection"
        if selection.capability_id not in descriptor.supported_capability_ids:
            return "Catalog descriptor does not support selected Capability ID"
        if (
            candidate.capability_ids
            != descriptor.supported_capability_ids
        ):
            return "Catalog Capability mappings conflict with Tool Selection"
        return None

    def _metadata_blocked(
        self,
        selection: ToolAdapterSelectionResult,
        descriptor: ToolAdapterDescriptor,
        status: ExecutionPathStatus,
        reason: str,
        trace_label: str,
    ) -> ExecutionPathResult:
        return self._blocked(
            selection,
            status,
            (reason,),
            (
                "01.selection.accepted:selected",
                f"02.catalog.adapter.found:{descriptor.adapter_id}",
                f"03.catalog.metadata.rejected:{trace_label}",
                f"05.path.{status.value}",
            ),
        )

    def _blocked(
        self,
        selection: ToolAdapterSelectionResult,
        status: ExecutionPathStatus,
        reasons: tuple[str, ...],
        trace: tuple[str, ...],
    ) -> ExecutionPathResult:
        return self._result(
            selection=selection,
            status=status,
            path_id=None,
            adapter_id=None,
            steps=(),
            blocked_reasons=reasons,
            trace=trace,
        )

    @staticmethod
    def _result(
        *,
        selection: ToolAdapterSelectionResult,
        status: ExecutionPathStatus,
        path_id: str | None,
        adapter_id: str | None,
        steps: tuple[RuntimeHandoffProjection, ...],
        blocked_reasons: tuple[str, ...],
        trace: tuple[str, ...],
    ) -> ExecutionPathResult:
        constructed = bool(steps)
        ready = (
            status is ExecutionPathStatus.CONSTRUCTED
            and constructed
            and steps[0].handoff_ready
        )
        return ExecutionPathResult(
            status=status,
            path_id=path_id,
            path_constructed=constructed,
            runtime_handoff_ready=ready,
            adapter_id=adapter_id,
            capability_id=selection.capability_id,
            steps=steps,
            resolver_status=selection.resolver_status,
            eligible=selection.eligible,
            decision_required=selection.decision_required,
            gaps=selection.gaps,
            rejection_reasons=selection.rejection_reasons,
            source_documents=selection.source_documents,
            reference_priority=selection.reference_priority,
            ordered_rationale=selection.ordered_rationale,
            resolver_trace=selection.resolver_trace,
            selection_rationale=selection.selection_rationale,
            selection_trace=selection.selection_trace,
            blocked_reasons=blocked_reasons,
            trace=trace,
            runtime_allowed=False,
            execution_allowed=False,
        )

    @staticmethod
    def _path_id(step: RuntimeHandoffProjection) -> str:
        parts = (
            step.adapter_id,
            step.capability_id,
            step.adapter_version,
            step.availability.value,
            step.runtime_compatibility.value,
            step.execution_contract.value,
            step.privacy_classification.value,
            step.cost_classification.value,
            str(step.credentials_required).lower(),
            *step.metadata_references,
        )
        digest = sha256("\x1f".join(parts).encode("utf-8")).hexdigest()
        return f"EXECPATH-{digest[:16].upper()}"
