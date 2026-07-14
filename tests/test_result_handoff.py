import json
from pathlib import Path

import pytest

from real_worker_runtime import (
    AgentResultHandoff,
    QARevisionOutcome,
    RealWorkerRuntime,
    ResultHandoffState,
    RuntimeOrchestrator,
    RuntimePipeline,
    RuntimeRole,
    RuntimeTask,
    WorkerContext,
)
from real_worker_runtime.errors import InvalidRoleResult, OrchestrationError
from real_worker_runtime.provider_bridge import ProviderBridge


def test_normal_result_handoffs_are_typed_persisted_and_delivered(tmp_path):
    session = RealWorkerRuntime(tmp_path).run("typed handoffs", live=False)
    task = session.runtime_tasks[0]
    handoffs = task["result_handoffs"]

    assert session.status == "completed"
    assert [(item["producer_role"], item["consumer_role"]) for item in handoffs] == [
        ("planner", "developer"),
        ("developer", "qa"),
        ("qa", "documentation"),
    ]
    assert all(item["task_id"] == task["id"] for item in handoffs)
    assert all(item["result_reference"].startswith("runtime_task:role_executions[")
               for item in handoffs)
    assert all(item["result_payload"] is None for item in handoffs)
    assert all([entry["state"] for entry in item["history"]] == [
        "created", "delivered",
    ] for item in handoffs)


def test_handoff_layer_connects_each_result_to_consumer_context(tmp_path, monkeypatch):
    original_generate = ProviderBridge.generate
    observed = {}

    def capture(provider, worker_id, request, context):
        role = RuntimeRole.from_worker(worker_id)
        if role in {RuntimeRole.DEVELOPER, RuntimeRole.QA, RuntimeRole.DOCUMENTATION}:
            observed[role.value] = dict(context.active_result_handoff or {})
        return original_generate(provider, worker_id, request, context)

    monkeypatch.setattr(ProviderBridge, "generate", capture)
    session = RealWorkerRuntime(tmp_path).run("context handoff", live=False)

    assert session.status == "completed"
    assert observed["developer"]["producer_role"] == "planner"
    assert observed["developer"]["consumer_role"] == "developer"
    assert observed["qa"]["producer_role"] == "developer"
    assert observed["qa"]["consumer_role"] == "qa"
    assert observed["documentation"]["producer_role"] == "qa"
    assert observed["documentation"]["consumer_role"] == "documentation"


def test_qa_revision_persists_reason_count_and_round_trip_handoffs(tmp_path):
    session = RealWorkerRuntime(tmp_path).run(
        "[qa-fail-once]", live=False, max_revisions=1,
    )
    task = session.runtime_tasks[0]
    handoffs = task["result_handoffs"]
    decisions = task["qa_revision_decisions"]

    assert session.status == "completed"
    assert [(item["producer_role"], item["consumer_role"]) for item in handoffs] == [
        ("planner", "developer"), ("developer", "qa"),
        ("qa", "developer"), ("developer", "qa"),
        ("qa", "documentation"),
    ]
    revision_handoff = handoffs[2]
    assert revision_handoff["revision_reason"] == "mock revision requested"
    assert revision_handoff["revision_count"] == 1
    assert handoffs[3]["revision_count"] == 1
    assert [(item["outcome"], item["revision_count"]) for item in decisions] == [
        ("revision_requested", 1), ("accepted", 1),
    ]
    assert decisions[0]["reason"] == "mock revision requested"


