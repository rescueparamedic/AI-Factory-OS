from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
import json
import os


@dataclass
class AIProviderInfo:
    provider_id: str
    name: str
    status: str
    mode: str
    env_key: str = ""
    approval_required: bool = False
    external_call: bool = False


class ProviderRegistry:
    """AI Factory OS v2.5 Real AI Worker Provider Registry.

    - mock provider는 항상 사용 가능하며 로컬 안전모드로 동작한다.
    - openai provider는 OPENAI_API_KEY가 있을 때만 ready 상태가 된다.
    - 실제 외부 호출은 provider=openai를 명시하고 키가 있을 때만 수행한다.
    """

    def __init__(self) -> None:
        self._provider_order = ["mock", "openai"]

    def list_providers(self) -> List[Dict[str, Any]]:
        return [asdict(self.get_provider(pid)) for pid in self._provider_order]

    def get_provider(self, provider_id: str) -> AIProviderInfo:
        provider_id = (provider_id or "mock").lower().strip()
        if provider_id == "mock":
            return AIProviderInfo(
                provider_id="mock",
                name="Mock AI Provider",
                status="configured",
                mode="local_safe_mode",
                approval_required=False,
                external_call=False,
            )
        if provider_id == "openai":
            has_key = bool(os.environ.get("OPENAI_API_KEY"))
            return AIProviderInfo(
                provider_id="openai",
                name="OpenAI Provider",
                env_key="OPENAI_API_KEY",
                status="configured" if has_key else "not_configured",
                mode="ready" if has_key else "disabled",
                approval_required=True,
                external_call=True,
            )
        raise ValueError(f"Unknown AI provider: {provider_id}")


class SecurityGuard:
    """외부 AI 호출 및 민감 데이터 전송을 제어하는 최소 안전장치."""

    BLOCKED_PATTERNS = ["api_key", "secret_key", "password", "passwd", "token=", "bearer "]

    def validate(self, prompt: str, provider: AIProviderInfo) -> Dict[str, Any]:
        prompt_lower = (prompt or "").lower()
        findings = [pattern for pattern in self.BLOCKED_PATTERNS if pattern in prompt_lower]
        if findings:
            return {
                "allowed": False,
                "reason": "Prompt appears to include sensitive credential-like text.",
                "findings": findings,
            }
        if provider.external_call and provider.status != "configured":
            return {
                "allowed": False,
                "reason": f"Provider {provider.provider_id} is not configured.",
                "findings": [],
            }
        return {"allowed": True, "reason": "security_check_passed", "findings": []}


class MockAIProvider:
    def generate(self, prompt: str, system: str = "") -> Dict[str, Any]:
        clean_prompt = (prompt or "").strip()
        output = (
            "[Mock AI Response]\n"
            "AI Factory OS v2.5 Real AI Worker가 로컬 안전모드에서 응답을 생성했습니다.\n\n"
            f"요청 요약: {clean_prompt[:500]}\n\n"
            "실제 외부 API 호출은 수행하지 않았습니다."
        )
        return {
            "status": "completed",
            "provider_id": "mock",
            "model": "mock-local-v1",
            "output": output,
            "usage": {"input_chars": len(clean_prompt), "output_chars": len(output)},
        }


class OpenAIProvider:
    def generate(self, prompt: str, system: str = "") -> Dict[str, Any]:
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is not configured.")
        try:
            from openai import OpenAI  # type: ignore
        except Exception as exc:
            raise RuntimeError(f"openai package is not available: {exc}") from exc

        model = os.environ.get("AI_FACTORY_OPENAI_MODEL", "gpt-4.1-mini")
        client = OpenAI(api_key=api_key)
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        response = client.chat.completions.create(model=model, messages=messages)
        content = response.choices[0].message.content or ""
        usage = getattr(response, "usage", None)
        usage_dict = {}
        if usage:
            usage_dict = {
                "prompt_tokens": getattr(usage, "prompt_tokens", None),
                "completion_tokens": getattr(usage, "completion_tokens", None),
                "total_tokens": getattr(usage, "total_tokens", None),
            }
        return {
            "status": "completed",
            "provider_id": "openai",
            "model": model,
            "output": content,
            "usage": usage_dict,
        }


