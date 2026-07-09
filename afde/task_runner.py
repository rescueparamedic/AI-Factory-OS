from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
import json

from .artifact_manager import ArtifactManager
from .workspace_manager import WorkspaceManager
from .provider_manager import ProviderManager


@dataclass
class AFDETask:
    task_id: str
    title: str
    request: str
    status: str = "created"
    created_at: str = ""


@dataclass
class AFDETaskResult:
    task_id: str
    status: str
    workspace_id: str
    artifact_path: str
    provider_status: list[dict]


class AFDETaskRunner:
    """Minimal local AFDE task runner for Sprint AFDE-1."""

    def __init__(self, project_root: str | Path = ".") -> None:
        self.project_root = Path(project_root).resolve()
        self.workspace_manager = WorkspaceManager(self.project_root)
        self.artifact_manager = ArtifactManager(self.project_root)
        self.provider_manager = ProviderManager(self.project_root)

    def create_task(self, title: str, request: str) -> AFDETask:
        task = AFDETask(
            task_id=f"AFDE-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
            title=title,
            request=request,
            status="created",
            created_at=datetime.now().isoformat(timespec="seconds"),
        )
        task_dir = self.project_root / "data" / "afde" / "tasks"
        task_dir.mkdir(parents=True, exist_ok=True)
        (task_dir / f"{task.task_id}.json").write_text(
            json.dumps(asdict(task), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return task

    def run_mock_pipeline(self, title: str, request: str) -> AFDETaskResult:
        task = self.create_task(title, request)
        workspace = self.workspace_manager.create_workspace(task.task_id)
        report = self._build_mock_report(task, workspace.workspace_id)
        artifact = self.artifact_manager.save_text(
            kind="reports",
            filename=f"{task.task_id}_mock_pipeline_report.md",
            content=report,
            description="AFDE-1 mock execution report",
        )
        return AFDETaskResult(
            task_id=task.task_id,
            status="success",
            workspace_id=workspace.workspace_id,
            artifact_path=artifact.path,
            provider_status=self.provider_manager.as_dicts(),
        )

    def _build_mock_report(self, task: AFDETask, workspace_id: str) -> str:
        return f"""# AFDE Mock Pipeline Report

## Task
- ID: {task.task_id}
- Title: {task.title}
- Status: SUCCESS

## Request
{task.request}

## Workspace
{workspace_id}

## Pipeline
- Planning: PASS
- Development: PASS
- QA: PASS
- Documentation: PASS

## Note
This is a local safe-mode AFDE execution result.
"""
