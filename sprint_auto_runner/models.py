from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class RunStatus(str, Enum):
    CREATED = "created"
    RUNNING = "running"
    WAITING_APPROVAL = "waiting_approval"
    BLOCKED = "blocked"
    FAILED = "failed"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class StepStatus(str, Enum):
    PENDING = "pending"
    EVALUATING = "evaluating"
    AUTO_APPROVED = "auto_approved"
    WAITING_APPROVAL = "waiting_approval"
    DENIED = "denied"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass(frozen=True)
class SprintStep:
    step_id: str
    name: str
    command: str
    cwd: str = "."
    environment: str = "local"
    timeout_seconds: int = 60
    continue_on_failure: bool = False
    expected_exit_codes: tuple[int, ...] = (0,)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SprintDefinition:
    sprint_id: str
    title: str
    version: str
    steps: tuple[SprintStep, ...]
    source_path: str
    fingerprint: str


@dataclass
class StepResult:
    step_id: str
    status: str = StepStatus.PENDING.value
    decision: str = ""
    rule_id: str = ""
    reason: str = ""
    normalized_command: str = ""
    command_fingerprint: str = ""
    context_fingerprint: str = ""
    exit_code: int | None = None
    stdout: str = ""
    stderr: str = ""
    duration_ms: int | None = None
    started_at: str | None = None
    completed_at: str | None = None


@dataclass
class SprintRun:
    run_id: str
    sprint_id: str
    branch: str
    status: str
    current_step_index: int
    started_at: str
    updated_at: str
    completed_at: str | None
    last_error: str
    resume_token: str
    definition_path: str
    definition_fingerprint: str
    head_sha: str
    step_results: list[StepResult]
    pending_approval: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
