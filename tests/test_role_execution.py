import json
from pathlib import Path

import pytest

from real_worker_runtime import (
    PipelineState,
    RealWorkerRuntime,
    RoleExecutionRequest,
    RoleExecutionResult,
    RoleExecutionState,
    RoleExecutor,
    RuntimeOrchestrator,
    RuntimePipeline,
    RuntimeRole,
    RuntimeTask,
    WorkerContext,
)
from real_worker_runtime.errors import InvalidRoleResult, RoleExecutionError
from real_worker_runtime.models import WorkerState
from real_worker_runtime.provider_bridge import ProviderBridge
from real_worker_runtime.worker_registry import WorkerRegistry


def test_full_role_path_persists_typed_results_and_reaches_done(tmp_path):
    session = RealWorkerRuntime(tmp_path).run("role-owned execution", live=False)
    task = session.runtime_tasks[0]
    pipeline = session.runtime_pipelines[0]
    results = task["role_executions"]
    events = _events(tmp_path, session.session_id)

    assert session.status == "completed"
    assert pipeline["state"] == "done"
    assert [item["role"] for item in results] == [
        "planner", "developer", "qa", "documentation",
    ]
    assert all(item["task_id"] == task["id"] for item in results)
    assert all(item["state"] == "completed" for item in results)
    assert [item["handoff_target"] for item in results] == [
        "development_worker", "qa_worker", "documentation_worker", "runtime",
    ]
    assert [item["event"] for item in events].count("ROLE_EXECUTION_STARTED") == 4
    assert [item["event"] for item in events].count("ROLE_RESULT_RECORDED") == 4
    assert [item["event"] for item in events].count("ROLE_EXECUTION_COMPLETED") == 4
    assert [item["event"] for item in events].count("ROLE_HANDOFF_REQUESTED") == 4


def test_planner_result_is_structured_and_hands_task_to_developer(tmp_path):
    session = RealWorkerRuntime(tmp_path).run("plan role", live=False)
    task = session.runtime_tasks[0]
    planner = task["role_executions"][0]

    assert planner["role"] == "planner"
    assert planner["worker_id"] == "planning_worker"
    assert planner["output"]["tasks"]
    assert planner["output"]["acceptance_criteria"]
    assert planner["handoff_target"] == "development_worker"
    assert task["inputs"]["planner_output"] == planner["output"]
    assert task["handoff_metadata"]["history"][0]["to"] == "development_worker"


def test_runtime_invokes_roles_through_injected_executor_boundary(tmp_path):
    calls = []

    def factory(provider):
        return RecordingExecutor(provider, calls)

    session = RealWorkerRuntime(tmp_path, role_executor_factory=factory).run(
        "injected role boundary", live=False,
    )

    assert session.status == "completed"
    assert [item["role"] for item in calls] == [
        "planner", "developer", "qa", "documentation",
    ]
    assert len({item["task_id"] for item in calls}) == 1
    assert all(item["runtime_request"] == "injected role boundary" for item in calls)


def test_developer_and_qa_results_preserve_outputs_and_evidence_references(tmp_path):
    session = RealWorkerRuntime(tmp_path).run("evidence path", live=False)
    task = session.runtime_tasks[0]
    developer = _role_result(task, "developer")
    qa = _role_result(task, "qa")

    assert developer["output"] == task["outputs"]["development_worker"]
    assert developer["handoff_target"] == "qa_worker"
    assert "worker_context:planner_output" in developer["evidence_references"]
    assert qa["output"] == task["outputs"]["qa_worker"]
    assert qa["handoff_target"] == "documentation_worker"
    assert "runtime_task:development_worker.output" in qa["evidence_references"]


def test_approval_pause_and_resume_append_role_outcomes_on_same_task(tmp_path):
    _prepare_approval_root(tmp_path)
    runtime = RealWorkerRuntime(tmp_path)
    paused = runtime.run(
        "[approval-resume-mvp]", live=False, enable_controlled_execution=True,
    )
    task_id = paused.runtime_tasks[0]["id"]
    waiting = _role_result(paused.runtime_tasks[0], "developer")

    assert paused.status == "waiting_approval"
    assert waiting["state"] == "waiting_approval"
    assert waiting["handoff_target"] == "approval_guardian"

    resumed = runtime.approval_approve(paused.pending_approval["approval_request_id"])
    developer_results = [
        item for item in resumed.runtime_tasks[0]["role_executions"]
        if item["role"] == "developer"
    ]

    assert resumed.status == "completed"
    assert resumed.runtime_tasks[0]["id"] == task_id
    assert [item["state"] for item in developer_results] == [
        "waiting_approval", "completed",
    ]
    assert developer_results[-1]["handoff_target"] == "qa_worker"
    assert "approval_record:consumed" in developer_results[-1]["evidence_references"]


