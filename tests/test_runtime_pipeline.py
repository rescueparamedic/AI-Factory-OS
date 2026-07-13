import json
from pathlib import Path

import pytest

from real_worker_runtime import (
    PipelineState, RealWorkerRuntime, RuntimePipeline, RuntimeTask, WorkerContext,
)
from real_worker_runtime.errors import InvalidPipelineTransition
from real_worker_runtime.provider_bridge import ProviderBridge


def test_runtime_pipeline_validates_normal_and_approval_paths():
    normal = RuntimePipeline("TASK-normal")
    for state, worker in (
        (PipelineState.ASSIGNED, "development_worker"),
        (PipelineState.DEVELOPING, "development_worker"),
        (PipelineState.QA_PENDING, "qa_worker"),
        (PipelineState.DOCUMENTING, "documentation_worker"),
        (PipelineState.DONE, "runtime"),
    ):
        normal.transition(state, worker, f"move to {state.name}")

    approval = RuntimePipeline("TASK-approval")
    for state, worker in (
        (PipelineState.ASSIGNED, "development_worker"),
        (PipelineState.DEVELOPING, "development_worker"),
        (PipelineState.APPROVAL_PENDING, "approval_guardian"),
        (PipelineState.QA_PENDING, "qa_worker"),
        (PipelineState.DOCUMENTING, "documentation_worker"),
        (PipelineState.DONE, "runtime"),
    ):
        approval.transition(state, worker, f"move to {state.name}")
    approval.mark_approved()

    assert normal.state is PipelineState.DONE
    assert approval.state is PipelineState.DONE
    assert approval.approved is True
    assert [entry["to"] for entry in approval.history] == [
        "planned", "assigned", "developing", "approval_pending",
        "qa_pending", "documenting", "done",
    ]


@pytest.mark.parametrize("target", [
    PipelineState.DEVELOPING, PipelineState.QA_PENDING,
    PipelineState.DOCUMENTING, PipelineState.DONE,
])
def test_runtime_pipeline_rejects_invalid_shortcuts(target):
    pipeline = RuntimePipeline("TASK-invalid")

    with pytest.raises(InvalidPipelineTransition, match="PLANNED"):
        pipeline.transition(target, "runtime", "invalid shortcut")

    assert pipeline.state is PipelineState.PLANNED
    assert len(pipeline.history) == 1


def test_runtime_task_records_owner_and_handoff_metadata():
    task = RuntimeTask.create("development_worker", owner="planning_worker")
    handoff = task.handoff(
        "development_worker", "Planner assigned task",
        {"pipeline_state": "assigned"},
    )
    restored = RuntimeTask.from_value(task.to_dict())

    assert task.worker == "development_worker"
    assert task.owner == "development_worker"
    assert handoff["from"] == "planning_worker"
    assert handoff["to"] == "development_worker"
    assert task.handoff_metadata["latest"] == handoff
    assert restored.to_dict() == task.to_dict()


def test_worker_context_round_trips_runtime_pipeline():
    task = RuntimeTask.create("development_worker")
    pipeline = RuntimePipeline(task.id)
    pipeline.transition(PipelineState.ASSIGNED, "development_worker", "assigned")
    context = WorkerContext(
        request="pipeline request", runtime_task=task, runtime_pipeline=pipeline,
    )

    restored = WorkerContext.from_value(context.to_dict())

    assert restored.runtime_pipeline is not pipeline
    assert restored.runtime_pipeline.to_dict() == pipeline.to_dict()
    assert restored.runtime_pipeline.task_id == restored.runtime_task.id


