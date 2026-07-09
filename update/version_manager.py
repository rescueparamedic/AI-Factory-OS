from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Dict, Any
import json


class VersionManager:
    def __init__(self, base_path: Path):
        self.base_path = base_path
        self.version_file = base_path / "VERSION.json"

    def ensure_version_file(self) -> None:
        if not self.version_file.exists():
            self.version_file.write_text(
                json.dumps(
                    {
                        "version": "0.1.6",
                        "sprint": "9-6",
                        "build": datetime.now().strftime("%Y%m%d"),
                        "status": "mvp",
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

    def get_version(self) -> Dict[str, Any]:
        self.ensure_version_file()
        return json.loads(self.version_file.read_text(encoding="utf-8"))

    def set_version(self, version: str, sprint: str, status: str = "mvp") -> Dict[str, Any]:
        data = {
            "version": version,
            "sprint": sprint,
            "build": datetime.now().strftime("%Y%m%d"),
            "status": status,
        }
        self.version_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return data
