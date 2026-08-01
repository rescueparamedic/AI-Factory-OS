"""Provider-neutral Worker facade over existing Runtime execution."""
from __future__ import annotations

from afde.production_adapter_runtime_execution import (
    ProductionAdapterRuntimeExecutionService,
)
from real_worker_runtime.models import WorkerExecutionResult

from .errors import InvalidProductionAdapterWorkerExecutionRequestError
from .models import (
    ProductionAdapterWorkerExecutionRequest,
    ProductionAdapterWorkerExecutionResult,
)


class ProductionAdapterWorkerExecutionService:
    """Preserve Worker identity around one existing Runtime execution call."""

    def __init__(
        self,
        runtime_execution_service: ProductionAdapterRuntimeExecutionService
        | None = None,
    ) -> None:
        service = (
            runtime_execution_service
            if runtime_execution_service is not None
            else ProductionAdapterRuntimeExecutionService()
        )
        if not isinstance(service, ProductionAdapterRuntimeExecutionService):
            raise TypeError(
                "runtime_execution_service must use the existing service"
            )
        self._runtime_execution_service = service

    def execute(
        self,
        request: ProductionAdapterWorkerExecutionRequest,
    ) -> ProductionAdapterWorkerExecutionResult:
        """Call Runtime execution exactly once and return existing Worker evidence."""

        if type(request) is not ProductionAdapterWorkerExecutionRequest:
            raise InvalidProductionAdapterWorkerExecutionRequestError(
                "request must be exactly one ProductionAdapterWorkerExecutionRequest"
            )
        runtime_request = request.build_runtime_execution_request()
        runtime_result = self._runtime_execution_service.execute(runtime_request)
        worker_input = request.worker_input
        worker_result = WorkerExecutionResult(
            plan_id=worker_input.plan_id,
            task_id=worker_input.task_id,
            worker_id=worker_input.worker_id,
            execution_status="completed",
            provider=worker_input.provider,
            model=worker_input.model,
            execution_mode=worker_input.execution_mode,
            output={
                "adapter_id": runtime_result.adapter_id,
                "projection_id": runtime_result.projection_id,
                "path_id": runtime_result.path_id,
                "capability_id": runtime_result.capability_id,
                "binding_id": runtime_result.binding_id,
            },
            started_at="",
            completed_at="",
            error="",
        )
        return ProductionAdapterWorkerExecutionResult(
            worker_id=worker_input.worker_id,
            worker_result=worker_result,
            runtime_execution_result=runtime_result,
        )
