from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List
import json


class AgentConversationEngine:
    """
    AI Factory OS v2.2 MVP Agent Conversation Engine.

    목적:
    - 사용자의 개발 요청을 AI 회사 회의 형태의 대화 로그로 변환한다.
    - 아직 실제 AI 호출은 하지 않고, 기존 Planning/Runtime 구조를 설명 가능한 Agent 메시지로 시각화한다.
    - 결과는 JSON과 Markdown으로 저장되어 이후 Dashboard/GUI에서 재사용할 수 있다.
    """

    def __init__(self, base_path: Path, planning_engine, worker_runtime_engine, worker_manager, event_bus):
        self.base_path = base_path
        self.planning_engine = planning_engine
        self.worker_runtime_engine = worker_runtime_engine
        self.worker_manager = worker_manager
        self.event_bus = event_bus

        self.conversation_dir = base_path / "data" / "conversations"
        self.report_dir = base_path / "docs" / "conversations"
        for d in [self.conversation_dir, self.report_dir]:
            d.mkdir(parents=True, exist_ok=True)

    def run(self, request: str, product_id: str = "blog_growth_analyzer") -> Dict[str, Any]:
        now = datetime.now().astimezone()
        conversation_id = f"CHAT-{now.strftime('%Y%m%d-%H%M%S')}"

        self.event_bus.publish("AGENT_CONVERSATION_STARTED", {
            "conversation_id": conversation_id,
            "request": request,
            "product_id": product_id,
        })

        plan = self.planning_engine.create_plan(request=request, product_id=product_id)
        providers = self.worker_runtime_engine.list_providers()
        workers = self.worker_runtime_engine.list_workers()

        messages = self._build_messages(
            conversation_id=conversation_id,
            request=request,
            product_id=product_id,
            plan=plan,
            providers=providers,
            workers=workers,
        )

        report_path = self._write_markdown_report(conversation_id, request, product_id, messages, plan)
        conversation_path = self.conversation_dir / f"{conversation_id}.json"

        result = {
            "conversation_id": conversation_id,
            "created_at": now.isoformat(timespec="seconds"),
            "status": "completed",
            "product_id": product_id,
            "request": request,
            "plan_id": plan.get("plan_id"),
            "message_count": len(messages),
            "messages": messages,
            "conversation_path": str(conversation_path),
            "report_path": str(report_path),
            "next_stage": "agent_conversation_review",
        }

        conversation_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

        self.event_bus.publish("AGENT_CONVERSATION_COMPLETED", {
            "conversation_id": conversation_id,
            "plan_id": result["plan_id"],
            "message_count": len(messages),
        })

        self.worker_manager.run(
            "audit_log_worker",
            {
                "actor": "AgentConversationEngine",
                "action": "AGENT_CONVERSATION_COMPLETED",
                "target": conversation_id,
                "reason": "Agent conversation generated from development request",
                "result": "success",
                "metadata": {
                    "product_id": product_id,
                    "plan_id": result["plan_id"],
                    "message_count": len(messages),
                    "report_path": str(report_path),
                },
            },
        )

        return result

    def latest(self) -> Dict[str, Any]:
        items = sorted(self.conversation_dir.glob("CHAT-*.json"), reverse=True)
        if not items:
            raise FileNotFoundError("No conversation found.")
        return json.loads(items[0].read_text(encoding="utf-8"))

    def list_conversations(self, limit: int = 10) -> List[Dict[str, Any]]:
        results = []
        for path in sorted(self.conversation_dir.glob("CHAT-*.json"), reverse=True):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                results.append({
                    "conversation_id": data.get("conversation_id", path.stem),
                    "status": data.get("status", ""),
                    "product_id": data.get("product_id", ""),
                    "request": data.get("request", ""),
                    "message_count": data.get("message_count", 0),
                    "created_at": data.get("created_at", ""),
                })
            except Exception:
                continue
            if len(results) >= limit:
                break
        return results

    def _build_messages(self, conversation_id: str, request: str, product_id: str, plan: Dict[str, Any], providers: List[Dict[str, Any]], workers: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        ts = datetime.now().astimezone().isoformat(timespec="seconds")

        plan_tasks = plan.get("tasks", [])
        expected_files = plan.get("expected_files", [])
        risks = plan.get("risks", [])
        difficulty = plan.get("difficulty", "")
        estimated_hours = plan.get("estimated_hours", "")
        regression = plan.get("regression", "")

        provider_summary = ", ".join([f"{p.get('name')}={p.get('status')}" for p in providers]) or "provider information unavailable"
        worker_summary = ", ".join([w.get("worker_id", "") for w in workers]) or "worker information unavailable"

        def msg(agent: str, role: str, message: str, status: str = "completed") -> Dict[str, Any]:
            return {
                "time": ts,
                "agent": agent,
                "role": role,
                "status": status,
                "message": message,
            }

        messages = [
            msg("CEO Agent", "decision_owner", f"새 개발 요청을 접수했습니다. 요청: {request}"),
            msg("PM Agent", "project_manager", f"제품 `{product_id}` 기준으로 작업 흐름을 구성합니다. 우선 Planning Engine에 분석을 요청합니다."),
            msg("Planning Agent", "planner", f"개발 계획 `{plan.get('plan_id')}`을 생성했습니다. 난이도: {difficulty}, 예상시간: {estimated_hours}, 회귀 영향: {regression}."),
            msg("Architecture Agent", "architect", f"예상 변경 파일을 확인했습니다: {', '.join(expected_files) if expected_files else 'expected files 없음'}."),
            msg("Risk Agent", "risk_manager", f"리스크를 검토했습니다: {self._format_risks(risks)}"),
            msg("Provider Agent", "provider_manager", f"AI Provider 상태를 확인했습니다: {provider_summary}. 현재는 API Key 미설정 시 Local Safe Mode로 진행합니다."),
            msg("Worker Manager", "worker_manager", f"사용 가능한 Runtime Worker를 확인했습니다: {worker_summary}."),
        ]

        if plan_tasks:
            for task in plan_tasks:
                messages.append(
                    msg(
                        "PM Agent",
                        "task_router",
                        f"작업 배정 후보: {task.get('id', '')} / {task.get('title', '')} → {task.get('owner', '')}, 중요도 {task.get('priority', '')}.",
                    )
                )

        messages.extend([
            msg("Development Agent", "developer", "현재 단계에서는 안전한 개발 후보 산출물 생성으로 진행합니다. 실제 코드 수정은 승인 및 실제 AI Provider 연결 후 수행합니다."),
            msg("QA Agent", "qa", "QA 관점에서 외부 API, 회귀 영향, 실패 시 fallback 경로를 확인해야 합니다."),
            msg("Documentation Agent", "documentation", "개발 보고서, 사용자 가이드, 변경 로그 문서화가 필요합니다."),
            msg("Release Agent", "release", "승인 후 Release Package 생성 대상이 될 수 있습니다."),
            msg("Deployment Agent", "deployment", "Release 완료 후 staging deploy candidate 생성이 가능합니다."),
            msg("CEO Agent", "decision_owner", "초기 회의가 완료되었습니다. 다음 단계는 개발 실행 또는 승인 대기입니다."),
        ])

        return messages

    def _format_risks(self, risks: Any) -> str:
        if not risks:
            return "명시된 리스크 없음"
        if isinstance(risks, list):
            formatted = []
            for item in risks:
                if isinstance(item, dict):
                    formatted.append(f"{item.get('level', '')}: {item.get('description', item)}")
                else:
                    formatted.append(str(item))
            return "; ".join(formatted)
        return str(risks)

    def _write_markdown_report(self, conversation_id: str, request: str, product_id: str, messages: List[Dict[str, Any]], plan: Dict[str, Any]) -> Path:
        path = self.report_dir / f"{conversation_id}_conversation_report.md"
        lines = [
            f"# Agent Conversation Report - {conversation_id}",
            "",
            f"Product: `{product_id}`",
            f"Request: {request}",
            f"Plan ID: `{plan.get('plan_id', '')}`",
            "",
            "## Conversation",
            "",
        ]
        for item in messages:
            lines.extend([
                f"### {item.get('agent')} / {item.get('role')}",
                "",
                f"- Status: `{item.get('status')}`",
                f"- Message: {item.get('message')}",
                "",
            ])
        lines.extend([
            "## Next",
            "",
            "이 대화 로그는 이후 Live Log / Dashboard / GUI에서 재사용됩니다.",
        ])
        path.write_text("\n".join(lines), encoding="utf-8")
        return path
