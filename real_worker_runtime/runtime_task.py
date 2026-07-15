from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping
from uuid import uuid4

from .errors import InvalidTaskTransition
from .models import WorkerState
from .runtime_lifecycle import (
    RoleLifecycleRecord, RoleLifecycleStatus, RuntimeExecutionSummary, RuntimeFailure,
    RuntimeLifecycleStatus, RuntimeTransition, lifecycle_status, safe_message,
    runtime_error_code, safe_metadata, validate_transition,
)


_TRANSITIONS = {
    WorkerState.PLANNING: {WorkerState.READY, WorkerState.FAILED},
    WorkerState.READY: {WorkerState.RUNNING, WorkerState.FAILED},
    WorkerState.RUNNING: {
        WorkerState.WAITING_APPROVAL, WorkerState.QA, WorkerState.FAILED,
    },
    WorkerState.WAITING_APPROVAL: {WorkerState.RESUMED, WorkerState.FAILED},
    WorkerState.RESUMED: {WorkerState.QA, WorkerState.FAILED},
    WorkerState.QA: {WorkerState.RUNNING, WorkerState.COMPLETED, WorkerState.FAILED},
    WorkerState.COMPLETED: set(),
    WorkerState.FAILED: set(),
}


class _TransitionHistory(list[dict[str, Any]]):
    """List-compatible persisted history with lifecycle-owned mutation."""

    def _append(self, value: dict[str, Any]) -> None:
        list.append(self, value)

    def append(self, value) -> None:
        raise TypeError("runtime transition history is append-only through transition_lifecycle")

    def extend(self, values) -> None:
        raise TypeError("runtime transition history is append-only through transition_lifecycle")

    def clear(self) -> None:
        raise TypeError("runtime transition history cannot be cleared")

    def pop(self, index=-1):
        raise TypeError("runtime transition history cannot be removed")

    def remove(self, value) -> None:
        raise TypeError("runtime transition history cannot be removed")

    def __setitem__(self, key, value) -> None:
        raise TypeError("runtime transition history records cannot be replaced")

    def __delitem__(self, key) -> None:
        raise TypeError("runtime transition history records cannot be removed")

    def __iadd__(self, values):
        raise TypeError("runtime transition history is append-only through transition_lifecycle")

    def __deepcopy__(self, memo):
        return _TransitionHistory(deepcopy(list(self), memo))


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _state(value: WorkerState | str) -> WorkerState:
    if isinstance(value, WorkerState):
        return value
    try:
        return WorkerState(value)
    except ValueError:
        try:
            return WorkerState[value.upper()]
        except KeyError as exc:
            raise ValueError(f"unknown worker state: {value}") from exc


