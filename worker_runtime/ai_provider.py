from __future__ import annotations

import os
from typing import Dict, Any


class AIProviderRegistry:
    """
    AI Factory OS v2.1 MVP AI Provider Registry.

    목적:
    - 실제 AI Worker 연결을 위한 설정 감지 계층.
    - API Key가 없어도 시스템이 실패하지 않고 local_safe_mode로 동작.
    - OpenAI/Gemini 등 외부 연결은 다음 단계에서 실제 호출로 확장.
    """

    def __init__(self):
        self.providers = {
            "openai": {
                "name": "OpenAI",
                "env_key": "OPENAI_API_KEY",
                "status": "not_configured",
                "mode": "disabled",
            },
            "gemini": {
                "name": "Gemini",
                "env_key": "GEMINI_API_KEY",
                "status": "not_configured",
                "mode": "disabled",
            },
        }
        self.refresh()

    def refresh(self) -> Dict[str, Any]:
        for provider_id, item in self.providers.items():
            key_name = item["env_key"]
            has_key = bool(os.environ.get(key_name))
            item["status"] = "configured" if has_key else "not_configured"
            item["mode"] = "ready" if has_key else "disabled"
        return self.providers

    def list_providers(self):
        self.refresh()
        return [
            {
                "provider_id": pid,
                "name": item["name"],
                "env_key": item["env_key"],
                "status": item["status"],
                "mode": item["mode"],
            }
            for pid, item in self.providers.items()
        ]

    def choose_provider(self) -> Dict[str, Any]:
        self.refresh()
        for pid in ["openai", "gemini"]:
            item = self.providers[pid]
            if item["status"] == "configured":
                return {
                    "provider_id": pid,
                    "name": item["name"],
                    "mode": "ai_ready",
                    "status": "configured",
                }
        return {
            "provider_id": "local",
            "name": "Local Safe Worker",
            "mode": "local_safe_mode",
            "status": "fallback",
        }
