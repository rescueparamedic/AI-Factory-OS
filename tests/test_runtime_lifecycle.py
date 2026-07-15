import json
from datetime import datetime
from pathlib import Path

import pytest

from real_worker_runtime import (
    RealWorkerRuntime, RuntimeLifecycleStatus, RuntimeTask,
)
from real_worker_runtime.errors import InvalidTaskTransition
from real_worker_runtime.provider_bridge import ProviderBridge


def test_successful_runtime_has_deterministic_terminal_summary_and_role_history(tmp_path):
    session = RealWorkerRuntime(tmp_path).run("lifecycle success", live=False)
    task = session.runtime_tasks[0]

    assert session.status == "completed"
    assert task["lifecycle_status"] == "completed"
    assert [item["to_status"] for item in task["lifecycle_transitions"]] == [
        "pending", "running", "completed",
    ]
    assert [item["sequence"] for item in task["lifecycle_transitions"]] == [1, 2, 3]
    assert [item["role"] for item in task["role_lifecycle"]] == [
        "planner", "developer", "qa", "documentation",
    ]
    assert all(item["status"] == "completed" for item in task["role_lifecycle"])
    assert all(item["attempt"] == 1 for item in task["role_lifecycle"])
    assert all(item["started_at"] and item["completed_at"] for item in task["role_lifecycle"])
    summary = session.execution_summary
    assert summary == task["execution_summary"]
    assert summary["final_status"] == "completed"
    assert summary["role_statuses"] == {
        "planner": "completed", "developer": "completed",
        "qa": "completed", "documentation": "completed",
    }
    assert summary["revision_count"] == 0
    assert summary["documentation_result_reference"].endswith("[3]")
    assert summary["transition_count"] == 3


def test_revision_lifecycle_preserves_attempts_results_and_order(tmp_path):
    session = RealWorkerRuntime(tmp_path).run(
        "[qa-fail-once]", live=False, max_revisions=1,
    )
    task = session.runtime_tasks[0]
    roles = task["role_lifecycle"]

    assert session.execution_summary["final_status"] == "completed"
    assert [(item["role"], item["attempt"], item["revision_index"])
            for item in roles] == [
        ("planner", 1, 0), ("developer", 1, 0), ("qa", 1, 0),
        ("developer", 2, 1), ("qa", 2, 1), ("documentation", 1, 1),
    ]
    assert len(task["role_executions"]) == 6
    assert len(task["result_handoffs"]) == 5
    assert session.execution_summary["revision_count"] == 1
    assert [item["to_status"] for item in task["lifecycle_transitions"]] == [
        "pending", "running", "revising", "running", "completed",
    ]
    revision = task["lifecycle_transitions"][2]
    assert revision["metadata"]["revision_number"] == 1
    assert revision["metadata"]["max_revisions"] == 1


def test_revision_exhaustion_is_structured_failure_and_skips_documentation(
    tmp_path, monkeypatch,
):
    original = ProviderBridge.generate

    def reject(provider, worker_id, request, context):
        output = original(provider, worker_id, request, context)
        if worker_id == "qa_worker":
            output.update({"claimed_failed": 1, "issues": ["still rejected"]})
        return output

    monkeypatch.setattr(ProviderBridge, "generate", reject)
    session = RealWorkerRuntime(tmp_path).run(
        "bounded rejection", live=False, max_revisions=0,
    )
    task = session.runtime_tasks[0]
    failure = session.execution_summary["failure"]

    assert session.status == "failed"
    assert task["lifecycle_status"] == "failed"
    assert failure["failure_code"] == "qa_revision_exhausted"
    assert failure["error_code"] == "RUNTIME_REVISION_LIMIT_EXCEEDED"
    assert failure["stage"] == "qa"
    assert session.execution_summary["role_statuses"]["documentation"] == "skipped"
    assert not any(item["role"] == "documentation" for item in task["role_lifecycle"])
    assert task["qa_revision_decisions"][-1]["outcome"] == "limit_exceeded"


@pytest.mark.parametrize("failed_worker", [
    "planning_worker", "development_worker", "qa_worker", "documentation_worker",
])
def test_required_role_failure_stops_subsequent_roles_and_reports_stage(
    tmp_path, monkeypatch, failed_worker,
):
    original = ProviderBridge.generate

    def fail(provider, worker_id, request, context):
        if worker_id == failed_worker:
            raise RuntimeError(f"{failed_worker} provider failure")
        return original(provider, worker_id, request, context)

    monkeypatch.setattr(ProviderBridge, "generate", fail)
    session = RealWorkerRuntime(tmp_path / failed_worker).run("role failure", live=False)
    task = session.runtime_tasks[0]
    expected_role = {
        "planning_worker": "planner", "development_worker": "developer",
        "qa_worker": "qa", "documentation_worker": "documentation",
    }[failed_worker]

    assert session.status == "failed"
    assert session.execution_summary["failure"]["stage"] == expected_role
    failed_index = list({
        "planner": 0, "developer": 1, "qa": 2, "documentation": 3,
    }) .index(expected_role)
    expected_roles = ["planner", "developer", "qa", "documentation"][:failed_index + 1]
    assert [item["role"] for item in task["role_lifecycle"]] == expected_roles