class RealAIWorker:
    """실제 AI Provider 호출을 감싸는 Worker.

    결과는 data/ai_runs 와 docs/ai_worker 에 저장하여 Dashboard/감사 추적이 가능하게 한다.
    """

    def __init__(self, base_path: Path, event_bus=None, worker_manager=None) -> None:
        self.base_path = base_path
        self.event_bus = event_bus
        self.worker_manager = worker_manager
        self.registry = ProviderRegistry()
        self.security_guard = SecurityGuard()
        self.run_dir = base_path / "data" / "ai_runs"
        self.report_dir = base_path / "docs" / "ai_worker"
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.report_dir.mkdir(parents=True, exist_ok=True)

    def list_providers(self) -> List[Dict[str, Any]]:
        return self.registry.list_providers()

    def run(self, prompt: str, provider_id: str = "mock", system: str = "", product_id: str = "blog_growth_analyzer") -> Dict[str, Any]:
        provider = self.registry.get_provider(provider_id)
        check = self.security_guard.validate(prompt, provider)
        now = datetime.now().astimezone()
        run_id = f"AI-{now.strftime('%Y%m%d-%H%M%S')}"

        if self.event_bus:
            self.event_bus.publish("REAL_AI_WORKER_STARTED", {
                "run_id": run_id,
                "provider_id": provider.provider_id,
                "product_id": product_id,
                "mode": provider.mode,
            })

        if not check.get("allowed"):
            result = {
                "run_id": run_id,
                "created_at": now.isoformat(timespec="seconds"),
                "status": "blocked",
                "worker_id": "real_ai_worker",
                "product_id": product_id,
                "provider": asdict(provider),
                "mode": provider.mode,
                "prompt": prompt,
                "system": system,
                "security": check,
                "output": "",
                "next_stage": "security_review",
            }
        else:
            engine = MockAIProvider() if provider.provider_id == "mock" else OpenAIProvider()
            try:
                generated = engine.generate(prompt=prompt, system=system)
                result = {
                    "run_id": run_id,
                    "created_at": now.isoformat(timespec="seconds"),
                    "status": generated.get("status", "completed"),
                    "worker_id": "real_ai_worker",
                    "product_id": product_id,
                    "provider": asdict(provider),
                    "mode": provider.mode,
                    "prompt": prompt,
                    "system": system,
                    "security": check,
                    "model": generated.get("model", ""),
                    "output": generated.get("output", ""),
                    "usage": generated.get("usage", {}),
                    "next_stage": "ai_result_review",
                }
            except Exception as exc:
                result = {
                    "run_id": run_id,
                    "created_at": now.isoformat(timespec="seconds"),
                    "status": "failed",
                    "worker_id": "real_ai_worker",
                    "product_id": product_id,
                    "provider": asdict(provider),
                    "mode": provider.mode,
                    "prompt": prompt,
                    "system": system,
                    "security": check,
                    "error": str(exc),
                    "output": "",
                    "next_stage": "ai_error_review",
                }

        run_path = self.run_dir / f"{run_id}.json"
        report_path = self.report_dir / f"{run_id}_real_ai_worker_report.md"
        result["run_path"] = str(run_path)
        result["report_path"] = str(report_path)
        run_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        report_path.write_text(self._render_report(result), encoding="utf-8")

        if self.event_bus:
            self.event_bus.publish("REAL_AI_WORKER_COMPLETED", {
                "run_id": run_id,
                "provider_id": provider.provider_id,
                "status": result.get("status"),
                "run_path": str(run_path),
                "report_path": str(report_path),
            })

        if self.worker_manager:
            try:
                self.worker_manager.run("audit_log_worker", {
                    "actor": "RealAIWorker",
                    "action": "REAL_AI_WORKER_COMPLETED",
                    "target": run_id,
                    "reason": "Real AI Worker execution completed",
                    "result": result.get("status"),
                    "metadata": {
                        "provider_id": provider.provider_id,
                        "product_id": product_id,
                        "run_path": str(run_path),
                    },
                })
            except Exception:
                pass
        return result

    def latest(self) -> Dict[str, Any]:
        runs = sorted(self.run_dir.glob("AI-*.json"), reverse=True)
        if not runs:
            raise FileNotFoundError("No AI Worker run found.")
        return json.loads(runs[0].read_text(encoding="utf-8"))

    def list_runs(self, limit: int = 10) -> List[Dict[str, Any]]:
        items = []
        for path in sorted(self.run_dir.glob("AI-*.json"), reverse=True):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                provider = data.get("provider") or {}
                items.append({
                    "run_id": data.get("run_id", path.stem),
                    "status": data.get("status", ""),
                    "provider_id": provider.get("provider_id", ""),
                    "mode": data.get("mode", ""),
                    "prompt": data.get("prompt", ""),
                    "created_at": data.get("created_at", ""),
                })
            except Exception:
                continue
            if len(items) >= limit:
                break
        return items

    def _render_report(self, result: Dict[str, Any]) -> str:
        provider = result.get("provider") or {}
        lines = [
            f"# Real AI Worker Report - {result.get('run_id')}",
            "",
            f"- Status: `{result.get('status')}`",
            f"- Provider: `{provider.get('provider_id')}` / `{provider.get('name')}`",
            f"- Mode: `{result.get('mode')}`",
            f"- Product: `{result.get('product_id')}`",
            f"- Created At: `{result.get('created_at')}`",
            "",
            "## Prompt",
            "",
            result.get("prompt", ""),
            "",
            "## Security",
            "",
            f"```json\n{json.dumps(result.get('security', {}), ensure_ascii=False, indent=2)}\n```",
            "",
            "## Output",
            "",
            result.get("output", "") or result.get("error", ""),
            "",
            "## Next",
            "",
            result.get("next_stage", ""),
        ]
        return "\n".join(lines)
