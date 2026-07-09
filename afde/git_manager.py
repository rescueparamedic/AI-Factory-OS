from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import subprocess


@dataclass
class GitCommandResult:
    command: list[str]
    returncode: int
    stdout: str
    stderr: str


class GitManager:
    """Safe Git helper. It runs read-only commands by default and prepares commit commands."""

    def __init__(self, project_root: str | Path = ".") -> None:
        self.project_root = Path(project_root).resolve()

    def status(self) -> GitCommandResult:
        return self._run(["git", "status", "--short"])

    def current_branch(self) -> str:
        result = self._run(["git", "branch", "--show-current"])
        return result.stdout.strip()

    def prepare_commit_commands(self, message: str) -> list[str]:
        safe_message = message.replace('"', "'")
        return [
            "git add .",
            f'git commit -m "{safe_message}"',
            "git push",
        ]

    def _run(self, command: list[str]) -> GitCommandResult:
        proc = subprocess.run(
            command,
            cwd=self.project_root,
            text=True,
            capture_output=True,
            shell=False,
        )
        return GitCommandResult(command=command, returncode=proc.returncode, stdout=proc.stdout, stderr=proc.stderr)
