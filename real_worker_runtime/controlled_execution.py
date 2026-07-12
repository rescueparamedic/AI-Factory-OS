from __future__ import annotations

from dataclasses import asdict, dataclass
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
from typing import Any, Callable
from uuid import uuid4

from approval_guardian import ApprovalDecision, ApprovalGuardian, ApprovalRequest


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

    @classmethod
    def file_write(cls, relative_path: str, content: str, source_worker: str, purpose: str) -> "ExecutionRequest":
        return cls(f"EXE-{uuid4().hex}", ActionType.FILE_WRITE, source_worker, _sanitize(purpose)[:255], relative_path, content)

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
        if lowered[0] in {"git", "pip", "npm", "python3", "python.exe"} and lowered[:3] != ("python.exe", "-m", "pytest"):
            return PolicyResult("DENY", "UNSUPPORTED_EXECUTABLE", "Executable is not in the MVP allowlist.", safe_repr)
        if any(item in _META or any(char in item for char in "\r\n") for item in argv):
            return PolicyResult("DENY", "COMMAND_COMPOSITION", "Chaining, redirection, and control operators are forbidden.", safe_repr)
        if lowered == ("python", "--version"):
            return PolicyResult("AUTO_APPROVE", "SAFE_PYTHON_VERSION", "Allowlisted local version check.", safe_repr)
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

    def execute(self, request: ExecutionRequest) -> dict[str, Any]:
        policy = self.policy.classify(request)
        if policy.decision == "DENY":
            return self._persist(request, policy, None, "DENIED")
        guardian = self.guardian.evaluate(ApprovalRequest(
            command=policy.safe_representation, cwd=str(self.root), actor="controlled-runtime",
            task_id=request.request_id, environment="local",
        ))
        if guardian.decision is ApprovalDecision.DENY:
            return self._persist(request, policy, guardian, "DENIED")
        approval_needed = policy.decision == "ASK_USER" or guardian.decision is ApprovalDecision.ASK_USER
        if approval_needed:
            return self._persist(request, policy, guardian, "WAITING_APPROVAL")
        if request.action_type is ActionType.FILE_WRITE:
            evidence = self._write_file(request, policy)
        else:
            evidence = self._run_command(request, policy)
        evidence["approval_decision"] = guardian.decision.value
        return self._persist_raw(evidence)

    def _write_file(self, request: ExecutionRequest, policy: PolicyResult) -> dict[str, Any]:
        target = Path(policy.resolved_target or "")
        before_exists = target.exists()
        before_hash = _file_hash(target) if before_exists else None
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(request.content or "", encoding="utf-8")
        after_hash = _file_hash(target)
        changed = not before_exists or before_hash != after_hash
        return self._base(request, policy, "SUCCEEDED" if changed else "NO_CHANGE") | {
            "relative_path": target.relative_to(self.root).as_posix(),
            "before_exists": before_exists, "before_sha256": before_hash,
            "after_exists": target.is_file(), "after_sha256": after_hash, "changed": changed,
        }

    def _run_command(self, request: ExecutionRequest, policy: PolicyResult) -> dict[str, Any]:
        started = datetime.now().astimezone(); clock = monotonic(); timed_out = False
        execution_argv = [sys.executable, *request.argv[1:]]
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

    def _base(self, request: ExecutionRequest, policy: PolicyResult, status: str) -> dict[str, Any]:
        return {"request_id": request.request_id, "action_type": request.action_type.value,
                "source_worker": request.source_worker, "purpose": request.purpose,
                "policy_classification": policy.classification, "status": status}

    def _persist(self, request: ExecutionRequest, policy: PolicyResult, guardian: Any, status: str) -> dict[str, Any]:
        evidence = self._base(request, policy, status)
        evidence["approval_decision"] = guardian.decision.value if guardian else policy.decision.lower()
        return self._persist_raw(evidence)

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


def _file_hash(path: Path) -> str: return sha256(path.read_bytes()).hexdigest()
def _as_text(value: Any) -> str: return value.decode(errors="replace") if isinstance(value, bytes) else (value or "")
def _sanitize(value: str) -> str:
    text = re.sub(r"\bsk-[A-Za-z0-9_-]{8,}\b", "[REDACTED]", value)
    text = re.sub(r"(?i)authorization\s*:\s*bearer\s+\S+", "Authorization: [REDACTED]", text)
    text = re.sub(r"(?i)(api[_-]?key|token|password|credential)\s*[=:]\s*\S+", r"\1=[REDACTED]", text)
    return text[:4000]
