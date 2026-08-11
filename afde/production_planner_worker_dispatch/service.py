"""Thin production composition from Planner orchestration to Worker result."""
from __future__ import annotations

from afde.production_adapter_worker_execution import (
    ProductionAdapterWorkerResultProjector,
)
from afde.production_orchestration import (
    ProductionOrchestrationStatus,
    ProductionPlannerRuntimeOrchestrator,
)
from real_worker_runtime.models import ExecutionInput

from .errors import InvalidProductionPlannerWorkerDispatchRequestError
from .models import (
    ProductionPlannerWorkerDispatchRequest,
    ProductionPlannerWorkerDispatchResult,
)


class ProductionPlannerWorkerDispatcher:
    """Run the canonical orchestrator, then project its completed result."""

    def __init__(
        self,
        *,
        orchestrator: ProductionPlannerRuntimeOrchestrator,
        projector: ProductionAdapterWorkerResultProjector | None = None,
    ) -> None:
        if not isinstance(orchestrator, ProductionPlannerRuntimeOrchestrator):
            raise TypeError("orchestrator must use the canonical service")
        selected = projector or ProductionAdapterWorkerResultProjector()
        if type(selected) is not ProductionAdapterWorkerResultProjector:
            raise TypeError("projector must use the canonical service")
        self._orchestrator = orchestrator
        self._projector = selected

    def dispatch(
        self,
        request: ProductionPlannerWorkerDispatchRequest,
    ) -> ProductionPlannerWorkerDispatchResult:
        if type(request) is not ProductionPlannerWorkerDispatchRequest:
            raise InvalidProductionPlannerWorkerDispatchRequestError(
                "request must be exactly one ProductionPlannerWorkerDispatchRequest"
            )
        orchestration = self._orchestrator.orchestrate(
            request.orchestration_request
        )
        if orchestration.status is not ProductionOrchestrationStatus.COMPLETED:
            return ProductionPlannerWorkerDispatchResult(
                status=orchestration.status,
                dispatch_request=request,
                orchestration_result=orchestration,
                worker_execution_result=None,
                blocked_reason=orchestration.blocked_reason,
            )
        if (
            orchestration.runtime_execution_result is None
            or orchestration.plan_id is None
        ):
            return ProductionPlannerWorkerDispatchResult(
                status=ProductionOrchestrationStatus.REJECTED,
                dispatch_request=request,
                orchestration_result=orchestration,
                worker_execution_result=None,
                blocked_reason=(
                    "completed orchestration is missing Runtime or Planner identity"
                ),
            )

        worker_input = ExecutionInput(
            plan_id=orchestration.plan_id,
            task_id=request.task_id,
            worker_id=request.worker_id,
            instruction=request.instruction,
            provider=request.provider,
            model=request.model,
            execution_mode=request.execution_mode,
        )
        try:
            worker_result = self._projector.project(
                worker_input,
                orchestration.runtime_execution_result,
            )
        except Exception as exc:
            return ProductionPlannerWorkerDispatchResult(
                status=ProductionOrchestrationStatus.REJECTED,
                dispatch_request=request,
                orchestration_result=orchestration,
                worker_execution_result=None,
                blocked_reason=(
                    "post-Runtime Worker projection rejected the result: "
                    f"{type(exc).__name__}"
                ),
            )
        return ProductionPlannerWorkerDispatchResult(
            status=ProductionOrchestrationStatus.COMPLETED,
            dispatch_request=request,
            orchestration_result=orchestration,
            worker_execution_result=worker_result,
            blocked_reason=None,
        )
