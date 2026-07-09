from __future__ import annotations

from typing import Dict, Any
from workers.base_worker import BaseWorker
import json


class TaskJsonWorker(BaseWorker):
    worker_id = "task_json_worker"
    worker_type = "json_worker"
    team = "development_team"
    role = "Task JSON 생성"
    permission_level = 2
    requires_approval = False
    log_required = True

    def execute(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        path = self.base_path / payload.get("path", "data/tasks/task_worker_output.json")
        path.parent.mkdir(parents=True, exist_ok=True)
        data = payload.get("data", payload)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return {
            "created_file": str(path),
            "json_keys": list(data.keys()) if isinstance(data, dict) else [],
        }
