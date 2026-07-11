from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from .audit import ApprovalAuditLogger
from .command_parser import CommandParseError, parse_commands
from .context import build_context
from .models import ApprovalDecision, ApprovalRequest, ApprovalResult
from .rules import RuleMatch, classify


_PRECEDENCE = {
    ApprovalDecision.AUTO_APPROVE: 0,
    ApprovalDecision.ASK_USER: 1,
    ApprovalDecision.DENY: 2,
}


class ApprovalGuardian:
    def __init__(self, repository_root: str | Path = ".", audit: bool = True) -> None:
        self.repository_root = Path(repository_root).resolve()
        self.audit_logger = ApprovalAuditLogger(self.repository_root) if audit else None

    def evaluate(self, request: ApprovalRequest) -> ApprovalResult:
        audit_request = request
        try:
            context = build_context(request, self.repository_root)
            audit_request = replace(request, cwd=str(context.cwd), branch=context.branch)
            commands = parse_commands(request.command)
            matches = [classify(command, context) for command in commands]
            selected = max(matches, key=lambda item: _PRECEDENCE[item.decision])
            normalized = " ; ".join(command.normalized for command in commands)
            result = self._result(selected, normalized)
        except (CommandParseError, OSError, ValueError) as exc:
            result = ApprovalResult(
                decision=ApprovalDecision.ASK_USER,
                risk_level="high",
                rule_id="AGV2-A999",
                reason=f"Command could not be classified safely: {exc}",
                normalized_command="[UNPARSEABLE]",
                requires_human=True,
            )
        except Exception:
            result = ApprovalResult(
                decision=ApprovalDecision.DENY,
                risk_level="critical",
                rule_id="AGV2-D004",
                reason="Approval evaluation failed closed.",
                normalized_command="[EVALUATION FAILED]",
                requires_human=False,
            )

        if self.audit_logger is not None:
            try:
                self.audit_logger.record(audit_request, result)
            except OSError:
                if result.decision is ApprovalDecision.DENY:
                    return result
                return ApprovalResult(
                    decision=ApprovalDecision.ASK_USER,
                    risk_level="high",
                    rule_id="AGV2-A999",
                    reason="Decision audit could not be recorded; user review is required.",
                    normalized_command=result.normalized_command,
                    requires_human=True,
                )
        return result

    @staticmethod
    def _result(match: RuleMatch, normalized: str) -> ApprovalResult:
        return ApprovalResult(
            decision=match.decision,
            risk_level=match.risk_level,
            rule_id=match.rule_id,
            reason=match.reason,
            normalized_command=normalized,
            requires_human=match.decision is ApprovalDecision.ASK_USER,
        )
