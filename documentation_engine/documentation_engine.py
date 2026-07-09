from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional
import json


class DocumentationEngine:
    """
    AI Factory OS v1.4 MVP Documentation Engine.

    QA 결과를 기반으로 개발 완료 보고서, QA 요약, 변경 이력, 사용자 가이드,
    릴리스 노트, 인수인계 문서를 생성한다.
    """

    def __init__(self, base_path: Path, qa_engine, worker_manager, event_bus):
        self.base_path = base_path
        self.qa_engine = qa_engine
        self.worker_manager = worker_manager
        self.event_bus = event_bus
        self.result_dir = base_path / "data" / "documentation_results"
        self.docs_root = base_path / "docs" / "generated"
        self.result_dir.mkdir(parents=True, exist_ok=True)
        self.docs_root.mkdir(parents=True, exist_ok=True)

    def run(self, qa_id: Optional[str] = None) -> Dict[str, Any]:
        qa = self._load_qa(qa_id)
        now = datetime.now().astimezone()
        doc_id = f"DOC-{now.strftime('%Y%m%d-%H%M%S')}"
        doc_dir = self.docs_root / doc_id
        doc_dir.mkdir(parents=True, exist_ok=True)

        documents = []
        docs_to_make = [
            ("development_report", "DEVELOPMENT_COMPLETION_REPORT.md", self._development_report),
            ("qa_summary", "QA_SUMMARY.md", self._qa_summary),
            ("changelog_draft", "CHANGELOG_DRAFT.md", self._changelog_draft),
            ("user_guide_draft", "USER_GUIDE_DRAFT.md", self._user_guide_draft),
            ("release_notes_draft", "RELEASE_NOTES_DRAFT.md", self._release_notes_draft),
            ("handoff", "HANDOFF.md", self._handoff),
        ]

        for doc_type, filename, builder in docs_to_make:
            path = doc_dir / filename
            path.write_text(builder(qa, doc_id), encoding="utf-8")
            documents.append({
                "type": doc_type,
                "path": str(path),
            })

        result = {
            "doc_id": doc_id,
            "created_at": now.isoformat(timespec="seconds"),
            "status": "completed",
            "qa_id": qa.get("qa_id", ""),
            "dev_run_id": qa.get("dev_run_id", ""),
            "plan_id": qa.get("plan_id", ""),
            "product_id": qa.get("product_id", ""),
            "qa_decision": qa.get("decision", ""),
            "qa_score": qa.get("score", ""),
            "documents": documents,
            "next_stage": "approval_ready" if qa.get("decision") in {"pass", "warn"} else "development_revision_required",
        }

        doc_path = self.result_dir / f"{doc_id}.json"
        result["doc_path"] = str(doc_path)
        doc_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

        self.event_bus.publish("DOCUMENTATION_RUN_COMPLETED", {
            "doc_id": doc_id,
            "qa_id": result["qa_id"],
            "decision": result["qa_decision"],
        })

        self.worker_manager.run(
            "audit_log_worker",
            {
                "actor": "DocumentationEngine",
                "action": "DOCUMENTATION_RUN_COMPLETED",
                "target": doc_id,
                "reason": "QA result converted into documentation package",
                "result": "success",
                "metadata": {
                    "qa_id": result["qa_id"],
                    "dev_run_id": result["dev_run_id"],
                    "plan_id": result["plan_id"],
                    "documents": len(documents),
                },
            },
        )

        return result

    def list_results(self, limit: int = 10) -> List[Dict[str, Any]]:
        items = []
        for path in sorted(self.result_dir.glob("DOC-*.json"), reverse=True):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                items.append({
                    "doc_id": data.get("doc_id", path.stem),
                    "qa_id": data.get("qa_id", ""),
                    "status": data.get("status", ""),
                    "created_at": data.get("created_at", ""),
                })
            except Exception:
                continue
            if len(items) >= limit:
                break
        return items

    def latest_result(self) -> Dict[str, Any]:
        results = sorted(self.result_dir.glob("DOC-*.json"), reverse=True)
        if not results:
            raise FileNotFoundError("No documentation result found.")
        return json.loads(results[0].read_text(encoding="utf-8"))

    def _load_qa(self, qa_id: Optional[str]) -> Dict[str, Any]:
        if not qa_id:
            return self.qa_engine.latest_result()
        path = self.base_path / "data" / "qa_results" / f"{qa_id}.json"
        if not path.exists():
            raise FileNotFoundError(f"QA result not found: {qa_id}")
        return json.loads(path.read_text(encoding="utf-8"))

    def _development_report(self, qa: Dict[str, Any], doc_id: str) -> str:
        return f"""# Development Completion Report

Document ID: `{doc_id}`

QA ID: `{qa.get('qa_id', '')}`

Development Run: `{qa.get('dev_run_id', '')}`

Plan ID: `{qa.get('plan_id', '')}`

Product: `{qa.get('product_id', '')}`

## Result

- QA Score: {qa.get('score', '')}
- QA Grade: {qa.get('grade', '')}
- QA Decision: {qa.get('decision', '')}
- Next Stage: {qa.get('next_stage', '')}

## Summary

Development Engine 산출물이 QA Engine을 통해 검수되었고, 본 문서는 승인 단계로 넘기기 위한 개발 완료 보고서 초안입니다.
"""

    def _qa_summary(self, qa: Dict[str, Any], doc_id: str) -> str:
        lines = [
            "# QA Summary",
            "",
            f"Document ID: `{doc_id}`",
            f"QA ID: `{qa.get('qa_id', '')}`",
            f"Score: {qa.get('score', '')}",
            f"Grade: {qa.get('grade', '')}",
            f"Decision: {qa.get('decision', '')}",
            "",
            "## Checks",
            "",
        ]
        for check in qa.get("checks", []):
            lines.append(f"- [{check.get('status')}] {check.get('name')}: {check.get('message')}")
        lines.extend(["", "## Recommendations", ""])
        for item in qa.get("recommendations", []):
            lines.append(f"- {item}")
        return "\n".join(lines)

    def _changelog_draft(self, qa: Dict[str, Any], doc_id: str) -> str:
        return f"""# CHANGELOG Draft

## Pending Release

- Documentation generated from QA result `{qa.get('qa_id', '')}`.
- Development run `{qa.get('dev_run_id', '')}` reached QA decision `{qa.get('decision', '')}`.
- Product `{qa.get('product_id', '')}` prepared for approval review.
"""

    def _user_guide_draft(self, qa: Dict[str, Any], doc_id: str) -> str:
        return f"""# User Guide Draft

## 목적

이 문서는 QA 결과 `{qa.get('qa_id', '')}` 기반으로 생성된 사용자 가이드 초안입니다.

## 사용 흐름

```powershell
python main.py plan create --request "요청 내용"
python main.py dev run
python main.py qa run
python main.py docs run
```

## 다음 단계

Approval Gate에서 사용자가 변경 내용을 승인하면 Release Engine으로 이동합니다.
"""

    def _release_notes_draft(self, qa: Dict[str, Any], doc_id: str) -> str:
        return f"""# Release Notes Draft

## Release Candidate

- Product: `{qa.get('product_id', '')}`
- Plan: `{qa.get('plan_id', '')}`
- Development Run: `{qa.get('dev_run_id', '')}`
- QA: `{qa.get('qa_id', '')}`
- QA Decision: `{qa.get('decision', '')}`
- QA Score: `{qa.get('score', '')}`

## Status

This release candidate is ready for owner approval if QA decision is PASS or WARN.
"""

    def _handoff(self, qa: Dict[str, Any], doc_id: str) -> str:
        return f"""# Handoff Document

Document ID: `{doc_id}`

## Current State

- QA ID: `{qa.get('qa_id', '')}`
- Development Run: `{qa.get('dev_run_id', '')}`
- Plan ID: `{qa.get('plan_id', '')}`
- Product ID: `{qa.get('product_id', '')}`
- Decision: `{qa.get('decision', '')}`

## Handoff To

Approval Gate

## Required Human Action

- 변경 내용 검토
- 승인 또는 반려
- 승인 시 Release Engine 진행
"""
