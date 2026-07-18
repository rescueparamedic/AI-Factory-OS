"""Minimal Provider -> Planner task -> single Worker Runtime pipeline."""
from __future__ import annotations

from afde.planner.models import ExecutionPlan, ExecutionTask
from afde.planner.planner import RuleBasedExecutionPlanner
from afde.providers.base import AIProvider
from real_worker_runtime.execution_adapter import SingleWorkerExecutionAdapter
from real_worker_runtime.models import WorkerExecutionResult

from .bridge import ProviderRuntimeBridge


class RealExecutionPipeline:
    """Execute one plan sequentially with one fixed registered worker."""

    def __init__(
        self, provider: AIProvider, *, worker_id: str = "development_worker",
        adapter: SingleWorkerExecutionAdapter | None = None,
        planner: RuleBasedExecutionPlanner | None = None,
    ) -> None:
        if not isinstance(provider, AIProvider):
            raise TypeError("provider must implement AIProvider")
        self.provider = provider
        self.adapter = adapter or SingleWorkerExecutionAdapter(worker_id)
        if self.adapter.worker_id != worker_id:
            raise ValueError("pipeline worker does not match adapter worker")
        self.worker_id = worker_id
        self.planner = planner or RuleBasedExecutionPlanner()
        self.last_evidence: dict[str, str] = {}

    def run(self, goal: str) -> tuple[WorkerExecutionResult, ...]:
        return self.execute(self.planner.create_plan(goal))

    def execute(self, plan: ExecutionPlan) -> tuple[WorkerExecutionResult, ...]:
        if not isinstance(plan, ExecutionPlan):
            raise TypeError("execution plan must be an ExecutionPlan")
        completed: set[str] = set()
        results: list[WorkerExecutionResult] = []
        for task in plan.tasks:
            _require_ready(task, completed)
            response = self.provider.generate(task.description)
            execution_input = ProviderRuntimeBridge.convert(
                response, plan=plan, task=task, worker_id=self.worker_id,
            )
            result = self.adapter.execute(execution_input)
            self.last_evidence = result.to_evidence()
            results.append(result)
            if result.execution_status != "completed":
                break
            completed.add(task.task_id)
        return tuple(results)


def _require_ready(task: ExecutionTask, completed: set[str]) -> None:
    missing = [item for item in task.depends_on if item not in completed]
    if missing:
        raise ValueError(
            f"execution task has incomplete dependencies: {', '.join(missing)}"
        )
