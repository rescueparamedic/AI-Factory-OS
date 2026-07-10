from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import subprocess

from .models import ApprovalRequest


PROTECTED_BRANCHES = frozenset({"main", "master"})


@dataclass(frozen=True)
class EvaluationContext:
    repository_root: Path
    cwd: Path
    cwd_in_repository: bool
    branch: str | None
    environment: str
    working_tree_clean: bool | None


def build_context(request: ApprovalRequest, repository_root: str | Path) -> EvaluationContext:
    root = Path(repository_root).resolve()
    cwd = Path(request.cwd or root).resolve()
    branch = request.branch or _git_value(root, ["branch", "--show-current"])
    clean_value = _git_value(root, ["status", "--porcelain"])
    clean = None if clean_value is None else not bool(clean_value)
    return EvaluationContext(
        repository_root=root,
        cwd=cwd,
        cwd_in_repository=_is_relative_to(cwd, root),
        branch=branch or None,
        environment=(request.environment or "dev").lower(),
        working_tree_clean=clean,
    )


def path_is_inside_repository(path: str, context: EvaluationContext) -> bool:
    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = context.cwd / candidate
    try:
        resolved = candidate.resolve()
    except OSError:
        return False
    return _is_relative_to(resolved, context.repository_root)


def is_feature_branch(branch: str | None) -> bool:
    return bool(branch and branch.startswith("feature/"))


def _git_value(root: Path, arguments: list[str]) -> str | None:
    try:
        result = subprocess.run(
            ["git", *arguments],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=3,
            shell=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False
