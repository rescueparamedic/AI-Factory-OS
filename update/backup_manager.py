from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional
import shutil


class BackupManager:
    EXCLUDED_DIRS = {
        "__pycache__",
        ".git",
        "backups",
    }

    def __init__(self, base_path: Path):
        self.base_path = base_path
        self.backup_root = base_path / "backups"
        self.backup_root.mkdir(parents=True, exist_ok=True)

    def create_backup(self) -> Dict[str, Any]:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        target = self.backup_root / f"backup_{stamp}"
        target.mkdir(parents=True, exist_ok=True)

        files_copied = 0
        for src in self.base_path.rglob("*"):
            if self._is_excluded(src):
                continue
            if src.is_file():
                rel = src.relative_to(self.base_path)
                dst = target / rel
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)
                files_copied += 1

        return {
            "status": "completed",
            "backup_path": str(target),
            "files_copied": files_copied,
        }

    def get_latest_backup_path(self) -> Optional[Path]:
        backups = sorted(self.backup_root.glob("backup_*"), reverse=True)
        for backup in backups:
            if backup.is_dir():
                return backup
        return None

    def restore_backup(self, backup_path: Path) -> int:
        files_restored = 0
        backup_path = Path(backup_path)
        if not backup_path.exists():
            raise FileNotFoundError(f"Backup not found: {backup_path}")

        for src in backup_path.rglob("*"):
            if src.is_file():
                rel = src.relative_to(backup_path)
                dst = self.base_path / rel
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)
                files_restored += 1
        return files_restored

    def _is_excluded(self, path: Path) -> bool:
        parts = set(path.relative_to(self.base_path).parts) if path != self.base_path else set()
        return any(part in self.EXCLUDED_DIRS for part in parts)
