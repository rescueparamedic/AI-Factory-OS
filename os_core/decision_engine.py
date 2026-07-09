from __future__ import annotations

from typing import Dict, Any


class DecisionEngine:
    APPROVAL_REQUIRED_TYPES = {
        "external_api",
        "paid_service",
        "auto_deploy",
        "delete_files",
        "security_exception",
    }

    def evaluate(self, request: Dict[str, Any]) -> Dict[str, Any]:
        request_type = request.get("request_type", "mvp_boot")
        approval_required = request_type in self.APPROVAL_REQUIRED_TYPES

        return {
            "approved_to_create_task": not approval_required,
            "approval_required": approval_required,
            "risk_level": "low" if not approval_required else "medium",
            "reason": "Sprint 9-3 internal task" if not approval_required else "Owner approval required",
        }
