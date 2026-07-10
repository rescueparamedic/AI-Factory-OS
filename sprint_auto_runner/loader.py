from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
from typing import Any

from .errors import SprintDefinitionError
from .models import SprintDefinition, SprintStep


ALLOWED_ENVIRONMENTS = frozenset({"local", "dev", "test", "staging", "prod", "production"})
MAX_TIMEOUT_SECONDS = 86_400


class SprintDefinitionLoader:
    def load(self, path: str | Path) -> SprintDefinition:
        source = Path(path).resolve()
        try:
            raw = source.read_text(encoding="utf-8")
        except OSError as exc:
            raise SprintDefinitionError(f"cannot read sprint definition: {exc}") from exc
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise SprintDefinitionError(f"invalid sprint JSON: {exc}") from exc
        return self.from_dict(data, source, raw)

    def from_dict(self, data: Any, source: Path, raw: str | None = None) -> SprintDefinition:
        if not isinstance(data, dict):
            raise SprintDefinitionError("sprint definition must be a JSON object")
        for field_name in ("sprint_id", "title", "version", "steps"):
            if field_name not in data:
                raise SprintDefinitionError(f"missing required field: {field_name}")
        if not all(isinstance(data[name], str) and data[name].strip() for name in ("sprint_id", "title", "version")):
            raise SprintDefinitionError("sprint_id, title, and version must be non-empty strings")
        if not isinstance(data["steps"], list) or not data["steps"]:
            raise SprintDefinitionError("steps must be a non-empty list")

        steps = tuple(self._step(item, index) for index, item in enumerate(data["steps"]))
        ids = [step.step_id for step in steps]
        if len(ids) != len(set(ids)):
            raise SprintDefinitionError("duplicate step_id is not allowed")
        canonical = raw if raw is not None else json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return SprintDefinition(
            sprint_id=data["sprint_id"].strip(),
            title=data["title"].strip(),
            version=data["version"].strip(),
            steps=steps,
            source_path=str(source),
            fingerprint=sha256(canonical.encode("utf-8")).hexdigest(),
        )

    def _step(self, item: Any, index: int) -> SprintStep:
        if not isinstance(item, dict):
            raise SprintDefinitionError(f"step {index} must be an object")
        for field_name in ("step_id", "name", "command"):
            if not isinstance(item.get(field_name), str) or not item[field_name].strip():
                raise SprintDefinitionError(f"step {index} has invalid {field_name}")
        timeout = item.get("timeout_seconds", 60)
        if isinstance(timeout, bool) or not isinstance(timeout, int) or not 1 <= timeout <= MAX_TIMEOUT_SECONDS:
            raise SprintDefinitionError(f"step {item['step_id']} has invalid timeout_seconds")
        environment = str(item.get("environment", "local")).lower()
        if environment not in ALLOWED_ENVIRONMENTS:
            raise SprintDefinitionError(f"step {item['step_id']} has unsupported environment: {environment}")
        exit_codes = item.get("expected_exit_codes", [0])
        if not isinstance(exit_codes, list) or not exit_codes or any(isinstance(code, bool) or not isinstance(code, int) for code in exit_codes):
            raise SprintDefinitionError(f"step {item['step_id']} has invalid expected_exit_codes")
        metadata = item.get("metadata", {})
        if not isinstance(metadata, dict):
            raise SprintDefinitionError(f"step {item['step_id']} metadata must be an object")
        return SprintStep(
            step_id=item["step_id"].strip(),
            name=item["name"].strip(),
            command=item["command"].strip(),
            cwd=str(item.get("cwd", ".")),
            environment=environment,
            timeout_seconds=timeout,
            continue_on_failure=bool(item.get("continue_on_failure", False)),
            expected_exit_codes=tuple(exit_codes),
            metadata=metadata,
        )
