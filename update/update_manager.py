from __future__ import annotations

from pathlib import Path
from typing import Dict, Any, Optional

from update.backup_manager import BackupManager
from update.integrity_checker import IntegrityChecker
from update.patch_manager import PatchManager
from update.version_manager import VersionManager


class UpdateManager:
    def __init__(self, base_path: Path):
        self.base_path = base_path
        self.backup_manager = BackupManager(base_path)
        self.integrity_checker = IntegrityChecker(base_path)
        self.patch_manager = PatchManager(base_path)
        self.version_manager = VersionManager(base_path)

    def get_version(self) -> Dict[str, Any]:
        return self.version_manager.get_version()

    def create_backup(self) -> Dict[str, Any]:
        return self.backup_manager.create_backup()

    def check_readiness(self) -> Dict[str, Any]:
        result = self.integrity_checker.check()
        version = self.get_version()
        result["version"] = version
        result["updates_dir"] = str(self.patch_manager.updates_dir)
        return result

    def find_latest_patch(self) -> Dict[str, Any]:
        return self.patch_manager.find_latest_patch()

    def preview_patch(self, patch_path: Optional[str] = None) -> Dict[str, Any]:
        current = self.get_version().get("version", "")
        return self.patch_manager.preview_patch(Path(patch_path) if patch_path else None, current)

    def install_patch(self, patch_path: Optional[str] = None) -> Dict[str, Any]:
        return self.patch_manager.install_patch(
            Path(patch_path) if patch_path else None,
            self.backup_manager,
            self.integrity_checker,
            self.version_manager,
        )

    def rollback_latest(self) -> Dict[str, Any]:
        return self.patch_manager.rollback_latest(self.backup_manager)

    def get_history(self) -> Dict[str, Any]:
        return self.patch_manager.get_history()
