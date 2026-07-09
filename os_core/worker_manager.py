from __future__ import annotations

from pathlib import Path
from typing import Dict, Any, List

from workers.markdown_worker import MarkdownWorker
from workers.task_json_worker import TaskJsonWorker
from workers.audit_log_worker import AuditLogWorker
from workers.project_status_worker import ProjectStatusWorker
from workers.python_file_worker import PythonFileWorker
from workers.checkpoint_worker import CheckpointWorker


class WorkerManager:
    def __init__(self, base_path: Path):
        self.workers = {
            "markdown_worker": MarkdownWorker(base_path),
            "task_json_worker": TaskJsonWorker(base_path),
            "audit_log_worker": AuditLogWorker(base_path),
            "project_status_worker": ProjectStatusWorker(base_path),
            "python_file_worker": PythonFileWorker(base_path),
            "checkpoint_worker": CheckpointWorker(base_path),
        }

    def run(self, worker_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        worker = self.workers.get(worker_id)
        if worker is None:
            raise ValueError(f"Unknown worker_id: {worker_id}")
        return worker.run(payload)

    def list_workers(self) -> List[Dict[str, Any]]:
        return [worker.profile() for worker in self.workers.values()]
