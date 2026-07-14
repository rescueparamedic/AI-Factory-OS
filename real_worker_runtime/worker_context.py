from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any, Mapping

from .runtime_pipeline import RuntimePipeline
from .runtime_task import RuntimeTask


@dataclass
class WorkerContext:
    """Runtime-owned context shared between sequential workers.

    The mapping-style accessors preserve the context contract used by the
    existing providers while the named fields make cross-worker inputs
    explicit and serializable for approval/resume continuations.
    """

    request: str
    planner_output: dict[str, Any] = field(default_factory=dict)
    task_metadata: dict[str, Any] = field(default_factory=dict)
    runtime_evidence: dict[str, Any] = field(default_factory=dict)
    prior_worker_artifacts: dict[str, dict[str, Any]] = field(default_factory=dict)
    runtime_task: RuntimeTask | None = None
    runtime_pipeline: RuntimePipeline | None = None
    outputs: dict[str, Any] = field(default_factory=dict)
    revision: int = 0
    result_handoffs: list[dict[str, Any]] = field(default_factory=list)
    active_result_handoff: dict[str, Any] | None = None

    @classmethod
    def from_value(cls, value: WorkerContext | Mapping[str, Any]) -> WorkerContext:
        if isinstance(value, cls):
            return value
        if not isinstance(value, Mapping):
            raise TypeError("worker context must be a WorkerContext or mapping")
        return cls(
            request=value["request"],
            planner_output=deepcopy(value.get("planner_output", {})),
            task_metadata=deepcopy(value.get("task_metadata", {})),
            runtime_evidence=deepcopy(value.get("runtime_evidence", {})),
            prior_worker_artifacts=deepcopy(value.get("prior_worker_artifacts", {})),
            runtime_task=RuntimeTask.from_value(value.get("runtime_task")),
            runtime_pipeline=RuntimePipeline.from_value(value.get("runtime_pipeline")),
            outputs=deepcopy(value.get("outputs", {})),
            revision=int(value.get("revision", 0)),
            result_handoffs=deepcopy(value.get("result_handoffs", [])),
            active_result_handoff=deepcopy(value.get("active_result_handoff")),
        )

    def record_worker_output(self, worker_id: str, output: dict[str, Any]) -> None:
        self.outputs[worker_id] = output
        self.prior_worker_artifacts[worker_id] = deepcopy(output)
        if worker_id == "planning_worker":
            self.planner_output = deepcopy(output)

    def update_runtime_evidence(self, evidence: Mapping[str, Any]) -> None:
        self.runtime_evidence = deepcopy(dict(evidence))

    def to_dict(self) -> dict[str, Any]:
        return {
            "request": self.request,
            "planner_output": deepcopy(self.planner_output),
            "task_metadata": deepcopy(self.task_metadata),
            "runtime_evidence": deepcopy(self.runtime_evidence),
            "prior_worker_artifacts": deepcopy(self.prior_worker_artifacts),
            "runtime_task": self.runtime_task.to_dict() if self.runtime_task else None,
            "runtime_pipeline": self.runtime_pipeline.to_dict() if self.runtime_pipeline else None,
            "outputs": deepcopy(self.outputs),
            "revision": self.revision,
            "result_handoffs": deepcopy(self.result_handoffs),
            "active_result_handoff": deepcopy(self.active_result_handoff),
        }

    def __getitem__(self, key: str) -> Any:
        if key not in self.__dataclass_fields__:
            raise KeyError(key)
        return getattr(self, key)

    def __setitem__(self, key: str, value: Any) -> None:
        if key not in self.__dataclass_fields__:
            raise KeyError(key)
        setattr(self, key, value)

    def get(self, key: str, default: Any = None) -> Any:
        try:
            return self[key]
        except KeyError:
            return default
