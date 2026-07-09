from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List
import json


class ProjectDoctor:
    EXPECTED_ROOT_NAME = "AI Factory OS"

    def __init__(self, base_path: Path):
        self.base_path = base_path
        self.reports_dir = base_path / "data" / "reports"
        self.reports_dir.mkdir(parents=True, exist_ok=True)

    def run(self) -> Dict[str, Any]:
        checks: List[Dict[str, str]] = []
        warnings: List[str] = []

        checks.extend(self._check_root())
        checks.extend(self._check_required_structure())
        checks.extend(self._check_runtime_files())
        checks.extend(self._check_registered_layers())

        failed = [c for c in checks if c["status"] == "FAIL"]
        warns = [c for c in checks if c["status"] == "WARN"]

        health_score = max(0, 100 - len(failed) * 15 - len(warns) * 5)

        if self.base_path.name != self.EXPECTED_ROOT_NAME:
            warnings.append(f"현재 프로젝트 폴더명이 '{self.base_path.name}'입니다. 권장 이름은 '{self.EXPECTED_ROOT_NAME}'입니다.")

        report = {
            "timestamp": datetime.now().astimezone().isoformat(timespec="seconds"),
            "project_path": str(self.base_path),
            "health_score": health_score,
            "status": "HEALTHY" if health_score >= 90 else "CHECK_REQUIRED",
            "checks": checks,
            "warnings": warnings,
        }

        report_path = self.reports_dir / f"DOCTOR_REPORT_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        report["report_path"] = str(report_path)
        return report

    def _check_root(self) -> List[Dict[str, str]]:
        return [{
            "name": "project_root",
            "status": "OK" if (self.base_path / "main.py").exists() else "FAIL",
            "message": "main.py found" if (self.base_path / "main.py").exists() else "main.py missing",
        }]

    def _check_required_structure(self) -> List[Dict[str, str]]:
        required = [
            "os_core", "workers", "agents", "teams", "managers",
            "runtime", "products", "data", "docs"
        ]
        checks = []
        for name in required:
            path = self.base_path / name
            checks.append({
                "name": f"folder:{name}",
                "status": "OK" if path.is_dir() else "FAIL",
                "message": "exists" if path.is_dir() else "missing",
            })
        return checks

    def _check_runtime_files(self) -> List[Dict[str, str]]:
        required = [
            "os_core/kernel.py",
            "workers/base_worker.py",
            "agents/ceo_agent.py",
            "agents/pm_agent.py",
            "teams/base_team.py",
            "managers/team_manager.py",
            "products/blog_growth_analyzer/product_config.json",
        ]
        checks = []
        for rel in required:
            path = self.base_path / rel
            checks.append({
                "name": f"file:{rel}",
                "status": "OK" if path.is_file() else "FAIL",
                "message": "exists" if path.is_file() else "missing",
            })
        return checks

    def _check_registered_layers(self) -> List[Dict[str, str]]:
        checks = []
        counts = {
            "agents": len(list((self.base_path / "agents").glob("*_agent.py"))) if (self.base_path / "agents").is_dir() else 0,
            "teams": len(list((self.base_path / "teams").glob("*_team.py"))) if (self.base_path / "teams").is_dir() else 0,
            "workers": len(list((self.base_path / "workers").glob("*_worker.py"))) if (self.base_path / "workers").is_dir() else 0,
        }

        checks.append({
            "name": "agents_registered",
            "status": "OK" if counts["agents"] >= 9 else "WARN",
            "message": f"{counts['agents']} agent files found",
        })
        checks.append({
            "name": "teams_registered",
            "status": "OK" if counts["teams"] >= 6 else "WARN",
            "message": f"{counts['teams']} team files found",
        })
        checks.append({
            "name": "workers_registered",
            "status": "OK" if counts["workers"] >= 6 else "WARN",
            "message": f"{counts['workers']} worker files found",
        })
        return checks
