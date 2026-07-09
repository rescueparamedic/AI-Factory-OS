from pathlib import Path
from scheduler_engine.task_scheduler import TaskScheduler
from os_core.worker_manager import WorkerManager


def test_scheduler_enqueue_and_status(tmp_path):
    wm = WorkerManager(tmp_path)
    scheduler = TaskScheduler(tmp_path, wm)
    job = scheduler.enqueue(
        title="v2.7 test markdown",
        worker_id="markdown_worker",
        payload={"filename": "docs/test_v27.md", "title": "v2.7", "body": ["ok"]},
        priority="high",
    )
    assert job["status"] == "queued"
    status = scheduler.status()
    assert status["total_jobs"] == 1
    assert status["next_job"]["job_id"] == job["job_id"]


def test_scheduler_run_next_completes(tmp_path):
    wm = WorkerManager(tmp_path)
    scheduler = TaskScheduler(tmp_path, wm)
    scheduler.enqueue(
        title="v2.7 run next",
        worker_id="markdown_worker",
        payload={"filename": "docs/test_run_next.md", "title": "Run", "body": ["done"]},
        priority="critical",
    )
    result = scheduler.run_next()
    assert result["status"] == "completed"
    assert Path(tmp_path / "docs" / "test_run_next.md").exists()
