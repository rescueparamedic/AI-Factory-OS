"""Immutable contracts for production Planner-to-Worker dispatch."""
from __future__ import annotations

from dataclasses import dataclass

from afde.production_adapter_worker_execution import (
    ProductionAdapterWorkerExecutionResult,
)
from afde.production_adapter_worker_execution.models import WORKER_ID_PATTERN
from afde.production_orchestration import (
    ProductionOrchestrationRequest,
    ProductionOrchestrationResult,
    ProductionOrchestrationStatus,
)

from .errors import (
    InvalidProductionPlannerWorkerDispatchRequestError,
    InvalidProductionPlannerWorkerDispatchResultError,
)


@dataclass(frozen=True)
class ProductionPlannerWorkerDispatchRequest:
    """Planner request plus the minimum explicit Worker invocation identity."""

    orchestration_request: ProductionOrchestrationRequest
    task_id: str
    worker_id: str
    instruction: str
    provider: str
    model: str
    execution_mode: str

    def __post_init__(self) -> None:
        error = InvalidProductionPlannerWorkerDispatchRequestError
        if type(self.orchestration_request) is not ProductionOrchestrationRequest:
            raise error(
                "orchestration_request must use the existing Production contract"
            )
        for name in (
            "task_id", "instruction", "provider", "model", "execution_mode",
        ):
            value = getattr(self, name)
            if (
                not isinstance(value, str)
                or not value
                or value != value.strip()
            ):
                raise error(f"{name} must be an exact non-empty string")
        if (
            not isinstance(self.worker_id, str)
            or not WORKER_ID_PATTERN.fullmatch(self.worker_id)
        ):
            raise error("worker_id is invalid")


@dataclass(frozen=True)
class ProductionPlannerWorkerDispatchResult:
    """Fail-closed top-level outcome ending at the existing Worker result."""

    status: ProductionOrchestrationStatus
    dispatch_request: ProductionPlannerWorkerDispatchRequest
    orchestration_result: ProductionOrchestrationResult
    worker_execution_result: ProductionAdapterWorkerExecutionResult | None
    blocked_reason: str | None

    def __post_init__(self) -> None:
        error = InvalidProductionPlannerWorkerDispatchResultError
        if not isinstance(self.status, ProductionOrchestrationStatus):
            raise error("status is invalid")
        if type(self.dispatch_request) is not ProductionPlannerWorkerDispatchRequest:
            raise error("dispatch_request must use the existing contract")
        if type(self.orchestration_result) is not ProductionOrchestrationResult:
            raise error("orchestration_result must use the existing contract")
        completed = self.status is ProductionOrchestrationStatus.COMPLETED
        if completed:
            if (
                self.orchestration_result.status
                is not ProductionOrchestrationStatus.COMPLETED
                or type(self.worker_execution_result)
                is not ProductionAdapterWorkerExecutionResult
                or self.blocked_reason is not None
            ):
                raise error("completed dispatch contracts conflict")
            worker = self.worker_execution_result
            assert worker is not None
            worker_result = worker.worker_result
            runtime_result = self.orchestration_result.runtime_execution_result
            if (
                worker.runtime_execution_result is not runtime_result
                or worker_result.plan_id != self.orchestration_result.plan_id
                or worker_result.task_id != self.dispatch_request.task_id
                or worker_result.worker_id != self.dispatch_request.worker_id
                or worker.worker_id != self.dispatch_request.worker_id
                or worker_result.provider != self.dispatch_request.provider
                or worker_result.model != self.dispatch_request.model
                or worker_result.execution_mode
                != self.dispatch_request.execution_mode
            ):
                raise error("completed dispatch identity continuity conflicts")
        elif (
            self.worker_execution_result is not None
            or not isinstance(self.blocked_reason, str)
            or not self.blocked_reason.strip()
        ):
            raise error("stopped dispatch must contain only a blocking reason")
