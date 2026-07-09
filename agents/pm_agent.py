from __future__ import annotations

from agents.base_agent import BaseAgent


class PMAgent(BaseAgent):
    agent_id = "pm_agent"
    role = "PM Agent"

    def plan(self, payload):
        self.status = "running"
        plan = {
            "plan_id": "PLAN-SPRINT-9-4",
            "summary": "Route task through Team Manager and Worker Manager",
            "recommended_team": "documentation_team",
            "target_worker": payload.get("assigned_worker", "markdown_worker"),
        }
        self.status = "completed"
        return {
            "agent_id": self.agent_id,
            "status": self.status,
            "plan": plan,
            "payload": payload,
        }
