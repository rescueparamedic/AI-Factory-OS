from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any, Mapping


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
    outputs: dict[str, Any] = field(default_factory=dict)
    revision: int = 0

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
            outputs=deepcopy(value.get("outputs", {})),
            revision=int(value.get("revision", 0)),
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
            "outputs": deepcopy(self.outputs),
            "revision": self.revision,
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
