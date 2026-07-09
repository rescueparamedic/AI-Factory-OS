from __future__ import annotations

from datetime import datetime
from pathlib import Path
from zipfile import ZipFile
from typing import Dict, Any, List
import hashlib
import json


class PackageBuilder:
    BLOCKED_PARTS = {"__pycache__", ".git", ".idea", ".vscode"}
    BLOCKED_SUFFIXES = {".pyc", ".pyo", ".exe", ".dll", ".obj", ".so", ".bin"}

    def __init__(self, base_path: Path):
        self.base_path = base_path
        self.report_dir = base_path / "data" / "package_reports"
        self.report_dir.mkdir(parents=True, exist_ok=True)

    def validate_zip(self, zip_path: str | Path) -> Dict[str, Any]:
        path = Path(zip_path)
        blocked: List[str] = []
        files: List[str] = []

        if not path.exists():
            return {"status": "failed", "safe": False, "file_count": 0, "sha256": "", "blocked": [f"file_not_found:{path}"]}

        with ZipFile(path, "r") as z:
            for name in z.namelist():
                if name.endswith("/"):
                    continue
                files.append(name)
                reason = self._blocked_reason(name)
                if reason:
                    blocked.append(f"{name} :: {reason}")

        sha256 = self._sha256(path)
        result = {"status": "completed", "safe": len(blocked) == 0, "file_count": len(files), "sha256": sha256, "blocked": blocked, "files": files}
        report_path = self.report_dir / f"PACKAGE_VALIDATE_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        result["report_path"] = str(report_path)
        report_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        return result

    def _blocked_reason(self, name: str) -> str:
        normalized = name.replace("\\", "/")
        parts = set(normalized.split("/"))
        if parts & self.BLOCKED_PARTS:
            return "blocked_directory"
        suffix = Path(normalized).suffix.lower()
        if suffix in self.BLOCKED_SUFFIXES:
            return "blocked_file_type"
        if normalized.startswith("/") or ".." in normalized.split("/"):
            return "unsafe_path"
        return ""

    def _sha256(self, path: Path) -> str:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                h.update(chunk)
        return h.hexdigest()
