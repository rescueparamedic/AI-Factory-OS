from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional
import json


class DevelopmentEngine:
    def __init__(self, base_path: Path, planning_engine, worker_manager, event_bus):
        self.base_path = base_path
        self.planning_engine = planning_engine
        self.worker_manager = worker_manager
        self.event_bus = event_bus
        self.run_dir = base_path / "data" / "development_runs"
        self.artifact_root = base_path / "data" / "development_artifacts"
        self.report_dir = base_path / "docs" / "development"
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.artifact_root.mkdir(parents=True, exist_ok=True)
        self.report_dir.mkdir(parents=True, exist_ok=True)

    def run(self, plan_id: Optional[str] = None, apply_changes: bool = False) -> Dict[str, Any]:
        if apply_changes:
            return self._blocked_apply_result(plan_id)

        plan = self.planning_engine.get_plan(plan_id)
        now = datetime.now().astimezone()
        run_id = f"DEV-{now.strftime('%Y%m%d-%H%M%S')}"
        artifact_dir = self.artifact_root / run_id
        artifact_dir.mkdir(parents=True, exist_ok=True)

        generated_files = []
        for target in plan.get("expected_files", []):
            if str(target).endswith("/"):
                continue
            artifact = self._create_artifact(artifact_dir, target, plan)
            generated_files.append({
                "target_path": target,
                "artifact_path": str(artifact),
                "action": self._infer_action(target),
                "status": "generated_draft",
            })

        diff_plan = self._make_diff_plan(run_id, plan, generated_files)
        diff_path = self.run_dir / f"{run_id}_diff_plan.json"
        diff_path.write_text(json.dumps(diff_plan, ensure_ascii=False, indent=2), encoding="utf-8")
        report_path = self._write_report(run_id, plan, generated_files, diff_path)

        result = {
            "run_id": run_id,
            "created_at": now.isoformat(timespec="seconds"),
            "status": "completed",
            "mode": "dry_run",
            "plan_id": plan["plan_id"],
            "product_id": plan["product_id"],
            "request": plan["request"],
            "generated_files": generated_files,
            "diff_path": str(diff_path),
            "report_path": str(report_path),
            "approval_required_before_apply": True,
            "next_stage": "qa_ready",
        }

        run_path = self.run_dir / f"{run_id}.json"
        result["run_path"] = str(run_path)
        run_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

        self.event_bus.publish("DEVELOPMENT_RUN_COMPLETED", {
            "run_id": run_id,
            "plan_id": plan["plan_id"],
            "product_id": plan["product_id"],
            "mode": "dry_run",
        })

        self.worker_manager.run(
            "audit_log_worker",
            {
                "actor": "DevelopmentEngine",
                "action": "DEVELOPMENT_DRY_RUN_COMPLETED",
                "target": run_id,
                "reason": "Planning handoff converted into development artifacts",
                "result": "success",
                "metadata": {
                    "plan_id": plan["plan_id"],
                    "product_id": plan["product_id"],
                    "generated_files": len(generated_files),
                    "apply_changes": False,
                },
            },
        )

        return result

    def list_runs(self, limit: int = 10) -> List[Dict[str, Any]]:
        items = []
        for path in sorted(self.run_dir.glob("DEV-*.json"), reverse=True):
            if path.name.endswith("_diff_plan.json"):
                continue
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                items.append({
                    "run_id": data.get("run_id", path.stem),
                    "plan_id": data.get("plan_id", ""),
                    "status": data.get("status", ""),
                    "created_at": data.get("created_at", ""),
                })
            except Exception:
                continue
            if len(items) >= limit:
                break
        return items

    def latest_run(self) -> Dict[str, Any]:
        runs = [p for p in sorted(self.run_dir.glob("DEV-*.json"), reverse=True) if not p.name.endswith("_diff_plan.json")]
        if not runs:
            raise FileNotFoundError("No development run found.")
        return json.loads(runs[0].read_text(encoding="utf-8"))

    def _blocked_apply_result(self, plan_id: Optional[str]) -> Dict[str, Any]:
        now = datetime.now().astimezone()
        run_id = f"DEV-BLOCKED-{now.strftime('%Y%m%d-%H%M%S')}"
        result = {
            "run_id": run_id,
            "created_at": now.isoformat(timespec="seconds"),
            "status": "blocked",
            "mode": "apply_blocked",
            "plan_id": plan_id or "",
            "product_id": "",
            "request": "",
            "generated_files": [],
            "message": "Direct apply is blocked in v1.2.1 MVP. Use dry_run and Approval Gate first.",
            "approval_required_before_apply": True,
            "next_stage": "needs_owner_approval",
        }
        path = self.run_dir / f"{run_id}.json"
        result["run_path"] = str(path)
        result["diff_path"] = ""
        result["report_path"] = ""
        path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        return result

    def _safe_artifact_name(self, target_path: str) -> str:
        return str(target_path).replace("\\", "/").replace("/", "__").replace(":", "_")

    def _infer_action(self, target_path: str) -> str:
        path = self.base_path / target_path
        return "modify_candidate" if path.exists() else "create_candidate"

    def _create_artifact(self, artifact_dir: Path, target_path: str, plan: Dict[str, Any]) -> Path:
        safe_name = self._safe_artifact_name(target_path)
        if target_path.endswith(".py"):
            artifact_path = artifact_dir / safe_name
            content = self._python_stub(target_path, plan)
        elif target_path.endswith(".json"):
            artifact_path = artifact_dir / safe_name
            content = json.dumps(self._json_stub(target_path, plan), ensure_ascii=False, indent=2)
        elif target_path.endswith(".md"):
            artifact_path = artifact_dir / safe_name
            content = self._markdown_stub(target_path, plan)
        else:
            artifact_path = artifact_dir / f"{safe_name}.txt"
            content = self._text_stub(target_path, plan)
        artifact_path.write_text(content, encoding="utf-8")
        return artifact_path

    def _python_stub(self, target_path: str, plan: Dict[str, Any]) -> str:
        if "ai_review_client" in target_path:
            return (
                "from __future__ import annotations\n\n"
                "from dataclasses import dataclass\n"
                "from typing import Dict, Any\n\n\n"
                "@dataclass\n"
                "class AIReviewResult:\n"
                "    status: str\n"
                "    score: int\n"
                "    summary: str\n"
                "    risks: list[str]\n"
                "    raw: Dict[str, Any]\n\n\n"
                "class AIReviewClient:\n"
                "    def __init__(self, provider: str = 'gemini', api_key: str | None = None, model: str = 'gemini-2.5-flash'):\n"
                "        self.provider = provider\n"
                "        self.api_key = api_key\n"
                "        self.model = model\n\n"
                "    def review_blog_post(self, title: str, body: str, keyword: str = '') -> AIReviewResult:\n"
                "        if not self.api_key:\n"
                "            return AIReviewResult(status='fallback', score=0, summary='API Key가 없어 외부 검수를 실행하지 않았습니다.', risks=['api_key_missing'], raw={})\n"
                "        return AIReviewResult(status='draft_not_connected', score=0, summary='검수 클라이언트 초안입니다. 실제 API 연결은 승인 후 진행합니다.', risks=['adapter_not_implemented'], raw={'provider': self.provider, 'model': self.model})\n"
            )
        return (
            f"\"\"\"\nDevelopment draft for {target_path}\n"
            f"Plan: {plan['plan_id']}\n"
            f"Request: {plan['request']}\n\"\"\"\n\n"
            "def development_placeholder():\n"
            "    return 'Generated draft artifact. Review before applying.'\n"
        )

    def _json_stub(self, target_path: str, plan: Dict[str, Any]) -> Dict[str, Any]:
        if "review_config" in target_path:
            return {
                "enabled": True,
                "provider": "gemini",
                "model": "gemini-2.5-flash",
                "auto_apply_revision": False,
                "fallback_enabled": True,
                "approval_required_for_external_api": True,
                "plan_id": plan["plan_id"],
                "notes": "Draft config generated by Development Engine. Review before applying."
            }
        if "product_config" in target_path:
            return {
                "change_type": "product_config_update_candidate",
                "plan_id": plan["plan_id"],
                "requested_feature": plan["request"],
                "required_workers_add": ["audit_log_worker", "python_file_worker"],
                "required_agents_add": ["development_agent", "test_agent", "documentation_agent"],
                "approval_required": plan.get("approval_required", False),
            }
        return {"generated_by": "AI Factory OS Development Engine", "plan_id": plan["plan_id"], "request": plan["request"]}

    def _markdown_stub(self, target_path: str, plan: Dict[str, Any]) -> str:
        return (
            f"# Development Draft\n\nTarget: `{target_path}`\n\nPlan: `{plan['plan_id']}`\n\n"
            f"Request:\n\n{plan['request']}\n\n"
            "## 적용 전 확인\n\n"
            "- 외부 API Key는 코드에 직접 저장하지 않습니다.\n"
            "- 실패 시 fallback 동작이 필요합니다.\n"
            "- QA 및 사용자 승인 후 실제 반영합니다.\n"
        )

    def _text_stub(self, target_path: str, plan: Dict[str, Any]) -> str:
        return f"Development draft for {target_path}\nPlan: {plan['plan_id']}\nRequest: {plan['request']}\n"

    def _make_diff_plan(self, run_id: str, plan: Dict[str, Any], generated_files: List[Dict[str, Any]]) -> Dict[str, Any]:
        return {
            "run_id": run_id,
            "plan_id": plan["plan_id"],
            "product_id": plan["product_id"],
            "mode": "dry_run",
            "summary": "Draft artifacts generated. No project files were modified.",
            "changes": generated_files,
            "approval_required_before_apply": True,
            "qa_required": plan.get("regression_required", True),
        }

    def _write_report(self, run_id: str, plan: Dict[str, Any], generated_files: List[Dict[str, Any]], diff_path: Path) -> Path:
        path = self.report_dir / f"{run_id}_development_report.md"
        lines = [
            f"# Development Engine Report - {run_id}",
            "",
            f"Plan ID: {plan['plan_id']}",
            f"Product ID: {plan['product_id']}",
            "Mode: dry_run",
            f"Request: {plan['request']}",
            f"Diff Plan: {diff_path}",
            "",
            "## Generated Draft Artifacts",
            "",
        ]
        for item in generated_files:
            lines.append(f"- Target: `{item['target_path']}`")
            lines.append(f"  - Artifact: `{item['artifact_path']}`")
            lines.append(f"  - Action: `{item['action']}`")
        lines.extend(["", "## Safety", "", "- 기존 파일은 수정하지 않았습니다.", "- 실제 반영은 Approval Gate 이후 진행해야 합니다.", "- 다음 단계는 QA Engine입니다."])
        path.write_text("\n".join(lines), encoding="utf-8")
        return path
