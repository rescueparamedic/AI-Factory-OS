from __future__ import annotations
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional
import ast, json

class QAEngine:
    def __init__(self, base_path: Path, development_engine, worker_manager, event_bus):
        self.base_path = base_path; self.development_engine = development_engine; self.worker_manager = worker_manager; self.event_bus = event_bus
        self.qa_dir = base_path / "data" / "qa_results"; self.report_dir = base_path / "docs" / "qa"
        self.qa_dir.mkdir(parents=True, exist_ok=True); self.report_dir.mkdir(parents=True, exist_ok=True)

    def run(self, dev_run_id: Optional[str] = None) -> Dict[str, Any]:
        dev_run = self._load_dev_run(dev_run_id); now = datetime.now().astimezone(); qa_id = f"QA-{now.strftime('%Y%m%d-%H%M%S')}"
        checks: List[Dict[str, str]] = [self._check_dev_run(dev_run), self._check_diff_plan(dev_run)]
        for item in dev_run.get("generated_files", []): checks.extend(self._check_artifact(item))
        score = self._score(checks); grade = self._grade(score); decision = self._decision(score, checks)
        recs = []
        if decision != "pass": recs.append("FAIL 또는 WARN 항목을 수정한 뒤 Development Engine을 다시 실행하세요.")
        if any(c["name"].startswith("python_syntax") and c["status"] != "OK" for c in checks): recs.append("Python 산출물 문법 오류를 먼저 해결하세요.")
        if any(c["name"].startswith("json_parse") and c["status"] != "OK" for c in checks): recs.append("JSON 산출물 구조를 먼저 수정하세요.")
        if not recs: recs.append("QA 기준을 통과했습니다. 다음 단계는 Documentation Engine 또는 Approval Gate입니다.")
        result = {"qa_id": qa_id, "created_at": now.isoformat(timespec="seconds"), "status": "completed", "dev_run_id": dev_run.get("run_id", ""), "plan_id": dev_run.get("plan_id", ""), "product_id": dev_run.get("product_id", ""), "score": score, "grade": grade, "decision": decision, "checks": checks, "recommendations": recs, "next_stage": "documentation_ready" if decision == "pass" else "development_revision_required"}
        qa_path = self.qa_dir / f"{qa_id}.json"; result["qa_path"] = str(qa_path); qa_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        report_path = self._write_report(result); result["report_path"] = str(report_path); qa_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        self.event_bus.publish("QA_RUN_COMPLETED", {"qa_id": qa_id, "dev_run_id": result["dev_run_id"], "score": score, "decision": decision})
        self.worker_manager.run("audit_log_worker", {"actor": "QAEngine", "action": "QA_RUN_COMPLETED", "target": qa_id, "reason": "Development artifacts validated", "result": decision, "metadata": {"dev_run_id": result["dev_run_id"], "plan_id": result["plan_id"], "score": score, "grade": grade, "decision": decision}})
        return result

    def list_results(self, limit: int = 10) -> List[Dict[str, Any]]:
        items=[]
        for path in sorted(self.qa_dir.glob("QA-*.json"), reverse=True):
            try:
                data=json.loads(path.read_text(encoding="utf-8")); items.append({"qa_id": data.get("qa_id", path.stem), "dev_run_id": data.get("dev_run_id", ""), "score": data.get("score", ""), "decision": data.get("decision", ""), "created_at": data.get("created_at", "")})
            except Exception: continue
            if len(items) >= limit: break
        return items

    def latest_result(self) -> Dict[str, Any]:
        results=sorted(self.qa_dir.glob("QA-*.json"), reverse=True)
        if not results: raise FileNotFoundError("No QA result found.")
        return json.loads(results[0].read_text(encoding="utf-8"))

    def _load_dev_run(self, dev_run_id: Optional[str]) -> Dict[str, Any]:
        if not dev_run_id: return self.development_engine.latest_run()
        path = self.base_path / "data" / "development_runs" / f"{dev_run_id}.json"
        if not path.exists(): raise FileNotFoundError(f"Development run not found: {dev_run_id}")
        return json.loads(path.read_text(encoding="utf-8"))

    def _check_dev_run(self, dev_run):
        return {"name": "development_run_status", "status": "OK", "message": "completed dry_run found"} if dev_run.get("status") == "completed" and dev_run.get("mode") == "dry_run" else {"name": "development_run_status", "status": "FAIL", "message": "development run is not completed dry_run"}

    def _check_diff_plan(self, dev_run):
        path=Path(dev_run.get("diff_path", ""))
        if path.exists():
            try: json.loads(path.read_text(encoding="utf-8")); return {"name": "diff_plan_json", "status": "OK", "message": "diff plan exists and is valid JSON"}
            except Exception as exc: return {"name": "diff_plan_json", "status": "FAIL", "message": f"diff plan parse failed: {exc}"}
        return {"name": "diff_plan_json", "status": "FAIL", "message": "diff plan missing"}

    def _check_artifact(self, item):
        checks=[]; target=item.get("target_path", ""); artifact_path=Path(item.get("artifact_path", ""))
        if not artifact_path.exists(): return [{"name": f"artifact_exists:{target}", "status": "FAIL", "message": "artifact file missing"}]
        checks.append({"name": f"artifact_exists:{target}", "status": "OK", "message": "artifact file exists"})
        # target path decides type because artifact files use safe names without suffix sometimes
        if str(target).endswith(".py"): checks.append(self._check_python_syntax(target, artifact_path))
        elif str(target).endswith(".json"): checks.append(self._check_json_parse(target, artifact_path))
        elif str(target).endswith(".md"): checks.append(self._check_markdown_basic(target, artifact_path))
        else: checks.append({"name": f"artifact_type:{target}", "status": "WARN", "message": "unverified file type"})
        return checks

    def _check_python_syntax(self, target, path):
        try: ast.parse(path.read_text(encoding="utf-8"), filename=str(path)); return {"name": f"python_syntax:{target}", "status": "OK", "message": "python syntax valid"}
        except SyntaxError as exc: return {"name": f"python_syntax:{target}", "status": "FAIL", "message": f"syntax error: {exc}"}
    def _check_json_parse(self, target, path):
        try: json.loads(path.read_text(encoding="utf-8")); return {"name": f"json_parse:{target}", "status": "OK", "message": "json parse valid"}
        except Exception as exc: return {"name": f"json_parse:{target}", "status": "FAIL", "message": f"json parse failed: {exc}"}
    def _check_markdown_basic(self, target, path):
        text=path.read_text(encoding="utf-8")
        if len(text.strip()) < 20: return {"name": f"markdown_basic:{target}", "status": "WARN", "message": "markdown content too short"}
        if "#" not in text: return {"name": f"markdown_basic:{target}", "status": "WARN", "message": "markdown heading missing"}
        return {"name": f"markdown_basic:{target}", "status": "OK", "message": "markdown basic check passed"}
    def _score(self, checks):
        score=100
        for c in checks:
            if c["status"] == "FAIL": score -= 20
            elif c["status"] == "WARN": score -= 8
        return max(0, score)
    def _grade(self, score): return "A" if score >= 90 else "B" if score >= 80 else "C" if score >= 70 else "D" if score >= 60 else "F"
    def _decision(self, score, checks):
        if any(c["status"] == "FAIL" for c in checks): return "fail"
        if score < 85 or any(c["status"] == "WARN" for c in checks): return "warn"
        return "pass"
    def _write_report(self, result):
        path=self.report_dir / f"{result['qa_id']}_qa_report.md"
        lines=[f"# QA Engine Report - {result['qa_id']}", "", f"Development Run: {result.get('dev_run_id', '')}", f"Plan ID: {result.get('plan_id', '')}", f"Product ID: {result.get('product_id', '')}", f"Score: {result.get('score')}", f"Grade: {result.get('grade')}", f"Decision: {result.get('decision')}", "", "## Checks", ""]
        for c in result.get("checks", []): lines.append(f"- [{c['status']}] {c['name']}: {c['message']}")
        lines.extend(["", "## Recommendations", ""])
        for item in result.get("recommendations", []): lines.append(f"- {item}")
        path.write_text("\n".join(lines), encoding="utf-8"); return path