def test_multiple_revisions_preserve_all_results_handoffs_and_decisions(tmp_path, monkeypatch):
    original_generate = ProviderBridge.generate

    def fail_twice(provider, worker_id, request, context):
        output = original_generate(provider, worker_id, request, context)
        if worker_id == "qa_worker" and context.revision < 2:
            output.update({
                "claimed_passed": 0, "claimed_failed": 1,
                "issues": [f"revision reason {context.revision + 1}"],
                "recommendation": "REVISE",
            })
        return output

    monkeypatch.setattr(ProviderBridge, "generate", fail_twice)
    session = RealWorkerRuntime(tmp_path).run(
        "two revisions", live=False, max_revisions=2,
    )
    task = session.runtime_tasks[0]

    assert session.status == "completed"
    assert len(task["role_executions"]) == 8
    assert len(task["result_handoffs"]) == 7
    assert [item["revision_count"] for item in task["qa_revision_decisions"]] == [1, 2, 2]
    assert [item["reason"] for item in task["qa_revision_decisions"][:2]] == [
        "revision reason 1", "revision reason 2",
    ]
    assert [item["consumer_role"] for item in task["result_handoffs"]].count("developer") == 3
    assert [item["consumer_role"] for item in task["result_handoffs"]].count("qa") == 3


def test_revision_limit_exceeded_is_explicit_and_does_not_create_loop_handoff(
    tmp_path, monkeypatch,
):
    original_generate = ProviderBridge.generate

    def always_revise(provider, worker_id, request, context):
        output = original_generate(provider, worker_id, request, context)
        if worker_id == "qa_worker":
            output.update({
                "claimed_passed": 0, "claimed_failed": 1,
                "issues": ["deterministic blocker"], "recommendation": "REVISE",
            })
        return output

    monkeypatch.setattr(ProviderBridge, "generate", always_revise)
    session = RealWorkerRuntime(tmp_path).run(
        "limit failure", live=False, max_revisions=0,
    )
    task = session.runtime_tasks[0]
    events = _events(tmp_path, session.session_id)

    assert session.status == "failed"
    assert session.error == "QA revision limit exceeded: 0/0 revisions used"
    assert task["qa_revision_decisions"][-1]["outcome"] == "limit_exceeded"
    assert task["qa_revision_decisions"][-1]["reason"] == "deterministic blocker"
    assert task["qa_revision_decisions"][-1]["revision_count"] == 0
    assert [(item["producer_role"], item["consumer_role"])
            for item in task["result_handoffs"]] == [
        ("planner", "developer"), ("developer", "qa"),
    ]
    assert len([item for item in events if item["event"] == "REVISION_LIMIT_EXCEEDED"]) == 1
    assert not any(item["event"] == "REVISION_RESUMED" for item in events)


def test_handoff_and_revision_events_are_deterministic(tmp_path):
    session = RealWorkerRuntime(tmp_path).run(
        "[qa-fail-once]", live=False, max_revisions=1,
    )
    events = _events(tmp_path, session.session_id)
    names = [item["event"] for item in events]

    assert names.count("RESULT_HANDOFF_CREATED") == 5
    assert names.count("RESULT_HANDOFF_DELIVERED") == 5
    assert names.count("QA_REVISION_REQUESTED") == 1
    assert names.count("REVISION_RESUMED") == 1
    assert names.count("QA_ACCEPTED") == 1
    assert names.index("QA_REVISION_REQUESTED") < names.index("REVISION_RESUMED")
    assert names.index("REVISION_RESUMED") < names.index("QA_ACCEPTED")


def test_approval_pause_serializes_handoffs_and_resume_creates_developer_to_qa(tmp_path):
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
    assert [(item["producer_role"], item["consumer_role"])
            for item in paused.runtime_tasks[0]["result_handoffs"]] == [
        ("planner", "developer"),
    ]
    assert continuation["context"]["result_handoffs"] == paused.runtime_tasks[0][
        "result_handoffs"
    ]

    resumed = runtime.approval_approve(paused.pending_approval["approval_request_id"])
    handoffs = resumed.runtime_tasks[0]["result_handoffs"]

    assert resumed.status == "completed"
    assert [(item["producer_role"], item["consumer_role"]) for item in handoffs] == [
        ("planner", "developer"), ("developer", "qa"), ("qa", "documentation"),
    ]
    assert len([item for item in _events(tmp_path, resumed.session_id)
                if item["event"] == "APPROVAL_CONSUMED"]) == 1


