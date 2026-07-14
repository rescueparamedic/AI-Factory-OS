from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Mapping
from uuid import uuid4

from .errors import OrchestrationError
from .role_execution import RoleExecutionResult, RuntimeRole
from .worker_context import WorkerContext


class ResultHandoffState(str, Enum):
    CREATED = "created"
    DELIVERED = "delivered"


class QARevisionOutcome(str, Enum):
    ACCEPTED = "accepted"
    REVISION_REQUESTED = "revision_requested"
    LIMIT_EXCEEDED = "limit_exceeded"


@dataclass
class AgentResultHandoff:
    handoff_id: str
    task_id: str
    producer_role: RuntimeRole
    consumer_role: RuntimeRole
    result_reference: str
    result_payload: dict[str, Any] | None
    validation_metadata: dict[str, Any]
    revision_count: int
    revision_reason: str
    created_at: str
    history: list[dict[str, Any]] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.producer_role = RuntimeRole(self.producer_role)
        self.consumer_role = RuntimeRole(self.consumer_role)
        if not self.handoff_id or not self.task_id:
            raise ValueError("result handoff identity is required")
        if not self.result_reference and self.result_payload is None:
            raise ValueError("result handoff requires a payload or reference")
        if not self.history:
            self.history.append({
                "state": ResultHandoffState.CREATED.value,
                "timestamp": self.created_at,
                "consumer_role": self.consumer_role.value,
            })

    @classmethod
    def create(
        cls, task_id: str, producer_role: RuntimeRole,
        consumer_role: RuntimeRole, result_reference: str, *,
        result_payload: Mapping[str, Any] | None = None,
        validation_metadata: Mapping[str, Any] | None = None,
        revision_count: int = 0, revision_reason: str = "",
    ) -> AgentResultHandoff:
        return cls(
            handoff_id=f"HANDOFF-{uuid4().hex}", task_id=task_id,
            producer_role=producer_role, consumer_role=consumer_role,
            result_reference=result_reference,
            result_payload=deepcopy(dict(result_payload)) if result_payload is not None else None,
            validation_metadata=deepcopy(dict(validation_metadata or {})),
            revision_count=int(revision_count), revision_reason=revision_reason,
            created_at=_now(),
        )

    @classmethod
    def from_value(cls, value: AgentResultHandoff | Mapping[str, Any]):
        if isinstance(value, cls):
            return value
        if not isinstance(value, Mapping):
            raise TypeError("result handoff must be an AgentResultHandoff or mapping")
        return cls(
            handoff_id=value["handoff_id"], task_id=value["task_id"],
            producer_role=value["producer_role"], consumer_role=value["consumer_role"],
            result_reference=value.get("result_reference", ""),
            result_payload=deepcopy(value.get("result_payload")),
            validation_metadata=deepcopy(value.get("validation_metadata", {})),
            revision_count=int(value.get("revision_count", 0)),
            revision_reason=value.get("revision_reason", ""),
            created_at=value["created_at"], history=deepcopy(value.get("history", [])),
        )

    def deliver(self, worker_id: str) -> None:
        if worker_id != self.consumer_role.worker_id:
            raise OrchestrationError("result handoff consumer identity mismatch")
        if any(item.get("state") == ResultHandoffState.DELIVERED.value for item in self.history):
            raise OrchestrationError("result handoff has already been delivered")
        self.history.append({
            "state": ResultHandoffState.DELIVERED.value,
            "timestamp": _now(), "consumer_role": self.consumer_role.value,
            "worker_id": worker_id,
        })

    def to_dict(self) -> dict[str, Any]:
        return {
            "handoff_id": self.handoff_id, "task_id": self.task_id,
            "producer_role": self.producer_role.value,
            "consumer_role": self.consumer_role.value,
            "result_reference": self.result_reference,
            "result_payload": deepcopy(self.result_payload),
            "validation_metadata": deepcopy(self.validation_metadata),
            "revision_count": self.revision_count,
            "revision_reason": self.revision_reason,
            "created_at": self.created_at, "history": deepcopy(self.history),
        }


@dataclass
class QARevisionDecision:
    task_id: str
    outcome: QARevisionOutcome
    reason: str
    revision_count: int
    max_revisions: int
    qa_result_reference: str
    timestamp: str
    history: list[dict[str, Any]] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.outcome = QARevisionOutcome(self.outcome)
        if not self.history:
            self.history.append({
                "outcome": self.outcome.value, "reason": self.reason,
                "revision_count": self.revision_count, "timestamp": self.timestamp,
            })

    @classmethod
    def create(
        cls, task_id: str, outcome: QARevisionOutcome, reason: str,
        revision_count: int, max_revisions: int, qa_result_reference: str,
    ) -> QARevisionDecision:
        return cls(
            task_id, outcome, reason, int(revision_count), int(max_revisions),
            qa_result_reference, _now(),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id, "outcome": self.outcome.value,
            "reason": self.reason, "revision_count": self.revision_count,
            "max_revisions": self.max_revisions,
            "qa_result_reference": self.qa_result_reference,
            "timestamp": self.timestamp, "history": deepcopy(self.history),
        }


class ResultHandoffLedger:
    """Append-only handoff ledger persisted by RuntimeTask and WorkerContext."""

    def __init__(self, context: WorkerContext) -> None:
        self.context = context
        self.task = context.runtime_task
        if self.task is not None:
            if context.result_handoffs and context.result_handoffs != self.task.result_handoffs:
                raise OrchestrationError("WorkerContext and RuntimeTask handoff history diverged")
            self._sync_context()

    def create(
        self, result: RoleExecutionResult, consumer_role: RuntimeRole, *,
        validation_metadata: Mapping[str, Any] | None = None,
        revision_count: int = 0, revision_reason: str = "",
    ) -> AgentResultHandoff:
        if self.task is None or result.task_id != self.task.id:
            raise OrchestrationError("result handoff task identity mismatch")
        result_index = len(self.task.role_executions) - 1
        reference = f"runtime_task:role_executions[{result_index}]"
        handoff = AgentResultHandoff.create(
            self.task.id, result.role, consumer_role, reference,
            validation_metadata=validation_metadata,
            revision_count=revision_count, revision_reason=revision_reason,
        )
        self.task.result_handoffs.append(handoff.to_dict())
        self._sync_context()
        return handoff

    def deliver(self, consumer_role: RuntimeRole) -> AgentResultHandoff | None:
        if self.task is None:
            return None
        for index in range(len(self.task.result_handoffs) - 1, -1, -1):
            handoff = AgentResultHandoff.from_value(self.task.result_handoffs[index])
            delivered = any(
                item.get("state") == ResultHandoffState.DELIVERED.value
                for item in handoff.history
            )
            if handoff.consumer_role is consumer_role and not delivered:
                handoff.deliver(consumer_role.worker_id)
                snapshot = handoff.to_dict()
                self.task.result_handoffs[index] = snapshot
                self.context.active_result_handoff = deepcopy(snapshot)
                self._sync_context()
                return handoff
        return None

    def record_qa_decision(self, decision: QARevisionDecision) -> None:
        if self.task is None or decision.task_id != self.task.id:
            raise OrchestrationError("QA revision decision task identity mismatch")
        self.task.qa_revision_decisions.append(decision.to_dict())

    def _sync_context(self) -> None:
        if self.task is not None:
            self.context.result_handoffs = deepcopy(self.task.result_handoffs)


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")
