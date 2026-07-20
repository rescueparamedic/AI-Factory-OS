"""Qt-independent application boundary for AI Factory Desktop."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any, Callable, Mapping

from real_worker_runtime.runtime_lifecycle import safe_message


ENGINE_ROOT = Path(__file__).resolve().parents[2]


class DesktopStatus(str, Enum):
    IDLE = "Idle"
    VALIDATING = "Validating"
    RUNNING = "Running"
    COMPLETED = "Completed"
    FAILED = "Failed"


@dataclass(frozen=True)
class DesktopViewState:
    status: DesktopStatus
    inputs_enabled: bool
    run_enabled: bool
    open_evidence_enabled: bool
    progress_active: bool


def view_state(
    status: DesktopStatus, *, evidence_available: bool = False,
) -> DesktopViewState:
    busy = status in {DesktopStatus.VALIDATING, DesktopStatus.RUNNING}
    return DesktopViewState(
        status=status,
        inputs_enabled=not busy,
        run_enabled=not busy,
        open_evidence_enabled=(
            status is DesktopStatus.COMPLETED and evidence_available
        ),
        progress_active=busy,
    )


@dataclass(frozen=True)
class DesktopExecutionRequest:
    workspace: Path
    request: str


@dataclass(frozen=True)
class DesktopExecutionResult:
    status: str
    session_id: str
    provider: str
    execution_mode: str
    evidence_path: Path
    exit_code: int
    payload: Mapping[str, Any]


class DesktopExecutionError(RuntimeError):
    def __init__(
        self, error: str, cause: str, next_action: str, *, exit_code: int,
    ) -> None:
        super().__init__(error)
        self.error = safe_message(error)
        self.cause = safe_message(cause)
        self.next_action = safe_message(next_action)
        self.exit_code = exit_code

    def log_lines(self) -> tuple[str, ...]:
        return (
            "Status: Failed",
            f"Error: {self.error}",
            f"Cause: {self.cause}",
            f"Next: {self.next_action}",
        )


Runner = Callable[..., subprocess.CompletedProcess[str]]


class DesktopExecutionService:
    """Validate inputs and reuse the official AFDE CLI JSON contract."""

    def __init__(self, *, runner: Runner = subprocess.run) -> None:
        self._runner = runner

    def validate(self, workspace: str, request: str) -> DesktopExecutionRequest:
        workspace_text = str(workspace or "").strip()
        if not workspace_text:
            raise DesktopExecutionError(
                "Project Workspace is required.",
                "No workspace path was supplied.",
                "Choose an existing project directory and run again.",
                exit_code=2,
            )
        try:
            resolved = Path(workspace_text).expanduser().resolve()
        except (OSError, ValueError) as exc:
            raise DesktopExecutionError(
                "Project Workspace is invalid.",
                safe_message(exc),
                "Choose an existing project directory and run again.",
                exit_code=2,
            ) from exc
        if not resolved.is_dir():
            raise DesktopExecutionError(
                "Project Workspace was not found.",
                f"The selected directory does not exist: {resolved}",
                "Browse to an existing project directory and run again.",
                exit_code=2,
            )
        request_text = str(request or "").strip()
        if not request_text:
            raise DesktopExecutionError(
                "Request is required.",
                "The natural-language goal is empty.",
                "Enter one bounded read-only goal and run again.",
                exit_code=2,
            )
        if len(request_text) > 1000:
            raise DesktopExecutionError(
                "Request is too long.",
                "The official Beta request limit is 1000 characters.",
                "Shorten the goal and run again.",
                exit_code=2,
            )
        return DesktopExecutionRequest(workspace=resolved, request=request_text)

    def build_command(self, request: DesktopExecutionRequest) -> tuple[str, ...]:
        return (
            sys.executable,
            "-m",
            "afde.cli",
            "execute",
            "--request",
            request.request,
            "--provider",
            "mock",
            "--workspace",
            str(request.workspace),
            "--json",
        )

    def safe_environment(self) -> dict[str, str]:
        environment = os.environ.copy()
        environment["OPENAI_API_KEY"] = ""
        environment["AI_FACTORY_RUN_LIVE_OPENAI_TESTS"] = "0"
        return environment

    def execute(self, workspace: str, request: str) -> DesktopExecutionResult:
        validated = self.validate(workspace, request)
        command = self.build_command(validated)
        try:
            completed = self._runner(
                command,
                cwd=str(ENGINE_ROOT),
                env=self.safe_environment(),
                capture_output=True,
                text=True,
                check=False,
            )
        except FileNotFoundError as exc:
            raise DesktopExecutionError(
                "Python execution failed.",
                safe_message(exc),
                "Verify the active Python installation and run again.",
                exit_code=5,
            ) from exc
        except OSError as exc:
            raise DesktopExecutionError(
                "AFDE execution could not start.",
                safe_message(exc),
                "Verify Python and workspace access, then run again.",
                exit_code=5,
            ) from exc
        return self.parse_completed(validated.workspace, completed)

    def parse_completed(
        self, workspace: Path, completed: subprocess.CompletedProcess[str],
    ) -> DesktopExecutionResult:
        try:
            payload = json.loads(completed.stdout)
        except (TypeError, json.JSONDecodeError) as exc:
            if completed.returncode != 0:
                raise self._process_error(completed) from exc
            raise DesktopExecutionError(
                "AFDE returned invalid JSON.",
                "The execute output could not be parsed as the Beta JSON contract.",
                "Review the AFDE CLI output and retry after resolving the error.",
                exit_code=5,
            ) from exc
        if not isinstance(payload, dict):
            raise DesktopExecutionError(
                "AFDE returned invalid JSON.",
                "The execute output root is not a JSON object.",
                "Review the AFDE CLI output and run again.",
                exit_code=5,
            )
        reported_exit = _integer(payload.get("exit_code"), completed.returncode)
        if completed.returncode != 0 or reported_exit != 0:
            raise self._payload_error(payload, reported_exit)
        status = str(payload.get("status") or "").strip().lower()
        if status != "completed":
            raise DesktopExecutionError(
                "AFDE execution did not complete.",
                f"The zero-exit result reported status: {status or 'missing'}",
                "Inspect the Runtime result before running the task again.",
                exit_code=5,
            )
        session_id = _required_text(payload, "session_id")
        provider = _required_text(payload, "provider")
        if provider != "mock":
            raise DesktopExecutionError(
                "Desktop provider boundary was violated.",
                f"AFDE reported the unsupported provider: {provider}",
                "Stop execution and verify the Desktop mock-only configuration.",
                exit_code=5,
            )
        evidence_path = self._evidence_path(
            workspace, _required_text(payload, "evidence_path"),
        )
        if not evidence_path.is_file():
            raise DesktopExecutionError(
                "Execution Evidence was not found.",
                f"AFDE reported a missing Evidence file: {evidence_path}",
                "Verify workspace access and inspect the Runtime session.",
                exit_code=5,
            )
        return DesktopExecutionResult(
            status=status,
            session_id=session_id,
            provider=provider,
            execution_mode=str(payload.get("execution_mode") or "unknown"),
            evidence_path=evidence_path,
            exit_code=reported_exit,
            payload=payload,
        )

    def open_evidence(
        self, path: Path, *, opener: Callable[[str], Any] | None = None,
    ) -> None:
        resolved = Path(path).resolve()
        if not resolved.is_file():
            raise DesktopExecutionError(
                "Execution Evidence was not found.",
                f"The Evidence file does not exist: {resolved}",
                "Run the task again or verify the Runtime session directory.",
                exit_code=4,
            )
        selected_opener = opener or getattr(os, "startfile", None)
        if selected_opener is None:
            raise DesktopExecutionError(
                "Evidence opening is unavailable.",
                "The operating system does not provide a default file opener.",
                "Open the displayed Evidence path manually.",
                exit_code=5,
            )
        selected_opener(str(resolved))

    @staticmethod
    def _evidence_path(workspace: Path, value: str) -> Path:
        supplied = Path(value)
        try:
            resolved = (
                supplied.resolve()
                if supplied.is_absolute()
                else (workspace / supplied).resolve()
            )
        except (OSError, ValueError) as exc:
            raise DesktopExecutionError(
                "Execution Evidence path is invalid.",
                safe_message(exc),
                "Stop execution and inspect the AFDE Runtime result.",
                exit_code=5,
            ) from exc
        if not resolved.is_relative_to(workspace):
            raise DesktopExecutionError(
                "Execution Evidence path is unsafe.",
                "The reported Evidence path escapes the selected workspace.",
                "Stop execution and inspect the AFDE Runtime result.",
                exit_code=5,
            )
        return resolved

    @staticmethod
    def _process_error(
        completed: subprocess.CompletedProcess[str],
    ) -> DesktopExecutionError:
        stderr = safe_message(completed.stderr or "AFDE CLI failed")
        if "No module named" in stderr or "ImportError" in stderr:
            return DesktopExecutionError(
                "AFDE CLI could not be loaded.",
                stderr,
                "Verify the AI Factory OS installation and Python environment.",
                exit_code=completed.returncode or 5,
            )
        return DesktopExecutionError(
            "AFDE execution failed.",
            stderr,
            "Review the error and run the bounded Mock task again.",
            exit_code=completed.returncode or 5,
        )

    @staticmethod
    def _payload_error(payload: Mapping[str, Any], code: int) -> DesktopExecutionError:
        error = payload.get("error")
        error = error if isinstance(error, Mapping) else {}
        return DesktopExecutionError(
            str(error.get("message") or payload.get("error") or "AFDE execution failed."),
            str(payload.get("cause") or error.get("category") or "Runtime execution did not complete."),
            str(payload.get("next_action") or "Review the Runtime Evidence and run again."),
            exit_code=code or 5,
        )


def _required_text(payload: Mapping[str, Any], field: str) -> str:
    value = str(payload.get(field) or "").strip()
    if value:
        return value
    raise DesktopExecutionError(
        "AFDE result is incomplete.",
        f"The required result field is missing: {field}",
        "Inspect the CLI JSON contract and run again.",
        exit_code=5,
    )


def _integer(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(default)
