import json
from hashlib import sha256
from pathlib import Path

import pytest

from afde.cli import main
from real_worker_runtime import RealWorkerRuntime
from real_worker_runtime.approval_resume import RuntimeApprovalStore, request_from_record
from real_worker_runtime.errors import RuntimeSessionError
from real_worker_runtime.controlled_execution import ControlledExecutor, ExecutionRequest


BASELINE = "approval_state=baseline\n"
APPROVED = "approval_state=approved\n"


def prepare_root(tmp_path: Path) -> Path:
    fixture = tmp_path / "tests" / "fixtures" / "afde_2_7_approval_target.txt"
    fixture.parent.mkdir(parents=True)
    fixture.write_text(BASELINE, encoding="utf-8")
    test_file = tmp_path / "tests" / "test_afde_2_7_fixture.py"
    test_file.write_text(
        "from pathlib import Path\n"
        "def test_state():\n"
        " p=Path(__file__).parent/'fixtures'/'afde_2_7_approval_target.txt'\n"
        " assert p.read_text() in {'approval_state=baseline\\n','approval_state=approved\\n'}\n",
        encoding="utf-8",
    )
    return fixture


def pause_runtime(tmp_path: Path):
    fixture = prepare_root(tmp_path)
    session = RealWorkerRuntime(tmp_path).run(
        "[approval-resume-mvp]", live=False, enable_controlled_execution=True
    )
    approval_id = session.pending_approval["approval_request_id"]
    return fixture, session, approval_id


def test_ask_user_persists_waiting_state_and_preserves_target(tmp_path):
    fixture, session, approval_id = pause_runtime(tmp_path)
    assert session.status == "waiting_approval"
    assert session.workers["development_worker"] == "waiting_approval"
    assert fixture.read_text(encoding="utf-8") == BASELINE
    record = RuntimeApprovalStore(tmp_path).load(approval_id)
    assert record["status"] == "PENDING"
    assert record["execution_request_id"].startswith("EXE-")
    assert record["target"] == "tests/fixtures/afde_2_7_approval_target.txt"
    assert record["guardian_policy_classification"] == "EXISTING_FILE_REPLACEMENT"
    assert record["guardian_rule_id"] == "AGV2-A999"
    assert record["action_fingerprint"]
    assert (tmp_path / "data" / "runtime_sessions" / session.session_id / "continuation.json").is_file()


def test_pending_state_survives_new_runtime_and_show(tmp_path):
    _, _, approval_id = pause_runtime(tmp_path)
    shown = RealWorkerRuntime(tmp_path).approval_show(approval_id)
    assert shown == RuntimeApprovalStore(tmp_path).load(approval_id)


def test_valid_approval_modifies_exact_file_consumes_once_and_resumes(tmp_path):
    fixture, paused, approval_id = pause_runtime(tmp_path)
    resumed = RealWorkerRuntime(tmp_path).approval_approve(approval_id)
    assert fixture.read_text(encoding="utf-8") == APPROVED
    assert resumed.status == "completed"
    assert resumed.workers["development_worker"] == "completed"
    assert resumed.execution_verification["status"] == "VERIFIED"
    assert resumed.execution_verification["verified_changed_files"] == [
        "tests/fixtures/afde_2_7_approval_target.txt"
    ]
    executions = resumed.execution_verification["verified_test_executions"]
    assert len(executions) == 1 and executions[0]["exit_code"] == 0
    assert executions[0]["argv"] == [
        "python", "-m", "pytest", "tests/test_afde_2_7_fixture.py", "-q",
    ]
    write = next(item for item in resumed.execution_verification["evidence"]
                 if item.get("action_type") == "FILE_WRITE" and item.get("status") == "SUCCEEDED")
    expected_bytes = APPROVED.encode("utf-8")
    assert fixture.read_bytes() == expected_bytes
    assert write["approved_payload_sha256"] == sha256(expected_bytes).hexdigest()
    assert write["after_sha256"] == sha256(expected_bytes).hexdigest()
    record = RuntimeApprovalStore(tmp_path).load(approval_id)
    assert record["status"] == "CONSUMED"
    assert record["approved_at"] and record["consumed_at"]
    events = (tmp_path / "data" / "runtime_sessions" / paused.session_id / "events.jsonl").read_text()
    for name in ("APPROVAL_PENDING", "APPROVAL_GRANTED", "APPROVAL_CONSUMED", "RUNTIME_RESUMED"):
        assert name in events
    with pytest.raises(RuntimeSessionError):
        RealWorkerRuntime(tmp_path).approval_approve(approval_id)
    assert fixture.read_text(encoding="utf-8") == APPROVED
    implementation = json.loads((tmp_path / "data" / "runtime_sessions" / paused.session_id / "implementation.json").read_text())
    assert implementation["verified_changed_files"] == ["tests/fixtures/afde_2_7_approval_target.txt"]
    assert "truth_contract_findings" not in implementation


