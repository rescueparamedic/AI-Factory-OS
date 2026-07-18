from afde.planner import ExecutionPlan, ExecutionTask


def test_execution_plan_models_round_trip():
    task = ExecutionTask(
        "TASK-ABCDEF0123456789-01", "Prepare", "Prepare inputs",
        "high", "pending", [],
    )
    plan = ExecutionPlan(
        "PLAN-ABCDEF0123456789", "Ship beta", "2026-07-18T00:00:00+09:00",
        "pending", [task],
    )

    restored = ExecutionPlan.from_dict(plan.to_dict())

    assert restored == plan
    assert "estimated_complexity" not in restored.tasks[0].to_dict()
