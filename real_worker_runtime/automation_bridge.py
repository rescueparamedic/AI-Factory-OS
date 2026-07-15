from __future__ import annotations

from datetime import datetime
from hashlib import sha256
import json
import os
from pathlib import Path
from time import monotonic
from typing import Any

from approval_guardian import ApprovalDecision, ApprovalGuardian, ApprovalRequest

from .controlled_execution import (
    ActionType, ControlledExecutor, ExecutionRequest, RuntimeApprovalContext,
)
from .tool_actions import (
    ToolAction, ToolActionType, ToolActionValidationError, ToolExecutionResult,
)


def _inside(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _redact(value: str) -> str:
    import re
    value = re.sub(r"\bsk-[A-Za-z0-9_-]{8,}\b", "[REDACTED]", value)
    value = re.sub(r"(?i)(api[_-]?key|token|password|authorization)\s*[=:]\s*\S+", r"\1=[REDACTED]", value)
    return value[:4000]


class FileToolAdapter:
    def __init__(self, root: Path) -> None:
        self.root = root

    def read(self, action: ToolAction) -> dict[str, Any]:
        candidate = Path(action.target)
        target = (self.root / candidate).resolve() if not candidate.is_absolute() else candidate.resolve()
        if candidate.is_absolute() or not _inside(target, self.root) or ".git" in {p.lower() for p in target.relative_to(self.root).parts}:
            return {"status": "DENIED", "reason": "file read target is outside the governed workspace"}
        if target.name.lower() in {".env", "credentials.json", "id_rsa", "id_ed25519"} or target.suffix.lower() in {".pem", ".key", ".pfx", ".p12"}:
            return {"status": "DENIED", "reason": "credential-like files cannot be read"}
        if not target.is_file() or target.stat().st_size > 65536:
            return {"status": "DENIED", "reason": "file is missing or exceeds the 64 KiB read bound"}
        started = monotonic()
        content = _redact(target.read_text(encoding="utf-8"))
        return {
            "status": "SUCCEEDED", "relative_path": target.relative_to(self.root).as_posix(),
            "content": content, "content_sha256": sha256(target.read_bytes()).hexdigest(),
            "bytes_read": target.stat().st_size, "duration_ms": int((monotonic() - started) * 1000),
        }

    def write_request(self, action: ToolAction) -> ExecutionRequest:
        content = action.arguments.get("content")
        if not isinstance(content, str):
            raise ToolActionValidationError("FILE_WRITE arguments.content must be a string")
        expected = action.preconditions.get("expected_preimage_sha256")
        if expected is not None and not isinstance(expected, str):
            raise ToolActionValidationError("expected preimage hash must be a string")
        return ExecutionRequest(
            action.action_id, ActionType.FILE_WRITE, action.source_worker, action.purpose,
            relative_path=action.target, content=content, expected_preimage_sha256=expected,
        )


class CommandToolAdapter:
    def request(self, action: ToolAction) -> ExecutionRequest:
        argv = action.arguments.get("argv")
        if not isinstance(argv, list) or not all(isinstance(item, str) for item in argv):
            raise ToolActionValidationError("COMMAND_RUN arguments.argv must be a string array")
        return ExecutionRequest(action.action_id, ActionType.COMMAND_RUN, action.source_worker, action.purpose, argv=tuple(argv))


class TestToolAdapter(CommandToolAdapter):
    def request(self, action: ToolAction) -> ExecutionRequest:
        request = super().request(action)
        if tuple(item.lower() for item in request.argv[:3]) != ("python", "-m", "pytest"):
            raise ToolActionValidationError("TEST_RUN only accepts python -m pytest")
        return request


class GitToolAdapter:
    def request(self, action: ToolAction) -> ExecutionRequest:
        argv: list[str]
        if action.action_type is ToolActionType.GIT_STATUS:
            argv = ["git", "status", "--short"]
        elif action.action_type is ToolActionType.GIT_DIFF:
            argv = ["git", "diff", "--check"]
        elif action.action_type is ToolActionType.GIT_ADD:
            paths = action.arguments.get("paths")
            if not isinstance(paths, list) or not paths or not all(isinstance(item, str) for item in paths):
                raise ToolActionValidationError("GIT_ADD arguments.paths must be a non-empty string array")
            argv = ["git", "add", "--", *paths]
        elif action.action_type is ToolActionType.GIT_COMMIT:
            message = action.arguments.get("message")
            if not isinstance(message, str) or not message.strip() or "\n" in message:
                raise ToolActionValidationError("GIT_COMMIT arguments.message is invalid")
            argv = ["git", "commit", "-m", message]
        elif action.action_type is ToolActionType.GIT_PUSH_FEATURE:
            argv = ["git", "push", "origin", action.target]
        else:
            raise ToolActionValidationError("unsupported Git tool action")
        return ExecutionRequest(action.action_id, ActionType.COMMAND_RUN, action.source_worker, action.purpose, argv=tuple(argv))


class CodexAutomationBridge:
    """Canonical structured worker-action bridge; no raw-text command extraction."""

    def __init__(self, root: str | Path, executor: ControlledExecutor | None = None) -> None:
        self.root = Path(root).resolve()
        self.executor = executor or ControlledExecutor(self.root)
        self.guardian = ApprovalGuardian(self.root)
        self.files = FileToolAdapter(self.root)
        self.commands = CommandToolAdapter()
        self.tests = TestToolAdapter()
        self.git = GitToolAdapter()
        self.evidence_dir = self.root / "data" / "tool_action_evidence"

    @staticmethod
    def extract(output: Any) -> list[ToolAction]:
        if not isinstance(output, dict) or "actions" not in output:
            return []
        if not isinstance(output["actions"], list):
            raise ToolActionValidationError("actions must be an array")
        return [ToolAction.from_value(value) for value in output["actions"]]

    def execute(self, action: ToolAction | dict[str, Any], context: RuntimeApprovalContext) -> ToolExecutionResult:
        action = action if isinstance(action, ToolAction) else ToolAction.from_value(action)
        duplicate = self._claim(action)
        if duplicate is not None:
            self._persist_duplicate(action, duplicate)
            return duplicate
        try:
            self._bind_context(action, context)
            if action.action_type is ToolActionType.FILE_READ:
                evidence = self._read(action, context)
                request = None
            else:
                request = self._request(action)
                evidence = self.executor.execute(request, context)
            result = ToolExecutionResult(
                action.action_id, action.fingerprint, action.action_type.value,
                str(evidence.get("status", "DENIED")), str(evidence.get("decision", evidence.get("approval_decision", "deny"))),
                evidence, request,
            )
        except Exception as exc:
            evidence = {"status": "DENIED", "decision": "deny", "reason": "tool action failed closed", "safe_cause": _redact(str(exc))}
            result = ToolExecutionResult(action.action_id, action.fingerprint, action.action_type.value, "DENIED", "deny", evidence)
        self._persist(action, result)
        return result

    def execute_output(self, output: Any, context: RuntimeApprovalContext) -> list[ToolExecutionResult]:
        return [self.execute(action, context) for action in self.extract(output)]

    def status(self, action_id: str) -> dict[str, Any]:
        if not isinstance(action_id, str) or not action_id or any(item in action_id for item in ('/', '\\', '..')):
            raise ValueError("invalid action_id")
        path = self.evidence_dir / f"{action_id}.json"
        if not path.is_file():
            raise FileNotFoundError(f"tool action evidence not found: {action_id}")
        return json.loads(path.read_text(encoding="utf-8"))

    def _bind_context(self, action: ToolAction, context: RuntimeApprovalContext) -> None:
        normalized = context.normalized()
        expected = {
            "cwd": str(Path(action.cwd).resolve()), "repository": str(Path(action.repository).resolve()),
            "branch": action.branch, "runtime_task_id": action.runtime_task_id,
            "runtime_session_id": action.runtime_session_id, "stage": action.stage,
            "actor": action.source_worker,
        }
        for key, value in expected.items():
            if normalized[key] != value:
                raise ToolActionValidationError(f"tool action {key} context mismatch")
        if int(action.revision) != int(normalized["metadata"].get("revision", 0)):
            raise ToolActionValidationError("tool action revision context mismatch")

    def _request(self, action: ToolAction) -> ExecutionRequest:
        if action.action_type is ToolActionType.FILE_WRITE:
            return self.files.write_request(action)
        if action.action_type is ToolActionType.COMMAND_RUN:
            return self.commands.request(action)
        if action.action_type is ToolActionType.TEST_RUN:
            return self.tests.request(action)
        return self.git.request(action)

    def _read(self, action: ToolAction, context: RuntimeApprovalContext) -> dict[str, Any]:
        result = self.guardian.evaluate(ApprovalRequest(
            command=f"Get-Content {action.target}", cwd=context.cwd, actor=action.source_worker,
            task_id=action.runtime_task_id, branch=action.branch, environment=context.environment,
        ))
        if result.decision is not ApprovalDecision.AUTO_APPROVE:
            return {"status": "DENIED" if result.decision is ApprovalDecision.DENY else "WAITING_APPROVAL", "decision": result.decision.value, "rule_id": result.rule_id, "reason": result.reason}
        evidence = self.files.read(action)
        evidence.update({"decision": result.decision.value, "rule_id": result.rule_id, "reason": result.reason})
        return evidence

    def _claim(self, action: ToolAction) -> ToolExecutionResult | None:
        self.evidence_dir.mkdir(parents=True, exist_ok=True)
        claim = self.evidence_dir / f"{action.action_id}.claim"
        try:
            descriptor = os.open(claim, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                stream.write(action.fingerprint)
            return None
        except FileExistsError:
            evidence = {"status": "DUPLICATE", "decision": "deny", "reason": "action_id was already claimed"}
            return ToolExecutionResult(action.action_id, action.fingerprint, action.action_type.value, "DUPLICATE", "deny", evidence)

    def _persist(self, action: ToolAction, result: ToolExecutionResult) -> None:
        record = {"recorded_at": datetime.now().astimezone().isoformat(timespec="seconds"), "action": _evidence_action(action), "result": result.to_dict()}
        (self.evidence_dir / f"{action.action_id}.json").write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
        with (self.evidence_dir / "ledger.jsonl").open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")

    def _persist_duplicate(self, action: ToolAction, result: ToolExecutionResult) -> None:
        record = {"recorded_at": datetime.now().astimezone().isoformat(timespec="seconds"), "action": _evidence_action(action), "result": result.to_dict()}
        with (self.evidence_dir / "ledger.jsonl").open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def _safe_value(value: Any) -> Any:
    if isinstance(value, str):
        return _redact(value)
    if isinstance(value, dict):
        return {str(key): _safe_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_safe_value(item) for item in value]
    return value if isinstance(value, (int, float, bool, type(None))) else _redact(str(value))


def _evidence_action(action: ToolAction) -> dict[str, Any]:
    value = action.to_dict()
    content = value["arguments"].pop("content", None)
    if isinstance(content, str):
        payload = content.encode("utf-8")
        value["arguments"].update({
            "content_sha256": sha256(payload).hexdigest(), "content_bytes": len(payload),
        })
    return _safe_value(value)
