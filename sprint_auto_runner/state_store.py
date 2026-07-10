from __future__ import annotations

import json
from pathlib import Path

from .errors import SprintStateError
from .models import SprintRun, StepResult


class SprintStateStore:
    def __init__(self, repository_root: str | Path) -> None:
        self.run_dir = Path(repository_root) / "data" / "sprint_runs"
        self.run_dir.mkdir(parents=True, exist_ok=True)

    def save(self, run: SprintRun) -> Path:
        path = self.path_for(run.run_id)
        temporary = path.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(run.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(path)
        return path

    def load(self, run_id: str) -> SprintRun:
        path = self.path_for(run_id)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise SprintStateError(f"run not found: {run_id}") from exc
        except (OSError, json.JSONDecodeError) as exc:
            raise SprintStateError(f"run state is unreadable: {run_id}: {exc}") from exc
        try:
            data["step_results"] = [StepResult(**item) for item in data["step_results"]]
            return SprintRun(**data)
        except (KeyError, TypeError, ValueError) as exc:
            raise SprintStateError(f"run state is invalid: {run_id}: {exc}") from exc

    def path_for(self, run_id: str) -> Path:
        if not run_id or any(char not in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_" for char in run_id):
            raise SprintStateError("invalid run_id")
        return self.run_dir / f"{run_id}.json"
