from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
import json
import os


@dataclass
class ProviderStatus:
    provider: str
    configured: bool
    mode: str


class ProviderManager:
    """Reports available AI provider configuration without sending external requests."""

    PROVIDERS = {
        "openai": "OPENAI_API_KEY",
        "gemini": "GEMINI_API_KEY",
        "claude": "ANTHROPIC_API_KEY",
    }

    def __init__(self, project_root: str | Path = ".") -> None:
        self.project_root = Path(project_root).resolve()
        self.settings_path = self.project_root / "settings.json"

    def list_status(self) -> list[ProviderStatus]:
        settings = self._load_settings()
        result: list[ProviderStatus] = []
        for provider, env_name in self.PROVIDERS.items():
            settings_key = f"{provider}_api_key"
            # OpenAI credentials are intentionally environment-only.
            configured = bool(os.environ.get(env_name)) if provider == "openai" else bool(os.environ.get(env_name) or settings.get(settings_key))
            result.append(ProviderStatus(provider=provider, configured=configured, mode="external" if configured else "mock"))
        result.append(ProviderStatus(provider="mock", configured=True, mode="local_safe"))
        return result

    def as_dicts(self) -> list[dict]:
        return [asdict(item) for item in self.list_status()]

    def _load_settings(self) -> dict:
        if not self.settings_path.exists():
            return {}
        try:
            return json.loads(self.settings_path.read_text(encoding="utf-8"))
        except Exception:
            return {}
