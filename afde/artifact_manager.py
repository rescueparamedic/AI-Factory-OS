from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
import json


@dataclass
class ArtifactRecord:
    artifact_id: str
    kind: str
    path: str
    created_at: str
    description: str = ""


class ArtifactManager:
    """Stores generated artifacts and records a lightweight manifest."""

    def __init__(self, project_root: str | Path = ".") -> None:
        self.project_root = Path(project_root).resolve()
        self.base_dir = self.project_root / "data" / "afde" / "artifacts"
        self.manifest_path = self.base_dir / "artifact_manifest.jsonl"
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def save_text(self, kind: str, filename: str, content: str, description: str = "") -> ArtifactRecord:
        safe_kind = self._safe_name(kind)
        target_dir = self.base_dir / safe_kind
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / filename
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        record = ArtifactRecord(
            artifact_id=f"{safe_kind}_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}",
            kind=kind,
            path=str(target),
            created_at=datetime.now().isoformat(timespec="seconds"),
            description=description,
        )
        self._append_manifest(record)
        return record

    def _append_manifest(self, record: ArtifactRecord) -> None:
        with self.manifest_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(record), ensure_ascii=False) + "\n")

    @staticmethod
    def _safe_name(value: str) -> str:
        return "".join(ch if ch.isalnum() or ch in ("-", "_", ".") else "_" for ch in value).strip("_") or "artifact"
