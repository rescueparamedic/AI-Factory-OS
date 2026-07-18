from dataclasses import FrozenInstanceError

import pytest

from real_worker_runtime import ExecutionInput, WorkerExecutionResult


def test_execution_models_are_immutable_structured_and_serializable():
    value = ExecutionInput(
        plan_id="PLAN-ABC", task_id="TASK-1", worker_id="development_worker",
        instruction="perform bounded task", provider="mock", model="mock-v1",
        execution_mode="deterministic_mock", metadata={"nested": {"value": 1}},
    )
    result = WorkerExecutionResult(
        plan_id=value.plan_id, task_id=value.task_id, worker_id=value.worker_id,
        execution_status="completed", provider=value.provider, model=value.model,
        execution_mode=value.execution_mode, output={"items": ["done"]},
    )

    with pytest.raises(FrozenInstanceError):
        value.instruction = "changed"
    with pytest.raises(TypeError):
        value.metadata["nested"]["value"] = 2
    with pytest.raises(TypeError):
        result.output["items"] = []

    assert value.content == "perform bounded task"
    assert result.to_dict()["output"] == {"items": ["done"]}
    assert result.to_evidence() == {
        "provider": "mock", "model": "mock-v1",
        "execution_mode": "deterministic_mock", "plan_id": "PLAN-ABC",
        "worker_id": "development_worker", "execution_status": "completed",
    }
