"""Single-worker adapter for the AFDE real execution foundation."""
from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime
from typing import Any

from .models import ExecutionInput, WorkerExecutionResult
from .worker_registry import WorkerRegistry


class SingleWorkerExecutionAdapter:
    """Execute inputs sequentially through one registered worker identity."""

    def __init__(
        self, worker_id: str = "development_worker", *,
        executor: Callable[[ExecutionInput], Mapping[str, Any] | str] | None = None,
        registry: WorkerRegistry | None = None,
    ) -> None:
        self.worker_id = worker_id
        self.executor = executor or _consume_instruction
        definitions = (registry or WorkerRegistry()).list()
        try:
            self.definition = next(
                item for item in definitions if item.worker_id == worker_id
            )
        except StopIteration as exc:
            raise ValueError(f"worker is not registered: {worker_id}") from exc

    def execute(self, value: ExecutionInput) -> WorkerExecutionResult:
        if not isinstance(value, ExecutionInput):
            raise TypeError("execution input must be an ExecutionInput")
        if value.worker_id != self.worker_id:
            raise ValueError("execution input worker does not match adapter worker")
        started_at = _now()
        try:
            raw_output = self.executor(value)
            output = _structured_output(raw_output)
            status = "completed"
            error = ""
        except Exception as exc:
            output = {}
            status = "failed"
            error = f"worker execution failed ({type(exc).__name__})"
        return WorkerExecutionResult(
            plan_id=value.plan_id,
            task_id=value.task_id,
            worker_id=value.worker_id,
            execution_status=status,
            provider=value.provider,
            model=value.model,
            execution_mode=value.execution_mode,
            output=output,
            started_at=started_at,
            completed_at=_now(),
            error=error,
        )


def _consume_instruction(value: ExecutionInput) -> dict[str, Any]:
    return {
        "content": value.instruction,
        "task_id": value.task_id,
    }


def _structured_output(value: Mapping[str, Any] | str) -> dict[str, Any]:
    if isinstance(value, str):
        return {"content": value}
    if isinstance(value, Mapping):
        return dict(value)
    raise TypeError("worker executor must return a mapping or string")


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")
