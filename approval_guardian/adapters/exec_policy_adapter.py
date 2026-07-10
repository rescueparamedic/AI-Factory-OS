from __future__ import annotations

from dataclasses import dataclass

from ..models import ApprovalDecision, ApprovalResult


@dataclass(frozen=True)
class ExecPolicyAdapter:
    """Map Codex Safe Approval Policy v1 decisions to Guardian v2 results."""

    _MAPPING = {
        "allow": ApprovalDecision.AUTO_APPROVE,
        "prompt": ApprovalDecision.ASK_USER,
        "forbidden": ApprovalDecision.DENY,
    }

    def adapt(
        self,
        decision: str,
        command: str,
        justification: str = "ExecPolicy compatibility decision.",
    ) -> ApprovalResult:
        mapped = self._MAPPING.get(decision.lower(), ApprovalDecision.ASK_USER)
        return ApprovalResult(
            decision=mapped,
            risk_level={
                ApprovalDecision.AUTO_APPROVE: "low",
                ApprovalDecision.ASK_USER: "medium",
                ApprovalDecision.DENY: "critical",
            }[mapped],
            rule_id={
                ApprovalDecision.AUTO_APPROVE: "AGV2-S001",
                ApprovalDecision.ASK_USER: "AGV2-A999",
                ApprovalDecision.DENY: "AGV2-D001",
            }[mapped],
            reason=justification,
            normalized_command=command.strip(),
            requires_human=mapped is ApprovalDecision.ASK_USER,
        )
