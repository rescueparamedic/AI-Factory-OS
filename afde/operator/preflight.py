"""Read-only readiness checks for the guided operator workflow."""
from __future__ import annotations

import importlib
import os
from pathlib import Path
import subprocess

from afde.provider_manager import ProviderManager
from real_worker_runtime.controlled_execution import (
    ControlledExecutionPolicy, ExecutionRequest,
)

from .models import PreflightCheck, PreflightResult


SUPPORTED_PROVIDERS = {"mock", "openai", "gemini"}


class OperatorPreflight:
    def __init__(
        self, workspace: str | Path = ".", provider: str = "mock",
        allow_live_api: bool = False,
    ) -> None:
        self.workspace = Path(workspace).expanduser().resolve()
        self.provider = str(provider or "mock").lower()
        self.allow_live_api = bool(allow_live_api)

    def run(self) -> PreflightResult:
        checks = (
            self._runtime(),
            self._workspace(),
            self._repository(),
            self._provider(),
            self._live_opt_in(),
            self._controlled_execution(),
            self._runtime_data(),
            PreflightCheck(
                "credential_output", "PASS",
                "Output reports credential state only; credential values are never read.",
            ),
        )
        blocking = any(item.status == "FAIL" for item in checks)
        status = "FAIL" if blocking else (
            "WARN" if any(item.status == "WARN" for item in checks) else "PASS"
        )
        return PreflightResult(
            status, blocking, self.provider, str(self.workspace), checks,
        )

    def _runtime(self) -> PreflightCheck:
        try:
            module = importlib.import_module("real_worker_runtime")
            available = hasattr(module, "RealWorkerRuntime")
        except ImportError:
            available = False
        return PreflightCheck(
            "runtime_availability", "PASS" if available else "FAIL",
            "AFDE Runtime is importable." if available else "AFDE Runtime is unavailable.",
        )

    def _workspace(self) -> PreflightCheck:
        exists = self.workspace.is_dir()
        return PreflightCheck(
            "workspace", "PASS" if exists else "FAIL",
            "Workspace directory exists." if exists else "Workspace directory does not exist.",
            {"workspace": str(self.workspace)},
        )

    def _repository(self) -> PreflightCheck:
        if not self.workspace.is_dir():
            return PreflightCheck("repository", "FAIL", "Repository cannot be inspected.")
        inside = self._git("rev-parse", "--is-inside-work-tree")
        if inside != "true":
            return PreflightCheck(
                "repository", "FAIL", "Workspace is not a Git repository.",
            )
        branch = self._git("branch", "--show-current") or "unavailable"
        dirty_output = self._git("status", "--porcelain")
        if dirty_output is None:
            return PreflightCheck("repository", "FAIL", "Git status is unavailable.")
        dirty = bool(dirty_output)
        return PreflightCheck(
            "repository", "WARN" if dirty else "PASS",
            "Repository working tree is dirty." if dirty else "Repository is available and clean.",
            {"branch": branch, "working_tree": "dirty" if dirty else "clean"},
        )

    def _provider(self) -> PreflightCheck:
        if self.provider not in SUPPORTED_PROVIDERS:
            return PreflightCheck(
                "provider", "FAIL", f"Unknown provider: {self.provider}.",
                {"provider": self.provider, "configured": False},
            )
        statuses = {
            item["provider"]: item
            for item in ProviderManager(self.workspace).as_dicts()
        }
        configured = self.provider == "mock" or bool(
            statuses.get(self.provider, {}).get("configured")
        )
        supported = self.provider in {"mock", "openai"}
        passed = configured and supported
        summary = (
            "Deterministic mock provider is available."
            if self.provider == "mock" else
            f"{self.provider} provider is configured."
            if passed else
            f"{self.provider} provider is unavailable or unsupported for execution."
        )
        return PreflightCheck(
            "provider", "PASS" if passed else "FAIL", summary,
            {"provider": self.provider, "configured": configured},
        )

    def _live_opt_in(self) -> PreflightCheck:
        if self.provider == "mock":
            return PreflightCheck(
                "live_provider_opt_in", "PASS",
                "Mock mode is network-free and needs no live-provider opt-in.",
            )
        allowed = self.allow_live_api
        return PreflightCheck(
            "live_provider_opt_in", "PASS" if allowed else "FAIL",
            "Explicit live-provider opt-in is present." if allowed else
            "Live provider requires explicit --allow-live-api opt-in.",
        )

    def _controlled_execution(self) -> PreflightCheck:
        if not self.workspace.is_dir():
            return PreflightCheck(
                "controlled_execution", "FAIL", "Controlled Execution cannot inspect the workspace.",
            )
        try:
            request = ExecutionRequest.file_write(
                "controlled_execution/operator_preflight_probe.txt", "probe\n",
                "operator_preflight", "Read-only policy compatibility probe",
            )
            decision = ControlledExecutionPolicy(self.workspace).classify(request)
        except (OSError, ValueError) as exc:
            return PreflightCheck(
                "controlled_execution", "FAIL",
                f"Controlled Execution compatibility check failed: {type(exc).__name__}.",
            )
        compatible = decision.decision in {"AUTO_APPROVE", "ASK_USER"}
        return PreflightCheck(
            "controlled_execution", "PASS" if compatible else "FAIL",
            "Controlled Execution accepts a contained text-write proposal."
            if compatible else "Controlled Execution rejected the compatibility probe.",
            {"decision": decision.decision, "classification": decision.classification},
        )

    def _runtime_data(self) -> PreflightCheck:
        target = self.workspace / "data" / "runtime_sessions"
        candidate = target if target.exists() else self.workspace
        writable = candidate.is_dir() and os.access(candidate, os.W_OK)
        return PreflightCheck(
            "runtime_data_path", "PASS" if writable else "FAIL",
            "Runtime data path is writable." if writable else "Runtime data path is not writable.",
        )

    def _git(self, *arguments: str) -> str | None:
        try:
            result = subprocess.run(
                ["git", *arguments], cwd=self.workspace, capture_output=True,
                text=True, encoding="utf-8", errors="replace", timeout=5,
                check=False, shell=False,
            )
        except (OSError, subprocess.SubprocessError):
            return None
        return result.stdout.strip() if result.returncode == 0 else None
