from __future__ import annotations

from dataclasses import dataclass, field
import ast
from datetime import datetime
from enum import Enum
from hashlib import sha256
import json
from pathlib import Path
import re
import subprocess
import sys
from time import monotonic
from typing import Any, Callable, Mapping
from uuid import uuid4

from approval_guardian import (
    ApprovalDecision, ApprovalGuardian, ApprovalRequest, ApprovalResult,
)
from approval_guardian.audit import command_fingerprint, redact_command


SAFE_EXECUTION_DIR = "controlled_execution"
_TEXT_SUFFIXES = {".py", ".md", ".txt", ".json", ".yaml", ".yml"}
_SECRET_NAMES = {".env", "credentials.json", "id_rsa", "id_ed25519"}
_SHELLS = {"powershell", "powershell.exe", "pwsh", "cmd", "cmd.exe", "bash", "sh"}
_NETWORK = {"curl", "curl.exe", "wget", "ssh", "scp", "ftp", "invoke-webrequest"}
_META = {"|", "||", "&&", ";", ">", ">>", "<"}


class ActionType(str, Enum):
    FILE_WRITE = "FILE_WRITE"
    COMMAND_RUN = "COMMAND_RUN"


@dataclass(frozen=True)
class ExecutionRequest:
    request_id: str
    action_type: ActionType
    source_worker: str
    purpose: str
    relative_path: str | None = None
    content: str | None = None
    argv: tuple[str, ...] = ()
    expected_preimage_sha256: str | None = None

    @classmethod
    def file_write(cls, relative_path: str, content: str, source_worker: str, purpose: str, expected_preimage_sha256: str | None = None) -> "ExecutionRequest":
        return cls(f"EXE-{uuid4().hex}", ActionType.FILE_WRITE, source_worker, _sanitize(purpose)[:255], relative_path, content, expected_preimage_sha256=expected_preimage_sha256)

    @classmethod
    def command_run(cls, argv: list[str], source_worker: str, purpose: str) -> "ExecutionRequest":
        return cls(f"EXE-{uuid4().hex}", ActionType.COMMAND_RUN, source_worker, _sanitize(purpose)[:255], argv=tuple(argv))


@dataclass(frozen=True)
class PolicyResult:
    decision: str
    classification: str
    reason: str
    safe_representation: str
    resolved_target: str | None = None


@dataclass(frozen=True)
class RuntimeApprovalContext:
    """Normalized execution-boundary context; policy remains Guardian-owned."""

    cwd: str
    repository: str
    branch: str
    environment: str
    runtime_task_id: str = ""
    runtime_session_id: str = ""
    stage: str = "runtime"
    actor: str = "controlled-runtime"
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def normalized(self) -> dict[str, Any]:
        return {
            "cwd": str(Path(self.cwd).resolve()),
            "repository": str(Path(self.repository).resolve()),
            "branch": str(self.branch or ""),
            "environment": str(self.environment or "dev").lower(),
            "runtime_task_id": str(self.runtime_task_id or ""),
            "runtime_session_id": str(self.runtime_session_id or ""),
            "stage": str(self.stage or "runtime"),
            "actor": str(self.actor or "controlled-runtime"),
            "metadata": _safe_metadata(self.metadata),
        }


def context_fingerprint(context: RuntimeApprovalContext) -> str:
    encoded = json.dumps(
        context.normalized(), ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    )
    return sha256(encoded.encode("utf-8")).hexdigest()


def build_runtime_approval_context(
    root: str | Path, *, runtime_task_id: str = "",
    runtime_session_id: str = "", stage: str = "runtime",
    actor: str = "controlled-runtime", environment: str = "local",
    metadata: Mapping[str, Any] | None = None,
) -> RuntimeApprovalContext:
    repository = Path(root).resolve()
    return RuntimeApprovalContext(
        cwd=str(repository), repository=str(repository),
        branch=_git_branch(repository), environment=environment,
        runtime_task_id=runtime_task_id,
        runtime_session_id=runtime_session_id,
        stage=stage, actor=actor, metadata=metadata,
    )


