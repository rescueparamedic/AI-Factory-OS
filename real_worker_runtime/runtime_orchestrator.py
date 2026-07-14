from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any

from .errors import OrchestrationError, RevisionLimitExceeded
from .runtime_pipeline import PipelineState
from .worker_context import WorkerContext
from .worker_registry import WorkerRegistry


class OrchestrationAction(str, Enum):
    HANDOFF = "handoff"
    REVISE = "revise"
    COMPLETE = "complete"


@dataclass(frozen=True)
class OrchestrationDecision:
    action: OrchestrationAction
    source_worker: str
    target_worker: str
    target_state: PipelineState
    reason: str
    metadata: dict[str, Any]


class RuntimeOrchestrator:
    """Deterministic coordinator for the existing real-worker pipeline.

    The orchestrator decides ownership and bounded revision routing. It does
    not execute workers, providers, controlled actions, or approvals; those
    responsibilities remain with their existing runtime components.
    """

    _ROUTES = {
        "planning_worker": ("development_worker", PipelineState.ASSIGNED),
        "development_worker": ("qa_worker", PipelineState.QA_PENDING),
        "qa_worker": ("documentation_worker", PipelineState.DOCUMENTING),
        "documentation_worker": ("runtime", PipelineState.DONE),
    }

    def __init__(
        self, context: WorkerContext, *, max_revisions: int = 1,
        registry: WorkerRegistry | None = None,
    ) -> None:
        if max_revisions < 0:
            raise ValueError("max_revisions must be non-negative")
        self.context = WorkerContext.from_value(context)
        self.max_revisions = int(max_revisions)
        self.registry = registry or WorkerRegistry()
        self._validate_coherence()
        self._initialize_metadata()

    @property
    def revision_count(self) -> int:
        task = self.context.runtime_task
        if task is None:
            return int(self.context.revision)
        return int(task.orchestration_metadata.get("revision_count", self.context.revision))

    def worker_definitions(self, start_index: int = 0):
        definitions = self.registry.list()
        if start_index < 0 or start_index > len(definitions):
            raise OrchestrationError("worker continuation index is out of range")
        return definitions[start_index:]

    def worker_definition(self, worker_id: str):
        try:
            return next(item for item in self.registry.list() if item.worker_id == worker_id)
        except StopIteration as exc:
            raise OrchestrationError(f"pipeline worker is not registered: {worker_id}") from exc

    def worker_index(self, worker_id: str) -> int:
        definitions = self.registry.list()
        for index, definition in enumerate(definitions):
            if definition.worker_id == worker_id:
                return index
        raise OrchestrationError(f"pipeline worker is not registered: {worker_id}")

    def revision_workers(self):
        return tuple(
            self.worker_definition(worker_id)
            for worker_id in ("development_worker", "qa_worker")
        )

    def handoff_after(self, worker_id: str) -> OrchestrationDecision:
        try:
            target_worker, target_state = self._ROUTES[worker_id]
        except KeyError as exc:
            raise OrchestrationError(f"worker has no deterministic pipeline route: {worker_id}") from exc
        action = (
            OrchestrationAction.COMPLETE
            if target_state is PipelineState.DONE else OrchestrationAction.HANDOFF
        )
        decision = OrchestrationDecision(
            action, worker_id, target_worker, target_state,
            f"{worker_id} completed; forwarding to {target_worker}",
            {"revision_count": self.revision_count},
        )
        self._record(decision)
        return decision

    def request_revision(self) -> OrchestrationDecision:
        current = self.revision_count
        if current >= self.max_revisions:
            self._record_error("revision_limit_exceeded", {
                "revision_count": current,
                "max_revisions": self.max_revisions,
            })
            raise RevisionLimitExceeded(
                f"QA revision limit exceeded: {current}/{self.max_revisions} revisions used"
            )
        revision = current + 1
        self.context.revision = revision
        task = self.context.runtime_task
        if task is not None:
            task.orchestration_metadata["revision_count"] = revision
            task.orchestration_metadata["max_revisions"] = self.max_revisions
        decision = OrchestrationDecision(
            OrchestrationAction.REVISE,
            "qa_worker", "development_worker", PipelineState.DEVELOPING,
            "QA requested development revision",
            {"revision_count": revision, "max_revisions": self.max_revisions},
        )
        self._record(decision)
        return decision

    def approval_required(self, source_worker: str) -> OrchestrationDecision:
        decision = OrchestrationDecision(
            OrchestrationAction.HANDOFF,
            source_worker, "approval_guardian", PipelineState.APPROVAL_PENDING,
            "controlled action requires Product Owner approval",
            {"revision_count": self.revision_count},
        )
        self._record(decision)
        return decision

    def approval_resumed(self, source_worker: str) -> OrchestrationDecision:
        decision = OrchestrationDecision(
            OrchestrationAction.HANDOFF,
            "approval_guardian", "qa_worker", PipelineState.QA_PENDING,
            "approved controlled action completed; forwarding to QA",
            {
                "approved_source_worker": source_worker,
                "revision_count": self.revision_count,
            },
        )
        self._record(decision)
        return decision

    def _initialize_metadata(self) -> None:
        task = self.context.runtime_task
        if task is None:
            return
        metadata = task.orchestration_metadata
        metadata.setdefault("revision_count", int(self.context.revision))
        metadata["max_revisions"] = self.max_revisions
        metadata.setdefault("decisions", [])
        self.context.revision = int(metadata["revision_count"])

    def _validate_coherence(self) -> None:
        task = self.context.runtime_task
        pipeline = self.context.runtime_pipeline
        if (task is None) != (pipeline is None):
            raise OrchestrationError("runtime task and pipeline must be restored together")
        if task is not None and pipeline.task_id != task.id:
            raise OrchestrationError("runtime task and pipeline identities do not match")
        if task is not None:
            stored = task.orchestration_metadata.get("revision_count")
            if stored is not None and int(stored) != int(self.context.revision):
                raise OrchestrationError("runtime task and WorkerContext revision state diverged")

    def _record(self, decision: OrchestrationDecision) -> None:
        task = self.context.runtime_task
        if task is None:
            return
        task.orchestration_metadata.setdefault("decisions", []).append({
            "action": decision.action.value,
            "source_worker": decision.source_worker,
            "target_worker": decision.target_worker,
            "target_state": decision.target_state.value,
            "reason": decision.reason,
            "metadata": deepcopy(decision.metadata),
            "timestamp": _now(),
        })

    def _record_error(self, code: str, metadata: dict[str, Any]) -> None:
        task = self.context.runtime_task
        if task is None:
            return
        task.orchestration_metadata.setdefault("errors", []).append({
            "code": code,
            "metadata": deepcopy(metadata),
            "timestamp": _now(),
        })


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")
