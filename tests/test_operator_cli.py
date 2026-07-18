from __future__ import annotations

import json

from afde.cli import main
from afde.operator.service import OperatorService

from test_operator_service import prepare_workspace


CONTRACT = {
    "status", "session_id", "request", "provider", "approval_id",
    "summary", "next_action", "evidence", "dashboard_hint", "history_hint",
}


def test_operator_preflight_cli_json_contract(tmp_path, capsys):
    prepare_workspace(tmp_path)

    code = main([
        "operator-preflight", "--workspace", str(tmp_path), "--json",
    ])
    value = json.loads(capsys.readouterr().out)

    assert code == 0
    assert value["blocking"] is False
    assert value["provider"] == "mock"


def test_operator_cli_complete_flow_and_json_result(tmp_path, capsys):
    prepare_workspace(tmp_path)
    code = main([
        "operator-run", "--request", "CLI operator proof",
        "--workspace", str(tmp_path), "--json",
    ])
    waiting = json.loads(capsys.readouterr().out)
    assert code == 0
    assert set(waiting) == CONTRACT
    assert waiting["status"] == "waiting_approval"

    code = main([
        "operator-status", "--session-id", waiting["session_id"],
        "--workspace", str(tmp_path), "--json",
    ])
    assert code == 0
    assert json.loads(capsys.readouterr().out)["next_action"] == waiting["next_action"]

    code = main([
        "operator-approve", "--session-id", waiting["session_id"],
        "--approval-id", waiting["approval_id"],
        "--workspace", str(tmp_path), "--json",
    ])
    approved = json.loads(capsys.readouterr().out)
    assert code == 0
    assert "operator-resume" in approved["next_action"]

    code = main([
        "operator-resume", "--session-id", waiting["session_id"],
        "--workspace", str(tmp_path), "--json",
    ])
    completed = json.loads(capsys.readouterr().out)
    assert code == 0
    assert completed["status"] == "completed"
    assert completed["evidence"]


def test_operator_cli_not_found_and_reject_exit_codes(tmp_path, capsys):
    prepare_workspace(tmp_path)
    code = main([
        "operator-status", "--session-id", "RWS-unknown",
        "--workspace", str(tmp_path), "--json",
    ])
    assert code == 4
    assert json.loads(capsys.readouterr().out)["status"] == "failed"

    waiting = OperatorService(tmp_path).run("CLI reject proof")
    code = main([
        "operator-reject", "--session-id", waiting.session_id,
        "--approval-id", waiting.approval_id, "--reason", "declined",
        "--workspace", str(tmp_path), "--json",
    ])
    assert code == 0
    assert json.loads(capsys.readouterr().out)["status"] == "blocked"


def test_operator_preflight_blocked_exit_code(tmp_path, capsys):
    code = main([
        "operator-preflight", "--workspace", str(tmp_path / "missing"),
        "--json",
    ])
    assert code == 3
    assert json.loads(capsys.readouterr().out)["blocking"] is True
