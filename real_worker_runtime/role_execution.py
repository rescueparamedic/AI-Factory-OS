from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Mapping

from .errors import InvalidRoleResult, RoleExecutionError
from .execution_truth import claimed_qa_failures
from .models import WorkerDefinition, WorkerResult, WorkerState
from .worker_context import WorkerContext
from .workers import BaseWorker


class RuntimeRole(str, Enum):
    PLANNER = "planner"
    DEVELOPER = "developer"
    QA = "qa"
    DOCUMENTATION = "documentation"

    @property
    def worker_id(self) -> str:
        return {
            RuntimeRole.PLANNER: "planning_worker",
            RuntimeRole.DEVELOPER: "development_worker",
            RuntimeRole.QA: "qa_worker",
            RuntimeRole.DOCUMENTATION: "documentation_worker",
        }[self]

    @classmethod
    def from_worker(cls, worker_id: str) -> RuntimeRole | None:
        return next((role for role in cls if role.worker_id == worker_id), None)


class RoleExecutionState(str, Enum):
    COMPLETED = "completed"
    WAITING_APPROVAL = "waiting_approval"
    FAILED = "failed"


@dataclass(frozen=True)
class RoleExecutionRequest:
    task_id: str
    role: RuntimeRole
    worker_id: str
    runtime_request: str
    revision: int
    task_state: str
    pipeline_state: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "role": self.role.value,
            "worker_id": self.worker_id,
            "runtime_request": self.runtime_request,
            "revision": self.revision,
            "task_state": self.task_state,
            "pipeline_state": self.pipeline_state,
        }