class ControlledExecutionPolicy:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).resolve()

    def classify(self, request: ExecutionRequest) -> PolicyResult:
        if request.action_type is ActionType.FILE_WRITE:
            return self._file_write(request)
        if request.action_type is ActionType.COMMAND_RUN:
            return self._command(request)
        return PolicyResult("DENY", "UNSUPPORTED_ACTION", "Unsupported action type.", "[DENIED]")

    def _file_write(self, request: ExecutionRequest) -> PolicyResult:
        raw = request.relative_path or ""
        candidate = Path(raw)
        safe_repr = f"afde-controlled-file-write {raw}"
        if not raw or candidate.is_absolute():
            return PolicyResult("DENY", "INVALID_PATH", "File path must be relative.", safe_repr)
        target = (self.root / candidate).resolve()
        if not _inside(target, self.root):
            return PolicyResult("DENY", "WORKSPACE_ESCAPE", "File target escapes the workspace.", safe_repr)
        relative = target.relative_to(self.root)
        lowered = {part.lower() for part in relative.parts}
        if ".git" in lowered:
            return PolicyResult("DENY", "GIT_METADATA_TARGET", ".git writes are forbidden.", safe_repr)
        if _secret_target(relative) or _contains_secret(request.content or ""):
            return PolicyResult("DENY", "SECRET_TARGET_OR_CONTENT", "Credential targets or content are forbidden.", safe_repr)
        if request.content is None or len(request.content.encode("utf-8")) > 65536 or "\x00" in request.content:
            return PolicyResult("DENY", "INVALID_TEXT_CONTENT", "Text content is missing or exceeds the 64 KiB bound.", safe_repr)
        if target.suffix.lower() not in _TEXT_SUFFIXES:
            return PolicyResult("DENY", "UNSUPPORTED_SUFFIX", "File suffix is not allowlisted.", safe_repr)
        if target.exists():
            return PolicyResult("ASK_USER", "EXISTING_FILE_REPLACEMENT", "Replacing an existing file requires approval.", safe_repr, str(target))
        if not relative.parts or relative.parts[0].lower() != SAFE_EXECUTION_DIR:
            return PolicyResult("ASK_USER", "OUTSIDE_EXECUTION_SANDBOX", "New files outside the execution sandbox require approval.", safe_repr, str(target))
        return PolicyResult("AUTO_APPROVE", "SAFE_NEW_SANDBOX_FILE", "New allowlisted text file in the execution sandbox.", safe_repr, str(target))

    def _command(self, request: ExecutionRequest) -> PolicyResult:
        argv = request.argv
        safe_repr = " ".join(argv)
        if not argv or len(argv) > 20 or any(not isinstance(item, str) or not item or len(item) > 255 for item in argv):
            return PolicyResult("DENY", "INVALID_ARGV", "Command argv is invalid or unbounded.", safe_repr)
        lowered = tuple(item.lower() for item in argv)
        if lowered[0] in _SHELLS:
            return PolicyResult("DENY", "SHELL_INVOCATION", "Shell invocation is forbidden.", safe_repr)
        if lowered[0] in _NETWORK:
            return PolicyResult("DENY", "NETWORK_COMMAND", "Network commands are forbidden.", safe_repr)
        if _contains_secret(" ".join(argv)):
            return PolicyResult("DENY", "SECRET_COMMAND_ARGUMENT", "Credential-like command arguments are forbidden.", safe_repr)
        if lowered[0] in {"pip", "npm", "python3", "python.exe"} and lowered[:3] != ("python.exe", "-m", "pytest"):
            return PolicyResult("DENY", "UNSUPPORTED_EXECUTABLE", "Executable is not in the MVP allowlist.", safe_repr)
        if any(item in _META or any(char in item for char in "\r\n") for item in argv):
            return PolicyResult("DENY", "COMMAND_COMPOSITION", "Chaining, redirection, and control operators are forbidden.", safe_repr)
        if lowered == ("python", "--version"):
            return PolicyResult("AUTO_APPROVE", "SAFE_PYTHON_VERSION", "Allowlisted local version check.", safe_repr)
        if lowered in {("git", "status", "--short"), ("git", "diff", "--check")}:
            return PolicyResult("AUTO_APPROVE", "SAFE_GIT_INSPECTION", "Allowlisted read-only Git inspection.", safe_repr)
        if len(argv) >= 4 and lowered[:3] == ("git", "add", "--"):
            if all(_safe_git_path(item, self.root) for item in argv[3:]):
                return PolicyResult("AUTO_APPROVE", "SAFE_GIT_ADD", "Explicit workspace-contained paths may be staged on a feature branch.", safe_repr)
            return PolicyResult("DENY", "UNSAFE_GIT_PATH", "Git staging paths must be explicit and workspace-contained.", safe_repr)
        branch = _git_branch(self.root)
        if len(argv) == 4 and lowered[:3] == ("git", "commit", "-m"):
            if branch.startswith("feature/") and "\n" not in argv[3]:
                return PolicyResult("AUTO_APPROVE", "SAFE_FEATURE_COMMIT", "Bounded commit on the current feature branch.", safe_repr)
            return PolicyResult("DENY", "PROTECTED_OR_INVALID_COMMIT", "Commits require the current feature branch and one message.", safe_repr)
        if len(argv) == 4 and lowered[:3] == ("git", "push", "origin"):
            if branch.startswith("feature/") and argv[3] == branch:
                return PolicyResult("AUTO_APPROVE", "SAFE_FEATURE_PUSH", "Exact current feature branch push is allowlisted.", safe_repr)
            return PolicyResult("DENY", "PROTECTED_OR_MISMATCHED_PUSH", "Push must target the exact current feature branch.", safe_repr)
        if len(argv) >= 3 and lowered[:3] == ("python", "-m", "pytest"):
            if all(_safe_pytest_arg(item, self.root) for item in argv[3:]):
                return PolicyResult("AUTO_APPROVE", "SAFE_PYTEST", "Allowlisted bounded pytest command.", safe_repr)
            return PolicyResult("DENY", "UNSAFE_PYTEST_ARGUMENT", "pytest argument is outside the bounded allowlist.", safe_repr)
        if len(argv) == 2 and lowered[0] == "python":
            script = Path(argv[1])
            target = (self.root / script).resolve() if not script.is_absolute() else script.resolve()
            sandbox = self.root / SAFE_EXECUTION_DIR
            if script.suffix.lower() == ".py" and _inside(target, sandbox.resolve()) and target.is_file() and _safe_python_script(target):
                return PolicyResult("AUTO_APPROVE", "SAFE_SANDBOX_PYTHON", "Allowlisted workspace-contained Python script.", safe_repr, str(target))
        if lowered[0] == "git":
            return PolicyResult("DENY", "UNSUPPORTED_EXECUTABLE", "Git command is outside the bounded automation allowlist.", safe_repr)
        return PolicyResult("DENY", "UNSUPPORTED_COMMAND", "Command is not exactly allowlisted.", safe_repr)


