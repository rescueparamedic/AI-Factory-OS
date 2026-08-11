"""Provider-neutral Worker facade over existing Runtime execution."""
from __future__ import annotations

from afde.production_adapter_runtime_execution import (
    ProductionAdapterRuntimeExecutionResult,
    ProductionAdapterRuntimeExecutionService,
)
from real_worker_runtime.models import ExecutionInput, WorkerExecutionResult

from .errors import (
    InvalidProductionAdapterWorkerExecutionRequestError,
    InvalidProductionAdapterWorkerExecutionResultError,
)
from .models import (
    WORKER_ID_PATTERN,
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
        worker_result = _worker_result(worker_input, runtime_result)
        return ProductionAdapterWorkerExecutionResult(
            worker_id=worker_input.worker_id,
            worker_result=worker_result,
            runtime_execution_result=runtime_result,
        )


class ProductionAdapterWorkerResultProjector:
    """Project completed Runtime evidence into the existing Worker contract."""

    def project(
        self,
        worker_input: ExecutionInput,
        runtime_result: ProductionAdapterRuntimeExecutionResult,
    ) -> ProductionAdapterWorkerExecutionResult:
        """Construct Worker evidence without authority or Runtime execution."""

        error = InvalidProductionAdapterWorkerExecutionResultError
        if type(worker_input) is not ExecutionInput:
            raise error("worker_input must be exactly one ExecutionInput")
        if type(runtime_result) is not ProductionAdapterRuntimeExecutionResult:
            raise error("runtime_result must use the existing Runtime contract")
        for name in (
            "plan_id", "task_id", "instruction", "provider", "model",
            "execution_mode",
        ):
            value = getattr(worker_input, name)
            if (
                not isinstance(value, str)
                or not value
                or value != value.strip()
            ):
                raise error(f"{name} must be an exact non-empty string")
        if not WORKER_ID_PATTERN.fullmatch(worker_input.worker_id):
            raise error("worker identity is missing or invalid")
        worker_result = _worker_result(worker_input, runtime_result)
        return ProductionAdapterWorkerExecutionResult(
            worker_id=worker_input.worker_id,
            worker_result=worker_result,
            runtime_execution_result=runtime_result,
        )


def _worker_result(
    worker_input: ExecutionInput,
    runtime_result: ProductionAdapterRuntimeExecutionResult,
) -> WorkerExecutionResult:
    return WorkerExecutionResult(
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