def test_provider_failure_does_not_fabricate_producer_handoff(tmp_path, monkeypatch):
    original_generate = ProviderBridge.generate

    def fail_developer(provider, worker_id, request, context):
        if worker_id == "development_worker":
            raise RuntimeError("provider failed")
        return original_generate(provider, worker_id, request, context)

    monkeypatch.setattr(ProviderBridge, "generate", fail_developer)
    session = RealWorkerRuntime(tmp_path).run("provider handoff failure", live=False)
    task = session.runtime_tasks[0]

    assert session.status == "failed"
    assert [(item["producer_role"], item["consumer_role"])
            for item in task["result_handoffs"]] == [("planner", "developer")]
    assert not any(item["producer_role"] == "developer" for item in task["result_handoffs"])


def test_controlled_execution_and_execution_truth_flow_into_handoff_validation(tmp_path):
    session = RealWorkerRuntime(tmp_path).run(
        "[controlled-execution-mvp]", live=False,
        enable_controlled_execution=True,
    )
    task = session.runtime_tasks[0]
    developer_handoff = next(
        item for item in task["result_handoffs"] if item["producer_role"] == "developer"
    )

    assert session.status == "completed"
    assert session.execution_verification["status"] == "VERIFIED"
    assert "runtime_evidence:verified_changed_files" in developer_handoff[
        "validation_metadata"
    ]["evidence_references"]
    assert "runtime_evidence:execution_evidence" in developer_handoff[
        "validation_metadata"
    ]["evidence_references"]
    assert developer_handoff["validation_metadata"]["has_error"] is False


def test_worker_context_round_trip_preserves_handoff_ledger_and_active_input():
    task = RuntimeTask.create("development_worker")
    handoff = AgentResultHandoff.create(
        task.id, RuntimeRole.PLANNER, RuntimeRole.DEVELOPER,
        "runtime_task:role_executions[0]",
        validation_metadata={"valid": True},
    )
    handoff.deliver("development_worker")
    task.result_handoffs.append(handoff.to_dict())
    context = WorkerContext(
        request="round trip", runtime_task=task,
        runtime_pipeline=RuntimePipeline(task.id),
        result_handoffs=[handoff.to_dict()],
        active_result_handoff=handoff.to_dict(),
    )

    restored = WorkerContext.from_value(context.to_dict())

    assert restored.result_handoffs == context.result_handoffs
    assert restored.active_result_handoff == context.active_result_handoff
    assert restored.runtime_task.result_handoffs == task.result_handoffs


def test_handoff_model_rejects_wrong_consumer_and_duplicate_delivery():
    handoff = AgentResultHandoff.create(
        "TASK-test", RuntimeRole.PLANNER, RuntimeRole.DEVELOPER,
        "runtime_task:role_executions[0]",
    )

    with pytest.raises(OrchestrationError, match="consumer identity"):
        handoff.deliver("qa_worker")
    handoff.deliver("development_worker")
    with pytest.raises(OrchestrationError, match="already been delivered"):
        handoff.deliver("development_worker")
    assert [item["state"] for item in handoff.history] == [
        ResultHandoffState.CREATED.value, ResultHandoffState.DELIVERED.value,
    ]


def test_orchestrator_rejects_handoff_target_mismatch():
    task = RuntimeTask.create("development_worker")
    pipeline = RuntimePipeline(task.id)
    context = WorkerContext(request="mismatch", runtime_task=task, runtime_pipeline=pipeline)
    orchestrator = RuntimeOrchestrator(context)
    result = type("Result", (), {"task_id": task.id, "role": RuntimeRole.PLANNER,
                                  "handoff_target": "development_worker"})()

    with pytest.raises(InvalidRoleResult, match="requested role target"):
        orchestrator.create_result_handoff(result, RuntimeRole.QA)


def test_qa_revision_outcome_enum_is_stable():
    assert [item.value for item in QARevisionOutcome] == [
        "accepted", "revision_requested", "limit_exceeded",
    ]


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
