# -*- coding: utf-8 -*-
"""AFDE Environment Checker.
Checks local development requirements for AI Factory OS.
"""
from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, List


@dataclass
class CheckResult:
    name: str
    status: str
    detail: str
    required: bool = True


def _command_version(command: List[str]) -> str:
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=10)
        output = (result.stdout or result.stderr or "").strip().splitlines()
        return output[0] if output else "installed"
    except Exception as exc:
        return f"error: {exc}"


class EnvironmentChecker:
    def __init__(self, project_root: str | Path | None = None) -> None:
        self.project_root = Path(project_root or Path.cwd()).resolve()

    def check_python(self) -> CheckResult:
        version = sys.version.split()[0]
        status = "PASS" if sys.version_info >= (3, 10) else "FAIL"
        return CheckResult("python", status, f"Python {version}")

    def check_git(self) -> CheckResult:
        git_path = shutil.which("git")
        if not git_path:
            return CheckResult("git", "FAIL", "git command not found")
        return CheckResult("git", "PASS", _command_version(["git", "--version"]))

    def check_pytest(self) -> CheckResult:
        if importlib.util.find_spec("pytest") is None:
            return CheckResult("pytest", "FAIL", "pytest module not installed")
        return CheckResult("pytest", "PASS", "pytest installed")

    def check_project_root(self) -> CheckResult:
        main_py = self.project_root / "main.py"
        if main_py.exists():
            return CheckResult("project_root", "PASS", str(self.project_root))
        return CheckResult("project_root", "FAIL", f"main.py not found in {self.project_root}")

    def check_git_repository(self) -> CheckResult:
        if (self.project_root / ".git").exists():
            branch = _command_version(["git", "branch", "--show-current"])
            return CheckResult("git_repository", "PASS", f"branch={branch}")
        return CheckResult("git_repository", "FAIL", ".git directory not found")

    def check_provider_keys(self) -> List[CheckResult]:
        checks = []
        key_map = {
            "openai_key": "OPENAI_API_KEY",
            "gemini_key": "GEMINI_API_KEY",
            "claude_key": "ANTHROPIC_API_KEY",
        }
        for name, env_name in key_map.items():
            configured = bool(os.environ.get(env_name, "").strip())
            checks.append(CheckResult(name, "PASS" if configured else "WARN", f"{env_name}={'configured' if configured else 'not configured'}", required=False))
        return checks

    def run_all(self) -> Dict[str, object]:
        results: List[CheckResult] = [
            self.check_python(),
            self.check_git(),
            self.check_pytest(),
            self.check_project_root(),
            self.check_git_repository(),
        ]
        results.extend(self.check_provider_keys())
        failed_required = [r for r in results if r.required and r.status != "PASS"]
        return {
            "status": "PASS" if not failed_required else "FAIL",
            "project_root": str(self.project_root),
            "results": [asdict(r) for r in results],
        }

    def save_report(self, output_path: str | Path | None = None) -> Path:
        report = self.run_all()
        if output_path is None:
            output_dir = self.project_root / "data" / "afde" / "environment"
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path = output_dir / "environment_check.json"
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        return output_path
