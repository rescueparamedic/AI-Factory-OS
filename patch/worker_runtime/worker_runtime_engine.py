from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List
import json

from worker_runtime.ai_provider import AIProviderRegistry


class WorkerRuntimeEngine:
    """
    AI Factory OS v2.1 MVP Worker Runtime Engine.

    v2.0 대비 변경:
    - AI Provider 감지 계층 추가
    - provider가 설정되면 ai_ready 모드로 기록
    - 아직 외부 API 실제 호출은 하지 않고, 안전한 provider-aware artifact를 생성
    """

    def __init__(self, base_path: Path, worker_manager, event_bus):
        self.base_path = base_path
        self.worker_manager = worker_manager
        self.event_bus = event_bus
        self.provider_registry = AIProviderRegistry()
        self.run_dir = base_path / "data" / "runtime_runs"
        self.artifact_dir = base_path / "data" / "runtime_artifacts"
        self.report_dir = base_path / "docs" / "runtime"
        for d in [self.run_dir, self.artifact_dir, self.report_dir]:
            d.mkdir(parents=True, exist_ok=True)

        self.runtime_workers = {
            "python_worker": {
                "name": "Python Worker",
                "capability": "Python 코드/설정/테스트 후보 생성",
                "status": "available",
                "preferred_provider": "openai",
            },
            "markdown_worker": {
                "name": "Markdown Worker",
                "capability": "문서/보고서/README 생성",
                "status": "available",
                "preferred_provider": "openai",
            },
            "qa_worker": {
                "name": "QA Worker",
                "capability": "결과 검토/체크리스트/품질 판단",
                "status": "available",
                "preferred_provider": "local",
            },
            "json_worker": {
                "name": "JSON Worker",
                "capability": "JSON 설정/manifest/task 정의 생성",
                "status": "available",
                "preferred_provider": "local",
            },
        }

    def list_workers(self) -> List[Dict[str, Any]]:
        return [{"worker_id": wid, **info} for wid, info in self.runtime_workers.items()]

    def list_providers(self) -> List[Dict[str, Any]]:
        return self.provider_registry.list_providers()

    def run(self, worker_id: str, task: str, product_id: str = "blog_growth_analyzer") -> Dict[str, Any]:
        if worker_id not in self.runtime_workers:
            raise ValueError(f"Unknown runtime worker: {worker_id}")

        now = datetime.now().astimezone()
        run_id = f"RUN-{now.strftime('%Y%m%d-%H%M%S')}"
        worker = self.runtime_workers[worker_id]
        provider = self.provider_registry.choose_provider()

        self.event_bus.publish("WORKER_RUNTIME_STARTED", {
            "run_id": run_id,
            "worker_id": worker_id,
            "task": task,
            "product_id": product_id,
            "provider": provider,
        })

        steps = [
            {"step": "receive_task", "status": "completed", "message": "Task received by runtime worker."},
            {"step": "select_provider", "status": "completed", "message": f"Provider selected: {provider['name']} / {provider['mode']}."},
            {"step": "analyze_task", "status": "completed", "message": "Task analyzed and converted to artifact plan."},
            {"step": "generate_artifact", "status": "completed", "message": "Provider-aware artifact candidate generated."},
            {"step": "save_result", "status": "completed", "message": "Runtime result saved."},
        ]

        artifact_path = self._create_artifact(run_id, worker_id, task, product_id, provider)
        report_path = self._create_report(run_id, worker_id, task, product_id, artifact_path, steps, provider)

        result = {
            "run_id": run_id,
            "created_at": now.isoformat(timespec="seconds"),
            "status": "completed",
            "worker_id": worker_id,
            "worker_name": worker["name"],
            "product_id": product_id,
            "task": task,
            "mode": provider["mode"],
            "provider": provider,
            "artifact_path": str(artifact_path),
            "report_path": str(report_path),
            "steps": steps,
            "next_stage": "runtime_result_review",
        }

        run_path = self.run_dir / f"{run_id}.json"
        result["run_path"] = str(run_path)
        run_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

        self.event_bus.publish("WORKER_RUNTIME_COMPLETED", {
            "run_id": run_id,
            "worker_id": worker_id,
            "artifact_path": str(artifact_path),
            "provider": provider,
        })

        self.worker_manager.run(
            "audit_log_worker",
            {
                "actor": "WorkerRuntimeEngine",
                "action": "WORKER_RUNTIME_COMPLETED",
                "target": run_id,
                "reason": "Runtime worker execution completed",
                "result": "success",
                "metadata": {
                    "worker_id": worker_id,
                    "product_id": product_id,
                    "artifact_path": str(artifact_path),
                    "provider": provider,
                },
            },
        )
        return result

    def latest(self) -> Dict[str, Any]:
        runs = sorted(self.run_dir.glob("RUN-*.json"), reverse=True)
        if not runs:
            raise FileNotFoundError("No runtime run found.")
        return json.loads(runs[0].read_text(encoding="utf-8"))

    def list_runs(self, limit: int = 10) -> List[Dict[str, Any]]:
        items = []
        for path in sorted(self.run_dir.glob("RUN-*.json"), reverse=True):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                items.append({
                    "run_id": data.get("run_id", path.stem),
                    "worker_id": data.get("worker_id", ""),
                    "status": data.get("status", ""),
                    "mode": data.get("mode", ""),
                    "task": data.get("task", ""),
                    "created_at": data.get("created_at", ""),
                })
            except Exception:
                continue
            if len(items) >= limit:
                break
        return items

    def _create_artifact(self, run_id: str, worker_id: str, task: str, product_id: str, provider: Dict[str, Any]) -> Path:
        safe_worker = worker_id.replace("/", "_")
        path = self.artifact_dir / f"{run_id}_{safe_worker}_artifact.md"

        provider_note = f"""
## Provider

- Provider: `{provider.get('name')}`
- Mode: `{provider.get('mode')}`
- Status: `{provider.get('status')}`

"""

        if worker_id == "python_worker":
            body = f"""# Python Worker Artifact - {run_id}

{provider_note}

## Product

`{product_id}`

## Task

{task}

## Candidate Output

```python
# Generated candidate by AI Factory Worker Runtime v2.1
# External AI call is not enabled in this MVP patch.
def generated_task_summary():
    return {task!r}
```

## Next

v2.2에서 실제 provider 호출 또는 patch candidate 생성으로 확장합니다.
"""
        elif worker_id == "json_worker":
            body = f"""# JSON Worker Artifact - {run_id}

{provider_note}

```json
{{
  "product_id": "{product_id}",
  "task": {json.dumps(task, ensure_ascii=False)},
  "status": "candidate",
  "generated_by": "json_worker",
  "provider_mode": "{provider.get('mode')}"
}}
```
"""
        elif worker_id == "qa_worker":
            body = f"""# QA Worker Artifact - {run_id}

{provider_note}

## QA Checklist

- [x] Task received
- [x] Provider selected
- [x] Artifact candidate generated
- [x] Runtime log saved
- [ ] Real code execution test - future version
- [ ] Regression test - future version

## Decision

PASS for runtime v2.1 MVP.
"""
        else:
            body = f"""# Markdown Worker Artifact - {run_id}

{provider_note}

## Task

{task}

## Result

Runtime Worker가 provider-aware 문서 후보를 생성했습니다.

## Next

v2.2에서 실제 AI 문서 생성 또는 문서 템플릿 엔진으로 확장합니다.
"""
        path.write_text(body, encoding="utf-8")
        return path

    def _create_report(self, run_id: str, worker_id: str, task: str, product_id: str, artifact_path: Path, steps: List[Dict[str, str]], provider: Dict[str, Any]) -> Path:
        path = self.report_dir / f"{run_id}_runtime_report.md"
        lines = [
            f"# Worker Runtime Report - {run_id}",
            "",
            f"Worker: `{worker_id}`",
            f"Product: `{product_id}`",
            f"Task: {task}",
            f"Provider: `{provider.get('name')}`",
            f"Mode: `{provider.get('mode')}`",
            f"Artifact: `{artifact_path}`",
            "",
            "## Steps",
            "",
        ]
        for step in steps:
            lines.append(f"- [{step.get('status')}] {step.get('step')}: {step.get('message')}")
        lines.extend(["", "## Status", "", "Worker Runtime v2.1 execution completed."])
        path.write_text("\n".join(lines), encoding="utf-8")
        return path
