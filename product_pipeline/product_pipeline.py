from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List
import json


class ProductDevelopmentPipeline:
    """
    Sprint 10-2 MVP.
    Product 개발 요청을 Agent/Team/Worker 흐름으로 연결한다.
    """

    def __init__(
        self,
        base_path: Path,
        product_loader,
        task_engine,
        workflow_engine,
        agent_manager,
        team_manager,
        worker_manager,
        event_bus,
    ):
        self.base_path = base_path
        self.product_loader = product_loader
        self.task_engine = task_engine
        self.workflow_engine = workflow_engine
        self.agent_manager = agent_manager
        self.team_manager = team_manager
        self.worker_manager = worker_manager
        self.event_bus = event_bus
        self.pipeline_dir = base_path / "data" / "product_pipelines"
        self.pipeline_dir.mkdir(parents=True, exist_ok=True)

    def run(self, product_id: str, title: str, request: str) -> Dict[str, Any]:
        product = self.product_loader.load(product_id)
        now = datetime.now().astimezone()
        pipeline_id = f"PIPE-{now.strftime('%Y%m%d-%H%M%S')}"

        task = self.task_engine.create_task(
            title=title,
            description=request,
            product_id=product_id,
            assigned_worker="python_file_worker",
        )
        self.event_bus.publish("PRODUCT_PIPELINE_STARTED", {
            "pipeline_id": pipeline_id,
            "product_id": product_id,
            "task_id": task["task_id"],
        })

        ceo = self.agent_manager.get("ceo_agent").decide({
            **task,
            "pipeline_id": pipeline_id,
            "product_request": request,
        })

        pm = self.agent_manager.get("pm_agent").plan({
            **task,
            "pipeline_id": pipeline_id,
            "assigned_worker": "python_file_worker",
            "product_request": request,
        })

        task = self.workflow_engine.run_until(task, "in_progress")
        self.task_engine.save_task(task)

        dev_file = f"products/{product_id}/docs/{pipeline_id}_development_note.py"
        dev_payload = {
            "filename": dev_file,
            "content": (
                '"""\n'
                f"Product: {product['product_name']}\n"
                f"Pipeline: {pipeline_id}\n"
                f"Task: {task['task_id']}\n"
                f"Request: {request}\n"
                '"""\n\n'
                "def product_development_note():\n"
                f"    return {request!r}\n"
            ),
        }

        dev_team_result = self.team_manager.execute(
            "development_team",
            "python_file_worker",
            dev_payload,
        )

        task = self.workflow_engine.run_until(task, "testing")
        self.task_engine.save_task(task)

        qa_status = self._qa_check(dev_team_result)

        task = self.workflow_engine.run_until(task, "documentation")
        self.task_engine.save_task(task)

        report_result = self.team_manager.execute(
            "documentation_team",
            "markdown_worker",
            {
                "filename": f"products/{product_id}/docs/{pipeline_id}_report.md",
                "title": f"{product['product_name']} Development Pipeline Report",
                "body": [
                    f"Pipeline ID: {pipeline_id}",
                    f"Task ID: {task['task_id']}",
                    f"Request: {request}",
                    f"CEO Decision: {ceo['decision']['decision']}",
                    f"PM Plan: {pm['plan']['summary']}",
                    f"Development Result: {dev_team_result['worker_result']['status']}",
                    f"QA Status: {qa_status}",
                    "Result: Product development MVP pipeline completed.",
                ],
            },
        )

        audit = self.worker_manager.run(
            "audit_log_worker",
            {
                "actor": "ProductDevelopmentPipeline",
                "action": "PRODUCT_DEVELOPMENT_PIPELINE_COMPLETED",
                "target": task["task_id"],
                "reason": "Sprint 10-2 product development MVP pipeline",
                "result": "success",
                "metadata": {
                    "pipeline_id": pipeline_id,
                    "product_id": product_id,
                    "dev_result": dev_team_result,
                    "report_result": report_result,
                    "qa_status": qa_status,
                },
            },
        )

        task = self.workflow_engine.run_until(task, "done")
        self.task_engine.save_task(task)

        record = {
            "pipeline_id": pipeline_id,
            "timestamp": now.isoformat(timespec="seconds"),
            "product_id": product_id,
            "product_name": product["product_name"],
            "task_id": task["task_id"],
            "request": request,
            "status": "completed",
            "ceo_decision": ceo["decision"]["decision"],
            "pm_plan": pm["plan"]["summary"],
            "dev_result": dev_team_result["worker_result"]["status"],
            "qa_status": qa_status,
            "report_path": report_result["worker_result"]["output"].get("created_file", ""),
            "audit_path": audit["output"].get("created_file", ""),
        }

        record_path = self.pipeline_dir / f"{pipeline_id}.json"
        record["record_path"] = str(record_path)
        record_path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")

        self.event_bus.publish("PRODUCT_PIPELINE_COMPLETED", {
            "pipeline_id": pipeline_id,
            "product_id": product_id,
            "task_id": task["task_id"],
            "status": "completed",
        })

        return record

    def status(self) -> Dict[str, Any]:
        records = sorted(self.pipeline_dir.glob("PIPE-*.json"), reverse=True)
        reports = list((self.base_path / "products" / "blog_growth_analyzer" / "docs").glob("*_report.md"))
        return {
            "pipeline_count": len(records),
            "latest_pipeline_id": records[0].stem if records else "",
            "report_count": len(reports),
        }

    def _qa_check(self, dev_team_result: Dict[str, Any]) -> str:
        worker_result = dev_team_result.get("worker_result", {})
        if worker_result.get("status") == "completed":
            return "passed"
        return "failed"
