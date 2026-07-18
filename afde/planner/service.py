"""Persistence and application service for the Execution Planner MVP."""
from __future__ import annotations

import json
from pathlib import Path
import re

from .models import ExecutionPlan
from .planner import RuleBasedExecutionPlanner
from .validator import ExecutionPlanValidator


PLAN_ID_PATTERN = re.compile(r"^PLAN-[A-F0-9]{16}$")


class PlanNotFoundError(FileNotFoundError):
    pass


class PlannerService:
    def __init__(self, root: str | Path = ".") -> None:
        self.root = Path(root).expanduser().resolve()
        self.directory = self.root / "data" / "execution_plans"
        self.planner = RuleBasedExecutionPlanner()
        self.validator = ExecutionPlanValidator()

    def create_plan(self, goal: str) -> ExecutionPlan:
        plan = self.planner.create_plan(goal)
        self.validate(plan)
        self._save(plan)
        return plan

    def validate(self, plan: ExecutionPlan) -> ExecutionPlan:
        return self.validator.validate(plan)

    def export_json(self, plan: ExecutionPlan) -> str:
        self.validate(plan)
        return json.dumps(plan.to_dict(), ensure_ascii=False, indent=2)

    def show_plan(self, plan_id: str) -> ExecutionPlan:
        path = self._path(plan_id)
        if not path.is_file():
            raise PlanNotFoundError(f"execution plan not found: {plan_id}")
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
            plan = ExecutionPlan.from_dict(value)
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise ValueError("execution plan is invalid") from exc
        return self.validate(plan)

    def latest_plan(self) -> ExecutionPlan | None:
        if not self.directory.is_dir():
            return None
        plans: list[ExecutionPlan] = []
        for path in self.directory.glob("PLAN-*.json"):
            try:
                plans.append(self.show_plan(path.stem))
            except (OSError, ValueError):
                continue
        if not plans:
            return None
        return max(plans, key=lambda plan: (plan.created_at, plan.plan_id))

    def summary(self, plan: ExecutionPlan | None = None) -> dict[str, object]:
        value = plan or self.latest_plan()
        if value is None:
            return {
                "available": False, "plan_id": "unavailable",
                "goal": "unavailable", "total_tasks": 0,
                "completed": 0, "pending": 0,
            }
        completed = sum(task.status == "completed" for task in value.tasks)
        return {
            "available": True,
            "plan_id": value.plan_id,
            "goal": value.goal,
            "total_tasks": len(value.tasks),
            "completed": completed,
            "pending": len(value.tasks) - completed,
        }

    def _save(self, plan: ExecutionPlan) -> Path:
        self.directory.mkdir(parents=True, exist_ok=True)
        path = self._path(plan.plan_id)
        temporary = path.with_suffix(".json.tmp")
        temporary.write_text(self.export_json(plan), encoding="utf-8")
        temporary.replace(path)
        return path

    def _path(self, plan_id: str) -> Path:
        if not isinstance(plan_id, str) or not PLAN_ID_PATTERN.fullmatch(plan_id):
            raise PlanNotFoundError("execution plan not found")
        return self.directory / f"{plan_id}.json"
