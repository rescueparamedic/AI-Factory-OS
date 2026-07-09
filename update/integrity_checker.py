from __future__ import annotations

from pathlib import Path
from typing import Dict, Any, List


class IntegrityChecker:
    REQUIRED_FILES = [
        "main.py",
        "os_core/kernel.py",
        "os_core/task_engine.py",
        "os_core/worker_manager.py",
        "workers/base_worker.py",
        "workers/markdown_worker.py",
        "agents/ceo_agent.py",
        "agents/pm_agent.py",
        "teams/base_team.py",
        "managers/agent_manager.py",
        "managers/team_manager.py",
        "runtime/product_loader.py",
        "products/blog_growth_analyzer/product_config.json",
    ]

    REQUIRED_DIRS = [
        "os_core",
        "workers",
        "agents",
        "teams",
        "managers",
        "runtime",
        "products",
        "data",
        "docs",
    ]

    def __init__(self, base_path: Path):
        self.base_path = base_path

    def check(self) -> Dict[str, Any]:
        checks: List[Dict[str, Any]] = []

        for rel in self.REQUIRED_DIRS:
            path = self.base_path / rel
            checks.append({
                "name": f"directory:{rel}",
                "status": "OK" if path.is_dir() else "FAIL",
                "message": "exists" if path.is_dir() else "missing",
            })

        for rel in self.REQUIRED_FILES:
            path = self.base_path / rel
            checks.append({
                "name": f"file:{rel}",
                "status": "OK" if path.is_file() else "FAIL",
                "message": "exists" if path.is_file() else "missing",
            })

        failed = [c for c in checks if c["status"] == "FAIL"]
        return {
            "ready": len(failed) == 0,
            "status": "ready" if not failed else "not_ready",
            "checks": checks,
        }
