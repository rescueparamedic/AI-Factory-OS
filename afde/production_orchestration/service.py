"""Thin production orchestration over the existing Golden Path services."""
from __future__ import annotations

from typing import Protocol

from afde.execution_path import ExecutionPathRequest, ExecutionPathStatus
from afde.planner import RuleBasedExecutionPlanner
from afde.planner_resolution import (
    IntegrationStatus,
    PlannerCapabilityResolutionRequest,
)
from afde.production_adapter_runtime_execution import (
    ProductionAdapterRuntimeExecutionAuthority,
    ProductionAdapterRuntimeExecutionRequest,
    ProductionAdapterRuntimeExecutionService,
)
from afde.production_adapter_runtime_startup_integration import (
    ProductionAdapterRuntimeStartupComposition,
    adapt_credential_readiness_to_runtime_prerequisite_satisfaction,
)
from afde.runtime_integration import (
    RuntimeIntegrationPrerequisiteRequest,
    RuntimeIntegrationStatus,
)
from afde.tool_adapter_contract import (
    ToolAdapterBinding,
    ToolAdapterContractStatus,
    ToolAdapterRequest,
)
from afde.tool_selection import (
    ToolAdapterSelectionRequest,
    ToolAdapterSelectionStatus,
)

from .errors import InvalidProductionOrchestrationRequestError
from .models import (
    ProductionOrchestrationRequest,
    ProductionOrchestrationResult,
    ProductionOrchestrationStatus,
)


class RuntimeExecutionAuthorityProvider(Protocol):
    """External Runtime owner of an already-approved binding authority."""

    def get_authority(
        self, binding: ToolAdapterBinding,
    ) -> ProductionAdapterRuntimeExecutionAuthority: ...


