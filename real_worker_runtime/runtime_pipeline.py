from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Mapping

from .errors import InvalidPipelineTransition


class PipelineState(str, Enum):
    PLANNED = "planned"
    ASSIGNED = "assigned"
    DEVELOPING = "developing"
    QA_PENDING = "qa_pending"
    DOCUMENTING = "documenting"
    APPROVAL_PENDING = "approval_pending"
    DONE = "done"


_TRANSITIONS = {
    PipelineState.PLANNED: {PipelineState.ASSIGNED},
    PipelineState.ASSIGNED: {PipelineState.DEVELOPING},
    PipelineState.DEVELOPING: {
        PipelineState.QA_PENDING, PipelineState.APPROVAL_PENDING,
    },
    PipelineState.QA_PENDING: {
        PipelineState.DEVELOPING, PipelineState.DOCUMENTING,
    },
    PipelineState.DOCUMENTING: {
        PipelineState.APPROVAL_PENDING, PipelineState.DONE,
    },
    PipelineState.APPROVAL_PENDING: {
        PipelineState.QA_PENDING, PipelineState.DONE,
    },
    PipelineState.DONE: set(),
}


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _state(value: PipelineState | str) -> PipelineState:
    if isinstance(value, PipelineState):
        return value
    try:
        return PipelineState(value)
    except ValueError:
        try:
            return PipelineState[value.upper()]
        except KeyError as exc:
            raise ValueError(f"unknown pipeline state: {value}") from exc


@dataclass
class RuntimePipeline:
    task_id: str
    state: PipelineState = PipelineState.PLANNED
    current_worker: str = "planning_worker"
    history: list[dict[str, Any]] = field(default_factory=list)
    approved: bool = False
    rejected: bool = False

    def __post_init__(self) -> None:
        self.state = _state(self.state)
        if not self.task_id:
            raise ValueError("runtime pipeline task_id is required")
        if not self.history:
            self.history.append({
                "from": None,
                "to": self.state.value,
                "worker": self.current_worker,
                "timestamp": _now(),
                "reason": "pipeline planned",
            })

    @classmethod
    def from_value(
        cls, value: RuntimePipeline | Mapping[str, Any] | None,
    ) -> RuntimePipeline | None:
        if value is None or isinstance(value, cls):
            return value
        if not isinstance(value, Mapping):
            raise TypeError("runtime pipeline must be a RuntimePipeline or mapping")
        return cls(
            task_id=value["task_id"],
            state=value.get("state", PipelineState.PLANNED.value),
            current_worker=value.get("current_worker", "planning_worker"),
            history=deepcopy(value.get("history", [])),
            approved=bool(value.get("approved", False)),
            rejected=bool(value.get("rejected", False)),
        )

    def transition(
        self, target: PipelineState | str, worker: str, reason: str,
        metadata: Mapping[str, Any] | None = None,
    ) -> None:
        next_state = _state(target)
        if next_state not in _TRANSITIONS[self.state]:
            raise InvalidPipelineTransition(
                f"invalid runtime pipeline transition: {self.state.name} -> {next_state.name}"
            )
        previous = self.state
        self.state = next_state
        self.current_worker = worker
        self.history.append({
            "from": previous.value,
            "to": next_state.value,
            "worker": worker,
            "timestamp": _now(),
            "reason": reason,
            "metadata": deepcopy(dict(metadata or {})),
        })

    def mark_approved(self) -> None:
        self.approved = True

    def mark_rejected(self) -> None:
        self.rejected = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "state": self.state.value,
            "current_worker": self.current_worker,
            "history": deepcopy(self.history),
            "approved": self.approved,
            "rejected": self.rejected,
        }
