from __future__ import annotations

from datetime import datetime
from typing import Dict, Any


class WorkflowEngine:
    ALLOWED_TRANSITIONS = {
        "created": "pending",
        "pending": "in_progress",
        "in_progress": "testing",
        "testing": "security_review",
        "security_review": "documentation",
        "documentation": "done",
    }

    def move_next(self, task: Dict[str, Any], note: str = "") -> Dict[str, Any]:
        current = task.get("status", "created")
        next_status = self.ALLOWED_TRANSITIONS.get(current)

        if not next_status:
            task.setdefault("history", []).append(
                {
                    "status": current,
                    "timestamp": datetime.now().astimezone().isoformat(timespec="seconds"),
                    "note": f"No next workflow transition from {current}",
                }
            )
            return task

        task["status"] = next_status
        task.setdefault("history", []).append(
            {
                "status": next_status,
                "timestamp": datetime.now().astimezone().isoformat(timespec="seconds"),
                "note": note or f"Workflow moved {current} -> {next_status}",
            }
        )
        return task

    def run_until(self, task: Dict[str, Any], target_status: str) -> Dict[str, Any]:
        safety_count = 0
        while task.get("status") != target_status and safety_count < 10:
            before = task.get("status")
            task = self.move_next(task)
            after = task.get("status")
            if before == after:
                break
            safety_count += 1
        return task
