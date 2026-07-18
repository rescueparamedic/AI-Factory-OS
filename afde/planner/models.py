"""Execution Planner MVP data contracts."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Mapping


@dataclass
class ExecutionTask:
    task_id: str
    title: str
    description: str
    priority: str
    status: str = "pending"
    depends_on: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "ExecutionTask":
        return cls(
            task_id=str(value["task_id"]),
            title=str(value["title"]),
            description=str(value["description"]),
            priority=str(value["priority"]),
            status=str(value.get("status", "pending")),
            depends_on=[str(item) for item in value.get("depends_on", [])],
        )


@dataclass
class ExecutionPlan:
    plan_id: str
    goal: str
    created_at: str
    status: str = "pending"
    tasks: list[ExecutionTask] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "goal": self.goal,
            "created_at": self.created_at,
            "status": self.status,
            "tasks": [task.to_dict() for task in self.tasks],
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "ExecutionPlan":
        return cls(
            plan_id=str(value["plan_id"]),
            goal=str(value["goal"]),
            created_at=str(value["created_at"]),
            status=str(value.get("status", "pending")),
            tasks=[ExecutionTask.from_dict(item) for item in value.get("tasks", [])],
        )