def test_normal_runtime_pipeline_handoffs_and_events(tmp_path, monkeypatch):
    original_generate = ProviderBridge.generate
    developer_observation = {}

    def capture_developer(provider, worker_id, request, context):
        if worker_id == "development_worker":
            developer_observation.update({
                "pipeline": context.runtime_pipeline.to_dict(),
                "task": context.runtime_task.to_dict(),
            })
        return original_generate(provider, worker_id, request, context)

    monkeypatch.setattr(ProviderBridge, "generate", capture_developer)
    session = RealWorkerRuntime(tmp_path).run("build pipeline", live=False)
    pipeline = session.runtime_pipelines[0]
    task = session.runtime_tasks[0]
    events = _events(tmp_path, session.session_id)

    assert session.status == "completed"
    assert developer_observation["pipeline"]["state"] == "developing"
    assert developer_observation["task"]["owner"] == "development_worker"
    assert pipeline["state"] == "done"
    assert pipeline["current_worker"] == "runtime"
    assert [entry["to"] for entry in pipeline["history"]] == [
        "planned", "assigned", "developing", "qa_pending", "documenting", "done",
    ]
    assert task["owner"] == "runtime"
    assert [entry["to"] for entry in task["handoff_metadata"]["history"]] == [
        "development_worker", "qa_worker", "documentation_worker", "runtime",
    ]
    assert _event_workers(events, "TaskStarted") == [
        "development_worker", "qa_worker", "documentation_worker",
    ]
    assert _event_workers(events, "TaskCompleted") == [
        "development_worker", "qa_worker", "documentation_worker",
    ]
    assert len([event for event in events if event["event"] == "TaskForwarded"]) == 4
    assert len([event for event in events if event["event"] == "TaskAssigned"]) == 1
    assert not any(event["event"] in {"TaskApproved", "TaskRejected"} for event in events)
    persisted = json.loads(
        (tmp_path / "data" / "runtime_sessions" / session.session_id / "runtime_pipeline.json")
        .read_text(encoding="utf-8")
    )
    assert persisted == pipeline


def test_approval_pipeline_pauses_and_resumes_through_existing_boundary(tmp_path):
    _prepare_approval_root(tmp_path)
    paused = RealWorkerRuntime(tmp_path).run(
        "[approval-resume-mvp]", live=False, enable_controlled_execution=True,
    )
    paused_pipeline = paused.runtime_pipelines[0]
    paused_task = paused.runtime_tasks[0]

    assert paused.status == "waiting_approval"
    assert paused_pipeline["state"] == "approval_pending"
    assert paused_pipeline["approved"] is False
    assert paused_task["owner"] == "approval_guardian"
    continuation = json.loads(
        (tmp_path / "data" / "runtime_sessions" / paused.session_id / "continuation.json")
        .read_text(encoding="utf-8")
    )
    assert continuation["context"]["runtime_pipeline"] == paused_pipeline

    resumed = RealWorkerRuntime(tmp_path).approval_approve(
        paused.pending_approval["approval_request_id"]
    )
    pipeline = resumed.runtime_pipelines[0]
    events = _events(tmp_path, resumed.session_id)

    assert resumed.status == "completed"
    assert resumed.execution_verification["status"] == "VERIFIED"
    assert pipeline["state"] == "done"
    assert pipeline["approved"] is True
    assert [entry["to"] for entry in pipeline["history"]] == [
        "planned", "assigned", "developing", "approval_pending",
        "qa_pending", "documenting", "done",
    ]
    assert len([event for event in events if event["event"] == "TaskApproved"]) == 1
    approved = next(event for event in events if event["event"] == "TaskApproved")
    assert approved["payload"]["approval_request_id"] == paused.pending_approval["approval_request_id"]


def test_pipeline_records_qa_revision_rejection_and_recovery(tmp_path):
    session = RealWorkerRuntime(tmp_path).run("[qa-fail-once]", live=False, max_revisions=1)
    pipeline = session.runtime_pipelines[0]
    events = _events(tmp_path, session.session_id)

    assert session.status == "completed"
    assert [entry["to"] for entry in pipeline["history"]] == [
        "planned", "assigned", "developing", "qa_pending", "developing",
        "qa_pending", "documenting", "done",
    ]
    assert any(
        event["event"] == "TaskRejected" and event["worker_id"] == "qa_worker"
        for event in events
    )
    assert pipeline["rejected"] is False


def test_pipeline_records_terminal_rejection_without_changing_approval_semantics(tmp_path):
    _prepare_approval_root(tmp_path)
    runtime = RealWorkerRuntime(tmp_path)
    paused = runtime.run(
        "[approval-resume-mvp]", live=False, enable_controlled_execution=True,
    )

    record = runtime.approval_reject(paused.pending_approval["approval_request_id"])
    persisted = runtime.status(paused.session_id)
    pipeline = persisted["runtime_pipelines"][0]
    events = _events(tmp_path, paused.session_id)

    assert record["status"] == "REJECTED"
    assert persisted["status"] == "blocked"
    assert pipeline["state"] == "approval_pending"
    assert pipeline["approved"] is False
    assert pipeline["rejected"] is True
    assert any(event["event"] == "TaskRejected" for event in events)
    assert not any(event["event"] == "TaskApproved" for event in events)


def _events(root: Path, session_id: str) -> list[dict]:
    path = root / "data" / "runtime_sessions" / session_id / "events.jsonl"
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def _event_workers(events: list[dict], name: str) -> list[str]:
    return [event["worker_id"] for event in events if event["event"] == name]


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