def test_approval_rejection_appends_failure_without_success_evidence(tmp_path):
    _prepare_approval_root(tmp_path)
    runtime = RealWorkerRuntime(tmp_path)
    paused = runtime.run(
        "[approval-resume-mvp]", live=False, enable_controlled_execution=True,
    )
    runtime.approval_reject(paused.pending_approval["approval_request_id"])
    task = runtime.status(paused.session_id)["runtime_tasks"][0]
    developer_results = [
        item for item in task["role_executions"] if item["role"] == "developer"
    ]

    assert [item["state"] for item in developer_results] == [
        "waiting_approval", "failed",
    ]
    assert developer_results[-1]["handoff_target"] == ""
    assert not any(item["state"] == "completed" for item in developer_results)


def test_non_approval_path_never_fabricates_approval_events(tmp_path):
    session = RealWorkerRuntime(tmp_path).run("no approval role path", live=False)
    event_names = [item["event"] for item in _events(tmp_path, session.session_id)]

    assert session.status == "completed"
    assert not any(name.startswith("APPROVAL_") for name in event_names)
    assert "RUNTIME_WAITING_APPROVAL" not in event_names


def test_qa_revision_records_developer_qa_cycle_before_documentation(tmp_path):
    session = RealWorkerRuntime(tmp_path).run(
        "[qa-fail-once]", live=False, max_revisions=1,
    )
    results = session.runtime_tasks[0]["role_executions"]

    assert session.status == "completed"
    assert [item["role"] for item in results] == [
        "planner", "developer", "qa", "developer", "qa", "documentation",
    ]
    assert results[2]["handoff_target"] == "development_worker"
    assert results[4]["handoff_target"] == "documentation_worker"
    assert results[-1]["role"] == "documentation"


def test_revision_limit_remains_authoritative_for_role_execution(tmp_path, monkeypatch):
    original_generate = ProviderBridge.generate

    def always_revise(provider, worker_id, request, context):
        output = original_generate(provider, worker_id, request, context)
        if worker_id == "qa_worker":
            output.update({"claimed_passed": 0, "claimed_failed": 1,
                           "recommendation": "REVISE", "issues": ["retry"]})
        return output

    monkeypatch.setattr(ProviderBridge, "generate", always_revise)
    session = RealWorkerRuntime(tmp_path).run(
        "role revision limit", live=False, max_revisions=1,
    )

    assert session.status == "failed"
    assert session.error == "QA revision limit exceeded: 1/1 revisions used"
    assert not any(
        item["role"] == "documentation"
        for item in session.runtime_tasks[0]["role_executions"]
    )


def test_documentation_runs_after_qa_and_consumes_existing_evidence(tmp_path):
    session = RealWorkerRuntime(tmp_path).run("documentation evidence", live=False)
    task = session.runtime_tasks[0]
    documentation = _role_result(task, "documentation")
    roles = [item["role"] for item in task["role_executions"]]

    assert roles.index("documentation") > roles.index("qa")
    assert documentation["output"]["user_summary"]
    assert documentation["evidence_references"] == [
        "worker_context:documentation_worker",
        "worker_context:planner_output",
        "runtime_task:development_worker.output",
        "runtime_task:qa_worker.output",
        "worker_context:runtime_evidence",
    ]
    assert task["history"][-1]["reason"] == "documentation role completed after QA pass"


def test_documentation_rejects_missing_or_fabricated_evidence(tmp_path, monkeypatch):
    provider = ProviderBridge(tmp_path)
    provider.select("mock")
    executor = RoleExecutor(provider)
    definition = _definition("documentation_worker")
    request = RoleExecutionRequest(
        "TASK-doc", RuntimeRole.DOCUMENTATION, "documentation_worker",
        "document", 0, "qa", "documenting",
    )
    with pytest.raises(RoleExecutionError, match="requires Planner, Developer, and QA"):
        executor.execute(request, WorkerContext(request="document"), definition)

    original_generate = ProviderBridge.generate

    def fabricate(provider, worker_id, runtime_request, context):
        output = original_generate(provider, worker_id, runtime_request, context)
        if worker_id == "documentation_worker":
            output["verified_changed_files"] = ["fabricated.py"]
        return output

    monkeypatch.setattr(ProviderBridge, "generate", fabricate)
    session = RealWorkerRuntime(tmp_path / "fabricated").run(
        "documentation fabrication", live=False,
    )
    assert session.status == "failed"
    assert "cannot fabricate verified_changed_files" in session.error


