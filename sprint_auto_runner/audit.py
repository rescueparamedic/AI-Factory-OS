from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from typing import Any
from uuid import uuid4

from approval_guardian.audit import command_fingerprint, redact_command


class SprintAuditLogger:
    def __init__(self, repository_root: str | Path) -> None:
        self.run_dir = Path(repository_root) / "data" / "sprint_runs"
        self.run_dir.mkdir(parents=True, exist_ok=True)

    def record(self, run_id: str, event: str, **fields: Any) -> Path:
        path = self.run_dir / f"{run_id}.audit.jsonl"
        command = str(fields.pop("command", ""))
        payload = {
            "event_id": f"EVT-SPR-{uuid4().hex}",
            "timestamp": datetime.now().astimezone().isoformat(timespec="seconds"),
            "event": event,
            "run_id": run_id,
            "sprint_id": fields.pop("sprint_id", ""),
            "step_id": fields.pop("step_id", ""),
            "actor": fields.pop("actor", "sprint-auto-runner"),
            "decision": fields.pop("decision", ""),
            "rule_id": fields.pop("rule_id", ""),
            "reason": fields.pop("reason", ""),
            "cwd": fields.pop("cwd", ""),
            "branch": fields.pop("branch", ""),
            "environment": fields.pop("environment", ""),
            "command_fingerprint": command_fingerprint(command) if command else "",
            "redacted_command": redact_command(command) if command else "",
            "exit_code": fields.pop("exit_code", None),
            "duration_ms": fields.pop("duration_ms", None),
            "result": fields.pop("result", ""),
            **fields,
        }
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
        return path
