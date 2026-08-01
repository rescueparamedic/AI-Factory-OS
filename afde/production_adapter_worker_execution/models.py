"""Immutable contracts for one Production Adapter Worker execution."""
from __future__ import annotations

import re
from dataclasses import dataclass

from afde.production_adapter_runtime_execution import (
    ProductionAdapterRuntimeExecutionAuthority,
    ProductionAdapterRuntimeExecutionRequest,
    ProductionAdapterRuntimeExecutionResult,
)
from afde.production_adapter_runtime_startup_integration import (
    ProductionAdapterRuntimeStartupComposition,
)
from afde.tool_adapter_contract import ToolAdapterBinding, ToolAdapterRequest
from real_worker_runtime.models import ExecutionInput, WorkerExecutionResult

from .errors import (
    InvalidProductionAdapterWorkerExecutionRequestError,
    InvalidProductionAdapterWorkerExecutionResultError,
    ProductionAdapterWorkerExecutionIdentityMismatchError,
)

WORKER_ID_PATTERN = re.compile(r"^[a-z][a-z0-9_]{0,63}$")


@dataclass(frozen=True)
class ProductionAdapterWorkerExecutionRequest:
    """Existing Worker input and contracts for one Runtime request."""

    worker_input: ExecutionInput
    startup_composition: ProductionAdapterRuntimeStartupComposition
    tool_adapter_request: ToolAdapterRequest
    binding: ToolAdapterBinding
    authority: ProductionAdapterRuntimeExecutionAuthority
    invocation_metadata_references: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        error = InvalidProductionAdapterWorkerExecutionRequestError
        if type(self.worker_input) is not ExecutionInput:
            raise error("worker_input must be exactly one ExecutionInput")
        exact_types = (
            (
                "startup_composition",
                self.startup_composition,
                ProductionAdapterRuntimeStartupComposition,
            ),
            ("tool_adapter_request", self.tool_adapter_request, ToolAdapterRequest),
            ("binding", self.binding, ToolAdapterBinding),
            (
                "authority",
                self.authority,
                ProductionAdapterRuntimeExecutionAuthority,
            ),
        )
        for name, value, expected in exact_types:
            if type(value) is not expected:
                raise error(f"{name} must use the existing contract")
        if not WORKER_ID_PATTERN.fullmatch(self.worker_input.worker_id):
            raise error("worker identity is missing or invalid")
        if (
            not isinstance(self.worker_input.instruction, str)
            or not self.worker_input.instruction
            or self.worker_input.instruction
            != self.worker_input.instruction.strip()
        ):
            raise error("worker invocation payload must be non-empty")

    def build_runtime_execution_request(
        self,
    ) -> ProductionAdapterRuntimeExecutionRequest:
        """Assemble only the existing Runtime execution request contract."""

        return ProductionAdapterRuntimeExecutionRequest(
            startup_composition=self.startup_composition,
            tool_adapter_request=self.tool_adapter_request,
            binding=self.binding,
            authority=self.authority,
            invocation_metadata_references=self.invocation_metadata_references,
        )


@dataclass(frozen=True)
class ProductionAdapterWorkerExecutionResult:
    """Existing Worker outcome paired with authority-free Runtime evidence."""

    worker_id: str
    worker_result: WorkerExecutionResult
    runtime_execution_result: ProductionAdapterRuntimeExecutionResult

    def __post_init__(self) -> None:
        error = InvalidProductionAdapterWorkerExecutionResultError
        if type(self.worker_result) is not WorkerExecutionResult:
            raise error("worker_result must use the existing Worker contract")
        if type(
            self.runtime_execution_result
        ) is not ProductionAdapterRuntimeExecutionResult:
            raise error(
                "runtime_execution_result must use the existing Runtime contract"
            )
        if (
            not WORKER_ID_PATTERN.fullmatch(self.worker_id)
            or self.worker_result.worker_id != self.worker_id
        ):
            raise ProductionAdapterWorkerExecutionIdentityMismatchError(
                "Worker result identity conflicts"
            )
        runtime_result = self.runtime_execution_result
        output = self.worker_result.output
        if (
            self.worker_result.execution_status != "completed"
            or self.worker_result.error
            or output.get("adapter_id") != runtime_result.adapter_id
            or output.get("projection_id") != runtime_result.projection_id
            or output.get("path_id") != runtime_result.path_id
            or output.get("capability_id") != runtime_result.capability_id
            or output.get("binding_id") != runtime_result.binding_id
        ):
            raise error("Worker result conflicts with Runtime execution evidence")
