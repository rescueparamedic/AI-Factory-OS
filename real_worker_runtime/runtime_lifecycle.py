from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from enum import Enum
import re
from typing import Any, Mapping

from .errors import InvalidTaskTransition


class RuntimeLifecycleStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"
    WAITING_APPROVAL = "waiting_approval"


class RoleLifecycleStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    WAITING_APPROVAL = "waiting_approval"


_TRANSITIONS = {
    RuntimeLifecycleStatus.PENDING: {
        RuntimeLifecycleStatus.RUNNING,
        RuntimeLifecycleStatus.FAILED,
        RuntimeLifecycleStatus.BLOCKED,
        RuntimeLifecycleStatus.WAITING_APPROVAL,
    },
    RuntimeLifecycleStatus.RUNNING: {
        RuntimeLifecycleStatus.COMPLETED,
        RuntimeLifecycleStatus.FAILED,
        RuntimeLifecycleStatus.BLOCKED,
        RuntimeLifecycleStatus.WAITING_APPROVAL,
    },
    RuntimeLifecycleStatus.WAITING_APPROVAL: {
        RuntimeLifecycleStatus.RUNNING,
        RuntimeLifecycleStatus.FAILED,
        RuntimeLifecycleStatus.BLOCKED,
    },
    RuntimeLifecycleStatus.COMPLETED: set(),
    RuntimeLifecycleStatus.FAILED: set(),
    RuntimeLifecycleStatus.BLOCKED: set(),
}

_SENSITIVE = re.compile(
    r"(?i)(authorization\s*:|bearer\s+|api[_-]?key\s*[=:]|secret[_-]?key\s*[=:]|"
    r"password\s*[=:]|token\s*[=:]|sk-[A-Za-z0-9_-]{8,})\S*"
)


def safe_message(value: Any, *, fallback: str = "runtime operation failed") -> str:
    text = str(value or fallback).replace("\r", " ").replace("\n", " ")
    text = _SENSITIVE.sub("[REDACTED]", text)
    return text[:500]


def lifecycle_status(value: RuntimeLifecycleStatus | str) -> RuntimeLifecycleStatus:
    if isinstance(value, RuntimeLifecycleStatus):
        return value
    return RuntimeLifecycleStatus(value)


def validate_transition(
    current: RuntimeLifecycleStatus | str,
    target: RuntimeLifecycleStatus | str,
) -> tuple[RuntimeLifecycleStatus, RuntimeLifecycleStatus]:
    source = lifecycle_status(current)
    destination = lifecycle_status(target)
    if destination not in _TRANSITIONS[source]:
        raise InvalidTaskTransition(
            f"invalid runtime lifecycle transition: {source.value} -> {destination.value}"
        )
    return source, destination


@dataclass(frozen=True)
class RuntimeTransition:
    sequence: int
    timestamp: str
    runtime_task_id: str
    from_status: str | None
    to_status: str
    stage: str
    role: str
    attempt: int
    revision_index: int
    reason_code: str
    safe_message: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "sequence": self.sequence,
            "timestamp": self.timestamp,
            "runtime_task_id": self.runtime_task_id,
            "from_status": self.from_status,
            "to_status": self.to_status,
            "stage": self.stage,
            "role": self.role,
            "attempt": self.attempt,
            "revision_index": self.revision_index,
            "reason_code": self.reason_code,
            "safe_message": self.safe_message,
            "metadata": deepcopy(self.metadata),
        }


@dataclass(frozen=True)
class RoleLifecycleRecord:
    role: str
    attempt: int
    revision_index: int
    started_at: str
    completed_at: str
    status: str
    result_reference: str
    failure_reference: str

    def to_dict(self) -> dict[str, Any]:
        return dict(self.__dict__)


@dataclass(frozen=True)
class RuntimeFailure:
    failure_code: str
    stage: str
    role: str
    attempt: int
    revision_index: int
    exception_type: str
    safe_message: str
    retryable: bool
    cause_reference: str
    timestamp: str

    def to_dict(self) -> dict[str, Any]:
        return dict(self.__dict__)


@dataclass(frozen=True)
class RuntimeExecutionSummary:
    runtime_task_id: str
    final_status: str
    started_at: str
    completed_at: str
    paused_at: str
    current_stage: str
    role_statuses: dict[str, str]
    revision_count: int
    maximum_revisions: int
    result_references: list[str]
    transition_count: int
    failure: dict[str, Any] | None
    approval: dict[str, Any] | None
    documentation_result_reference: str

    def to_dict(self) -> dict[str, Any]:
        return {
            **self.__dict__,
            "role_statuses": deepcopy(self.role_statuses),
            "result_references": list(self.result_references),
            "failure": deepcopy(self.failure),
            "approval": deepcopy(self.approval),
        }


def safe_metadata(value: Mapping[str, Any] | None) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, item in dict(value or {}).items():
        lowered = str(key).lower()
        if any(marker in lowered for marker in ("authorization", "api_key", "secret", "password", "token")):
            result[str(key)] = "[REDACTED]"
        elif isinstance(item, str):
            result[str(key)] = safe_message(item, fallback="")
        elif isinstance(item, (bool, int, float)) or item is None:
            result[str(key)] = item
        else:
            result[str(key)] = safe_message(item, fallback="")
    return result
