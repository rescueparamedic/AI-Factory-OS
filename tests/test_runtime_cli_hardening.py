from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

from afde.cli import main
from afde.execution.bridge import ProviderRuntimeBridge
from real_worker_runtime import RealWorkerRuntime


def _json_output(capsys):
    return json.loads(capsys.readouterr().out)


def test_runtime_status_success_has_zero_exit_code(tmp_path, capsys):
    session = RealWorkerRuntime(tmp_path).run("Beta CLI success", live=False)

    code = main([
        "runtime-status", "--session-id", session.session_id,
        "--workspace", str(tmp_path),
    ])

    # ``python -m afde.cli`` maps the legacy None success return to process code 0.
    assert code is None
    assert _json_output(capsys)["session_id"] == session.session_id
    process = subprocess.run(
        [sys.executable, "-m", "afde.cli", "runtime-status", "--session-id",
         session.session_id, "--workspace", str(tmp_path)],
        cwd=Path(__file__).parents[1], capture_output=True, text=True,
        check=False,
    )
    assert process.returncode == 0
    assert json.loads(process.stdout)["session_id"] == session.session_id


def test_missing_runtime_session_has_actionable_error_and_not_found_code(
    tmp_path, capsys,
):
    code = main([
        "runtime-history", "--session-id", "RWS-missing",
        "--workspace", str(tmp_path), "--json",
    ])
    value = _json_output(capsys)

    assert code == 4
    assert value["status"] == "failed"
    assert "No session exists" in value["cause"]
    assert "runtime-history" in value["next_action"]
    assert value["evidence"].endswith("RWS-missing")


def test_invalid_runtime_request_has_input_exit_code_and_next_action(
    tmp_path, capsys,
):
    code = main([
        "runtime-history", "--session-id", "../escape",
        "--workspace", str(tmp_path), "--json",
    ])
    value = _json_output(capsys)

    assert code == 2
    assert "invalid session ID" in value["cause"]
    assert "--help" in value["next_action"]


def test_terminal_runtime_cancel_is_expected_request_error(tmp_path, capsys):
    session = RealWorkerRuntime(tmp_path).run("Beta CLI terminal", live=False)

    code = main([
        "runtime-cancel", "--session-id", session.session_id,
        "--workspace", str(tmp_path),
    ])
    value = _json_output(capsys)

    assert code == 2
    assert "cannot cancel terminal session" in value["cause"]
    assert value["next_action"]


def test_corrupt_runtime_status_has_runtime_failure_code(tmp_path, capsys):
    session_id = "RWS-corrupt"
    directory = tmp_path / "data" / "runtime_sessions" / session_id
    directory.mkdir(parents=True)
    (directory / "session.json").write_text("{broken", encoding="utf-8")

    code = main([
        "runtime-status", "--session-id", session_id,
        "--workspace", str(tmp_path),
    ])
    value = _json_output(capsys)

    assert code == 5
    assert "valid JSON" in value["cause"]
    assert value["next_action"]


def test_beta_runtime_failure_includes_cause_and_next_action(
    tmp_path, capsys, monkeypatch,
):
    def fail_bridge(*args, **kwargs):
        raise RuntimeError("bounded bridge failure")

    monkeypatch.setattr(ProviderRuntimeBridge, "convert", fail_bridge)
    code = main([
        "execute", "--request", "Beta failure guidance",
        "--workspace", str(tmp_path), "--json",
    ])
    value = _json_output(capsys)

    assert code == 5
    assert "bridge" in value["cause"]
    assert "runtime-history" in value["next_action"]
    assert value["evidence_path"]


def test_human_runtime_error_has_required_field_labels(tmp_path, capsys):
    code = main([
        "runtime-report", "--session-id", "RWS-missing",
        "--workspace", str(tmp_path),
    ])
    output = capsys.readouterr().out

    assert code == 4
    for label in ("Status:", "Session ID:", "Error:", "Cause:",
                  "Next action:", "Evidence:"):
        assert label in output


def test_missing_approval_uses_not_found_code_and_real_recovery_command(
    tmp_path, capsys, monkeypatch,
):
    monkeypatch.chdir(tmp_path)
    code = main(["approval-show", "--id", "APR-missing"])
    value = _json_output(capsys)

    assert code == 4
    assert value["approval_id"] == "APR-missing"
    assert "No approval exists" in value["cause"]
    assert "approval-show --id APR-missing" in value["next_action"]