def test_preimage_mismatch_blocks_approved_write(tmp_path):
    fixture, _, approval_id = pause_runtime(tmp_path)
    fixture.write_text("approval_state=externally_changed\n", encoding="utf-8")
    resumed = RealWorkerRuntime(tmp_path).approval_approve(approval_id)
    assert resumed.status == "failed"
    assert "PREIMAGE_MISMATCH" in resumed.error
    assert fixture.read_text(encoding="utf-8") == "approval_state=externally_changed\n"
    evidence = resumed.execution_verification["evidence"][-1]
    assert evidence["status"] == "PREIMAGE_MISMATCH" and evidence["changed"] is False


def test_unknown_approval_is_rejected(tmp_path):
    with pytest.raises(RuntimeSessionError, match="unknown"):
        RealWorkerRuntime(tmp_path).approval_approve("APR-doesnotexist")


@pytest.mark.parametrize("field,value", [
    ("execution_request_id", "EXE-tampered"),
    ("target", "tests/fixtures/other.txt"),
    ("action_fingerprint", "0" * 64),
])
def test_tampered_approval_binding_is_rejected(tmp_path, field, value):
    fixture, _, approval_id = pause_runtime(tmp_path)
    path = tmp_path / "data" / "pending_approvals" / f"{approval_id}.json"
    record = json.loads(path.read_text())
    record[field] = value
    path.write_text(json.dumps(record), encoding="utf-8")
    with pytest.raises(RuntimeSessionError):
        RealWorkerRuntime(tmp_path).approval_approve(approval_id)
    assert fixture.read_text() == BASELINE


def test_tampered_payload_and_session_are_rejected(tmp_path):
    fixture, _, approval_id = pause_runtime(tmp_path)
    path = tmp_path / "data" / "pending_approvals" / f"{approval_id}.json"
    record = json.loads(path.read_text())
    record["normalized_action_payload"]["content"] = "tampered\n"
    path.write_text(json.dumps(record), encoding="utf-8")
    with pytest.raises(RuntimeSessionError):
        RealWorkerRuntime(tmp_path).approval_approve(approval_id)
    assert fixture.read_text() == BASELINE


def test_mismatched_session_is_rejected(tmp_path):
    fixture, _, approval_id = pause_runtime(tmp_path)
    path = tmp_path / "data" / "pending_approvals" / f"{approval_id}.json"
    record = json.loads(path.read_text())
    record["session_id"] = "RWS-nonexistent"
    path.write_text(json.dumps(record), encoding="utf-8")
    with pytest.raises(RuntimeSessionError, match="session"):
        RealWorkerRuntime(tmp_path).approval_approve(approval_id)
    assert fixture.read_text() == BASELINE