def test_unexpected_executor_exception_is_normalized_and_redacted(tmp_path):
    class ExplodingExecutor:
        def execute(self, request, context, definition):
            raise RuntimeError("api_key=topsecret Authorization: Bearer unsafe")

    session = RealWorkerRuntime(
        tmp_path, role_executor_factory=lambda provider: ExplodingExecutor(),
    ).run("unexpected failure", live=False)
    failure = session.execution_summary["failure"]

    assert session.status == "failed"
    assert failure["failure_code"] == "role_execution_exception"
    assert failure["exception_type"] == "RuntimeError"
    assert "topsecret" not in failure["safe_message"]
    assert "Bearer unsafe" not in failure["safe_message"]
    assert failure["cause_reference"] == "exception:RuntimeError"


@pytest.mark.parametrize(("worker_id", "required_key"), [
    ("planning_worker", "tasks"),
    ("development_worker", "implementation_summary"),
    ("qa_worker", "recommendation"),
    ("documentation_worker", "user_summary"),
])
def test_invalid_role_result_fails_closed_at_exact_stage(
    tmp_path, monkeypatch, worker_id, required_key,
):
    original = ProviderBridge.generate

    def invalidate(provider, current_worker, request, context):
        output = original(provider, current_worker, request, context)
        if current_worker == worker_id:
            output.pop(required_key, None)
        return output

    monkeypatch.setattr(ProviderBridge, "generate", invalidate)
    session = RealWorkerRuntime(tmp_path / worker_id).run("invalid result", live=False)
    failure = session.execution_summary["failure"]

    assert session.status == "failed"
    assert failure["failure_code"] == "invalid_role_result"
    assert failure["stage"] == {
        "planning_worker": "planner", "development_worker": "developer",
        "qa_worker": "qa", "documentation_worker": "documentation",
    }[worker_id]


def test_approval_pause_preserves_state_and_produces_paused_summary(tmp_path):
    _prepare_approval_root(tmp_path)
    session = RealWorkerRuntime(tmp_path).run(
        "[approval-resume-mvp]", live=False, enable_controlled_execution=True,
    )
    task = session.runtime_tasks[0]

    assert session.status == "waiting_approval"
    assert task["lifecycle_status"] == "waiting_approval"
    assert task["execution_summary"]["final_status"] == "waiting_approval"
    assert task["execution_summary"]["paused_at"]
    assert task["execution_summary"]["approval"]["approval_request_id"]
    assert task["execution_summary"]["role_statuses"]["developer"] == "waiting_approval"
    assert task["execution_summary"]["role_statuses"]["qa"] == "skipped"


def test_approval_resume_reuses_lifecycle_and_finishes(tmp_path):
    _prepare_approval_root(tmp_path)
    runtime = RealWorkerRuntime(tmp_path)
    paused = runtime.run(
        "[approval-resume-mvp]", live=False, enable_controlled_execution=True,
    )
    resumed = runtime.approval_approve(paused.pending_approval["approval_request_id"])
    transitions = resumed.runtime_tasks[0]["lifecycle_transitions"]

    assert resumed.status == "completed"
    assert [item["to_status"] for item in transitions] == [
        "pending", "running", "waiting_approval", "running", "completed",
    ]
    assert resumed.execution_summary["final_status"] == "completed"


def test_approval_rejection_preserves_blocked_semantics(tmp_path):
    _prepare_approval_root(tmp_path)
    runtime = RealWorkerRuntime(tmp_path)
    paused = runtime.run(
        "[approval-resume-mvp]", live=False, enable_controlled_execution=True,
    )
    runtime.approval_reject(paused.pending_approval["approval_request_id"])
    stored = runtime.status(paused.session_id)

    assert stored["status"] == "blocked"
    assert stored["runtime_tasks"][0]["lifecycle_status"] == "blocked"
    assert stored["execution_summary"]["final_status"] == "blocked"
    assert stored["execution_summary"]["failure"]["failure_code"] == "approval_rejected"


