import json
from pathlib import Path

import pytest

from real_worker_runtime import RealWorkerRuntime, RuntimeTask, WorkerContext
from real_worker_runtime.artifact_store import ArtifactStore
from real_worker_runtime.errors import InvalidTaskTransition
from real_worker_runtime.event_stream import EventStream
from real_worker_runtime.models import WorkerState
from real_worker_runtime.provider_bridge import ProviderBridge


def test_runtime_task_contains_required_fields_and_creation_history():
    task = RuntimeTask.create(
        "development_worker",
        priority=7,
        dependencies=["PM analysis"],
        inputs={"planner_output": {"tasks": ["implement"]}},
    )

    assert task.id.startswith("TASK-")
    assert task.worker == "development_worker"
    assert task.state is WorkerState.PLANNING
    assert task.priority == 7
    assert task.dependencies == ["PM analysis"]
    assert task.inputs == {"planner_output": {"tasks": ["implement"]}}
    assert task.outputs == {}
    assert task.evidence == []
    assert task.history[0]["to"] == WorkerState.PLANNING.value


def test_runtime_task_validates_standard_and_approval_lifecycles():
    standard = RuntimeTask.create("development_worker")
    for state in (
        WorkerState.READY, WorkerState.RUNNING,
        WorkerState.QA, WorkerState.COMPLETED,
    ):
        standard.transition(state, f"move to {state.name}")

    approval = RuntimeTask.create("development_worker")
    for state in (
        WorkerState.READY, WorkerState.RUNNING, WorkerState.WAITING_APPROVAL,
        WorkerState.RESUMED, WorkerState.QA, WorkerState.COMPLETED,
    ):
        approval.transition(state, f"move to {state.name}")

    assert standard.state is WorkerState.COMPLETED
    assert approval.state is WorkerState.COMPLETED
    assert [item["to"] for item in approval.history] == [
        "planning", "ready", "running", "waiting_approval",
        "resumed", "qa", "completed",
    ]


@pytest.mark.parametrize("target", [WorkerState.RUNNING, WorkerState.QA, WorkerState.COMPLETED])
def test_runtime_task_rejects_invalid_transitions(target):
    task = RuntimeTask.create("development_worker")

    with pytest.raises(InvalidTaskTransition, match="PLANNING"):
        task.transition(target, "invalid shortcut")

    assert task.state is WorkerState.PLANNING
    assert len(task.history) == 1


def test_runtime_task_requires_qa_before_completion():
    task = RuntimeTask.create("development_worker")
    task.transition(WorkerState.READY, "planned")
    task.transition(WorkerState.RUNNING, "started")

    with pytest.raises(InvalidTaskTransition, match="RUNNING -> COMPLETED"):
        task.transition(WorkerState.COMPLETED, "invalid completion")


def test_runtime_task_round_trips_through_worker_context():
    task = RuntimeTask.create("development_worker", inputs={"request": "demo"})
    task.transition(WorkerState.READY, "planned")
    context = WorkerContext(request="demo", runtime_task=task)

    restored = WorkerContext.from_value(context.to_dict())

    assert restored.runtime_task is not task
    assert restored.runtime_task.to_dict() == task.to_dict()
    assert restored.runtime_task.state is WorkerState.READY


def test_runtime_event_records_task_identity_state_and_payload(tmp_path):
    stream = EventStream(ArtifactStore(tmp_path, "RWS-event-test"))
    event = stream.emit(
        "TASK_CREATED", "development_worker", "created",
        task_id="TASK-test", state="planning", payload={"priority": 1},
    )
    persisted = json.loads(
        (tmp_path / "data" / "runtime_sessions" / "RWS-event-test" / "events.jsonl")
        .read_text(encoding="utf-8").strip()
    )

    assert event.task_id == "TASK-test"
    assert event.state == "planning"
    assert persisted == {
        "event": "TASK_CREATED",
        "timestamp": event.timestamp,
        "worker_id": "development_worker",
        "detail": "created",
        "task_id": "TASK-test",
        "state": "planning",
        "payload": {"priority": 1},
    }


def test_planner_creates_task_and_developer_receives_running_task(tmp_path, monkeypatch):
    original_generate = ProviderBridge.generate
    observed = {}

    def capture_generate(provider, worker_id, request, context):
        if worker_id in {"planning_worker", "development_worker"}:
            observed[worker_id] = (
                None if context.runtime_task is None else context.runtime_task.to_dict()
            )
        return original_generate(provider, worker_id, request, context)

    monkeypatch.setattr(ProviderBridge, "generate", capture_generate)
    session = RealWorkerRuntime(tmp_path).run("build task engine", live=False)
    task = session.runtime_tasks[0]

    assert observed["planning_worker"] is None
    assert observed["development_worker"]["state"] == "running"
    assert observed["development_worker"]["inputs"]["planner_output"]["tasks"]
    assert observed["development_worker"]["worker"] == "development_worker"
    assert task["state"] == "completed"
    assert set(task["outputs"]) == {"development_worker", "qa_worker"}
    assert json.loads(
        (tmp_path / "data" / "runtime_sessions" / session.session_id / "runtime_task.json")
        .read_text(encoding="utf-8")
    ) == task
    events = _events(tmp_path, session.session_id)
    assert [item["event"] for item in events if item["event"].startswith("TASK_")] == [
        "TASK_CREATED", "TASK_STARTED", "TASK_COMPLETED",
    ]
    assert any(item["event"] == "QA_COMPLETED" for item in events)
    assert all(item["task_id"] == task["id"] for item in events if item["event"].startswith("TASK_"))