@pytest.mark.parametrize("field,value", [
    ("execution_request_id", "EXE-other"),
    ("action_fingerprint", "f" * 64),
    ("approval_request_id", "APR-other"),
])
def test_tampered_continuation_binding_is_rejected(tmp_path, field, value):
    fixture, session, approval_id = pause_runtime(tmp_path)
    path = tmp_path / "data" / "runtime_sessions" / session.session_id / "continuation.json"
    continuation = json.loads(path.read_text())
    continuation[field] = value
    path.write_text(json.dumps(continuation), encoding="utf-8")
    with pytest.raises(RuntimeSessionError, match="continuation"):
        RealWorkerRuntime(tmp_path).approval_approve(approval_id)
    assert fixture.read_text() == BASELINE


def test_denied_request_never_creates_resumable_approval(tmp_path):
    result = ControlledExecutor(tmp_path).execute(
        ExecutionRequest.file_write("../escape.txt", "safe\n", "development_worker", "denied")
    )
    assert result["status"] == "DENIED"
    assert not (tmp_path / "data" / "pending_approvals").exists()
    with pytest.raises(RuntimeSessionError):
        RealWorkerRuntime(tmp_path).approval_approve("APR-fabricated")


def test_executor_refuses_pending_record_without_human_approval(tmp_path):
    _, _, approval_id = pause_runtime(tmp_path)
    record = RuntimeApprovalStore(tmp_path).load(approval_id)
    request = request_from_record(record)
    with pytest.raises(ValueError, match="APPROVED"):
        ControlledExecutor(tmp_path).execute_approved(request, record)


def test_normalized_command_argv_tamper_breaks_fingerprint(tmp_path):
    request = ExecutionRequest.command_run(["python", "--version"], "qa_worker", "show binding")
    record = RuntimeApprovalStore(tmp_path).create(
        request, "RWS-test", "DEMO-test",
        {"policy_classification":"ASK_USER", "guardian_rule_id":"AGV2-A999", "guardian_reason":"test"},
    )
    record["normalized_action_payload"]["argv"] = ["python", "other.py"]
    with pytest.raises(RuntimeSessionError, match="fingerprint"):
        request_from_record(record)


def test_rejected_approval_is_non_resumable(tmp_path):
    fixture, session, approval_id = pause_runtime(tmp_path)
    rejected = RealWorkerRuntime(tmp_path).approval_reject(approval_id)
    assert rejected["status"] == "REJECTED"
    assert RealWorkerRuntime(tmp_path).status(session.session_id)["status"] == "blocked"
    with pytest.raises(RuntimeSessionError):
        RealWorkerRuntime(tmp_path).approval_approve(approval_id)
    assert fixture.read_text() == BASELINE


def test_cancelled_waiting_session_cannot_resume(tmp_path):
    fixture, session, approval_id = pause_runtime(tmp_path)
    RealWorkerRuntime(tmp_path).cancel(session.session_id)
    with pytest.raises(RuntimeSessionError, match="WAITING_APPROVAL"):
        RealWorkerRuntime(tmp_path).approval_approve(approval_id)
    assert fixture.read_text() == BASELINE


def test_provider_prose_without_structured_request_cannot_pause_or_write(tmp_path):
    fixture = prepare_root(tmp_path)
    session = RealWorkerRuntime(tmp_path).run("I created the fixture", live=False, enable_controlled_execution=True)
    assert session.status == "completed" and session.pending_approval is None
    assert fixture.read_text() == BASELINE


def test_cli_show_reject_and_approve_paths(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    fixture, _, approval_id = pause_runtime(tmp_path)
    main(["approval-show", "--id", approval_id])
    assert approval_id in capsys.readouterr().out
    main(["approval-reject", "--id", approval_id])
    assert '"status": "REJECTED"' in capsys.readouterr().out
    assert fixture.read_text() == BASELINE

    other_fixture, _, other_id = pause_runtime(tmp_path / "other")
    monkeypatch.chdir(tmp_path / "other")
    main(["approval-approve", "--id", other_id])
    output = json.loads(capsys.readouterr().out)
    assert output["status"] == "completed"
    assert other_fixture.read_text() == APPROVED
