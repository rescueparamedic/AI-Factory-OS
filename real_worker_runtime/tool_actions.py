from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from hashlib import sha256
import json
import re
from typing import Any, Mapping


class ToolActionValidationError(ValueError):
    """Raised when a worker output is not a valid structured tool action."""


class ToolActionType(str, Enum):
    FILE_READ = "FILE_READ"
    FILE_WRITE = "FILE_WRITE"
    COMMAND_RUN = "COMMAND_RUN"
    TEST_RUN = "TEST_RUN"
    GIT_STATUS = "GIT_STATUS"
    GIT_DIFF = "GIT_DIFF"
    GIT_ADD = "GIT_ADD"
    GIT_COMMIT = "GIT_COMMIT"
    GIT_PUSH_FEATURE = "GIT_PUSH_FEATURE"


_REQUIRED = {
    "action_id", "action_type", "source_worker", "purpose", "target",
    "arguments", "cwd", "repository", "branch", "runtime_task_id",
    "runtime_session_id", "stage", "revision", "preconditions",
    "expected_result", "metadata",
}


@dataclass(frozen=True)
class ToolAction:
    action_id: str
    action_type: ToolActionType
    source_worker: str
    purpose: str
    target: str
    arguments: Mapping[str, Any]
    cwd: str
    repository: str
    branch: str
    runtime_task_id: str
    runtime_session_id: str
    stage: str
    revision: int
    preconditions: Mapping[str, Any] = field(default_factory=dict)
    expected_result: Mapping[str, Any] = field(default_factory=dict)
    metadata: Mapping[str, Any] = field(default_factory=dict)

    @classmethod
    def from_value(cls, value: Any) -> "ToolAction":
        if not isinstance(value, dict):
            raise ToolActionValidationError("tool action must be a structured object")
        missing = sorted(_REQUIRED - value.keys())
        if missing:
            raise ToolActionValidationError(f"tool action is missing required fields: {', '.join(missing)}")
        unknown = sorted(set(value) - _REQUIRED)
        if unknown:
            raise ToolActionValidationError(f"tool action has unknown fields: {', '.join(unknown)}")
        try:
            action_type = ToolActionType(value["action_type"])
        except (TypeError, ValueError) as exc:
            raise ToolActionValidationError("unsupported tool action type") from exc
        strings = (
            "action_id", "source_worker", "purpose", "target", "cwd",
            "repository", "branch", "runtime_task_id", "runtime_session_id", "stage",
        )
        if any(not isinstance(value[name], str) for name in strings):
            raise ToolActionValidationError("tool action string fields must be strings")
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", value["action_id"]):
            raise ToolActionValidationError("action_id is invalid")
        if not value["source_worker"].strip() or not value["purpose"].strip():
            raise ToolActionValidationError("source_worker and purpose are required")
        if not isinstance(value["revision"], int) or isinstance(value["revision"], bool) or value["revision"] < 0:
            raise ToolActionValidationError("revision must be a non-negative integer")
        for name in ("arguments", "preconditions", "expected_result", "metadata"):
            if not isinstance(value[name], dict):
                raise ToolActionValidationError(f"{name} must be an object")
        return cls(
            action_type=action_type,
            **{name: value[name] for name in _REQUIRED if name != "action_type"},
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "action_id": self.action_id, "action_type": self.action_type.value,
            "source_worker": self.source_worker, "purpose": self.purpose,
            "target": self.target, "arguments": dict(self.arguments), "cwd": self.cwd,
            "repository": self.repository, "branch": self.branch,
            "runtime_task_id": self.runtime_task_id,
            "runtime_session_id": self.runtime_session_id, "stage": self.stage,
            "revision": self.revision, "preconditions": dict(self.preconditions),
            "expected_result": dict(self.expected_result), "metadata": dict(self.metadata),
        }

    @property
    def fingerprint(self) -> str:
        encoded = json.dumps(self.to_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return sha256(encoded.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ToolExecutionResult:
    action_id: str
    action_fingerprint: str
    action_type: str
    status: str
    decision: str
    evidence: Mapping[str, Any]
    execution_request: Any = field(default=None, repr=False, compare=False)

    def to_dict(self) -> dict[str, Any]:
        return {
            "action_id": self.action_id,
            "action_fingerprint": self.action_fingerprint,
            "action_type": self.action_type, "status": self.status,
            "decision": self.decision, "evidence": dict(self.evidence),
        }
