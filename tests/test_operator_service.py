from __future__ import annotations

import subprocess

import pytest

from afde.operator import (
    OperatorInputError, OperatorNotFound, OperatorPreflightBlocked,
    OperatorService,
)


def prepare_workspace(path):
    subprocess.run(
        ["git", "init", "-q"], cwd=path, check=True,
        capture_output=True, text=True,
    )
    fixture = path / "tests" / "fixtures" / "afde_2_7_approval_target.txt"
    fixture.parent.mkdir(parents=True)
    fixture.write_text("approval_state=baseline\n", encoding="utf-8")
    test_file = path / "tests" / "test_afde_2_7_fixture.py"
    test_file.write_text(
        "from pathlib import Path\n"
        "def test_state():\n"
        " p=Path(__file__).parent/'fixtures'/'afde_2_7_approval_target.txt'\n"
        " assert p.read_text() == 'approval_state=approved\\n'\n",
        encoding="utf-8",
    )
    return fixture


def test_mock_waiting_approve_and_resume(tmp_path):
    fixture = prepare_workspace(tmp_path)
    service = OperatorService(tmp_path)

    waiting = service.run("Create the deterministic operator proof")
    assert waiting.status == "waiting_approval"
    assert waiting.approval_id
    assert (
        f"--session-id {waiting.session_id} --approval-id {waiting.approval_id}"
        in waiting.next_action
    )
    assert fixture.read_text(encoding="utf-8") == "approval_state=baseline\n"

    approved = service.approve(waiting.session_id, waiting.approval_id)
    assert approved.status == "waiting_approval"
    assert approved.next_action.startswith(
        f"python -m afde.cli operator-resume --session-id {waiting.session_id}"
    )

    completed = service.resume(waiting.session_id)
    assert completed.status == "completed"
    assert completed.evidence
    assert f"--session-id {waiting.session_id}" in completed.history_hint
    assert fixture.read_text(encoding="utf-8") == "approval_state=approved\n"


def test_reject_path_is_blocked_and_records_safe_reason(tmp_path):
    prepare_workspace(tmp_path)
    service = OperatorService(tmp_path)
    waiting = service.run("Reject this deterministic proof")

    rejected = service.reject(
        waiting.session_id, waiting.approval_id, "Operator declined replacement",
    )

    assert rejected.status == "blocked"
    assert rejected.next_action.startswith(
        f"python -m afde.cli operator-status --session-id {waiting.session_id}"
    )


def test_request_validation_provider_and_not_found_errors(tmp_path):
    prepare_workspace(tmp_path)
    service = OperatorService(tmp_path)
    with pytest.raises(OperatorInputError):
        service.run("   ")
    with pytest.raises(OperatorPreflightBlocked):
        service.run("request", provider="unknown")
    with pytest.raises(OperatorNotFound):
        service.status("RWS-does-not-exist")


def test_unknown_approval_and_terminal_resume_are_rejected(tmp_path):
    prepare_workspace(tmp_path)
    service = OperatorService(tmp_path)
    waiting = service.run("Validate exact approval binding")
    with pytest.raises(OperatorNotFound):
        service.approve(waiting.session_id, "APR-UNKNOWN")
    service.approve(waiting.session_id, waiting.approval_id)
    completed = service.resume(waiting.session_id)
    with pytest.raises(OperatorInputError, match="terminal"):
        service.resume(completed.session_id)


def test_secret_is_redacted_before_runtime_persistence(tmp_path):
    prepare_workspace(tmp_path)
    service = OperatorService(tmp_path)
    secret = "never-store-this-secret"

    result = service.run(f"Create proof token={secret}")
    session = service.runtime.status(result.session_id)

    assert secret not in result.request
    assert secret not in session["request"]
    assert "[REDACTED]" in result.request