class ProductionPlannerRuntimeOrchestrator:
    """Call existing Golden Path capabilities in order and stop fail-closed."""

    def __init__(
        self,
        *,
        startup_composition: ProductionAdapterRuntimeStartupComposition,
        authority_provider: RuntimeExecutionAuthorityProvider | None,
        planner: RuleBasedExecutionPlanner | None = None,
        runtime_execution: ProductionAdapterRuntimeExecutionService | None = None,
    ) -> None:
        if type(startup_composition) is not ProductionAdapterRuntimeStartupComposition:
            raise TypeError("startup_composition must use the canonical contract")
        if authority_provider is not None and not callable(
            getattr(authority_provider, "get_authority", None)
        ):
            raise TypeError("authority_provider must provide get_authority(binding)")
        self._startup = startup_composition
        self._authority_provider = authority_provider
        self._planner = planner or RuleBasedExecutionPlanner()
        self._runtime_execution = (
            runtime_execution or ProductionAdapterRuntimeExecutionService()
        )

    def orchestrate(
        self, request: ProductionOrchestrationRequest,
    ) -> ProductionOrchestrationResult:
        if type(request) is not ProductionOrchestrationRequest:
            raise InvalidProductionOrchestrationRequestError(
                "request must be exactly one ProductionOrchestrationRequest"
            )
        trace: list[str] = []
        composition = self._startup.production_composition
        identities: dict[str, str | None] = {
            "plan_id": None,
            "capability_id": request.capability_id,
            "adapter_id": None,
            "path_id": None,
            "projection_id": None,
            "binding_id": None,
        }

        try:
            plan = self._planner.create_plan(request.goal)
            identities["plan_id"] = plan.plan_id
            trace.append(f"01.planner.completed:{plan.plan_id}")
        except Exception as exc:
            return self._stopped(
                ProductionOrchestrationStatus.REJECTED,
                "Planner rejected the governed input",
                trace + ["01.planner.rejected"], identities, exc,
            )

        try:
            resolved = composition.planner_resolution.resolve(
                PlannerCapabilityResolutionRequest(
                    planning_result=plan,
                    capability_id=request.capability_id,
                    requested_scope=request.requested_scope,
                    minimum_maturity=request.minimum_maturity,
                    require_operational=request.require_operational,
                    constraints=request.constraints,
                )
            )
            trace.append(
                "02.planner_resolution.completed:"
                f"{resolved.integration_status.value}"
            )
        except Exception as exc:
            return self._stopped(
                ProductionOrchestrationStatus.REJECTED,
                "Planner Resolution rejected the request",
                trace + ["02.planner_resolution.rejected"], identities, exc,
            )
        if resolved.integration_status is not IntegrationStatus.RESOLVED:
            return self._stopped(
                ProductionOrchestrationStatus.BLOCKED,
                f"Capability resolution is {resolved.integration_status.value}",
                trace + ["02.planner_resolution.blocked"], identities,
            )

        try:
            selection = composition.tool_adapter_selection.select(
                ToolAdapterSelectionRequest(resolved)
            )
            trace.append(
                f"03.tool_selection.completed:{selection.selection_status.value}"
            )
        except Exception as exc:
            return self._stopped(
                ProductionOrchestrationStatus.REJECTED,
                "Tool Adapter Selection rejected the resolution",
                trace + ["03.tool_selection.rejected"], identities, exc,
            )
        if selection.selection_status is not ToolAdapterSelectionStatus.SELECTED:
            status = (
                ProductionOrchestrationStatus.UNAVAILABLE
                if selection.selection_status is ToolAdapterSelectionStatus.NO_SELECTION
                else ProductionOrchestrationStatus.BLOCKED
            )
            return self._stopped(
                status, selection.selection_rationale[0],
                trace + ["03.tool_selection.stopped"], identities,
            )
        assert selection.selected_adapter is not None
        identities["adapter_id"] = selection.selected_adapter.adapter_id
        if identities["adapter_id"] != self._startup.adapter_id:
            return self._stopped(
                ProductionOrchestrationStatus.REJECTED,
                "selected adapter identity conflicts with production startup",
                trace + ["03.tool_selection.identity_mismatch"], identities,
            )

        try:
            path = composition.execution_path.build(ExecutionPathRequest(selection))
            trace.append(f"04.execution_path.completed:{path.status.value}")
        except Exception as exc:
            return self._stopped(
                ProductionOrchestrationStatus.REJECTED,
                "Execution Path rejected the selection",
                trace + ["04.execution_path.rejected"], identities, exc,
            )
        identities["path_id"] = path.path_id
        if path.status is not ExecutionPathStatus.PREREQUISITES_REQUIRED:
            status = (
                ProductionOrchestrationStatus.UNAVAILABLE
                if path.status is ExecutionPathStatus.UNAVAILABLE
                else ProductionOrchestrationStatus.BLOCKED
            )
            reason = path.blocked_reasons[0] if path.blocked_reasons else (
                "credential-required production path was not reached"
            )
            return self._stopped(
                status, reason, trace + ["04.execution_path.stopped"], identities,
            )

        try:
            satisfaction = (
                adapt_credential_readiness_to_runtime_prerequisite_satisfaction(
                    execution_path=path,
                    credential_readiness=self._startup.credential_readiness,
                )
            )
            trace.append("05.credential_readiness.satisfied")
            runtime = (
                composition.runtime_integration
                .project_with_prerequisite_satisfaction(
                    RuntimeIntegrationPrerequisiteRequest(path, satisfaction)
                )
            )
            trace.append(f"06.runtime_integration.completed:{runtime.status.value}")
        except Exception as exc:
            return self._stopped(
                ProductionOrchestrationStatus.BLOCKED,
                "credential prerequisite or Runtime Integration was rejected",
                trace + ["06.runtime_integration.rejected"], identities, exc,
            )
        if runtime.status is not RuntimeIntegrationStatus.READY:
            return self._stopped(
                ProductionOrchestrationStatus.BLOCKED,
                runtime.blocked_reasons[0],
                trace + ["06.runtime_integration.blocked"], identities,
            )
        projection = runtime.projection
        assert projection is not None
        identities["projection_id"] = projection.projection_id

        try:
            tool_request = ToolAdapterRequest(projection)
            adapter_result = composition.tool_adapter_contract.bind(tool_request)
            trace.append(
                f"07.tool_adapter_binding.completed:{adapter_result.status.value}"
            )
        except Exception as exc:
            return self._stopped(
                ProductionOrchestrationStatus.REJECTED,
                "Tool Adapter binding rejected the Runtime projection",
                trace + ["07.tool_adapter_binding.rejected"], identities, exc,
            )
        if adapter_result.status is not ToolAdapterContractStatus.VALIDATED:
            return self._stopped(
                ProductionOrchestrationStatus.REJECTED,
                adapter_result.errors[0].message,
                trace + ["07.tool_adapter_binding.stopped"], identities,
            )
        binding = adapter_result.binding
        assert binding is not None
        identities["binding_id"] = binding.binding_id

        if self._authority_provider is None:
            return self._stopped(
                ProductionOrchestrationStatus.BLOCKED,
                "Runtime execution authority is missing",
                trace + ["08.runtime_authority.missing"], identities,
            )
        try:
            authority = self._authority_provider.get_authority(binding)
            execution_request = ProductionAdapterRuntimeExecutionRequest(
                startup_composition=self._startup,
                tool_adapter_request=tool_request,
                binding=binding,
                authority=authority,
                invocation_metadata_references=(
                    request.invocation_metadata_references
                ),
            )
            trace.append("08.runtime_authority.validated")
        except Exception as exc:
            return self._stopped(
                ProductionOrchestrationStatus.REJECTED,
                "Runtime execution authority was rejected",
                trace + ["08.runtime_authority.rejected"], identities, exc,
            )

        try:
            execution = self._runtime_execution.execute(execution_request)
            trace.append("09.runtime_execution.completed")
        except Exception as exc:
            return self._stopped(
                ProductionOrchestrationStatus.REJECTED,
                "Production Adapter Runtime Execution failed",
                trace + ["09.runtime_execution.failed"], identities, exc,
            )
        return ProductionOrchestrationResult(
            status=ProductionOrchestrationStatus.COMPLETED,
            runtime_execution_result=execution,
            blocked_reason=None,
            trace=tuple(trace),
            runtime_allowed=False,
            execution_allowed=False,
            **identities,
        )

    @staticmethod
    def _stopped(
        status: ProductionOrchestrationStatus,
        reason: str,
        trace: list[str] | tuple[str, ...],
        identities: dict[str, str | None],
        exception: Exception | None = None,
    ) -> ProductionOrchestrationResult:
        detail = (
            reason
            if exception is None
            else f"{reason}: {type(exception).__name__}"
        )
        return ProductionOrchestrationResult(
            status=status,
            runtime_execution_result=None,
            blocked_reason=detail,
            trace=tuple(trace),
            runtime_allowed=False,
            execution_allowed=False,
            **identities,
        )