@dataclass
class RuntimeTask:
    id: str
    worker: str
    state: WorkerState = WorkerState.PLANNING
    priority: int = 0
    dependencies: list[str] = field(default_factory=list)
    inputs: dict[str, Any] = field(default_factory=dict)
    outputs: dict[str, Any] = field(default_factory=dict)
    evidence: list[dict[str, Any]] = field(default_factory=list)
    history: list[dict[str, Any]] = field(default_factory=list)
    owner: str = ""
    handoff_metadata: dict[str, Any] = field(default_factory=dict)
    orchestration_metadata: dict[str, Any] = field(default_factory=dict)
    role_executions: list[dict[str, Any]] = field(default_factory=list)
    result_handoffs: list[dict[str, Any]] = field(default_factory=list)
    qa_revision_decisions: list[dict[str, Any]] = field(default_factory=list)
    lifecycle_status: RuntimeLifecycleStatus = RuntimeLifecycleStatus.PENDING
    lifecycle_transitions: list[dict[str, Any]] = field(default_factory=list)
    role_lifecycle: list[dict[str, Any]] = field(default_factory=list)
    failures: list[dict[str, Any]] = field(default_factory=list)
    execution_summary: dict[str, Any] | None = None
    started_at: str = field(default_factory=_now)
    completed_at: str = ""
    paused_at: str = ""

    def __post_init__(self) -> None:
        self.state = _state(self.state)
        self.lifecycle_status = lifecycle_status(self.lifecycle_status)
        self.lifecycle_transitions = _TransitionHistory(self.lifecycle_transitions)
        if not self.id or not self.worker:
            raise ValueError("runtime task id and worker are required")
        if not self.owner:
            self.owner = self.worker
        if not self.history:
            self.history.append({
                "from": None,
                "to": self.state.value,
                "timestamp": _now(),
                "reason": "task created",
            })
        if not self.lifecycle_transitions:
            self.lifecycle_transitions._append(RuntimeTransition(
                sequence=1, timestamp=self.started_at, runtime_task_id=self.id,
                from_status=None, to_status=self.lifecycle_status.value,
                stage="runtime", role="", attempt=0, revision_index=0,
                reason_code="runtime_task_created", safe_message="runtime task created",
            ).to_dict())

    @classmethod
    def create(
        cls, worker: str, *, priority: int = 0,
        dependencies: list[str] | None = None,
        inputs: Mapping[str, Any] | None = None,
        owner: str | None = None,
    ) -> RuntimeTask:
        return cls(
            id=f"TASK-{uuid4().hex}",
            worker=worker,
            priority=priority,
            dependencies=list(dependencies or []),
            inputs=deepcopy(dict(inputs or {})),
            owner=owner or worker,
        )

    @classmethod
    def from_value(cls, value: RuntimeTask | Mapping[str, Any] | None) -> RuntimeTask | None:
        if value is None or isinstance(value, cls):
            return value
        if not isinstance(value, Mapping):
            raise TypeError("runtime task must be a RuntimeTask or mapping")
        return cls(
            id=value["id"],
            worker=value["worker"],
            state=value.get("state", WorkerState.PLANNING.value),
            priority=int(value.get("priority", 0)),
            dependencies=deepcopy(value.get("dependencies", [])),
            inputs=deepcopy(value.get("inputs", {})),
            outputs=deepcopy(value.get("outputs", {})),
            evidence=deepcopy(value.get("evidence", [])),
            history=deepcopy(value.get("history", [])),
            owner=value.get("owner", value["worker"]),
            handoff_metadata=deepcopy(value.get("handoff_metadata", {})),
            orchestration_metadata=deepcopy(value.get("orchestration_metadata", {})),
            role_executions=deepcopy(value.get("role_executions", [])),
            result_handoffs=deepcopy(value.get("result_handoffs", [])),
            qa_revision_decisions=deepcopy(value.get("qa_revision_decisions", [])),
            lifecycle_status=value.get("lifecycle_status", RuntimeLifecycleStatus.PENDING.value),
            lifecycle_transitions=deepcopy(value.get("lifecycle_transitions", [])),
            role_lifecycle=deepcopy(value.get("role_lifecycle", [])),
            failures=deepcopy(value.get("failures", [])),
            execution_summary=deepcopy(value.get("execution_summary")),
            started_at=value.get("started_at", _now()),
            completed_at=value.get("completed_at", ""),
            paused_at=value.get("paused_at", ""),
        )

    def transition_lifecycle(
        self, target: RuntimeLifecycleStatus | str, *, stage: str,
        reason_code: str, message: str, role: str = "", attempt: int = 0,
        revision_index: int = 0, metadata: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        source, destination = validate_transition(self.lifecycle_status, target)
        timestamp = _now()
        record = RuntimeTransition(
            sequence=len(self.lifecycle_transitions) + 1,
            timestamp=timestamp, runtime_task_id=self.id,
            from_status=source.value, to_status=destination.value,
            stage=stage, role=role, attempt=int(attempt),
            revision_index=int(revision_index), reason_code=reason_code,
            safe_message=safe_message(message), metadata=safe_metadata(metadata),
        ).to_dict()
        self.lifecycle_status = destination
        if destination is RuntimeLifecycleStatus.WAITING_APPROVAL:
            self.paused_at = timestamp
        elif destination in {
            RuntimeLifecycleStatus.COMPLETED, RuntimeLifecycleStatus.FAILED,
            RuntimeLifecycleStatus.BLOCKED,
        }:
            self.completed_at = timestamp
        self.lifecycle_transitions._append(record)
        return deepcopy(record)

    @property
    def transition_history(self) -> tuple[dict[str, Any], ...]:
        """Read-only-by-copy public view of successful lifecycle transitions."""
        return tuple(deepcopy(self.lifecycle_transitions))

    def record_role_lifecycle(
        self, *, role: str, revision_index: int, started_at: str,
        completed_at: str, status: str, result_reference: str,
        failure_reference: str = "",
    ) -> dict[str, Any]:
        attempt = 1 + sum(item.get("role") == role for item in self.role_lifecycle)
        record = RoleLifecycleRecord(
            role=role, attempt=attempt, revision_index=int(revision_index),
            started_at=started_at, completed_at=completed_at, status=status,
            result_reference=result_reference, failure_reference=failure_reference,
        ).to_dict()
        self.role_lifecycle.append(record)
        return deepcopy(record)

    def record_failure(
        self, *, failure_code: str, stage: str, role: str, message: str,
        exception_type: str = "RuntimeError", retryable: bool = False,
        cause_reference: str = "", revision_index: int = 0,
        metadata: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        attempt = sum(item.get("role") == role for item in self.role_lifecycle)
        failure = RuntimeFailure(
            error_code=runtime_error_code(failure_code), stage=stage, actor=role,
            attempt=attempt, revision_index=int(revision_index),
            error_type=exception_type, message=safe_message(message),
            retryable=bool(retryable), cause=safe_message(cause_reference),
            metadata=safe_metadata({
                **dict(metadata or {}), "legacy_failure_code": failure_code,
            }),
            timestamp=_now(),
        ).to_dict()
        self.failures.append(failure)
        return deepcopy(failure)

    def build_execution_summary(
        self, *, current_stage: str, maximum_revisions: int,
        approval: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        required = ("planner", "developer", "qa", "documentation")
        statuses = {role: RoleLifecycleStatus.PENDING.value for role in required}
        for item in self.role_lifecycle:
            statuses[item["role"]] = item["status"]
        if self.lifecycle_status in {
            RuntimeLifecycleStatus.FAILED, RuntimeLifecycleStatus.BLOCKED,
            RuntimeLifecycleStatus.WAITING_APPROVAL,
        }:
            for role in required:
                if statuses[role] == RoleLifecycleStatus.PENDING.value:
                    statuses[role] = RoleLifecycleStatus.SKIPPED.value
        references = [item["result_reference"] for item in self.role_lifecycle
                      if item.get("result_reference")]
        documentation_reference = next((
            item["result_reference"] for item in reversed(self.role_lifecycle)
            if item.get("role") == "documentation"
            and item.get("status") == RoleLifecycleStatus.COMPLETED.value
        ), "")
        summary = RuntimeExecutionSummary(
            runtime_task_id=self.id, final_status=self.lifecycle_status.value,
            started_at=self.started_at, completed_at=self.completed_at,
            paused_at=self.paused_at, current_stage=current_stage,
            role_statuses=statuses,
            revision_count=int(self.orchestration_metadata.get("revision_count", 0)),
            maximum_revisions=int(maximum_revisions),
            result_references=references,
            transition_count=len(self.lifecycle_transitions),
            failure=deepcopy(self.failures[-1]) if self.failures else None,
            approval=safe_metadata(approval) if approval else None,
            documentation_result_reference=documentation_reference,
        ).to_dict()
        self.execution_summary = summary
        return deepcopy(summary)

    def transition(
        self, target: WorkerState | str, reason: str,
        evidence: Mapping[str, Any] | None = None,
    ) -> None:
        next_state = _state(target)
        if next_state not in _TRANSITIONS.get(self.state, set()):
            raise InvalidTaskTransition(
                f"invalid runtime task transition: {self.state.name} -> {next_state.name}"
            )
        previous = self.state
        self.state = next_state
        entry = {
            "from": previous.value,
            "to": next_state.value,
            "timestamp": _now(),
            "reason": reason,
        }
        if evidence:
            observed = deepcopy(dict(evidence))
            entry["evidence"] = observed
            self.evidence.append(observed)
        self.history.append(entry)

    def record_output(self, worker_id: str, output: Mapping[str, Any]) -> None:
        self.outputs[worker_id] = deepcopy(dict(output))

    def record_evidence(self, evidence: Mapping[str, Any]) -> None:
        self.evidence.append(deepcopy(dict(evidence)))

    def record_role_execution(self, result: Mapping[str, Any]) -> None:
        self.role_executions.append(deepcopy(dict(result)))

    def handoff(
        self, target_worker: str, reason: str,
        metadata: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not target_worker:
            raise ValueError("handoff target worker is required")
        entry = {
            "from": self.owner,
            "to": target_worker,
            "timestamp": _now(),
            "reason": reason,
            "metadata": deepcopy(dict(metadata or {})),
        }
        self.owner = target_worker
        self.handoff_metadata.setdefault("history", []).append(entry)
        self.handoff_metadata["latest"] = deepcopy(entry)
        return deepcopy(entry)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "worker": self.worker,
            "state": self.state.value,
            "priority": self.priority,
            "dependencies": deepcopy(self.dependencies),
            "inputs": deepcopy(self.inputs),
            "outputs": deepcopy(self.outputs),
            "evidence": deepcopy(self.evidence),
            "history": deepcopy(self.history),
            "owner": self.owner,
            "handoff_metadata": deepcopy(self.handoff_metadata),
            "orchestration_metadata": deepcopy(self.orchestration_metadata),
            "role_executions": deepcopy(self.role_executions),
            "result_handoffs": deepcopy(self.result_handoffs),
            "qa_revision_decisions": deepcopy(self.qa_revision_decisions),
            "lifecycle_status": self.lifecycle_status.value,
            "lifecycle_transitions": deepcopy(self.lifecycle_transitions),
            "role_lifecycle": deepcopy(self.role_lifecycle),
            "failures": deepcopy(self.failures),
            "execution_summary": deepcopy(self.execution_summary),
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "paused_at": self.paused_at,
        }
