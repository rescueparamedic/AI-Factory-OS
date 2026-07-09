from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Dict
import json
import traceback


class BaseWorker:
    worker_id = "base_worker"
    worker_type = "base"
    team = "base_team"
    role = "Base Worker"
    permission_level = 1
    requires_approval = False
    log_required = True

    def __init__(self, base_path: Path):
        self.base_path = base_path
        self.results_dir = base_path / "data" / "worker_results"
        self.results_dir.mkdir(parents=True, exist_ok=True)

    def profile(self) -> Dict[str, Any]:
        return {
            "worker_id": self.worker_id,
            "worker_type": self.worker_type,
            "team": self.team,
            "role": self.role,
            "permission_level": self.permission_level,
            "requires_approval": self.requires_approval,
            "log_required": self.log_required,
        }

    def run(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        started_at = datetime.now().astimezone()
        try:
            output = self.execute(payload)
            status = "completed"
            error = None
        except Exception as exc:
            output = {}
            status = "failed"
            error = {
                "type": exc.__class__.__name__,
                "message": str(exc),
                "traceback": traceback.format_exc(),
            }

        finished_at = datetime.now().astimezone()
        result = {
            "result_id": f"WR-{finished_at.strftime('%Y%m%d-%H%M%S-%f')}",
            "worker_id": self.worker_id,
            "worker_type": self.worker_type,
            "team": self.team,
            "role": self.role,
            "status": status,
            "started_at": started_at.isoformat(timespec="seconds"),
            "finished_at": finished_at.isoformat(timespec="seconds"),
            "input": payload,
            "output": output,
            "error": error,
            "permission_level": self.permission_level,
            "requires_approval": self.requires_approval,
            "log_required": self.log_required,
        }

        saved_path = self._save_result(result)
        result["saved_path"] = str(saved_path)
        return result

    def execute(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError("Worker must implement execute().")

    def _save_result(self, result: Dict[str, Any]) -> Path:
        worker_dir = self.results_dir / self.worker_id
        worker_dir.mkdir(parents=True, exist_ok=True)
        path = worker_dir / f"{result['result_id']}.json"
        path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        return path