@dataclass
class RoleExecutionResult:
    task_id: str
    role: RuntimeRole
    worker_id: str
    state: RoleExecutionState
    output: dict[str, Any]
    evidence_references: list[str]
    handoff_target: str
    started_at: str
    completed_at: str
    summary: str
    error: str = ""
    history: list[dict[str, Any]] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.role = RuntimeRole(self.role)
        self.state = RoleExecutionState(self.state)
        if not self.history:
            self.history.append({
                "state": self.state.value,
                "timestamp": self.completed_at or _now(),
                "handoff_target": self.handoff_target,
                "error": self.error,
            })

    @classmethod
    def from_value(cls, value: RoleExecutionResult | Mapping[str, Any]):
        if isinstance(value, RoleExecutionResult):
            return value
        if not isinstance(value, Mapping):
            raise InvalidRoleResult("role result must be a typed result or mapping")
        try:
            role = RuntimeRole(value["role"])
            result_type = _RESULT_TYPES[role]
            return result_type(
                task_id=value["task_id"], role=role,
                worker_id=value["worker_id"], state=value["state"],
                output=deepcopy(value.get("output", {})),
                evidence_references=list(value.get("evidence_references", [])),
                handoff_target=value.get("handoff_target", ""),
                started_at=value.get("started_at", ""),
                completed_at=value.get("completed_at", ""),
                summary=value.get("summary", ""), error=value.get("error", ""),
                history=deepcopy(value.get("history", [])),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise InvalidRoleResult("role result mapping is invalid") from exc

    def to_worker_result(self) -> WorkerResult:
        status = "completed" if self.state is not RoleExecutionState.FAILED else "failed"
        return WorkerResult(
            self.worker_id, status, self.started_at, self.completed_at,
            self.summary, deepcopy(self.output), self.error,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "role": self.role.value,
            "worker_id": self.worker_id,
            "state": self.state.value,
            "output": deepcopy(self.output),
            "evidence_references": list(self.evidence_references),
            "handoff_target": self.handoff_target,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "summary": self.summary,
            "error": self.error,
            "history": deepcopy(self.history),
        }


@dataclass
class PlannerExecutionResult(RoleExecutionResult):
    pass


@dataclass
class DeveloperExecutionResult(RoleExecutionResult):
    pass


@dataclass
class QAExecutionResult(RoleExecutionResult):
    pass


@dataclass
class DocumentationExecutionResult(RoleExecutionResult):
    pass


_RESULT_TYPES = {
    RuntimeRole.PLANNER: PlannerExecutionResult,
    RuntimeRole.DEVELOPER: DeveloperExecutionResult,
    RuntimeRole.QA: QAExecutionResult,
    RuntimeRole.DOCUMENTATION: DocumentationExecutionResult,
}


class RoleExecutor:
    """Provider-neutral role boundary backed by the existing worker bridge."""

    def __init__(self, provider) -> None:
        self.provider = provider

    def execute(
        self, request: RoleExecutionRequest, context: WorkerContext,
        definition: WorkerDefinition,
    ) -> RoleExecutionResult:
        self._validate_request(request, context, definition)
        worker_result = BaseWorker(definition, self.provider).execute(context)
        if worker_result.status != "completed":
            return _RESULT_TYPES[request.role](
                task_id=request.task_id, role=request.role,
                worker_id=request.worker_id, state=RoleExecutionState.FAILED,
                output={}, evidence_references=[], handoff_target="",
                started_at=worker_result.started_at,
                completed_at=worker_result.completed_at,
                summary=worker_result.summary, error=worker_result.error,
            )
        self._validate_output(request.role, worker_result.output, context)
        return _RESULT_TYPES[request.role](
            task_id=request.task_id, role=request.role,
            worker_id=request.worker_id, state=RoleExecutionState.COMPLETED,
            output=deepcopy(worker_result.output),
            evidence_references=_evidence_references(request.role, context),
            handoff_target=_handoff_target(request.role, worker_result.output),
            started_at=worker_result.started_at,
            completed_at=worker_result.completed_at,
            summary=worker_result.summary,
        )

    @staticmethod
    def _validate_request(
        request: RoleExecutionRequest, context: WorkerContext,
        definition: WorkerDefinition,
    ) -> None:
        if request.role.worker_id != request.worker_id or definition.worker_id != request.worker_id:
            raise RoleExecutionError("role execution worker identity mismatch")
        task = context.runtime_task
        if task is not None and task.state in {WorkerState.COMPLETED, WorkerState.FAILED}:
            raise RoleExecutionError("cannot execute a role after terminal task state")
        if request.role is RuntimeRole.DEVELOPER and not context.planner_output:
            raise RoleExecutionError("Developer requires Planner output")
        if request.role is RuntimeRole.QA and "development_worker" not in context.prior_worker_artifacts:
            raise RoleExecutionError("QA requires Developer output")
        if request.role is RuntimeRole.DOCUMENTATION:
            required = {"planning_worker", "development_worker", "qa_worker"}
            if not required.issubset(context.prior_worker_artifacts):
                raise RoleExecutionError("Documentation requires Planner, Developer, and QA evidence")
            qa_output = context.prior_worker_artifacts["qa_worker"]
            if claimed_qa_failures(qa_output):
                raise RoleExecutionError("Documentation cannot run before QA passes")

    @staticmethod
    def _validate_output(
        role: RuntimeRole, output: Any, context: WorkerContext,
    ) -> None:
        if not isinstance(output, dict):
            raise InvalidRoleResult(f"{role.value} role output must be structured")
        requirements = {
            RuntimeRole.PLANNER: ("tasks", "acceptance_criteria"),
            RuntimeRole.DEVELOPER: ("implementation_summary", "proposed_file_writes"),
            RuntimeRole.QA: ("recommendation",),
            RuntimeRole.DOCUMENTATION: ("user_summary",),
        }
        missing = [key for key in requirements[role] if key not in output]
        if missing:
            raise InvalidRoleResult(
                f"{role.value} role result is missing: {', '.join(missing)}"
            )
        if role is RuntimeRole.DOCUMENTATION:
            evidence = context.runtime_evidence
            for key in ("verified_changed_files", "verified_test_executions"):
                if key in output and output[key] != evidence.get(key, []):
                    raise InvalidRoleResult(
                        f"Documentation cannot fabricate {key} evidence"
                    )


def _handoff_target(role: RuntimeRole, output: dict[str, Any]) -> str:
    if role is RuntimeRole.PLANNER:
        return "development_worker"
    if role is RuntimeRole.DEVELOPER:
        return "qa_worker"
    if role is RuntimeRole.QA:
        raw_failed = output.get("claimed_failed", output.get("failed", 0))
        return "development_worker" if raw_failed else "documentation_worker"
    return "runtime"


def _evidence_references(role: RuntimeRole, context: WorkerContext) -> list[str]:
    references = [f"worker_context:{role.worker_id}"]
    if role is not RuntimeRole.PLANNER:
        references.append("worker_context:planner_output")
    if role in {RuntimeRole.QA, RuntimeRole.DOCUMENTATION}:
        references.append("runtime_task:development_worker.output")
    if role is RuntimeRole.DOCUMENTATION:
        references.extend([
            "runtime_task:qa_worker.output",
            "worker_context:runtime_evidence",
        ])
    return references


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")
