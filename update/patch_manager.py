from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional
from zipfile import ZipFile
import json
import shutil
import hashlib


class PatchManager:
    PROTECTED_DIRS = {
        "backups",
        ".git",
        "__pycache__",
    }

    def __init__(self, base_path: Path):
        self.base_path = base_path
        self.updates_dir = base_path / "updates"
        self.updates_dir.mkdir(parents=True, exist_ok=True)
        self.history_dir = base_path / "data" / "update_history"
        self.history_dir.mkdir(parents=True, exist_ok=True)

    def preview_patch(self, patch_path: Optional[Path] = None, current_version: str = "") -> Dict[str, Any]:
        if patch_path is None:
            found = self.find_latest_patch()
            if not found["found"]:
                return {
                    "found": False,
                    "message": found["message"],
                }
            patch_path = Path(found["patch_path"])
        else:
            patch_path = Path(patch_path)

        inspected = self.inspect_patch(patch_path)
        if not inspected["valid"]:
            return {
                "found": False,
                "message": inspected["message"],
                "patch_path": str(patch_path),
            }

        manifest = inspected["manifest"]
        files = manifest.get("files", [])

        return {
            "found": True,
            "message": "Patch is ready for preview.",
            "patch_path": str(patch_path),
            "current_version": current_version,
            "patch_version": manifest.get("patch_version", ""),
            "sprint": manifest.get("sprint", ""),
            "description": manifest.get("description", ""),
            "file_count": len([f for f in files if f != "patch_manifest.json"]),
            "files": [f for f in files if f != "patch_manifest.json"],
            "manifest": manifest,
        }

    def find_latest_patch(self) -> Dict[str, Any]:
        candidates = []
        for path in self.updates_dir.glob("*.zip"):
            inspected = self.inspect_patch(path)
            if inspected["valid"]:
                manifest = inspected["manifest"]
                candidates.append({
                    "path": path,
                    "created": manifest.get("created", ""),
                    "patch_version": manifest.get("patch_version", ""),
                    "sprint": manifest.get("sprint", ""),
                })

        if not candidates:
            return {
                "found": False,
                "message": "No valid patch zip found in updates folder.",
                "patch_path": "",
            }

        candidates.sort(key=lambda x: (x["created"], x["patch_version"], x["path"].name), reverse=True)
        latest = candidates[0]
        return {
            "found": True,
            "message": f"Latest patch found: {latest['path'].name}",
            "patch_path": str(latest["path"]),
            "patch_version": latest["patch_version"],
            "sprint": latest["sprint"],
        }

    def inspect_patch(self, patch_path: Path) -> Dict[str, Any]:
        if not patch_path.exists():
            return {
                "valid": False,
                "message": f"Patch file not found: {patch_path}",
                "manifest": {},
            }

        try:
            with ZipFile(patch_path, "r") as z:
                names = z.namelist()
                if "patch_manifest.json" not in names:
                    return {
                        "valid": False,
                        "message": "patch_manifest.json missing",
                        "manifest": {},
                    }
                manifest = json.loads(z.read("patch_manifest.json").decode("utf-8"))

                declared_files = set(manifest.get("files", []))
                actual_files = set(n for n in names if not n.endswith("/"))
                missing = declared_files - actual_files
                if missing:
                    return {
                        "valid": False,
                        "message": f"Manifest lists missing files: {sorted(missing)}",
                        "manifest": manifest,
                    }

        except Exception as exc:
            return {
                "valid": False,
                "message": f"Failed to inspect patch: {exc}",
                "manifest": {},
            }

        return {
            "valid": True,
            "message": "Patch manifest loaded",
            "manifest": manifest,
        }

    def install_patch(self, patch_path: Optional[Path], backup_manager, integrity_checker, version_manager) -> Dict[str, Any]:
        if patch_path is None:
            found = self.find_latest_patch()
            if not found["found"]:
                return self._record_history({
                    "status": "failed",
                    "message": found["message"],
                    "patch_path": "",
                    "patch_version": None,
                })
            patch_path = Path(found["patch_path"])
        else:
            patch_path = Path(patch_path)

        inspected = self.inspect_patch(patch_path)

        if not inspected["valid"]:
            return self._record_history({
                "status": "failed",
                "message": inspected["message"],
                "patch_path": str(patch_path),
                "patch_version": None,
            })

        manifest = inspected["manifest"]

        readiness = integrity_checker.check()
        if not readiness["ready"]:
            return self._record_history({
                "status": "failed",
                "message": "Project is not ready for update. Run doctor/update check first.",
                "patch_path": str(patch_path),
                "patch_version": manifest.get("patch_version"),
                "manifest": manifest,
            })

        backup = backup_manager.create_backup()

        files_copied = 0
        try:
            with ZipFile(patch_path, "r") as z:
                for name in z.namelist():
                    if name.endswith("/") or name == "patch_manifest.json":
                        continue
                    if self._is_unsafe_name(name):
                        raise ValueError(f"Unsafe patch path blocked: {name}")

                    target = self.base_path / name
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with z.open(name) as src, open(target, "wb") as dst:
                        shutil.copyfileobj(src, dst)
                    files_copied += 1

            if manifest.get("patch_version"):
                version_manager.set_version(
                    manifest.get("patch_version", "0.1.9"),
                    manifest.get("sprint", "9-9"),
                    manifest.get("status", "mvp"),
                )

            after = integrity_checker.check()
            if not after["ready"]:
                return self._record_history({
                    "status": "installed_with_warning",
                    "message": "Patch installed but integrity check has warnings/failures.",
                    "patch_path": str(patch_path),
                    "patch_version": manifest.get("patch_version"),
                    "backup_path": backup["backup_path"],
                    "files_copied": files_copied,
                    "manifest": manifest,
                })

            return self._record_history({
                "status": "completed",
                "message": "Patch installed successfully.",
                "patch_path": str(patch_path),
                "patch_version": manifest.get("patch_version"),
                "backup_path": backup["backup_path"],
                "files_copied": files_copied,
                "manifest": manifest,
            })

        except Exception as exc:
            return self._record_history({
                "status": "failed",
                "message": f"Patch install failed after backup: {exc}",
                "patch_path": str(patch_path),
                "patch_version": manifest.get("patch_version"),
                "backup_path": backup["backup_path"],
                "files_copied": files_copied,
                "manifest": manifest,
            })

    def rollback_latest(self, backup_manager) -> Dict[str, Any]:
        backup_path = backup_manager.get_latest_backup_path()
        if backup_path is None:
            return {
                "status": "failed",
                "message": "No backup found.",
                "backup_path": "",
                "files_restored": 0,
            }

        files_restored = backup_manager.restore_backup(backup_path)
        result = {
            "status": "completed",
            "message": "Rollback completed.",
            "backup_path": str(backup_path),
            "files_restored": files_restored,
        }
        self._record_history({
            "status": "rollback_completed",
            "message": "Rollback completed.",
            "backup_path": str(backup_path),
            "files_restored": files_restored,
            "patch_version": None,
        })
        return result

    def get_history(self) -> Dict[str, Any]:
        items: List[Dict[str, Any]] = []
        for path in sorted(self.history_dir.glob("UPD-*.json"), reverse=True):
            try:
                items.append(json.loads(path.read_text(encoding="utf-8")))
            except json.JSONDecodeError:
                continue
        return {"items": items}

    def _record_history(self, data: Dict[str, Any]) -> Dict[str, Any]:
        now = datetime.now().astimezone()
        record = {
            "update_id": f"UPD-{now.strftime('%Y%m%d-%H%M%S-%f')}",
            "timestamp": now.isoformat(timespec="seconds"),
            **data,
        }
        path = self.history_dir / f"{record['update_id']}.json"
        record["history_path"] = str(path)
        path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
        return record

    def _is_unsafe_name(self, name: str) -> bool:
        normalized = name.replace("\\", "/")
        parts = normalized.split("/")
        if normalized.startswith("/") or ".." in parts:
            return True
        if any(part in self.PROTECTED_DIRS for part in parts):
            return True
        return False