class ControlledExecutor:
    def __init__(
        self, root: str | Path, timeout_seconds: float = 30.0,
        runner: Callable[..., Any] = subprocess.run,
    ) -> None:
        self.root = Path(root).resolve()
        self.policy = ControlledExecutionPolicy(self.root)
        self.guardian = ApprovalGuardian(self.root)
        self.timeout_seconds = timeout_seconds
        self.runner = runner
        self.evidence_dir = self.root / "data" / "execution_evidence"

    def execute(
        self, request: ExecutionRequest,
        context: RuntimeApprovalContext | None = None,
    ) -> dict[str, Any]:
        try:
            normalized_context = self._context(request, context)
            policy = self.policy.classify(request)
        except Exception as exc:
            return self._failed_closed(request, "CONTEXT_OR_POLICY_FAILURE", exc, context)
        if policy.decision == "DENY":
            return self._persist(request, policy, None, "DENIED", normalized_context)
        try:
            guardian = self.guardian.evaluate(ApprovalRequest(
                command=policy.safe_representation,
                cwd=normalized_context.cwd,
                actor=normalized_context.actor,
                task_id=normalized_context.runtime_task_id or request.request_id,
                branch=normalized_context.branch or None,
                environment=normalized_context.environment,
                metadata=normalized_context.normalized()["metadata"],
            ))
            if not isinstance(guardian, ApprovalResult) or not isinstance(
                guardian.decision, ApprovalDecision
            ):
                raise ValueError("Approval Guardian returned an invalid decision")
        except Exception as exc:
            return self._failed_closed(request, "GUARDIAN_FAILURE", exc, normalized_context)
        if guardian.decision is ApprovalDecision.DENY:
            return self._persist(request, policy, guardian, "DENIED", normalized_context)
        approval_needed = policy.decision == "ASK_USER" or guardian.decision is ApprovalDecision.ASK_USER
        if approval_needed:
            return self._persist(
                request, policy, guardian, "WAITING_APPROVAL", normalized_context,
            )
        authorized = self._base(request, policy, "AUTO_APPROVED", normalized_context)
        authorized.update(self._approval_fields(policy, guardian, normalized_context))
        try:
            self._persist_raw(authorized)
        except OSError as exc:
            return self._failed_closed(
                request, "AUDIT_RECORD_FAILURE", exc, normalized_context,
                persist=False,
            )
        if request.action_type is ActionType.FILE_WRITE:
            execution = self._write_file(request, policy)
        else:
            execution = self._run_command(request, policy)
        evidence = {**authorized, **execution}
        evidence.update(self._approval_fields(policy, guardian, normalized_context))
        try:
            return self._persist_raw(evidence)
        except OSError as exc:
            evidence["status"] = "AUDIT_FAILURE_AFTER_EXECUTION"
            evidence["safe_cause"] = _sanitize(str(exc))
            evidence["error_code"] = "RUNTIME_CONTROLLED_EXECUTION_BLOCKED"
            return evidence

    def execute_approved(
        self, request: ExecutionRequest, approval_record: dict[str, Any],
        context: RuntimeApprovalContext | None = None,
    ) -> dict[str, Any]:
        from .approval_resume import APPROVED, request_from_record
        if approval_record.get("status") != APPROVED:
            raise ValueError("an exact persisted APPROVED record is required")
        bound_request = request_from_record(approval_record)
        from .approval_resume import fingerprint_matches
        if bound_request != request or not fingerprint_matches(request, approval_record.get("action_fingerprint")):
            raise ValueError("approved execution request binding mismatch")
        normalized_context = self._context(request, context)
        if approval_record.get("context_fingerprint") != context_fingerprint(normalized_context):
            raise ValueError("approved execution context fingerprint mismatch")
        try:
            policy = self.policy.classify(request)
        except Exception as exc:
            return self._failed_closed(
                request, "POLICY_REVALIDATION_FAILURE", exc, normalized_context,
            )
        if policy.decision != "ASK_USER" or policy.classification != "EXISTING_FILE_REPLACEMENT":
            return self._persist(request, policy, None, "DENIED", normalized_context)
        try:
            guardian = self.guardian.evaluate(ApprovalRequest(
                command=policy.safe_representation, cwd=normalized_context.cwd,
                actor="approved-runtime-resume",
                task_id=normalized_context.runtime_task_id or request.request_id,
                branch=normalized_context.branch or None,
                environment=normalized_context.environment,
                metadata=normalized_context.normalized()["metadata"],
            ))
        except Exception as exc:
            return self._failed_closed(
                request, "GUARDIAN_REVALIDATION_FAILURE", exc, normalized_context,
            )
        if not isinstance(guardian, ApprovalResult) or guardian.decision is not ApprovalDecision.ASK_USER:
            return self._persist(request, policy, guardian, "DENIED", normalized_context)
        execution = self._write_file(request, policy)
        evidence = {
            **self._base(request, policy, execution["status"], normalized_context),
            **execution,
        }
        evidence.update(self._approval_fields(policy, guardian, normalized_context))
        evidence["approval_decision"] = "human_approved"
        evidence["approval_state"] = "consumption_pending"
        evidence["approved_by"] = approval_record.get("approved_by", "Product Owner")
        evidence["approved_at"] = approval_record.get("approved_at")
        evidence["revalidation_result"] = "matched"
        try:
            return self._persist_raw(evidence)
        except OSError as exc:
            evidence["status"] = "AUDIT_FAILURE_AFTER_EXECUTION"
            evidence["safe_cause"] = _sanitize(str(exc))
            evidence["error_code"] = "RUNTIME_CONTROLLED_EXECUTION_BLOCKED"
            return evidence

    def _write_file(self, request: ExecutionRequest, policy: PolicyResult) -> dict[str, Any]:
        target = Path(policy.resolved_target or "")
        before_exists = target.exists()
        before_hash = _file_hash(target) if before_exists else None
        if before_exists and request.expected_preimage_sha256 != before_hash:
            return self._base(request, policy, "PREIMAGE_MISMATCH") | {
                "relative_path": target.relative_to(self.root).as_posix(),
                "before_exists": True, "before_sha256": before_hash,
                "expected_preimage_sha256": request.expected_preimage_sha256,
                "after_exists": True, "after_sha256": before_hash, "changed": False,
            }
        target.parent.mkdir(parents=True, exist_ok=True)
        approved_bytes = (request.content or "").encode("utf-8")
        target.write_bytes(approved_bytes)
        after_hash = _file_hash(target)
        changed = not before_exists or before_hash != after_hash
        return self._base(request, policy, "SUCCEEDED" if changed else "NO_CHANGE") | {
            "relative_path": target.relative_to(self.root).as_posix(),
            "before_exists": before_exists, "before_sha256": before_hash,
            "after_exists": target.is_file(), "after_sha256": after_hash, "changed": changed,
            "approved_payload_sha256": sha256(approved_bytes).hexdigest(),
        }

    def _run_command(self, request: ExecutionRequest, policy: PolicyResult) -> dict[str, Any]:
        started = datetime.now().astimezone(); clock = monotonic(); timed_out = False
        execution_argv = list(request.argv) if request.argv and request.argv[0].lower() == 'git' else [sys.executable, *request.argv[1:]]
        try:
            completed = self.runner(
                execution_argv, cwd=self.root, capture_output=True, text=True,
                timeout=self.timeout_seconds, shell=False,
            )
            exit_code = int(completed.returncode); stdout = completed.stdout or ""; stderr = completed.stderr or ""
        except subprocess.TimeoutExpired as exc:
            timed_out = True; exit_code = 124; stdout = _as_text(exc.stdout); stderr = _as_text(exc.stderr) or "Command timed out."
        completed_at = datetime.now().astimezone()
        return self._base(request, policy, "SUCCEEDED" if exit_code == 0 else "FAILED") | {
            "argv": list(request.argv), "started_at": started.isoformat(timespec="seconds"),
            "completed_at": completed_at.isoformat(timespec="seconds"),
            "duration_ms": int((monotonic() - clock) * 1000), "exit_code": exit_code,
            "timed_out": timed_out, "stdout": _sanitize(stdout), "stderr": _sanitize(stderr),
        }

    def _base(
        self, request: ExecutionRequest, policy: PolicyResult, status: str,
        context: RuntimeApprovalContext | None = None,
    ) -> dict[str, Any]:
        value = {"request_id": request.request_id, "action_type": request.action_type.value,
                "source_worker": request.source_worker, "purpose": request.purpose,
                "policy_classification": policy.classification, "status": status}
        if context is not None:
            normalized = context.normalized()
            value.update({
                "actor": normalized["actor"], "stage": normalized["stage"],
                "runtime_task_id": normalized["runtime_task_id"],
                "runtime_session_id": normalized["runtime_session_id"],
                "action_fingerprint": execution_action_fingerprint(request),
                "context_fingerprint": context_fingerprint(context),
                "normalized_context": normalized,
                "approval_timestamp": datetime.now().astimezone().isoformat(timespec="seconds"),
                "approval_state": "evaluated",
            })
        return value

    def _persist(
        self, request: ExecutionRequest, policy: PolicyResult, guardian: Any,
        status: str, context: RuntimeApprovalContext,
    ) -> dict[str, Any]:
        evidence = self._base(request, policy, status, context)
        evidence.update(self._approval_fields(policy, guardian, context))
        try:
            return self._persist_raw(evidence)
        except OSError as exc:
            return self._failed_closed(
                request, "AUDIT_RECORD_FAILURE", exc, context, persist=False,
            )

    def _approval_fields(self, policy, guardian, context) -> dict[str, Any]:
        guardian_decision = (
            guardian.decision if isinstance(guardian, ApprovalResult) else None
        )
        if policy.decision == "DENY" or guardian_decision is ApprovalDecision.DENY:
            decision = ApprovalDecision.DENY.value
        elif policy.decision == "ASK_USER" or guardian_decision is ApprovalDecision.ASK_USER:
            decision = ApprovalDecision.ASK_USER.value
        else:
            decision = ApprovalDecision.AUTO_APPROVE.value
        policy_controls = policy.decision in {"DENY", "ASK_USER"} and (
            guardian_decision is None or guardian_decision is ApprovalDecision.AUTO_APPROVE
        )
        rule_id = (
            f"CE-{policy.classification}"
            if policy_controls else guardian.rule_id
            if isinstance(guardian, ApprovalResult) else f"CE-{policy.classification}"
        )
        reason = (
            policy.reason if policy_controls else guardian.reason
            if isinstance(guardian, ApprovalResult) else policy.reason
        )
        return {
            "approval_decision": decision,
            "decision": decision,
            "policy_reason": _sanitize(policy.reason),
            "guardian_rule_id": guardian.rule_id if isinstance(guardian, ApprovalResult) else None,
            "rule_id": rule_id,
            "guardian_reason": _sanitize(guardian.reason) if isinstance(guardian, ApprovalResult) else _sanitize(policy.reason),
            "reason": _sanitize(reason),
            "normalized_action": redact_command(policy.safe_representation),
            "normalized_action_fingerprint": command_fingerprint(policy.safe_representation),
            "execution_result_reference": f"execution_evidence:{context.runtime_session_id}:{context.runtime_task_id}",
        }

    def _context(
        self, request: ExecutionRequest, context: RuntimeApprovalContext | None,
    ) -> RuntimeApprovalContext:
        value = context or RuntimeApprovalContext(
            cwd=str(self.root), repository=str(self.root),
            branch=_git_branch(self.root), environment="local",
            actor=request.source_worker, stage=_stage_for(request),
        )
        normalized = value.normalized()
        if Path(normalized["repository"]) != self.root:
            raise ValueError("approval repository context mismatch")
        if not _inside(Path(normalized["cwd"]), self.root):
            raise ValueError("approval cwd is outside the repository")
        return RuntimeApprovalContext(**normalized)

    def _failed_closed(
        self, request: ExecutionRequest, classification: str, error: Exception,
        context: RuntimeApprovalContext | None, *, persist: bool = True,
    ) -> dict[str, Any]:
        safe_context = context if isinstance(context, RuntimeApprovalContext) else RuntimeApprovalContext(
            cwd=str(self.root), repository=str(self.root), branch="",
            environment="local", actor=request.source_worker, stage=_stage_for(request),
        )
        policy = PolicyResult(
            "DENY", classification, "Approval enforcement failed closed.", "[DENIED]",
        )
        evidence = self._base(request, policy, "DENIED", safe_context)
        evidence.update({
            "approval_decision": ApprovalDecision.DENY.value,
            "decision": ApprovalDecision.DENY.value,
            "guardian_rule_id": "AGV2-D004", "rule_id": "AGV2-D004",
            "guardian_reason": "Approval enforcement failed closed.",
            "reason": "Approval enforcement failed closed.",
            "safe_cause": _sanitize(str(error)),
            "error_code": "RUNTIME_CONTROLLED_EXECUTION_BLOCKED",
        })
        if persist:
            try:
                return self._persist_raw(evidence)
            except OSError:
                pass
        return evidence

    def _persist_raw(self, evidence: dict[str, Any]) -> dict[str, Any]:
        self.evidence_dir.mkdir(parents=True, exist_ok=True)
        path = self.evidence_dir / f"{evidence['request_id']}.json"
        path.write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
        return evidence


