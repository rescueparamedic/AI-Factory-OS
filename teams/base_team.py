from __future__ import annotations

from typing import Dict, Any


class BaseTeam:
    team_id = "base_team"
    role = "Base Team"

    def __init__(self, worker_manager):
        self.worker_manager = worker_manager
        self.status = "idle"

    def profile(self):
        return {
            "team_id": self.team_id,
            "role": self.role,
            "status": self.status,
        }

    def execute(self, worker_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        self.status = "running"
        result = self.worker_manager.run(worker_id, payload)
        self.status = "completed"
        return {
            "team_id": self.team_id,
            "status": self.status,
            "worker_result": result,
        }
