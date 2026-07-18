import json

from afde.planner import PlannerService, RuleBasedExecutionPlanner
from real_worker_runtime.dashboard import RuntimeDashboard
from real_worker_runtime.runtime_pipeline import PipelineState, RuntimePipeline


def test_rule_based_planner_is_deterministic_and_minimal():
    planner = RuleBasedExecutionPlanner()

    first = planner.create_plan("  Ship   AFDE-4.0 Beta  ")
    second = planner.create_plan("Ship AFDE-4.0 Beta")

    assert first.plan_id == second.plan_id
    assert first.goal == "Ship AFDE-4.0 Beta"
    assert [task.title for task in first.tasks] == [
        "Prepare execution", "Execute goal", "Verify result",
    ]
    assert first.tasks[0].depends_on == []
    assert first.tasks[1].depends_on == [first.tasks[0].task_id]
    assert first.tasks[2].depends_on == [first.tasks[1].task_id]
    assert all(task.status == "pending" for task in first.tasks)


def test_planner_service_persists_shows_and_exports_json(tmp_path):
    service = PlannerService(tmp_path)

    created = service.create_plan("Deliver planner MVP")
    shown = service.show_plan(created.plan_id)
    exported = json.loads(service.export_json(shown))

    assert shown == created
    assert exported == created.to_dict()
    assert service.latest_plan() == created
    assert service.summary(created) == {
        "available": True,
        "plan_id": created.plan_id,
        "goal": "Deliver planner MVP",
        "total_tasks": 3,
        "completed": 0,
        "pending": 3,
    }


def test_runtime_dashboard_displays_latest_execution_plan_summary(tmp_path):
    plan = PlannerService(tmp_path).create_plan("Display planner summary")
    directory = tmp_path / "data" / "runtime_sessions" / "RWS-plan"
    directory.mkdir(parents=True)
    pipeline = RuntimePipeline("TASK-runtime", state=PipelineState.DEVELOPING)
    (directory / "session.json").write_text(json.dumps({
        "status": "running", "progress": 25,
        "runtime_pipelines": [pipeline.to_dict()], "artifacts": [],
        "pending_approval": None,
    }), encoding="utf-8")

    dashboard = RuntimeDashboard(tmp_path)
    snapshot = dashboard.snapshot("RWS-plan")
    rendered = dashboard.render("RWS-plan")

    assert snapshot["execution_plan_summary"] == {
        "available": True, "plan_id": plan.plan_id,
        "goal": "Display planner summary", "total_tasks": 3,
        "completed": 0, "pending": 3,
    }
    assert "Execution Plan Summary" in rendered
    assert plan.plan_id in rendered


def test_dashboard_web_asset_contains_read_only_plan_summary():
    html = (
        __import__("pathlib").Path("real_worker_runtime/web_assets/index.html")
        .read_text(encoding="utf-8")
    )
    script = (
        __import__("pathlib").Path("real_worker_runtime/web_assets/dashboard.js")
        .read_text(encoding="utf-8")
    )

    assert "Execution Plan Summary" in html
    assert "execution-plan-summary" in html
    assert "renderExecutionPlan" in script
    assert "execution_plan_summary" in script
