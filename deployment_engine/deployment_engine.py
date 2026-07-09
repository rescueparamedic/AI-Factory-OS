from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional
import json


class DeploymentEngine:
    def __init__(self, base_path: Path, release_engine, worker_manager, event_bus):
        self.base_path = base_path
        self.release_engine = release_engine
        self.worker_manager = worker_manager
        self.event_bus = event_bus
        self.deploy_dir = base_path / "data" / "deployments"
        self.history_dir = base_path / "data" / "deployment_history"
        self.rollback_dir = base_path / "data" / "deployment_rollbacks"
        self.report_dir = base_path / "docs" / "deployments"
        self.environment_dir = base_path / "deployments"
        for d in [self.deploy_dir, self.history_dir, self.rollback_dir, self.report_dir, self.environment_dir]:
            d.mkdir(parents=True, exist_ok=True)

    def create(self, release_id: Optional[str] = None, environment: str = "staging", apply: bool = False) -> Dict[str, Any]:
        release = self._load_release(release_id)
        now = datetime.now().astimezone()
        deploy_id = f"DEPLOY-{now.strftime('%Y%m%d-%H%M%S')}"
        mode = "apply_blocked_dry_run" if apply else "dry_run"
        warnings: List[str] = []

        if apply:
            warnings.append("MVP safety policy: real deployment is blocked. Recorded as dry_run.")
        if environment == "production":
            warnings.append("Production deployment is recorded as deploy candidate only in MVP.")

        rollback_path = self._create_rollback_point(deploy_id, release, environment)
        manifest_path = self._write_deploy_manifest(deploy_id, release, environment, mode, rollback_path)
        report_path = self._write_deploy_report(deploy_id, release, environment, mode, rollback_path, warnings)

        env_dir = self.environment_dir / environment
        env_dir.mkdir(parents=True, exist_ok=True)
        candidate_path = env_dir / f"{deploy_id}_DEPLOY_CANDIDATE.json"
        candidate = {
            "deploy_id": deploy_id,
            "release_id": release.get("release_id"),
            "version": release.get("version"),
            "environment": environment,
            "mode": mode,
            "package_path": release.get("package_path", ""),
            "manifest_path": str(manifest_path),
            "rollback_path": str(rollback_path),
            "status": "candidate_created",
        }
        candidate_path.write_text(json.dumps(candidate, ensure_ascii=False, indent=2), encoding="utf-8")

        result = {
            "deploy_id": deploy_id,
            "created_at": now.isoformat(timespec="seconds"),
            "status": "completed",
            "mode": mode,
            "environment": environment,
            "release_id": release.get("release_id", ""),
            "product_id": release.get("product_id", ""),
            "version": release.get("version", ""),
            "package_path": release.get("package_path", ""),
            "manifest_path": str(manifest_path),
            "rollback_path": str(rollback_path),
            "candidate_path": str(candidate_path),
            "report_path": str(report_path),
            "warnings": warnings,
            "next_stage": "deployed_candidate_ready",
        }

        deploy_path = self.deploy_dir / f"{deploy_id}.json"
        history_path = self.history_dir / f"{deploy_id}.json"
        result["deploy_path"] = str(deploy_path)
        result["history_path"] = str(history_path)
        deploy_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        history_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

        self.event_bus.publish("DEPLOYMENT_CREATED", {
            "deploy_id": deploy_id,
            "release_id": result["release_id"],
            "environment": environment,
            "mode": mode,
        })

        self.worker_manager.run(
            "audit_log_worker",
            {
                "actor": "DeploymentEngine",
                "action": "DEPLOYMENT_CREATED",
                "target": deploy_id,
                "reason": "Release package converted into deployment candidate",
                "result": "success",
                "metadata": {
                    "release_id": result["release_id"],
                    "environment": environment,
                    "version": result["version"],
                    "mode": mode,
                    "rollback_path": str(rollback_path),
                },
            },
        )
        return result

    def latest(self) -> Dict[str, Any]:
        deployments = sorted(self.history_dir.glob("DEPLOY-*.json"), reverse=True)
        if not deployments:
            raise FileNotFoundError("No deployment found.")
        return json.loads(deployments[0].read_text(encoding="utf-8"))

    def list_deployments(self, limit: int = 10) -> List[Dict[str, Any]]:
        items = []
        for path in sorted(self.history_dir.glob("DEPLOY-*.json"), reverse=True):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                items.append({
                    "deploy_id": data.get("deploy_id", path.stem),
                    "environment": data.get("environment", ""),
                    "status": data.get("status", ""),
                    "created_at": data.get("created_at", ""),
                })
            except Exception:
                continue
            if len(items) >= limit:
                break
        return items

    def rollback_point(self, deploy_id: Optional[str] = None) -> Dict[str, Any]:
        if deploy_id:
            path = self.history_dir / f"{deploy_id}.json"
            if not path.exists():
                raise FileNotFoundError(f"Deployment not found: {deploy_id}")
            deployment = json.loads(path.read_text(encoding="utf-8"))
        else:
            deployment = self.latest()
        rollback_path = Path(deployment.get("rollback_path", ""))
        return {
            "deploy_id": deployment.get("deploy_id", ""),
            "status": "available" if rollback_path.exists() else "missing",
            "rollback_path": str(rollback_path),
            "message": "Rollback point is available." if rollback_path.exists() else "Rollback point is missing.",
        }

    def _load_release(self, release_id: Optional[str]) -> Dict[str, Any]:
        if not release_id:
            return self.release_engine.latest()
        paths = [
            self.base_path / "data" / "release_history" / f"{release_id}.json",
            self.base_path / "data" / "releases" / f"{release_id}.json",
        ]
        for path in paths:
            if path.exists():
                return json.loads(path.read_text(encoding="utf-8"))
        raise FileNotFoundError(f"Release not found: {release_id}")

    def _create_rollback_point(self, deploy_id: str, release: Dict[str, Any], environment: str) -> Path:
        path = self.rollback_dir / f"{deploy_id}_rollback.json"
        data = {
            "deploy_id": deploy_id,
            "environment": environment,
            "release_id": release.get("release_id"),
            "version": release.get("version"),
            "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "rollback_type": "metadata_snapshot",
            "note": "MVP rollback point stores metadata only. Future versions will snapshot deployed files.",
        }
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    def _write_deploy_manifest(self, deploy_id: str, release: Dict[str, Any], environment: str, mode: str, rollback_path: Path) -> Path:
        path = self.deploy_dir / f"{deploy_id}_manifest.json"
        manifest = {
            "deploy_id": deploy_id,
            "release_id": release.get("release_id"),
            "version": release.get("version"),
            "environment": environment,
            "mode": mode,
            "package_path": release.get("package_path"),
            "release_sha256": release.get("sha256"),
            "rollback_path": str(rollback_path),
            "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        }
        path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    def _write_deploy_report(self, deploy_id: str, release: Dict[str, Any], environment: str, mode: str, rollback_path: Path, warnings: List[str]) -> Path:
        path = self.report_dir / f"{deploy_id}_deployment_report.md"
        lines = [
            f"# Deployment Report - {deploy_id}",
            "",
            f"Release: `{release.get('release_id', '')}`",
            f"Version: `{release.get('version', '')}`",
            f"Environment: `{environment}`",
            f"Mode: `{mode}`",
            f"Package: `{release.get('package_path', '')}`",
            f"Rollback Point: `{rollback_path}`",
            "",
            "## Result",
            "",
            "Deployment candidate created.",
            "",
        ]
        if warnings:
            lines.extend(["## Warnings", ""])
            for warning in warnings:
                lines.append(f"- {warning}")
        lines.extend(["", "## Next", "", "Future versions will add real deployment apply and automated rollback execution."])
        path.write_text("\n".join(lines), encoding="utf-8")
        return path
