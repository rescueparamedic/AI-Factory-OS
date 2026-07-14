import json
from pathlib import Path

import pytest

from real_worker_runtime import (
    PipelineState,
    RealWorkerRuntime,
    RuntimeOrchestrator,
    RuntimePipeline,
    RuntimeTask,
    WorkerContext,
)
from real_worker_runtime.errors import OrchestrationError, RevisionLimitExceeded
from real_worker_runtime.provider_bridge import ProviderBridge


def test_orchestrator_coordinates_normal_flow_and_preserves_context(tmp_path, monkeypatch):
    original_generate = ProviderBridge.generate
    observed = {}

    def capture(provider, worker_id, request, context):
        if worker_id in {"development_worker", "qa_worker", "documentation_worker"}:
            observed[worker_id] = context.to_dict()
        return original_generate(provider, worker_id, request, context)

    monkeypatch.setattr(ProviderBridge, "generate", capture)
    session = RealWorkerRuntime(tmp_path).run("orchestrate normal flow", live=False)
    task = session.runtime_tasks[0]
    pipeline = session.runtime_pipelines[0]
    events = _events(tmp_path, session.session_id)

    assert session.status == "completed"
    assert pipeline["state"] == "done"
    assert [item["target_worker"] for item in task["orchestration_metadata"]["decisions"]] == [
        "development_worker", "qa_worker", "documentation_worker", "runtime",
    ]
    assert [item["payload"]["target_worker"] for item in events
            if item["event"] == "ORCHESTRATION_DECISION"] == [
        "development_worker", "qa_worker", "documentation_worker", "runtime",
    ]
    assert observed["development_worker"]["planner_output"]
    assert "planning_worker" in observed["development_worker"]["prior_worker_artifacts"]
    assert "development_worker" in observed["qa_worker"]["prior_worker_artifacts"]
    assert "qa_worker" in observed["documentation_worker"]["prior_worker_artifacts"]
    assert {
        observed[worker]["runtime_task"]["id"] for worker in observed
    } == {task["id"]}


def test_orchestrator_uses_registered_pipeline_ownership_and_rejects_bad_restore():
    task = RuntimeTask.create("development_worker")
    context = WorkerContext(
        request="route task", runtime_task=task, runtime_pipeline=RuntimePipeline(task.id),
    )
    orchestrator = RuntimeOrchestrator(context, max_revisions=2)

    assert [item.worker_id for item in orchestrator.revision_workers()] == [
        "development_worker", "qa_worker",
    ]
    assert orchestrator.handoff_after("development_worker").target_state is PipelineState.QA_PENDING
    assert orchestrator.worker_index("qa_worker") == 3

    mismatched = WorkerContext(
        request="bad restore", runtime_task=task,
        runtime_pipeline=RuntimePipeline("TASK-other"),
    )
    with pytest.raises(OrchestrationError, match="identities"):
        RuntimeOrchestrator(mismatched)


def test_multiple_revisions_are_persisted_and_append_only(tmp_path, monkeypatch):
    original_generate = ProviderBridge.generate

    def fail_twice(provider, worker_id, request, context):
        output = original_generate(provider, worker_id, request, context)
        if worker_id == "qa_worker" and context.revision < 2:
            output.update({
                "claimed_passed": 0,
                "claimed_failed": 1,
                "issues": [f"revision {context.revision + 1} required"],
                "recommendation": "REVISE",
            })
        return output

    monkeypatch.setattr(ProviderBridge, "generate", fail_twice)
    session = RealWorkerRuntime(tmp_path).run(
        "bounded multiple revisions", live=False, max_revisions=2,
    )
    task = session.runtime_tasks[0]
    pipeline = session.runtime_pipelines[0]
    persisted = json.loads(
        (tmp_path / "data" / "runtime_sessions" / session.session_id / "runtime_task.json")
        .read_text(encoding="utf-8")
    )

    assert session.status == "completed"
    assert task["orchestration_metadata"]["revision_count"] == 2
    assert persisted == task
    assert [item["action"] for item in task["orchestration_metadata"]["decisions"]].count(
        "revise"
    ) == 2
    assert [item["to"] for item in task["handoff_metadata"]["history"]] == [
        "development_worker", "qa_worker", "development_worker", "qa_worker",
        "development_worker", "qa_worker", "documentation_worker", "runtime",
    ]
    assert [item["to"] for item in pipeline["history"]].count("developing") == 3


def test_revision_limit_fails_safely_with_task_and_event_evidence(tmp_path, monkeypatch):
    original_generate = ProviderBridge.generate

    def always_revise(provider, worker_id, request, context):
        output = original_generate(provider, worker_id, request, context)
        if worker_id == "qa_worker":
            output.update({
                "claimed_passed": 0, "claimed_failed": 1,
                "issues": ["still failing"], "recommendation": "REVISE",
            })
        return output

    monkeypatch.setattr(ProviderBridge, "generate", always_revise)
    session = RealWorkerRuntime(tmp_path).run(
        "bounded failure", live=False, max_revisions=2,
    )
    task = session.runtime_tasks[0]
    events = _events(tmp_path, session.session_id)

    assert session.status == "failed"
    assert session.error == "QA revision limit exceeded: 2/2 revisions used"
    assert task["state"] == "failed"
    assert task["orchestration_metadata"]["revision_count"] == 2
    assert task["orchestration_metadata"]["errors"][-1]["code"] == "revision_limit_exceeded"
    error = next(item for item in events if item["event"] == "ORCHESTRATION_ERROR")
    assert error["task_id"] == task["id"]
    assert error["detail"] == session.error


