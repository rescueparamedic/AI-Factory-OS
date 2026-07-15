from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from enum import Enum
import re
from typing import Any, Mapping

from .errors import InvalidTaskTransition
from .models import RuntimeState

RuntimeLifecycleStatus = RuntimeState


class RoleLifecycleStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    WAITING_APPROVAL = "waiting_approval"


_TRANSITIONS = {
    RuntimeLifecycleStatus.CREATED: {
        RuntimeLifecycleStatus.QUEUED,
        RuntimeLifecycleStatus.CANCELLED,
    },
    RuntimeLifecycleStatus.PENDING: {
        RuntimeLifecycleStatus.QUEUED,
        RuntimeLifecycleStatus.RUNNING,
        RuntimeLifecycleStatus.FAILED,
        RuntimeLifecycleStatus.BLOCKED,
        RuntimeLifecycleStatus.CANCELLED,
        RuntimeLifecycleStatus.WAITING_APPROVAL,
    },
    RuntimeLifecycleStatus.QUEUED: {
        RuntimeLifecycleStatus.RUNNING,
        RuntimeLifecycleStatus.BLOCKED,
        RuntimeLifecycleStatus.CANCELLED,
    },
    RuntimeLifecycleStatus.RUNNING: {
        RuntimeLifecycleStatus.COMPLETED,
        RuntimeLifecycleStatus.FAILED,
        RuntimeLifecycleStatus.BLOCKED,
        RuntimeLifecycleStatus.CANCELLED,
        RuntimeLifecycleStatus.REVISING,
        RuntimeLifecycleStatus.WAITING_APPROVAL,
    },
    RuntimeLifecycleStatus.WAITING_APPROVAL: {
        RuntimeLifecycleStatus.RUNNING,
        RuntimeLifecycleStatus.FAILED,
        RuntimeLifecycleStatus.BLOCKED,
        RuntimeLifecycleStatus.CANCELLED,
    },
    RuntimeLifecycleStatus.REVISING: {
        RuntimeLifecycleStatus.RUNNING,
        RuntimeLifecycleStatus.FAILED,
        RuntimeLifecycleStatus.BLOCKED,
        RuntimeLifecycleStatus.CANCELLED,
    },
    RuntimeLifecycleStatus.COMPLETED: set(),
    RuntimeLifecycleStatus.FAILED: set(),
    RuntimeLifecycleStatus.BLOCKED: set(),
    RuntimeLifecycleStatus.CANCELLED: set(),
}

ERROR_CODES = {
    "approval_rejected": "RUNTIME_APPROVAL_REJECTED",
    "approval_required": "RUNTIME_APPROVAL_REQUIRED",
    "controlled_execution_blocked": "RUNTIME_CONTROLLED_EXECUTION_BLOCKED",
    "invalid_role_result": "RUNTIME_INVALID_RESULT_HANDOFF",
    "pipeline_failure": "RUNTIME_PIPELINE_FAILURE",
    "provider_or_worker_failure": "RUNTIME_WORKER_FAILURE",
    "qa_revision_exhausted": "RUNTIME_REVISION_LIMIT_EXCEEDED",
    "revision_limit_exceeded": "RUNTIME_REVISION_LIMIT_EXCEEDED",
    "role_execution_exception": "RUNTIME_ROLE_EXECUTION_FAILURE",
    "role_execution_failed": "RUNTIME_ROLE_EXECUTION_FAILURE",
    "runtime_illegal_transition": "RUNTIME_ILLEGAL_TRANSITION",
}


def runtime_error_code(value: str) -> str:
    if value.startswith("RUNTIME_"):
        return value
    return ERROR_CODES.get(value, "RUNTIME_ROLE_EXECUTION_FAILURE")

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
            "actor": self.role,
            "attempt": self.attempt,
            "revision_index": self.revision_index,
            "reason_code": self.reason_code,
            "reason": self.safe_message,
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
    error_code: str
    stage: str
    actor: str
    attempt: int
    revision_index: int
    error_type: str
    message: str
    retryable: bool
    cause: str
    metadata: dict[str, Any]
    timestamp: str

    def to_dict(self) -> dict[str, Any]:
        value = {**self.__dict__, "metadata": deepcopy(self.metadata)}
        # Compatibility aliases for persisted Sprint 1-4/Sprint 5 consumers.
        value.update({
            "failure_code": self.metadata.get("legacy_failure_code", self.error_code),
            "role": self.actor,
            "exception_type": self.error_type,
            "safe_message": self.message,
            "cause_reference": self.cause,
        })
        return value


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
