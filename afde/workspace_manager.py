from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
import json


@dataclass
class WorkspaceInfo:
    workspace_id: str
    sprint_id: str
    root: str
    created_at: str
    status: str = "ready"


class WorkspaceManager:
    """Creates and manages isolated AFDE sprint workspaces."""

    def __init__(self, project_root: str | Path = ".") -> None:
        self.project_root = Path(project_root).resolve()
        self.base_dir = self.project_root / "data" / "afde" / "workspaces"

    def create_workspace(self, sprint_id: str) -> WorkspaceInfo:
        safe_sprint_id = self._safe_name(sprint_id)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        workspace_id = f"{safe_sprint_id}_{timestamp}"
        workspace_root = self.base_dir / workspace_id
        for child in ["tasks", "artifacts", "logs", "reports"]:
            (workspace_root / child).mkdir(parents=True, exist_ok=True)
        info = WorkspaceInfo(
            workspace_id=workspace_id,
            sprint_id=sprint_id,
            root=str(workspace_root),
            created_at=datetime.now().isoformat(timespec="seconds"),
        )
        self._write_manifest(workspace_root, info)
        return info

    def latest_workspace(self) -> WorkspaceInfo | None:
        if not self.base_dir.exists():
            return None
        candidates = sorted([p for p in self.base_dir.iterdir() if p.is_dir()], reverse=True)
        for path in candidates:
            manifest = path / "workspace.json"
            if manifest.exists():
                data = json.loads(manifest.read_text(encoding="utf-8"))
                return WorkspaceInfo(**data)
        return None

    def _write_manifest(self, workspace_root: Path, info: WorkspaceInfo) -> None:
        (workspace_root / "workspace.json").write_text(
            json.dumps(asdict(info), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    @staticmethod
    def _safe_name(value: str) -> str:
        return "".join(ch if ch.isalnum() or ch in ("-", "_", ".") else "_" for ch in value).strip("_") or "sprint"
