# -*- coding: utf-8 -*-
from pathlib import Path

from afde.environment_checker import EnvironmentChecker
from afde.real_ai_worker_bootstrap import RealAIWorkerBootstrap


def test_environment_checker_runs():
    report = EnvironmentChecker(project_root=Path.cwd()).run_all()
    assert "status" in report
    assert "results" in report
    assert any(item["name"] == "python" for item in report["results"])


def test_environment_checker_saves_report(tmp_path):
    output = tmp_path / "env.json"
    path = EnvironmentChecker(project_root=Path.cwd()).save_report(output)
    assert path.exists()


def test_real_ai_worker_bootstrap_runs(tmp_path):
    output = tmp_path / "bootstrap.json"
    result = RealAIWorkerBootstrap(project_root=Path.cwd()).run(output)
    assert result["status"] == "READY"
    assert output.exists()