def test_transition_validation_rejects_duplicate_and_terminal_restart():
    task = RuntimeTask.create("development_worker")
    task.transition_lifecycle(
        RuntimeLifecycleStatus.RUNNING, stage="planner",
        reason_code="start", message="start",
    )
    with pytest.raises(InvalidTaskTransition) as rejected:
        task.transition_lifecycle(
            RuntimeLifecycleStatus.RUNNING, stage="planner",
            reason_code="duplicate", message="duplicate",
        )
    assert rejected.value.error_code == "RUNTIME_ILLEGAL_TRANSITION"
    task.transition_lifecycle(
        RuntimeLifecycleStatus.COMPLETED, stage="runtime",
        reason_code="done", message="done",
    )
    with pytest.raises(InvalidTaskTransition):
        task.transition_lifecycle(
            RuntimeLifecycleStatus.RUNNING, stage="runtime",
            reason_code="restart", message="restart",
        )
    assert [item["sequence"] for item in task.lifecycle_transitions] == [1, 2, 3]


def test_full_additive_lifecycle_policy_supports_queue_revision_and_cancel():
    task = RuntimeTask(
        id="TASK-policy", worker="development_worker",
        lifecycle_status=RuntimeLifecycleStatus.CREATED,
    )
    task.transition_lifecycle(
        "queued", stage="scheduler", reason_code="queued", message="queued",
    )
    task.transition_lifecycle(
        "running", stage="planner", reason_code="started", message="started",
    )
    task.transition_lifecycle(
        "revising", stage="qa", role="qa", reason_code="revise",
        message="QA requested revision", metadata={"revision_number": 1},
    )
    task.transition_lifecycle(
        "running", stage="developer", role="developer",
        reason_code="revision_started", message="revision started",
    )
    task.transition_lifecycle(
        "cancelled", stage="runtime", role="product_owner",
        reason_code="cancelled", message="cancelled",
    )

    assert [item["to_status"] for item in task.lifecycle_transitions] == [
        "created", "queued", "running", "revising", "running", "cancelled",
    ]
    with pytest.raises(InvalidTaskTransition):
        task.transition_lifecycle(
            "running", stage="runtime", reason_code="restart", message="restart",
        )


def test_structured_failure_contract_and_transition_history_are_safe():
    task = RuntimeTask.create("development_worker")
    task.transition_lifecycle(
        "running", stage="developer", role="developer",
        reason_code="start", message="start",
    )
    failure = task.record_failure(
        failure_code="provider_or_worker_failure", stage="developer",
        role="developer", message="token=super-secret", exception_type="WorkerError",
        cause_reference="authorization: bearer hidden", metadata={"api_key": "hidden"},
    )

    assert {
        "error_type", "error_code", "message", "stage", "actor",
        "retryable", "cause", "metadata",
    } <= failure.keys()
    assert failure["error_code"] == "RUNTIME_WORKER_FAILURE"
    assert "super-secret" not in failure["message"]
    assert "hidden" not in failure["cause"]
    assert failure["metadata"]["api_key"] == "[REDACTED]"
    view = task.transition_history
    view[0]["to_status"] = "corrupted"
    assert task.lifecycle_transitions[0]["to_status"] == "pending"
    with pytest.raises(TypeError):
        task.lifecycle_transitions.append({"to_status": "corrupted"})
    assert datetime.fromisoformat(task.lifecycle_transitions[-1]["timestamp"]).tzinfo


def test_lifecycle_serialization_round_trip_is_append_only():
    task = RuntimeTask.create("development_worker")
    task.transition_lifecycle(
        "running", stage="planner", reason_code="start", message="start",
    )
    restored = RuntimeTask.from_value(task.to_dict())

    assert restored.lifecycle_transitions == task.lifecycle_transitions
    assert restored.lifecycle_status is RuntimeLifecycleStatus.RUNNING
    restored.transition_lifecycle(
        "failed", stage="planner", role="planner",
        reason_code="failure", message="failure",
    )
    assert len(task.lifecycle_transitions) == 2
    assert len(restored.lifecycle_transitions) == 3


def test_lifecycle_events_match_append_only_transition_history(tmp_path):
    session = RealWorkerRuntime(tmp_path).run("lifecycle events", live=False)
    task = session.runtime_tasks[0]
    events = _events(tmp_path, session.session_id)
    lifecycle_events = [item for item in events
                        if item["event"] == "RUNTIME_LIFECYCLE_TRANSITION"]

    assert [item["payload"]["sequence"] for item in lifecycle_events] == [2, 3]
    assert [item["state"] for item in lifecycle_events] == ["running", "completed"]
    assert len(task["lifecycle_transitions"]) == len(lifecycle_events) + 1


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
