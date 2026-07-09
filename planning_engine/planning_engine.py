from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional
import json
import re


class PlanningEngine:
    APPROVAL_KEYWORDS = [
        "유료", "결제", "api key", "api키", "외부전송", "개인정보", "자동배포",
        "삭제", "대량삭제", "github main", "메인브랜치", "로그인", "비밀번호",
        "보안", "운영계정", "배포"
    ]

    def __init__(self, base_path: Path, worker_manager, event_bus):
        self.base_path = base_path
        self.worker_manager = worker_manager
        self.event_bus = event_bus
        self.plan_dir = base_path / "data" / "development_plans"
        self.report_dir = base_path / "docs" / "plans"
        self.handoff_dir = base_path / "data" / "development_handoff"
        self.plan_dir.mkdir(parents=True, exist_ok=True)
        self.report_dir.mkdir(parents=True, exist_ok=True)
        self.handoff_dir.mkdir(parents=True, exist_ok=True)

    def create_plan(self, request: str, product_id: str = "blog_growth_analyzer") -> Dict[str, Any]:
        now = datetime.now().astimezone()
        plan_id = f"PLAN-{now.strftime('%Y%m%d-%H%M%S')}"
        normalized = self._normalize(request)

        requirements = self._extract_requirements(request)
        tasks = self._decompose_tasks(request)
        risks = self._analyze_risks(request)
        approval_required = self._approval_required(request)
        priority = self._estimate_priority(request, risks)
        risk_level = self._overall_risk(risks)
        expected_files = self._estimate_expected_files(request, product_id)
        regression_required = self._regression_required(request, expected_files)
        difficulty = self._estimate_difficulty(request, risk_level, expected_files)
        estimated_total_time = self._estimate_total_time(tasks, difficulty, risk_level)

        plan = {
            "plan_id": plan_id,
            "created_at": now.isoformat(timespec="seconds"),
            "status": "planned",
            "product_id": product_id,
            "request": request,
            "normalized_request": normalized,
            "priority": priority,
            "risk_level": risk_level,
            "difficulty": difficulty,
            "estimated_total_time": estimated_total_time,
            "regression_required": regression_required,
            "approval_required": approval_required,
            "requirements": requirements,
            "expected_files": expected_files,
            "tasks": tasks,
            "risks": risks,
            "agent_assignments": self._agent_assignments(tasks),
            "next_stage": "development_ready" if not approval_required else "needs_owner_approval",
        }

        handoff_path = self._write_handoff(plan)
        plan["handoff_path"] = str(handoff_path)

        plan_path = self.plan_dir / f"{plan_id}.json"
        plan["plan_path"] = str(plan_path)
        plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")

        report_path = self._write_report(plan)
        plan["report_path"] = str(report_path)
        plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")

        self.event_bus.publish("DEVELOPMENT_PLAN_CREATED", {
            "plan_id": plan_id,
            "product_id": product_id,
            "priority": priority,
            "risk_level": risk_level,
            "approval_required": approval_required,
            "difficulty": difficulty,
            "regression_required": regression_required,
        })

        self.worker_manager.run(
            "audit_log_worker",
            {
                "actor": "PlanningEngine",
                "action": "DEVELOPMENT_PLAN_CREATED",
                "target": plan_id,
                "reason": "User request converted into structured development plan",
                "result": "success",
                "metadata": {
                    "product_id": product_id,
                    "request": request,
                    "risk_level": risk_level,
                    "approval_required": approval_required,
                    "difficulty": difficulty,
                    "regression_required": regression_required,
                },
            },
        )

        return plan

    def list_plans(self, limit: int = 10) -> List[Dict[str, Any]]:
        items = []
        for path in sorted(self.plan_dir.glob("PLAN-*.json"), reverse=True)[:limit]:
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                items.append({
                    "plan_id": data.get("plan_id", path.stem),
                    "product_id": data.get("product_id", ""),
                    "priority": data.get("priority", ""),
                    "risk_level": data.get("risk_level", ""),
                    "created_at": data.get("created_at", ""),
                })
            except Exception:
                continue
        return items

    def get_plan(self, plan_id: Optional[str] = None) -> Dict[str, Any]:
        if not plan_id:
            return self.get_latest_plan()
        path = self.plan_dir / f"{plan_id}.json"
        if not path.exists():
            raise FileNotFoundError(f"Plan not found: {plan_id}")
        return json.loads(path.read_text(encoding="utf-8"))

    def get_latest_plan(self) -> Dict[str, Any]:
        plans = sorted(self.plan_dir.glob("PLAN-*.json"), reverse=True)
        if not plans:
            raise FileNotFoundError("No development plan found.")
        return json.loads(plans[0].read_text(encoding="utf-8"))

    def _normalize(self, text: str) -> str:
        return re.sub(r"\s+", " ", str(text or "").strip())

    def _extract_requirements(self, request: str) -> List[str]:
        text = self._normalize(request)
        requirements = []

        if any(word in text.lower() for word in ["api", "gemini", "openai", "네이버", "구글"]):
            requirements.append("외부 API 또는 외부 서비스 연동 영향 검토")
        if any(word in text for word in ["UI", "ui", "화면", "버튼", "창", "패널"]):
            requirements.append("사용자 화면/CLI 흐름 변경")
        if any(word in text for word in ["저장", "파일", "json", "문서", "리포트"]):
            requirements.append("결과 파일 저장 및 기록 구조 필요")
        if any(word in text for word in ["테스트", "검증", "오류", "품질", "검수"]):
            requirements.append("QA 테스트 및 회귀 검증 필요")
        if any(word in text for word in ["배포", "릴리즈", "업데이트"]):
            requirements.append("Release / Update Package 영향 검토")

        requirements.append(f"사용자 요청 원문 반영: {text}")
        return requirements

    def _decompose_tasks(self, request: str) -> List[Dict[str, Any]]:
        text = self._normalize(request)
        task_defs = [
            ("REQ", "요구사항 분석", "planning_agent", "요청 범위, 제외 범위, 성공 기준 정의", "low"),
            ("DESIGN", "구현 설계", "planning_agent", "수정 파일, 데이터 흐름, 입력/출력 정의", "medium"),
            ("DEV", "기능 구현", "development_agent", "Python 코드 또는 Product 코드 수정", "medium"),
            ("QA", "기능 검증", "test_agent", "실행 테스트, 회귀 테스트, 실패 조건 확인", "medium"),
            ("DOC", "문서화", "documentation_agent", "CHANGELOG, RELEASE NOTE, 사용법 업데이트", "low"),
        ]

        if any(word in text.lower() for word in ["api", "key", "개인정보", "외부", "보안"]):
            task_defs.insert(3, ("SEC", "보안 검토", "security_agent", "API Key, 개인정보, 외부 전송 위험 확인", "high"))

        if any(word in text for word in ["배포", "릴리즈", "업데이트", "실행파일"]):
            task_defs.append(("REL", "릴리즈 준비", "deploy_agent", "릴리즈 후보, 업데이트 패키지, 승인 대기열 준비", "medium"))

        tasks = []
        for idx, (code, title, agent, desc, effort) in enumerate(task_defs, start=1):
            tasks.append({
                "task_id": f"T{idx:02d}-{code}",
                "title": title,
                "description": desc,
                "owner_agent": agent,
                "estimated_effort": effort,
                "status": "planned",
            })
        return tasks

    def _estimate_expected_files(self, request: str, product_id: str) -> List[str]:
        lower = request.lower()
        files = []

        if product_id == "blog_growth_analyzer":
            files.extend([
                "products/blog_growth_analyzer/product_config.json",
                "products/blog_growth_analyzer/docs/",
            ])

        if any(k in lower for k in ["gemini", "openai", "api", "검수", "review"]):
            files.extend([
                "integrations/ai_review_client.py",
                "products/blog_growth_analyzer/review_config.json",
                "docs/operations/ai_review_usage.md",
            ])

        if any(k in lower for k in ["ui", "화면", "버튼", "패널", "창"]):
            files.append("cli/product_cli.py")

        if any(k in lower for k in ["설정", "config", "환경변수", "api key", "api키"]):
            files.extend([".env.example", "README.md"])

        if any(k in lower for k in ["테스트", "검증", "qa", "오류"]):
            files.append("tests/test_product_pipeline.py")

        if any(k in lower for k in ["문서", "가이드", "사용법"]):
            files.append("docs/operations/")

        # 중복 제거
        return list(dict.fromkeys(files))

    def _regression_required(self, request: str, files: List[str]) -> bool:
        lower = request.lower()
        if any(k in lower for k in ["api", "연동", "검수", "품질", "업데이트", "저장", "파일"]):
            return True
        if len(files) >= 4:
            return True
        return False

    def _estimate_difficulty(self, request: str, risk_level: str, files: List[str]) -> str:
        lower = request.lower()
        score = 0
        score += len(files)
        if risk_level == "high":
            score += 4
        elif risk_level == "medium":
            score += 2
        if any(k in lower for k in ["api", "연동", "자동", "검수", "배포"]):
            score += 2
        if any(k in lower for k in ["개인정보", "보안", "삭제"]):
            score += 3

        if score >= 8:
            return "high"
        if score >= 4:
            return "medium"
        return "low"

    def _estimate_total_time(self, tasks: List[Dict[str, Any]], difficulty: str, risk_level: str) -> str:
        base_minutes = 30 + len(tasks) * 20
        if difficulty == "medium":
            base_minutes += 45
        elif difficulty == "high":
            base_minutes += 120
        if risk_level == "high":
            base_minutes += 60

        if base_minutes < 60:
            return f"{base_minutes} minutes"
        hours = round(base_minutes / 60, 1)
        return f"{hours} hours"

    def _analyze_risks(self, request: str) -> List[Dict[str, str]]:
        lower = request.lower()
        risks = []

        if any(k in lower for k in ["api", "gemini", "openai", "quota", "연동", "검수"]):
            risks.append({
                "level": "medium",
                "risk": "외부 API 비용, 제한량, 응답 실패 가능성",
                "mitigation": "API Key는 설정파일/환경변수 사용, 실패 시 fallback 설계",
            })
        if any(k in lower for k in ["개인정보", "비밀번호", "로그인", "외부전송"]):
            risks.append({
                "level": "high",
                "risk": "개인정보 또는 인증정보 처리 위험",
                "mitigation": "Security Agent 검토 및 사용자 승인 후 진행",
            })
        if any(k in lower for k in ["삭제", "대량삭제", "덮어쓰기"]):
            risks.append({
                "level": "high",
                "risk": "기존 데이터 손상 가능성",
                "mitigation": "백업 생성, 변경 파일 목록 확인, rollback 준비",
            })
        if any(k in lower for k in ["ui", "화면", "버튼", "패널"]):
            risks.append({
                "level": "low",
                "risk": "UI 흐름 변경으로 사용성 혼란 가능성",
                "mitigation": "기존 버튼/흐름 유지, 새 기능은 독립 메뉴로 추가",
            })

        if not risks:
            risks.append({
                "level": "low",
                "risk": "일반 기능 변경 리스크",
                "mitigation": "작은 단위 구현 후 smoke test 실행",
            })
        return risks

    def _approval_required(self, request: str) -> bool:
        lower = request.lower()
        return any(keyword in lower for keyword in self.APPROVAL_KEYWORDS)

    def _estimate_priority(self, request: str, risks: List[Dict[str, str]]) -> str:
        text = request.lower()
        if any(word in text for word in ["오류", "버그", "실행안됨", "안됨", "긴급"]):
            return "high"
        if any(word in text for word in ["자동화", "업데이트", "개발", "연동", "검수"]):
            return "medium"
        return "normal"

    def _overall_risk(self, risks: List[Dict[str, str]]) -> str:
        levels = [r.get("level", "low") for r in risks]
        if "high" in levels:
            return "high"
        if "medium" in levels:
            return "medium"
        return "low"

    def _agent_assignments(self, tasks: List[Dict[str, Any]]) -> Dict[str, List[str]]:
        assignments: Dict[str, List[str]] = {}
        for task in tasks:
            assignments.setdefault(task["owner_agent"], []).append(task["task_id"])
        return assignments

    def _write_handoff(self, plan: Dict[str, Any]) -> Path:
        path = self.handoff_dir / f"{plan['plan_id']}_handoff.json"
        data = {
            "plan_id": plan["plan_id"],
            "product_id": plan["product_id"],
            "request": plan["request"],
            "status": "development_ready" if not plan["approval_required"] else "blocked_for_approval",
            "expected_files": plan["expected_files"],
            "tasks": plan["tasks"],
            "risks": plan["risks"],
            "regression_required": plan["regression_required"],
            "difficulty": plan["difficulty"],
            "estimated_total_time": plan["estimated_total_time"],
            "approval_required": plan["approval_required"],
        }
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    def _write_report(self, plan: Dict[str, Any]) -> Path:
        path = self.report_dir / f"{plan['plan_id']}_planning_report.md"
        lines = [
            f"# Development Planning Report - {plan['plan_id']}",
            "",
            f"Product: {plan['product_id']}",
            f"Priority: {plan['priority']}",
            f"Risk Level: {plan['risk_level']}",
            f"Difficulty: {plan.get('difficulty')}",
            f"Estimated Time: {plan.get('estimated_total_time')}",
            f"Regression Required: {plan.get('regression_required')}",
            f"Approval Required: {plan['approval_required']}",
            f"Handoff: {plan.get('handoff_path', '')}",
            "",
            "## User Request",
            "",
            plan["request"],
            "",
            "## Requirements",
            "",
        ]
        lines.extend([f"- {item}" for item in plan["requirements"]])
        lines.extend(["", "## Expected Files", ""])
        lines.extend([f"- {item}" for item in plan.get("expected_files", [])])
        lines.extend(["", "## Tasks", ""])
        for task in plan["tasks"]:
            lines.append(f"- **{task['task_id']} / {task['title']}**")
            lines.append(f"  - Agent: {task['owner_agent']}")
            lines.append(f"  - Effort: {task['estimated_effort']}")
            lines.append(f"  - Description: {task['description']}")
        lines.extend(["", "## Risks", ""])
        for risk in plan["risks"]:
            lines.append(f"- [{risk['level']}] {risk['risk']}")
            lines.append(f"  - Mitigation: {risk['mitigation']}")
        lines.extend(["", "## Next Stage", "", plan["next_stage"]])
        path.write_text("\n".join(lines), encoding="utf-8")
        return path
