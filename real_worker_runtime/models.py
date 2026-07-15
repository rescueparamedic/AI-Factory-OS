from __future__ import annotations
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import uuid4

class WorkerState(str, Enum):
    IDLE="idle"; QUEUED="queued"; WAITING="waiting"; BLOCKED="blocked"; CANCELLED="cancelled"
    PLANNING="planning"; READY="ready"; RUNNING="running"; WAITING_APPROVAL="waiting_approval"
    RESUMED="resumed"; QA="qa"; COMPLETED="completed"; FAILED="failed"
class RuntimeState(str, Enum):
    CREATED="created"; PENDING="pending"; QUEUED="queued"; RUNNING="running"
    WAITING_APPROVAL="waiting_approval"; REVISING="revising"; BLOCKED="blocked"
    FAILED="failed"; COMPLETED="completed"; CANCELLED="cancelled"

@dataclass(frozen=True)
class WorkerDefinition:
    worker_id: str; role: str; order: int
@dataclass
class WorkerMessage:
    message_id: str; session_id: str; from_worker: str; to_worker: str; message_type: str; timestamp: str; summary: str; payload: dict[str,Any]; correlation_id: str
    @classmethod
    def create(cls, session_id, source, target, kind, summary, payload=None):
        return cls(f"MSG-{uuid4().hex}",session_id,source,target,kind,datetime.now().astimezone().isoformat(timespec="seconds"),summary,payload or {},uuid4().hex)
@dataclass
class WorkerResult:
    worker_id: str; status: str; started_at: str; completed_at: str; summary: str; output: dict[str,Any]; error: str=""
@dataclass
class RuntimeArtifact:
    artifact_type: str; path: str
@dataclass
class RuntimeEvent:
    event: str; timestamp: str; worker_id: str=""; detail: str=""; task_id: str=""; state: str=""; payload: dict[str,Any]=field(default_factory=dict)
@dataclass
class RuntimeSession:
    session_id: str; sprint_id: str; request: str; provider: str; status: str; created_at: str; updated_at: str; workers: dict[str,str]; progress: int=0; current_activity: str=""; messages: list[dict]=field(default_factory=list); results: list[dict]=field(default_factory=list); artifacts: list[dict]=field(default_factory=list); runner_run_id: str=""; error: str=""
    execution_verification: dict[str,Any]=field(default_factory=lambda: {"status":"NOT_VERIFIED","verified_changed_files":[],"verified_test_executions":[]})
    truth_contract_findings: list[dict[str,Any]]=field(default_factory=list)
    pending_approval: dict[str,Any]|None=None
    runtime_tasks: list[dict[str,Any]]=field(default_factory=list)
    runtime_pipelines: list[dict[str,Any]]=field(default_factory=list)
    execution_summary: dict[str,Any]|None=None
    def to_dict(self): return asdict(self)
