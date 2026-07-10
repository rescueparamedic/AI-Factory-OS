from __future__ import annotations

import json

import pytest

from afde.cli import main
from afde.task_runner import AFDETaskRunner, TaskRunner


def _run_cli(capsys, *args: str):
    assert main(list(args)) is None
    return json.loads(capsys.readouterr().out)


def test_task_runner_preserves_legacy_interface(tmp_path):
    runner = AFDETaskRunner(tmp_path)
    result = runner.run_mock_pipeline("Legacy caller", "Keep dataclass API")

    assert result.status == "success"


def test_task_runner_exposes_json_serializable_run_mock(tmp_path):
    result = TaskRunner(tmp_path).run_mock("CLI caller", "Return a mapping")

    assert result["status"] == "success"
    assert json.loads(json.dumps(result))["task_id"] == result["task_id"]


@pytest.mark.parametrize("command", [("providers",), ("env-check",)])
def test_read_only_cli_commands_emit_json(capsys, command):
    result = _run_cli(capsys, *command)

    assert result


def test_bootstrap_worker_cli_emits_json(capsys, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = _run_cli(capsys, "bootstrap-worker")

    assert result["status"] == "READY"


def test_run_mock_cli_emits_success_json(capsys, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = _run_cli(
        capsys,
        "run-mock",
        "--title",
        "AFDE-2.2 validation",
        "--request",
        "CLI runtime regression test",
    )

    assert result["status"] == "success"
    assert result["artifact_path"]
