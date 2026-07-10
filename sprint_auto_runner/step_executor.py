from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import subprocess
from time import monotonic

from approval_guardian.command_parser import parse_commands

from .models import SprintStep


@dataclass(frozen=True)
class ExecutionResult:
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: int
    started_at: str
    completed_at: str
    timed_out: bool = False


class StepExecutor:
    """Execute parsed commands as argument arrays; never enables a shell."""

    def execute(self, step: SprintStep, cwd: str) -> ExecutionResult:
        started = datetime.now().astimezone()
        start_clock = monotonic()
        stdout_parts: list[str] = []
        stderr_parts: list[str] = []
        exit_code = 0
        timed_out = False
        remaining = float(step.timeout_seconds)
        try:
            for command in parse_commands(step.command):
                command_start = monotonic()
                result = subprocess.run(
                    list(command.tokens),
                    cwd=cwd,
                    capture_output=True,
                    text=True,
                    timeout=max(0.001, remaining),
                    shell=False,
                )
                stdout_parts.append(result.stdout)
                stderr_parts.append(result.stderr)
                exit_code = result.returncode
                remaining -= monotonic() - command_start
                if exit_code != 0:
                    break
        except subprocess.TimeoutExpired as exc:
            timed_out = True
            exit_code = 124
            stdout_parts.append(_text(exc.stdout))
            stderr_parts.append(_text(exc.stderr) or "Command timed out.")
        except OSError as exc:
            exit_code = 127
            stderr_parts.append(f"Process start failed: {exc}")

        completed = datetime.now().astimezone()
        return ExecutionResult(
            exit_code=exit_code,
            stdout="".join(stdout_parts),
            stderr="".join(stderr_parts),
            duration_ms=int((monotonic() - start_clock) * 1000),
            started_at=started.isoformat(timespec="seconds"),
            completed_at=completed.isoformat(timespec="seconds"),
            timed_out=timed_out,
        )


def _text(value: str | bytes | None) -> str:
    if value is None:
        return ""
    return value.decode(errors="replace") if isinstance(value, bytes) else value
