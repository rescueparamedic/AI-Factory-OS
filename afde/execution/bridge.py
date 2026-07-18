"""Conversion boundary from public provider output to Runtime input."""
from __future__ import annotations

from afde.planner.models import ExecutionPlan, ExecutionTask
from afde.providers.models import ProviderResponse
from real_worker_runtime.models import ExecutionInput


class ProviderRuntimeBridge:
    @staticmethod
    def convert(
        response: ProviderResponse, *, plan: ExecutionPlan,
        task: ExecutionTask, worker_id: str,
    ) -> ExecutionInput:
        if not isinstance(response, ProviderResponse):
            raise TypeError("provider response must be a ProviderResponse")
        if task not in plan.tasks:
            raise ValueError("execution task does not belong to the plan")
        execution_mode = str(response.metadata.get("execution_mode", "unspecified"))
        return ExecutionInput(
            plan_id=plan.plan_id,
            task_id=task.task_id,
            worker_id=worker_id,
            instruction=response.content,
            provider=response.provider,
            model=response.model,
            execution_mode=execution_mode,
            metadata={
                "goal": plan.goal,
                "task_title": task.title,
                "priority": task.priority,
                "depends_on": list(task.depends_on),
                "provider_metadata": response.to_dict()["metadata"],
            },
        )

    to_execution_input = convert
