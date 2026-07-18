"""Deterministic rule-based Execution Planner."""
from __future__ import annotations

from datetime import datetime
from hashlib import sha256

from .models import ExecutionPlan, ExecutionTask


class RuleBasedExecutionPlanner:
    """Create one small prepare/execute/verify task chain without AI."""

    def create_plan(self, goal: str) -> ExecutionPlan:
        normalized = _goal(goal)
        digest = sha256(normalized.casefold().encode("utf-8")).hexdigest()[:16].upper()
        plan_id = f"PLAN-{digest}"
        task_prefix = f"TASK-{digest}"
        prepare_id = f"{task_prefix}-01"
        execute_id = f"{task_prefix}-02"
        verify_id = f"{task_prefix}-03"
        return ExecutionPlan(
            plan_id=plan_id,
            goal=normalized,
            created_at=datetime.now().astimezone().isoformat(timespec="seconds"),
            status="pending",
            tasks=[
                ExecutionTask(
                    prepare_id, "Prepare execution",
                    f"Confirm the inputs and boundaries for: {normalized}",
                    "high", "pending", [],
                ),
                ExecutionTask(
                    execute_id, "Execute goal",
                    f"Perform the bounded work required for: {normalized}",
                    "high", "pending", [prepare_id],
                ),
                ExecutionTask(
                    verify_id, "Verify result",
                    f"Verify that the result satisfies: {normalized}",
                    "medium", "pending", [execute_id],
                ),
            ],
        )


def _goal(value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("goal must not be empty")
    normalized = " ".join(value.split())
    if len(normalized) > 1000:
        raise ValueError("goal must not exceed 1000 characters")
    return normalized
