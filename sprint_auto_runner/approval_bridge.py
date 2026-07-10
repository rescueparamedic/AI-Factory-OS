from __future__ import annotations

from approval_guardian import ApprovalDecision, ApprovalGuardian, ApprovalRequest, ApprovalResult
from approval_guardian.command_parser import parse_commands

from .models import SprintStep


class ApprovalBridge:
    def __init__(self, guardian: ApprovalGuardian) -> None:
        self.guardian = guardian

    def evaluate(self, step: SprintStep, cwd: str, branch: str, run_id: str) -> ApprovalResult:
        try:
            if _pushes_protected_branch(step.command):
                return ApprovalResult(
                    decision=ApprovalDecision.DENY,
                    risk_level="critical",
                    rule_id="AGV2-D001",
                    reason="Sprint Auto Runner forbids direct push to main, master, or develop.",
                    normalized_command=step.command.strip(),
                    requires_human=False,
                )
            return self.guardian.evaluate(
                ApprovalRequest(
                    command=step.command,
                    cwd=cwd,
                    actor="sprint-auto-runner",
                    task_id=f"{run_id}:{step.step_id}",
                    branch=branch,
                    environment=step.environment,
                    metadata=step.metadata,
                )
            )
        except Exception:
            return ApprovalResult(
                decision=ApprovalDecision.DENY,
                risk_level="critical",
                rule_id="AGV2-D004",
                reason="Approval Guardian failed; runner stopped fail-closed.",
                normalized_command="[GUARDIAN FAILURE]",
                requires_human=False,
            )


def _pushes_protected_branch(command: str) -> bool:
    protected = {"main", "master", "develop"}
    for parsed in parse_commands(command):
        tokens = tuple(token.lower() for token in parsed.tokens)
        if tokens[:2] != ("git", "push"):
            continue
        values = [token for token in tokens[2:] if not token.startswith("-")]
        if len(values) >= 2 and values[1].split(":")[-1] in protected:
            return True
        if any(token.startswith(":") and token[1:] in protected for token in tokens[2:]):
            return True
    return False
