from __future__ import annotations

from agents.base_agent import BaseAgent


class CEOAgent(BaseAgent):
    agent_id = "ceo_agent"
    role = "CEO Agent"

    def decide(self, payload):
        self.status = "running"
        decision = {
            "decision": "approved_for_pm_planning",
            "reason": "Sprint 9-4 internal OS architecture task",
            "priority": "high",
            "approval_required": False,
        }
        self.status = "completed"
        return {
            "agent_id": self.agent_id,
            "status": self.status,
            "decision": decision,
            "payload": payload,
        }
