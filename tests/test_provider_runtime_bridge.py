from afde.execution import ProviderRuntimeBridge
from afde.planner import ExecutionPlan, ExecutionTask
from afde.providers import ProviderResponse


def test_provider_runtime_bridge_preserves_provider_execution_identity():
    task = ExecutionTask(
        "TASK-ABC-01", "Execute", "Execute the bounded goal", "high",
    )
    plan = ExecutionPlan(
        "PLAN-ABC", "Ship beta", "2026-07-18T00:00:00+09:00",
        tasks=[task],
    )
    response = ProviderResponse(
        provider="openai", model="test-model", content="worker instruction",
        metadata={"execution_mode": "live", "request_id": "resp-test"},
    )

    value = ProviderRuntimeBridge.convert(
        response, plan=plan, task=task, worker_id="development_worker",
    )

    assert value.plan_id == plan.plan_id
    assert value.task_id == task.task_id
    assert value.worker_id == "development_worker"
    assert value.instruction == "worker instruction"
    assert value.provider == "openai"
    assert value.model == "test-model"
    assert value.execution_mode == "live"
    assert value.metadata["provider_metadata"]["request_id"] == "resp-test"