def test_orchestrator_revision_counter_round_trips_and_is_bounded():
    task = RuntimeTask.create("development_worker")
    context = WorkerContext(
        request="revision state", runtime_task=task, runtime_pipeline=RuntimePipeline(task.id),
    )
    orchestrator = RuntimeOrchestrator(context, max_revisions=2)
    orchestrator.request_revision()
    restored = WorkerContext.from_value(context.to_dict())
    resumed = RuntimeOrchestrator(restored, max_revisions=2)
    resumed.request_revision()

    assert restored.revision == 2
    assert restored.runtime_task.orchestration_metadata["revision_count"] == 2
    with pytest.raises(RevisionLimitExceeded, match="2/2"):
        resumed.request_revision()


def test_provider_failure_fails_orchestration_without_fabricated_handoff(tmp_path, monkeypatch):
    original_generate = ProviderBridge.generate

    def fail_developer(provider, worker_id, request, context):
        if worker_id == "development_worker":
            raise RuntimeError("deterministic provider failure")
        return original_generate(provider, worker_id, request, context)

    monkeypatch.setattr(ProviderBridge, "generate", fail_developer)
    session = RealWorkerRuntime(tmp_path).run("provider failure", live=False)
    task = session.runtime_tasks[0]
    events = _events(tmp_path, session.session_id)

    assert session.status == "failed"
    assert session.error == "deterministic provider failure"
    assert task["state"] == "failed"
    assert not any(
        item["event"] == "ORCHESTRATION_DECISION"
        and item["payload"].get("target_worker") == "qa_worker"
        for item in events
    )
    assert any(item["event"] == "PROVIDER_ERROR" for item in events)


def test_approval_pause_and_resume_return_to_orchestrated_qa(tmp_path):
    _prepare_approval_root(tmp_path)
    runtime = RealWorkerRuntime(tmp_path)
    paused = runtime.run(
        "[approval-resume-mvp]", live=False, enable_controlled_execution=True,
    )
    continuation = json.loads(
        (tmp_path / "data" / "runtime_sessions" / paused.session_id / "continuation.json")
        .read_text(encoding="utf-8")
    )

    assert paused.status == "waiting_approval"
    assert paused.runtime_tasks[0]["owner"] == "approval_guardian"
    assert continuation["context"]["runtime_task"] == paused.runtime_tasks[0]
    assert continuation["context"]["runtime_pipeline"] == paused.runtime_pipelines[0]

    resumed = runtime.approval_approve(paused.pending_approval["approval_request_id"])
    decisions = resumed.runtime_tasks[0]["orchestration_metadata"]["decisions"]
    events = _events(tmp_path, resumed.session_id)

    assert resumed.status == "completed"
    assert any(
        item["source_worker"] == "approval_guardian"
        and item["target_worker"] == "qa_worker" for item in decisions
    )
    granted = next(index for index, item in enumerate(events) if item["event"] == "APPROVAL_GRANTED")
    qa_started = next(
        index for index, item in enumerate(events)
        if item["event"] == "WORKER_STARTED" and item["worker_id"] == "qa_worker"
    )
    assert granted < qa_started


def test_approval_rejection_preserves_existing_blocked_semantics(tmp_path):
    _prepare_approval_root(tmp_path)
    runtime = RealWorkerRuntime(tmp_path)
    paused = runtime.run(
        "[approval-resume-mvp]", live=False, enable_controlled_execution=True,
    )
    record = runtime.approval_reject(paused.pending_approval["approval_request_id"])
    persisted = runtime.status(paused.session_id)
    events = _events(tmp_path, paused.session_id)

    assert record["status"] == "REJECTED"
    assert persisted["status"] == "blocked"
    assert persisted["runtime_tasks"][0]["state"] == "failed"
    assert persisted["runtime_pipelines"][0]["state"] == "approval_pending"
    assert not any(item["event"] == "APPROVAL_GRANTED" for item in events)


def test_revision_approval_pause_is_resumable_without_moving_boundary(tmp_path, monkeypatch):
    _prepare_approval_root(tmp_path)
    (tmp_path / "tests" / "test_afde_2_7_fixture.py").write_text(
        "from pathlib import Path\n"
        "def test_state():\n"
        " p=Path(__file__).parent/'fixtures'/'afde_2_7_approval_target.txt'\n"
        " assert p.read_text() in {'approval_state=approved\\n', "
        "'approval_state=approved_revision\\n'}\n",
        encoding="utf-8",
    )
    original_generate = ProviderBridge.generate

    def revise_controlled_content(provider, worker_id, request, context):
        output = original_generate(provider, worker_id, request, context)
        if worker_id == "development_worker" and context.revision == 1:
            output["proposed_file_writes"][0]["content"] = (
                "approval_state=approved_revision\n"
            )
        return output

    monkeypatch.setattr(ProviderBridge, "generate", revise_controlled_content)
    runtime = RealWorkerRuntime(tmp_path)
    first_pause = runtime.run(
        "[approval-resume-mvp] [qa-fail-once]", live=False,
        enable_controlled_execution=True, max_revisions=1,
    )
    after_initial_approval = runtime.approval_approve(
        first_pause.pending_approval["approval_request_id"]
    )

    assert after_initial_approval.status == "waiting_approval"
    assert after_initial_approval.runtime_tasks[0]["orchestration_metadata"][
        "revision_count"
    ] == 1
    assert after_initial_approval.runtime_pipelines[0]["state"] == "approval_pending"

    completed = runtime.approval_approve(
        after_initial_approval.pending_approval["approval_request_id"]
    )
    events = _events(tmp_path, completed.session_id)

    assert completed.status == "completed", completed.error
    assert completed.runtime_pipelines[0]["state"] == "done"
    assert len([item for item in events if item["event"] == "APPROVAL_CONSUMED"]) == 2
    assert len([item for item in events if item["event"] == "RUNTIME_RESUMED"]) == 2


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
