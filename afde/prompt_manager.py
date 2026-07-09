from __future__ import annotations

from pathlib import Path
from string import Template


class PromptManager:
    """Loads and renders prompt templates for AFDE workers."""

    def __init__(self, project_root: str | Path = ".") -> None:
        self.project_root = Path(project_root).resolve()
        self.prompt_dir = self.project_root / "afde" / "prompts"
        self.prompt_dir.mkdir(parents=True, exist_ok=True)

    def save_template(self, name: str, template: str) -> Path:
        path = self.prompt_dir / f"{self._safe_name(name)}.txt"
        path.write_text(template, encoding="utf-8")
        return path

    def render(self, name: str, **kwargs: str) -> str:
        path = self.prompt_dir / f"{self._safe_name(name)}.txt"
        if not path.exists():
            raise FileNotFoundError(f"Prompt template not found: {path}")
        return Template(path.read_text(encoding="utf-8")).safe_substitute(**kwargs)

    @staticmethod
    def _safe_name(value: str) -> str:
        return "".join(ch if ch.isalnum() or ch in ("-", "_", ".") else "_" for ch in value).strip("_") or "prompt"
