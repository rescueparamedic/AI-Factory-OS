from __future__ import annotations

from typing import Dict, Any


class BaseAgent:
    agent_id = "base_agent"
    role = "Base Agent"

    def __init__(self):
        self.status = "idle"

    def profile(self) -> Dict[str, str]:
        return {
            "agent_id": self.agent_id,
            "role": self.role,
            "status": self.status,
        }

    def handle(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        self.status = "completed"
        return {
            "agent_id": self.agent_id,
            "status": self.status,
            "result": payload,
        }