@pytest.mark.parametrize("role", list(RuntimeRole))
def test_each_role_failure_fails_task_without_false_completion(tmp_path, role):
    def factory(provider):
        return FailingRoleExecutor(provider, role)

    session = RealWorkerRuntime(
        tmp_path / role.value, role_executor_factory=factory,
    ).run(f"fail {role.value}", live=False)
    task = session.runtime_tasks[0]
    events = _events(tmp_path / role.value, session.session_id)

    assert session.status == "failed"
    assert session.error == f"scripted {role.value} failure"
    assert task["state"] == "failed"
    failed = [item for item in task["role_executions"] if item["role"] == role.value][-1]
    assert failed["state"] == "failed"
    assert failed["handoff_target"] == ""
    assert any(
        item["event"] == "ROLE_EXECUTION_FAILED"
        and item["payload"]["role"] == role.value for item in events
    )
    assert not any(
        item["event"] == "ROLE_HANDOFF_REQUESTED"
        and item["payload"]["role"] == role.value for item in events
    )


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda result: setattr(result, "task_id", "TASK-other"), "task identity"),
        (lambda result: setattr(result, "role", RuntimeRole.QA), "role identity"),
        (lambda result: setattr(result, "handoff_target", "documentation_worker"),
         "invalid developer handoff"),
        (lambda result: setattr(result, "output", "opaque"), "output must be structured"),
    ],
)
def test_invalid_role_results_are_rejected(mutation, message):
    context = _developer_context()
    orchestrator = RuntimeOrchestrator(context)
    request = orchestrator.build_role_request("development_worker")
    result = _completed_result(request, {
        "implementation_summary": "candidate", "proposed_file_writes": [],
    })
    mutation(result)

    with pytest.raises(InvalidRoleResult, match=message):
        orchestrator.record_role_result(result, request)

    assert context.runtime_task.role_executions == []


def test_role_execution_after_terminal_task_state_is_rejected():
    context = _developer_context()
    task = context.runtime_task
    task.transition(WorkerState.RUNNING, "developer")
    task.transition(WorkerState.QA, "qa")
    task.transition(WorkerState.COMPLETED, "done")
    orchestrator = RuntimeOrchestrator(context)

    with pytest.raises(RoleExecutionError, match="terminal"):
        orchestrator.build_role_request("development_worker")


class RecordingExecutor:
    def __init__(self, provider, calls):
        self.base = RoleExecutor(provider)
        self.calls = calls

    def execute(self, request, context, definition):
        self.calls.append(request.to_dict())
        return self.base.execute(request, context, definition)


class FailingRoleExecutor:
    def __init__(self, provider, failed_role):
        self.base = RoleExecutor(provider)
        self.failed_role = failed_role

    def execute(self, request, context, definition):
        if request.role is self.failed_role:
            return RoleExecutionResult(
                task_id=request.task_id, role=request.role,
                worker_id=request.worker_id, state=RoleExecutionState.FAILED,
                output={}, evidence_references=[], handoff_target="",
                started_at="2026-07-14T00:00:00+00:00",
                completed_at="2026-07-14T00:00:01+00:00",
                summary="scripted role failure",
                error=f"scripted {request.role.value} failure",
            )
        return self.base.execute(request, context, definition)


def _completed_result(request, output):
    return RoleExecutionResult(
        task_id=request.task_id, role=request.role, worker_id=request.worker_id,
        state=RoleExecutionState.COMPLETED, output=output,
        evidence_references=[], handoff_target="qa_worker",
        started_at="2026-07-14T00:00:00+00:00",
        completed_at="2026-07-14T00:00:01+00:00", summary="completed",
    )


def _developer_context():
    task = RuntimeTask.create("development_worker")
    task.transition(WorkerState.READY, "planned")
    pipeline = RuntimePipeline(task.id)
    pipeline.transition(PipelineState.ASSIGNED, "development_worker", "assigned")
    pipeline.transition(PipelineState.DEVELOPING, "development_worker", "started")
    return WorkerContext(
        request="develop", planner_output={"tasks": ["implement"]},
        runtime_task=task, runtime_pipeline=pipeline,
    )


def _definition(worker_id):
    return next(item for item in WorkerRegistry().list() if item.worker_id == worker_id)


def _role_result(task, role):
    return next(item for item in task["role_executions"] if item["role"] == role)


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