def _inside(path: Path, root: Path) -> bool:
    try: path.relative_to(root); return True
    except ValueError: return False


def _secret_target(path: Path) -> bool:
    lowered = path.name.lower()
    return lowered in _SECRET_NAMES or path.suffix.lower() in {".pem", ".key", ".pfx", ".p12"} or any(word in lowered for word in ("credential", "secret", "api_key", "apikey"))


def _contains_secret(content: str) -> bool:
    return bool(re.search(r"(?i)(authorization\s*:\s*bearer|api[_-]?key\s*[=:]|\bsk-[A-Za-z0-9_-]{8,})", content))


def _safe_python_script(path: Path) -> bool:
    """MVP executable profile: one or more print calls with literal scalar arguments."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, SyntaxError):
        return False
    if not tree.body:
        return False
    for statement in tree.body:
        if not isinstance(statement, ast.Expr) or not isinstance(statement.value, ast.Call):
            return False
        call = statement.value
        if not isinstance(call.func, ast.Name) or call.func.id != "print" or call.keywords:
            return False
        if not all(isinstance(argument, ast.Constant) and isinstance(argument.value, (str, int, float, bool, type(None))) for argument in call.args):
            return False
    return True


def _safe_pytest_arg(value: str, root: Path) -> bool:
    if value in {"-q", "-x", "--disable-warnings"} or value.startswith("--maxfail=") and value[10:].isdigit(): return True
    if value.startswith("-") or any(item in value for item in _META): return False
    target = (root / value.split("::", 1)[0]).resolve()
    return _inside(target, root) and (target.suffix == ".py" or "tests" in target.parts)


def _safe_git_path(value: str, root: Path) -> bool:
    if not value or value in {".", "..", "*", ":/"} or value.startswith("-"):
        return False
    candidate = Path(value)
    if candidate.is_absolute():
        return False
    target = (root / candidate).resolve()
    return _inside(target, root) and ".git" not in {part.lower() for part in target.relative_to(root).parts}


def _file_hash(path: Path) -> str: return sha256(path.read_bytes()).hexdigest()
def _as_text(value: Any) -> str: return value.decode(errors="replace") if isinstance(value, bytes) else (value or "")
def _sanitize(value: str) -> str:
    text = re.sub(r"\bsk-[A-Za-z0-9_-]{8,}\b", "[REDACTED]", value)
    text = re.sub(r"(?i)authorization\s*:\s*bearer\s+\S+", "Authorization: [REDACTED]", text)
    text = re.sub(r"(?i)(api[_-]?key|token|password|credential)\s*[=:]\s*\S+", r"\1=[REDACTED]", text)
    return text[:4000]


def _safe_metadata(value: Mapping[str, Any] | None) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, item in dict(value or {}).items():
        name = str(key)
        if any(marker in name.lower() for marker in ("key", "token", "secret", "password", "authorization")):
            result[name] = "[REDACTED]"
        elif isinstance(item, (str, int, float, bool)) or item is None:
            result[name] = _sanitize(item) if isinstance(item, str) else item
        else:
            result[name] = _sanitize(str(item))
    return result


def execution_action_fingerprint(request: ExecutionRequest) -> str:
    payload = {
        "action_type": request.action_type.value,
        "source_worker": request.source_worker,
        "relative_path": request.relative_path,
        "content_sha256": (
            sha256((request.content or "").encode("utf-8")).hexdigest()
            if request.action_type is ActionType.FILE_WRITE else ""
        ),
        "argv": list(request.argv),
        "expected_preimage_sha256": request.expected_preimage_sha256,
        "purpose": request.purpose,
    }
    return sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()


def _stage_for(request: ExecutionRequest) -> str:
    return "qa" if request.action_type is ActionType.COMMAND_RUN else "development"


def _git_branch(root: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "branch", "--show-current"], cwd=root,
            capture_output=True, text=True, timeout=3, shell=False,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return result.stdout.strip() if result.returncode == 0 else ""
