from dataclasses import replace
from types import SimpleNamespace

import pytest

from afde.planner import RuleBasedExecutionPlanner
from afde.production_adapter_runtime_execution import (
    ProductionAdapterRuntimeExecutionService,
)
from afde.production_adapter_worker_execution import (
    InvalidProductionAdapterWorkerExecutionResultError,
    ProductionAdapterWorkerResultProjector,
)
from afde.production_orchestration import (
    ProductionOrchestrationStatus,
    ProductionPlannerRuntimeOrchestrator,
)
from afde.production_planner_worker_dispatch import (
    InvalidProductionPlannerWorkerDispatchRequestError,
    ProductionPlannerWorkerDispatchRequest,
    ProductionPlannerWorkerDispatcher,
)
from real_worker_runtime.models import ExecutionInput, WorkerExecutionResult
from real_worker_runtime.tool_actions import ToolActionType
from test_production_orchestration import (
    BindingAuthorityProvider,
    _action,
    _request,
    _startup,
)


class RecordingPlanner(RuleBasedExecutionPlanner):
    def __init__(self):
        self.plans = []

    def create_plan(self, goal):
        plan = super().create_plan(goal)
        self.plans.append(plan)
        return plan


class RecordingRuntimeExecutionService(
    ProductionAdapterRuntimeExecutionService
):
    def __init__(self):
        self.requests = []

    def execute(self, request):
        self.requests.append(request)
        return super().execute(request)


def _dispatch_request(**changes):
    request = ProductionPlannerWorkerDispatchRequest(
        orchestration_request=_request(),
        task_id="TASK-AFDE-6.20-001",
        worker_id="development_worker",
        instruction="Project the governed Production Runtime result",
        provider="codex_automation_bridge",
        model="controlled-runtime",
        execution_mode="production_adapter_runtime",
    )
    return replace(request, **changes)


def test_full_production_dispatch_executes_runtime_and_adapter_exactly_once(
    tmp_path,
):
    adapter_calls = []

    def runner(argv, **kwargs):
        adapter_calls.append((argv, kwargs))
        return SimpleNamespace(returncode=0, stdout="Python test", stderr="")

    startup, target = _startup(tmp_path, runner=runner)
    planner = RecordingPlanner()
    runtime_execution = RecordingRuntimeExecutionService()
    authority = BindingAuthorityProvider()
    dispatcher = ProductionPlannerWorkerDispatcher(
        orchestrator=ProductionPlannerRuntimeOrchestrator(
            startup_composition=startup,
            authority_provider=authority,
            planner=planner,
            runtime_execution=runtime_execution,
        )
    )
    request = _dispatch_request()

    result = dispatcher.dispatch(request)

    assert result.status is ProductionOrchestrationStatus.COMPLETED
    assert len(runtime_execution.requests) == 1
    assert len(adapter_calls) == 1
    assert len(authority.bindings) == 1
    assert target.last_execution_result.status == "SUCCEEDED"
    assert len(planner.plans) == 1
    projected = result.worker_execution_result
    assert projected is not None
    assert type(projected.worker_result) is WorkerExecutionResult
    assert projected.worker_result.plan_id == planner.plans[0].plan_id
    assert projected.worker_result.task_id == request.task_id
    assert projected.worker_id == request.worker_id
    assert projected.worker_result.worker_id == request.worker_id
    assert projected.worker_result.execution_status == "completed"
    assert projected.worker_result.error == ""
    runtime = result.orchestration_result.runtime_execution_result
    assert runtime is projected.runtime_execution_result
    assert runtime is not None
    for identity in (
        "adapter_id", "projection_id", "path_id", "capability_id", "binding_id",
    ):
        assert projected.worker_result.output[identity] == getattr(runtime, identity)
    assert not hasattr(projected, "authority")


def test_actual_denied_action_blocks_worker_projection(tmp_path, monkeypatch):
    action = _action(
        tmp_path,
        action_type=ToolActionType.FILE_WRITE,
        purpose="Prove dispatch preserves controlled path denial",
        target="../outside.py",
        arguments={"content": "print('blocked')"},
    )
    startup, target = _startup(tmp_path, action=action)
    runtime_execution = RecordingRuntimeExecutionService()
    projector = ProductionAdapterWorkerResultProjector()
    projection_calls = []

    def forbidden_projection(*args):
        projection_calls.append(args)
        raise AssertionError("Worker projection must not run")

    monkeypatch.setattr(projector, "project", forbidden_projection)
    dispatcher = ProductionPlannerWorkerDispatcher(
        orchestrator=ProductionPlannerRuntimeOrchestrator(
            startup_composition=startup,
            authority_provider=BindingAuthorityProvider(),
            runtime_execution=runtime_execution,
        ),
        projector=projector,
    )

    result = dispatcher.dispatch(_dispatch_request())

    assert result.status is ProductionOrchestrationStatus.REJECTED
    assert result.worker_execution_result is None
    assert result.orchestration_result.runtime_execution_result is None
    assert len(runtime_execution.requests) == 1
    assert projection_calls == []
    assert target.last_execution_result.status == "DENIED"


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"task_id": ""}, "task_id"),
        ({"worker_id": "BAD-ID"}, "worker_id"),
        ({"instruction": ""}, "instruction"),
    ],
)
def test_invalid_worker_input_fails_before_runtime(changes, message):
    with pytest.raises(
        InvalidProductionPlannerWorkerDispatchRequestError,
        match=message,
    ):
        _dispatch_request(**changes)


def test_projector_rejects_worker_identity_without_runtime_execution(tmp_path):
    startup, _ = _startup(tmp_path)
    runtime_execution = RecordingRuntimeExecutionService()
    orchestration = ProductionPlannerRuntimeOrchestrator(
        startup_composition=startup,
        authority_provider=BindingAuthorityProvider(),
        runtime_execution=runtime_execution,
    ).orchestrate(_request())
    assert orchestration.runtime_execution_result is not None
    runtime_call_count = len(runtime_execution.requests)

    with pytest.raises(
        InvalidProductionAdapterWorkerExecutionResultError,
        match="worker identity",
    ):
        ProductionAdapterWorkerResultProjector().project(
            ExecutionInput(
                plan_id=orchestration.plan_id,
                task_id="TASK-AFDE-6.20-IDENTITY",
                worker_id="BAD-ID",
                instruction="Reject invalid identity",
                provider="codex_automation_bridge",
                model="controlled-runtime",
                execution_mode="production_adapter_runtime",
            ),
            orchestration.runtime_execution_result,
        )

    assert len(runtime_execution.requests) == runtime_call_count == 1