def test_runtime_records_task_failed_when_developer_fails(tmp_path, monkeypatch):
    original_generate = ProviderBridge.generate

    def fail_developer(provider, worker_id, request, context):
        if worker_id == "development_worker":
            raise RuntimeError("bounded provider failure")
        return original_generate(provider, worker_id, request, context)

    monkeypatch.setattr(ProviderBridge, "generate", fail_developer)
    session = RealWorkerRuntime(tmp_path).run("fail development", live=False)

    assert session.status == "failed"
    assert session.runtime_tasks[0]["state"] == "failed"
    failed = next(item for item in _events(tmp_path, session.session_id) if item["event"] == "TASK_FAILED")
    assert failed["worker_id"] == "development_worker"
    assert failed["task_id"] == session.runtime_tasks[0]["id"]


def test_qa_revision_cycles_through_running_and_qa(tmp_path):
    session = RealWorkerRuntime(tmp_path).run("[qa-fail-once]", live=False, max_revisions=1)
    states = [item["to"] for item in session.runtime_tasks[0]["history"]]

    assert session.status == "completed"
    assert states == [
        "planning", "ready", "running", "qa", "running", "qa", "completed",
    ]
    assert len([
        item for item in _events(tmp_path, session.session_id)
        if item["event"] == "QA_COMPLETED"
    ]) == 2


def test_approval_resume_preserves_task_lifecycle_and_events(tmp_path):
    _prepare_approval_root(tmp_path)
    runtime = RealWorkerRuntime(tmp_path)
    paused = runtime.run(
        "[approval-resume-mvp]", live=False, enable_controlled_execution=True,
    )
    paused_task = paused.runtime_tasks[0]

    assert paused.status == "waiting_approval"
    assert paused_task["state"] == "waiting_approval"
    assert "APPROVAL_REQUESTED" in [item["event"] for item in _events(tmp_path, paused.session_id)]

    resumed = RealWorkerRuntime(tmp_path).approval_approve(
        paused.pending_approval["approval_request_id"]
    )
    task = resumed.runtime_tasks[0]
    names = [WorkerState(item["to"]).name for item in task["history"]]
    event_names = [item["event"] for item in _events(tmp_path, resumed.session_id)]

    assert resumed.status == "completed"
    assert task["state"] == "completed"
    assert names == [
        "PLANNING", "READY", "RUNNING", "WAITING_APPROVAL",
        "RESUMED", "QA", "COMPLETED",
    ]
    for required in (
        "APPROVAL_REQUESTED", "APPROVAL_GRANTED", "QA_COMPLETED", "TASK_COMPLETED",
    ):
        assert required in event_names
    assert resumed.execution_verification["status"] == "VERIFIED"


def test_approval_rejection_fails_task_without_resuming(tmp_path):
    _prepare_approval_root(tmp_path)
    runtime = RealWorkerRuntime(tmp_path)
    paused = runtime.run(
        "[approval-resume-mvp]", live=False, enable_controlled_execution=True,
    )

    rejected = runtime.approval_reject(paused.pending_approval["approval_request_id"])
    persisted = runtime.status(paused.session_id)
    event_names = [item["event"] for item in _events(tmp_path, paused.session_id)]

    assert rejected["status"] == "REJECTED"
    assert persisted["status"] == "blocked"
    assert persisted["runtime_tasks"][0]["state"] == "failed"
    assert "TASK_FAILED" in event_names
    assert "APPROVAL_REJECTED" in event_names
    assert "APPROVAL_GRANTED" not in event_names


def _events(root: Path, session_id: str) -> list[dict]:
    path = root / "data" / "runtime_sessions" / session_id / "events.jsonl"
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def _prepare_approval_root(root: Path) -> None:
    fixture = root / "tests" / "fixtures" / "afde_2_7_approval_target.txt"
    fixture.parent.mkdir(parents=True)
    fixture.write_bytes(b"approval_state=baseline\n")
    (root / "tests" / "test_afde_2_7_fixture.py").write_text(
        "from pathlib import Path\n"
        "def test_state():\n"
        " p=Path(__file__).parent/'fixtures'/'afde_2_7_approval_target.txt'\n"
        " assert p.read_bytes() == b'approval_state=approved\\n'\n",
        encoding="utf-8",
    )
