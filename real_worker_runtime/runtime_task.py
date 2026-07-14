from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Mapping
from uuid import uuid4

from .errors import InvalidTaskTransition
from .models import WorkerState


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


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


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

    def __post_init__(self) -> None:
        self.state = _state(self.state)
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
        )

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
        }
