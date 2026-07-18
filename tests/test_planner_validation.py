import pytest

from afde.planner import (
    ExecutionPlan, ExecutionPlanValidator, ExecutionTask, PlanValidationError,
)


def _plan(tasks):
    return ExecutionPlan(
        "PLAN-ABCDEF0123456789", "Validate plan",
        "2026-07-18T00:00:00+09:00", "pending", tasks,
    )


def _task(task_id, dependencies=()):
    return ExecutionTask(
        task_id, task_id, "validation task", "high", "pending",
        list(dependencies),
    )


def test_validator_rejects_duplicate_task_id():
    plan = _plan([_task("TASK-1"), _task("TASK-1")])

    with pytest.raises(PlanValidationError, match="duplicate task id"):
        ExecutionPlanValidator().validate(plan)


def test_validator_rejects_missing_dependency():
    plan = _plan([_task("TASK-1", ["TASK-missing"])])

    with pytest.raises(PlanValidationError, match="missing dependency"):
        ExecutionPlanValidator().validate(plan)


def test_validator_rejects_cyclic_dependency():
    plan = _plan([
        _task("TASK-1", ["TASK-2"]),
        _task("TASK-2", ["TASK-1"]),
    ])

    with pytest.raises(PlanValidationError, match="cyclic dependency"):
        ExecutionPlanValidator().validate(plan)


def test_validator_accepts_acyclic_dependency_chain():
    plan = _plan([
        _task("TASK-1"),
        _task("TASK-2", ["TASK-1"]),
        _task("TASK-3", ["TASK-2"]),
    ])

    assert ExecutionPlanValidator().validate(plan) is plan
