from __future__ import annotations

from datetime import datetime
from pathlib import Path
import json
from typing import Dict, Any, List


VALID_STATUSES = {
    "created",
    "pending",
    "in_progress",
    "blocked",
    "needs_approval",
    "needs_revision",
    "testing",
    "security_review",
    "documentation",
    "ready_for_release",
    "done",
    "failed",
    "discarded",
}


class TaskEngine:
    def __init__(self, base_path: Path):
        self.base_path = base_path
        self.tasks_dir = base_path / "data" / "tasks"
        self.tasks_dir.mkdir(parents=True, exist_ok=True)

    def create_task(self, title: str, description: str, product_id: str, assigned_worker: str) -> Dict[str, Any]:
        now = datetime.now().astimezone()
        task_id = f"TASK-{now.strftime('%Y%m%d-%H%M%S')}"
        task = {
            "task_id": task_id,
            "title": title,
            "description": description,
            "product_id": product_id,
            "assigned_worker": assigned_worker,
            "status": "created",
            "created_at": now.isoformat(timespec="seconds"),
            "updated_at": now.isoformat(timespec="seconds"),
            "history": [
                {
                    "status": "created",
                    "timestamp": now.isoformat(timespec="seconds"),
                    "note": "Task created by TaskEngine",
                }
            ],
        }
        self.save_task(task)
        return task

    def save_task(self, task: Dict[str, Any]) -> Path:
        task["updated_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
        path = self.tasks_dir / f"{task['task_id']}.json"
        path.write_text(json.dumps(task, ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    def load_task(self, task_id: str) -> Dict[str, Any]:
        path = self.tasks_dir / f"{task_id}.json"
        if not path.exists():
            raise FileNotFoundError(f"Task not found: {task_id}")
        return json.loads(path.read_text(encoding="utf-8"))

    def list_tasks(self, limit: int = 20) -> List[Dict[str, Any]]:
        files = sorted(self.tasks_dir.glob("TASK-*.json"), reverse=True)
        tasks = []
        for file in files[:limit]:
            try:
                tasks.append(json.loads(file.read_text(encoding="utf-8")))
            except json.JSONDecodeError:
                continue
        return tasks

    def update_status(self, task_id: str, status: str, note: str = "") -> Dict[str, Any]:
        if status not in VALID_STATUSES:
            raise ValueError(f"Invalid status: {status}")

        task = self.load_task(task_id)
        now = datetime.now().astimezone()
        task["status"] = status
        task.setdefault("history", []).append(
            {
                "status": status,
                "timestamp": now.isoformat(timespec="seconds"),
                "note": note or f"Status manually changed to {status}",
            }
        )
        self.save_task(task)
        return task
