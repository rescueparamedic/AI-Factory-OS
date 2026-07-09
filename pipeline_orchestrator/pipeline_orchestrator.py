from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List
import json


class PipelineOrchestrator:
    """
    AI Factory OS v1.6 MVP Pipeline Orchestrator.

    사용자 요청 하나로 다음 순서를 자동 실행한다.

    Planning → Development → QA → Documentation → Approval Queue
    """

    def __init__(
        self,
        base_path: Path,
        planning_engine,
        development_engine,
        qa_engine,
        documentation_engine,
        approval_gate,
        worker_manager,
        event_bus,
    ):
        self.base_path = base_path
        self.planning_engine = planning_engine
        self.development_engine = development_engine
        self.qa_engine = qa_engine
        self.documentation_engine = documentation_engine
        self.approval_gate = approval_gate
        self.worker_manager = worker_manager
        self.event_bus = event_bus
        self.result_dir = base_path / "data" / "pipeline_runs"
        self.report_dir = base_path / "docs" / "pipeline"
        self.result_dir.mkdir(parents=True, exist_ok=True)
        self.report_dir.mkdir(parents=True, exist_ok=True)

    def run(self, request: str, product_id: str = "blog_growth_analyzer") -> Dict[str, Any]:
        now = datetime.now().astimezone()
        pipeline_id = f"PIPELINE-{now.strftime('%Y%m%d-%H%M%S')}"
        steps: List[Dict[str, str]] = []

        self.event_bus.publish("PIPELINE_STARTED", {
            "pipeline_id": pipeline_id,
            "product_id": product_id,
            "request": request,
        })

        plan = self.planning_engine.create_plan(request=request, product_id=product_id)
        steps.append({"name": "planning", "status": "completed", "id": plan.get("plan_id", "")})

        dev = self.development_engine.run(plan_id=plan["plan_id"], apply_changes=False)
        steps.append({"name": "development", "status": dev.get("status", ""), "id": dev.get("run_id", "")})

        qa = self.qa_engine.run(dev_run_id=dev["run_id"])
        steps.append({"name": "qa", "status": qa.get("decision", ""), "id": qa.get("qa_id", "")})

        docs = self.documentation_engine.run(qa_id=qa["qa_id"])
        steps.append({"name": "documentation", "status": docs.get("status", ""), "id": docs.get("doc_id", "")})

        approval = self.approval_gate.create(doc_id=docs["doc_id"])
        steps.append({"name": "approval_queue", "status": approval.get("status", ""), "id": approval.get("approval_id", "")})

        result = {
            "pipeline_id": pipeline_id,
            "created_at": now.isoformat(timespec="seconds"),
            "status": "completed",
            "product_id": product_id,
            "request": request,
            "plan_id": plan.get("plan_id", ""),
            "dev_run_id": dev.get("run_id", ""),
            "qa_id": qa.get("qa_id", ""),
            "doc_id": docs.get("doc_id", ""),
            "approval_id": approval.get("approval_id", ""),
            "qa_decision": qa.get("decision", ""),
            "qa_score": qa.get("score", ""),
            "steps": steps,
            "next_stage": "owner_approval_required",
        }

        pipeline_path = self.result_dir / f"{pipeline_id}.json"
        result["pipeline_path"] = str(pipeline_path)
        pipeline_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

        report_path = self._write_report(result)
        result["report_path"] = str(report_path)
        pipeline_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

        self.event_bus.publish("PIPELINE_COMPLETED", {
            "pipeline_id": pipeline_id,
            "approval_id": result["approval_id"],
            "qa_decision": result["qa_decision"],
        })

        self.worker_manager.run(
            "audit_log_worker",
            {
                "actor": "PipelineOrchestrator",
                "action": "PIPELINE_COMPLETED",
                "target": pipeline_id,
                "reason": "User request executed through AI Factory development pipeline",
                "result": "success",
                "metadata": {
                    "product_id": product_id,
                    "plan_id": result["plan_id"],
                    "dev_run_id": result["dev_run_id"],
                    "qa_id": result["qa_id"],
                    "doc_id": result["doc_id"],
                    "approval_id": result["approval_id"],
                },
            },
        )

        return result

    def latest(self) -> Dict[str, Any]:
        results = sorted(self.result_dir.glob("PIPELINE-*.json"), reverse=True)
        if not results:
            raise FileNotFoundError("No pipeline result found.")
        return json.loads(results[0].read_text(encoding="utf-8"))

    def list_results(self, limit: int = 10) -> List[Dict[str, Any]]:
        items = []
        for path in sorted(self.result_dir.glob("PIPELINE-*.json"), reverse=True):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                items.append({
                    "pipeline_id": data.get("pipeline_id", path.stem),
                    "status": data.get("status", ""),
                    "approval_id": data.get("approval_id", ""),
                    "created_at": data.get("created_at", ""),
                })
            except Exception:
                continue
            if len(items) >= limit:
                break
        return items

    def _write_report(self, result: Dict[str, Any]) -> Path:
        path = self.report_dir / f"{result['pipeline_id']}_pipeline_report.md"
        lines = [
            f"# Pipeline Orchestrator Report - {result['pipeline_id']}",
            "",
            f"Product: {result.get('product_id')}",
            f"Request: {result.get('request')}",
            f"Status: {result.get('status')}",
            f"Next Stage: {result.get('next_stage')}",
            "",
            "## Result IDs",
            "",
            f"- Plan: `{result.get('plan_id')}`",
            f"- Development: `{result.get('dev_run_id')}`",
            f"- QA: `{result.get('qa_id')}`",
            f"- Documentation: `{result.get('doc_id')}`",
            f"- Approval: `{result.get('approval_id')}`",
            "",
            "## QA",
            "",
            f"- Decision: {result.get('qa_decision')}",
            f"- Score: {result.get('qa_score')}",
            "",
            "## Steps",
            "",
        ]
        for step in result.get("steps", []):
            lines.append(f"- [{step.get('status')}] {step.get('name')}: `{step.get('id')}`")
        lines.extend([
            "",
            "## Owner Action Required",
            "",
            "다음 명령으로 승인 또는 반려하세요.",
            "",
            "```powershell",
            "python main.py approve latest",
            "python main.py approve approve",
            "python main.py approve reject --reason \"수정 필요\"",
            "```",
        ])
        path.write_text("\n".join(lines), encoding="utf-8")
        return path
