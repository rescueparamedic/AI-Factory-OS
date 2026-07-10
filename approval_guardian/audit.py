from __future__ import annotations

from datetime import datetime
from hashlib import sha256
import json
from pathlib import Path
import re
from typing import Any

from .models import ApprovalRequest, ApprovalResult


_SECRET_PATTERNS = (
    re.compile(r"(?i)(api[_-]?key|token|password|credential)\s*[=:]\s*([^\s]+)"),
    re.compile(r"(?i)(authorization:\s*(?:bearer|basic))\s+([^\s]+)"),
)


class ApprovalAuditLogger:
    """Write Guardian decisions into the existing JSON audit directory."""

    def __init__(self, repository_root: str | Path) -> None:
        self.audit_dir = Path(repository_root) / "data" / "audit"

    def record(self, request: ApprovalRequest, result: ApprovalResult) -> Path:
        self.audit_dir.mkdir(parents=True, exist_ok=True)
        now = datetime.now().astimezone()
        redacted = redact_command(result.normalized_command)
        record: dict[str, Any] = {
            "event": "APPROVAL_GUARDIAN_DECISION",
            "decision": result.decision.value,
            "risk_level": result.risk_level,
            "rule_id": result.rule_id,
            "reason": result.reason,
            "actor": request.actor or "unknown",
            "task_id": request.task_id or "",
            "command": redacted,
            "command_fingerprint": command_fingerprint(result.normalized_command),
            "cwd": request.cwd or "",
            "branch": request.branch or "",
            "timestamp": now.isoformat(timespec="seconds"),
        }
        audit_id = f"AUD-AGV2-{now.strftime('%Y%m%d-%H%M%S-%f')}"
        path = self.audit_dir / f"{audit_id}.json"
        path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
        return path


def command_fingerprint(command: str) -> str:
    return sha256(command.encode("utf-8")).hexdigest()


def redact_command(command: str) -> str:
    redacted = command
    for pattern in _SECRET_PATTERNS:
        redacted = pattern.sub(lambda match: f"{match.group(1)}=[REDACTED]", redacted)
    if ".env" in redacted.lower():
        return "[REDACTED SENSITIVE COMMAND]"
    return redacted
