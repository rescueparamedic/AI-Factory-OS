"""Minimal dependency validation for Execution Plans."""
from __future__ import annotations

from .models import ExecutionPlan


class PlanValidationError(ValueError):
    def __init__(self, errors: list[str]) -> None:
        self.errors = tuple(errors)
        super().__init__("; ".join(errors))


class ExecutionPlanValidator:
    def validate(self, plan: ExecutionPlan) -> ExecutionPlan:
        errors: list[str] = []
        task_ids = [task.task_id for task in plan.tasks]
        duplicates = sorted({task_id for task_id in task_ids if task_ids.count(task_id) > 1})
        if duplicates:
            errors.append("duplicate task id: " + ", ".join(duplicates))

        known = set(task_ids)
        missing = sorted({
            dependency
            for task in plan.tasks
            for dependency in task.depends_on
            if dependency not in known
        })
        if missing:
            errors.append("missing dependency: " + ", ".join(missing))

        if not duplicates and not missing and _has_cycle(plan):
            errors.append("cyclic dependency")

        if errors:
            raise PlanValidationError(errors)
        return plan


def _has_cycle(plan: ExecutionPlan) -> bool:
    dependencies = {task.task_id: tuple(task.depends_on) for task in plan.tasks}
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(task_id: str) -> bool:
        if task_id in visiting:
            return True
        if task_id in visited:
            return False
        visiting.add(task_id)
        if any(visit(dependency) for dependency in dependencies[task_id]):
            return True
        visiting.remove(task_id)
        visited.add(task_id)
        return False

    return any(visit(task_id) for task_id in dependencies)
