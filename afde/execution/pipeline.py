"""Minimal Provider -> Planner task -> single Worker Runtime pipeline."""
from __future__ import annotations

from afde.planner.models import ExecutionPlan, ExecutionTask
from afde.planner.planner import RuleBasedExecutionPlanner
from afde.providers.base import AIProvider
from real_worker_runtime.execution_adapter import SingleWorkerExecutionAdapter
from real_worker_runtime.models import ExecutionInput, WorkerExecutionResult

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
        self.last_stage = "planning"
        self._execution_inputs: list[ExecutionInput] = []

    @property
    def execution_inputs(self) -> tuple[ExecutionInput, ...]:
        return tuple(self._execution_inputs)

    def run(self, goal: str) -> tuple[WorkerExecutionResult, ...]:
        return self.execute(self.planner.create_plan(goal))

    def execute(self, plan: ExecutionPlan) -> tuple[WorkerExecutionResult, ...]:
        if not isinstance(plan, ExecutionPlan):
            raise TypeError("execution plan must be an ExecutionPlan")
        self._reset()
        completed: set[str] = set()
        results: list[WorkerExecutionResult] = []
        for task in plan.tasks:
            _require_ready(task, completed)
            result = self._execute_task(plan, task)
            results.append(result)
            if result.execution_status != "completed":
                break
            completed.add(task.task_id)
        return tuple(results)

    def execute_task(
        self, plan: ExecutionPlan, task: ExecutionTask,
    ) -> WorkerExecutionResult:
        """Execute exactly one selected plan task through the existing path."""
        if not isinstance(plan, ExecutionPlan):
            raise TypeError("execution plan must be an ExecutionPlan")
        if task not in plan.tasks:
            raise ValueError("execution task does not belong to the plan")
        self._reset()
        return self._execute_task(plan, task)

    def _execute_task(
        self, plan: ExecutionPlan, task: ExecutionTask,
    ) -> WorkerExecutionResult:
        self.last_stage = "provider"
        response = self.provider.generate(task.description)
        self.last_stage = "bridge"
        execution_input = ProviderRuntimeBridge.convert(
            response, plan=plan, task=task, worker_id=self.worker_id,
        )
        self._execution_inputs.append(execution_input)
        self.last_stage = "worker"
        result = self.adapter.execute(execution_input)
        self.last_evidence = result.to_evidence()
        return result

    def _reset(self) -> None:
        self.last_stage = "planning"
        self.last_evidence = {}
        self._execution_inputs = []


def _require_ready(task: ExecutionTask, completed: set[str]) -> None:
    missing = [item for item in task.depends_on if item not in completed]
    if missing:
        raise ValueError(
            f"execution task has incomplete dependencies: {', '.join(missing)}"
        )
