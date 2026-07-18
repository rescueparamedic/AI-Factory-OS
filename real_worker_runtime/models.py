from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from types import MappingProxyType
from typing import Any, Mapping
from uuid import uuid4


class WorkerState(str, Enum):
    IDLE = 'idle'; QUEUED = 'queued'; WAITING = 'waiting'; BLOCKED = 'blocked'; CANCELLED = 'cancelled'
    PLANNING = 'planning'; READY = 'ready'; RUNNING = 'running'; WAITING_APPROVAL = 'waiting_approval'
    RESUMED = 'resumed'; QA = 'qa'; COMPLETED = 'completed'; FAILED = 'failed'


class RuntimeState(str, Enum):
    CREATED = 'created'; PENDING = 'pending'; QUEUED = 'queued'; RUNNING = 'running'
    WAITING_APPROVAL = 'waiting_approval'; REVISING = 'revising'; BLOCKED = 'blocked'
    FAILED = 'failed'; COMPLETED = 'completed'; CANCELLED = 'cancelled'


@dataclass(frozen=True)
class WorkerDefinition:
    worker_id: str; role: str; order: int


@dataclass
class WorkerMessage:
    message_id: str; session_id: str; from_worker: str; to_worker: str; message_type: str; timestamp: str; summary: str; payload: dict[str, Any]; correlation_id: str

    @classmethod
    def create(cls, session_id, source, target, kind, summary, payload=None):
        return cls(
            f'MSG-{uuid4().hex}', session_id, source, target, kind,
            datetime.now().astimezone().isoformat(timespec='seconds'),
            summary, payload or {}, uuid4().hex,
        )


@dataclass
class WorkerResult:
    worker_id: str; status: str; started_at: str; completed_at: str; summary: str; output: dict[str, Any]; error: str = ''


@dataclass(frozen=True)
class ExecutionInput:
    """Provider output prepared for one registered Runtime worker."""

    plan_id: str
    task_id: str
    worker_id: str
    instruction: str
    provider: str
    model: str
    execution_mode: str
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "metadata", _freeze_mapping(self.metadata))

    @property
    def content(self) -> str:
        """Backward-friendly name for the provider-generated instruction."""
        return self.instruction

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "task_id": self.task_id,
            "worker_id": self.worker_id,
            "instruction": self.instruction,
            "provider": self.provider,
            "model": self.model,
            "execution_mode": self.execution_mode,
            "metadata": _thaw_value(self.metadata),
        }


@dataclass(frozen=True)
class WorkerExecutionResult:
    """Structured outcome from one sequential worker execution."""

    plan_id: str
    task_id: str
    worker_id: str
    execution_status: str
    provider: str
    model: str
    execution_mode: str
    output: Mapping[str, Any] = field(default_factory=dict)
    started_at: str = ""
    completed_at: str = ""
    error: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "output", _freeze_mapping(self.output))

    @property
    def status(self) -> str:
        return self.execution_status

    def to_evidence(self) -> dict[str, str]:
        return {
            "provider": self.provider,
            "model": self.model,
            "execution_mode": self.execution_mode,
            "plan_id": self.plan_id,
            "worker_id": self.worker_id,
            "execution_status": self.execution_status,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            **self.to_evidence(),
            "task_id": self.task_id,
            "output": _thaw_value(self.output),
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "error": self.error,
        }


@dataclass
class RuntimeArtifact:
    artifact_type: str; path: str


@dataclass
class RuntimeEvent:
    event: str
    timestamp: str
    worker_id: str = ''
    detail: str = ''
    task_id: str = ''
    state: str = ''
    payload: dict[str, Any] = field(default_factory=dict)
    event_id: str = ''
    session_id: str = ''
    event_type: str = ''
    actor: str = ''
    status: str = ''
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self):
        return asdict(self)


@dataclass
class RuntimeSession:
    session_id: str; sprint_id: str; request: str; provider: str; status: str; created_at: str; updated_at: str; workers: dict[str, str]; progress: int = 0; current_activity: str = ''; messages: list[dict] = field(default_factory=list); results: list[dict] = field(default_factory=list); artifacts: list[dict] = field(default_factory=list); runner_run_id: str = ''; error: str = ''
    execution_verification: dict[str, Any] = field(default_factory=lambda: {'status': 'NOT_VERIFIED', 'verified_changed_files': [], 'verified_test_executions': []})
    truth_contract_findings: list[dict[str, Any]] = field(default_factory=list)
    pending_approval: dict[str, Any] | None = None
    runtime_tasks: list[dict[str, Any]] = field(default_factory=list)
    runtime_pipelines: list[dict[str, Any]] = field(default_factory=list)
    execution_summary: dict[str, Any] | None = None

    def to_dict(self):
        return asdict(self)


def _freeze_mapping(value: Mapping[str, Any]) -> Mapping[str, Any]:
    return MappingProxyType({key: _freeze_value(item) for key, item in dict(value).items()})


def _freeze_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return _freeze_mapping(value)
    if isinstance(value, list | tuple):
        return tuple(_freeze_value(item) for item in value)
    return value


def _thaw_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _thaw_value(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw_value(item) for item in value]
    return value
