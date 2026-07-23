"""Read-only loader for the governed Knowledge Foundation registry."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .errors import (
    RegistryLoadError,
    RegistryNotFoundError,
    RegistryPathError,
    RegistryValidationError,
)
from .models import KnowledgeFoundationSnapshot
from .validator import KnowledgeRegistryValidator


DEFAULT_REGISTRY_PATH = Path(
    "docs/registry/KNOWLEDGE_FOUNDATION_REGISTRY_v1.json"
)


class KnowledgeRegistryLoader:
    """Load one repository-contained JSON snapshot without modifying it."""

    def __init__(
        self,
        repository_root: str | Path,
        registry_path: str | Path | None = None,
    ) -> None:
        self.root = Path(repository_root).expanduser().resolve()
        supplied = Path(registry_path) if registry_path is not None else DEFAULT_REGISTRY_PATH
        candidate = supplied if supplied.is_absolute() else self.root / supplied
        self.path = candidate.resolve()
        if not _inside(self.path, self.root):
            raise RegistryPathError("registry path escapes repository")

    def load(self) -> KnowledgeFoundationSnapshot:
        if not self.path.is_file():
            raise RegistryNotFoundError("knowledge registry snapshot not found")
        try:
            raw = self.path.read_bytes()
        except OSError as exc:
            raise RegistryLoadError("knowledge registry snapshot is unreadable") from exc
        try:
            value: Any = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RegistryLoadError("knowledge registry snapshot is malformed") from exc
        try:
            snapshot = KnowledgeFoundationSnapshot.from_value(value)
        except (KeyError, TypeError, ValueError) as exc:
            raise RegistryValidationError([str(exc)]) from exc
        return KnowledgeRegistryValidator(self.root).validate(snapshot)


def _inside(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False
