# -*- coding: utf-8 -*-
"""Real AI Worker bootstrap for AFDE.
Creates a safe local bootstrap manifest before real provider execution is enabled.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Dict


class RealAIWorkerBootstrap:
    def __init__(self, project_root: str | Path | None = None) -> None:
        self.project_root = Path(project_root or Path.cwd()).resolve()

    def build_manifest(self) -> Dict[str, object]:
        worker_runtime = self.project_root / "worker_runtime"
        provider_files = [
            worker_runtime / "ai_provider.py",
            worker_runtime / "real_ai_worker.py",
            worker_runtime / "worker_runtime_engine.py",
        ]
        return {
            "status": "READY",
            "mode": "local_safe_bootstrap",
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "project_root": str(self.project_root),
            "worker_runtime_exists": worker_runtime.exists(),
            "provider_files": [
                {"path": str(path), "exists": path.exists()} for path in provider_files
            ],
            "next_step": "Enable real provider execution after API keys and approval are configured.",
        }

    def run(self, output_path: str | Path | None = None) -> Dict[str, object]:
        manifest = self.build_manifest()
        if output_path is None:
            output_dir = self.project_root / "data" / "afde" / "bootstrap"
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path = output_dir / "real_ai_worker_bootstrap.json"
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        manifest["manifest_path"] = str(output_path)
        return manifest
