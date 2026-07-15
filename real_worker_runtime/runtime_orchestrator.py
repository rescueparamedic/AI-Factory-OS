from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any

from .errors import OrchestrationError, RevisionLimitExceeded
from .errors import InvalidRoleResult, RoleExecutionError
from .execution_truth import claimed_qa_failures
from .models import WorkerState
from .role_execution import (
    RoleExecutionRequest, RoleExecutionResult, RoleExecutionState, RuntimeRole,
)
from .result_handoff import (
    AgentResultHandoff, QARevisionDecision, QARevisionOutcome,
    ResultHandoffLedger,
)
from .runtime_pipeline import PipelineState
from .runtime_lifecycle import RuntimeLifecycleStatus
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
        self.handoff_ledger = ResultHandoffLedger(self.context)

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

    @property
    def current_owner(self) -> str:
        task = self.context.runtime_task
        pipeline = self.context.runtime_pipeline
        if task is not None:
            return task.owner
        return pipeline.current_worker if pipeline is not None else "planning_worker"

    def build_role_request(
        self, worker_id: str, *, task_id: str | None = None,
    ) -> RoleExecutionRequest:
        role = RuntimeRole.from_worker(worker_id)
        if role is None:
            raise RoleExecutionError(f"worker does not own a runtime role: {worker_id}")
        task = self.context.runtime_task
        pipeline = self.context.runtime_pipeline
        identity = task.id if task is not None else task_id
        if not identity:
            raise RoleExecutionError("role execution requires a task identity")
        if task is not None:
            if task.state in {WorkerState.COMPLETED, WorkerState.FAILED}:
                raise RoleExecutionError("cannot execute a role after terminal task state")
            if task.owner != worker_id or pipeline.current_worker != worker_id:
                raise RoleExecutionError("role execution does not match current pipeline ownership")
        elif role is not RuntimeRole.PLANNER:
            raise RoleExecutionError("only Planner may execute before task persistence")
        input_handoff = self.handoff_ledger.deliver(role)
        return RoleExecutionRequest(
            task_id=identity, role=role, worker_id=worker_id,
            runtime_request=self.context.request, revision=self.revision_count,
            task_state=task.state.value if task else WorkerState.PLANNING.value,
            pipeline_state=(pipeline.state.value if pipeline else PipelineState.PLANNED.value),
            input_handoff_id=input_handoff.handoff_id if input_handoff else "",
            input_result_reference=(input_handoff.result_reference if input_handoff else ""),
        )

    def create_result_handoff(
        self, result: RoleExecutionResult, consumer_role: RuntimeRole, *,
        validation_metadata: dict[str, Any] | None = None,
        revision_reason: str = "",
    ) -> AgentResultHandoff:
        if result.handoff_target != consumer_role.worker_id:
            raise InvalidRoleResult("result handoff does not match requested role target")
        return self.handoff_ledger.create(
            result, consumer_role,
            validation_metadata=validation_metadata,
            revision_count=self.revision_count,
            revision_reason=revision_reason,
        )

    def execute_role(self, executor, definition, *, task_id: str | None = None):
        request = self.build_role_request(definition.worker_id, task_id=task_id)
        return request, self.invoke_role(executor, request, definition)

    def invoke_role(self, executor, request: RoleExecutionRequest, definition):
        result = executor.execute(request, self.context, definition)
        return self._validate_role_result(result, request, persist=False)

    def record_role_result(
        self, result, request: RoleExecutionRequest,
    ) -> RoleExecutionResult:
        normalized = self._validate_role_result(result, request, persist=True)
        return normalized

    def record_approval_role_outcome(
        self, worker_id: str, *, completed: bool,
        output: dict[str, Any] | None = None, error: str = "",
        evidence_references: list[str] | None = None,
    ) -> RoleExecutionResult:
        task = self.context.runtime_task
        if task is None:
            raise RoleExecutionError("approval role outcome requires a runtime task")
        waiting = next((
            RoleExecutionResult.from_value(item)
            for item in reversed(task.role_executions)
            if item.get("worker_id") == worker_id
            and item.get("state") == RoleExecutionState.WAITING_APPROVAL.value
        ), None)
        if waiting is None:
            raise RoleExecutionError("approval continuation has no waiting role result")
        now = _now()
        state = RoleExecutionState.COMPLETED if completed else RoleExecutionState.FAILED
        result = type(waiting)(
            task_id=waiting.task_id, role=waiting.role, worker_id=waiting.worker_id,
            state=state, output=deepcopy(output if output is not None else waiting.output),
            evidence_references=list(evidence_references or waiting.evidence_references),
            handoff_target="qa_worker" if completed else "",
            started_at=waiting.started_at, completed_at=now,
            summary=("approved role execution completed" if completed else "role approval rejected"),
            error=error,
            history=deepcopy(waiting.history) + [{
                "state": state.value, "timestamp": now,
                "handoff_target": "qa_worker" if completed else "",
                "error": error,
            }],
        )
        request = RoleExecutionRequest(
            task_id=task.id, role=waiting.role, worker_id=worker_id,
            runtime_request=self.context.request, revision=self.revision_count,
            task_state=task.state.value,
            pipeline_state=self.context.runtime_pipeline.state.value,
        )
        return self.record_role_result(result, request)

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

    def request_revision(
        self, reason: str = "QA requested development revision",
        qa_result_reference: str = "",
    ) -> OrchestrationDecision:
        current = self.revision_count
        if current >= self.max_revisions:
            self._record_qa_decision(
                QARevisionOutcome.LIMIT_EXCEEDED, reason, current,
                qa_result_reference,
            )
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
            if task.lifecycle_status is RuntimeLifecycleStatus.RUNNING:
                task.transition_lifecycle(
                    RuntimeLifecycleStatus.REVISING,
                    stage="qa", role="qa", revision_index=revision,
                    reason_code="qa_revision_requested", message=reason,
                    metadata={
                        "revision_number": revision,
                        "max_revisions": self.max_revisions,
                        "qa_reason": reason,
                    },
                )
        self._record_qa_decision(
            QARevisionOutcome.REVISION_REQUESTED, reason, revision,
            qa_result_reference,
        )
        decision = OrchestrationDecision(
            OrchestrationAction.REVISE,
            "qa_worker", "development_worker", PipelineState.DEVELOPING,
            reason,
            {"revision_count": revision, "max_revisions": self.max_revisions},
        )
        self._record(decision)
        return decision

    def accept_qa(
        self, reason: str = "QA accepted development result",
        qa_result_reference: str = "",
    ) -> QARevisionDecision:
        return self._record_qa_decision(
            QARevisionOutcome.ACCEPTED, reason, self.revision_count,
            qa_result_reference,
        )

    @property
    def latest_qa_revision_decision(self) -> dict[str, Any] | None:
        task = self.context.runtime_task
        return task.qa_revision_decisions[-1] if task and task.qa_revision_decisions else None

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

    def _validate_role_result(
        self, value, request: RoleExecutionRequest, *, persist: bool,
    ) -> RoleExecutionResult:
        result = RoleExecutionResult.from_value(value)
        if result.task_id != request.task_id:
            raise InvalidRoleResult("role result task identity mismatch")
        if result.role is not request.role:
            raise InvalidRoleResult("role result role identity mismatch")
        if result.worker_id != request.worker_id:
            raise InvalidRoleResult("role result worker identity mismatch")
        if not isinstance(result.output, dict):
            raise InvalidRoleResult("role result output must be structured")
        allowed = self._allowed_handoffs(result)
        if result.handoff_target not in allowed:
            raise InvalidRoleResult(
                f"invalid {result.role.value} handoff target: {result.handoff_target}"
            )
        task = self.context.runtime_task
        if persist:
            if task is None or task.id != result.task_id:
                raise InvalidRoleResult("role result cannot be persisted to another task")
            task.record_role_execution(result.to_dict())
            result_reference = f"runtime_task:role_executions[{len(task.role_executions) - 1}]"
            failure_reference = ""
            if result.state is RoleExecutionState.FAILED:
                failure = task.record_failure(
                    failure_code=result.failure_code or "role_execution_failed",
                    stage=result.role.value, role=result.role.value,
                    message=result.error or result.summary,
                    exception_type=result.exception_type or "RoleExecutionError",
                    retryable=result.retryable,
                    cause_reference=result.cause_reference or result_reference,
                    revision_index=request.revision,
                )
                failure_reference = (
                    f"runtime_task:failures[{len(task.failures) - 1}]"
                )
            task.record_role_lifecycle(
                role=result.role.value, revision_index=request.revision,
                started_at=result.started_at, completed_at=result.completed_at,
                status=result.state.value, result_reference=result_reference,
                failure_reference=failure_reference,
            )
        return result

    @staticmethod
    def _allowed_handoffs(result: RoleExecutionResult) -> set[str]:
        if result.state is RoleExecutionState.FAILED:
            return {""}
        if result.state is RoleExecutionState.WAITING_APPROVAL:
            return {"approval_guardian"} if result.role is RuntimeRole.DEVELOPER else set()
        if result.role is RuntimeRole.PLANNER:
            return {"development_worker"}
        if result.role is RuntimeRole.DEVELOPER:
            return {"qa_worker"}
        if result.role is RuntimeRole.QA:
            raw_failed = result.output.get(
                "claimed_failed", result.output.get("failed", 0),
            )
            expected = (
                "development_worker"
                if claimed_qa_failures(result.output) or raw_failed
                else "documentation_worker"
            )
            return {expected}
        return {"runtime"}

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

    def _record_qa_decision(
        self, outcome: QARevisionOutcome, reason: str, revision_count: int,
        qa_result_reference: str,
    ) -> QARevisionDecision:
        task = self.context.runtime_task
        if task is None:
            raise RoleExecutionError("QA revision decision requires a runtime task")
        decision = QARevisionDecision.create(
            task.id, outcome, reason, revision_count, self.max_revisions,
            qa_result_reference,
        )
        self.handoff_ledger.record_qa_decision(decision)
        return decision


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")
