from pathlib import Path
from types import SimpleNamespace
from hashlib import sha256
import json
import subprocess

import pytest

from real_worker_runtime import RealWorkerRuntime
from real_worker_runtime.controlled_execution import (
    ControlledExecutionPolicy, ControlledExecutor, ExecutionRequest,
)
from real_worker_runtime.execution_truth import apply_execution_truth_contract


def file_request(path="controlled_execution/hello.py", content='print("hello")\n'):
    return ExecutionRequest.file_write(path, content, "development_worker", "test proposal")


def command_request(argv):
    return ExecutionRequest.command_run(argv, "qa_worker", "test validation")


def test_safe_new_file_creates_observed_evidence_and_guardian_audit(tmp_path):
    result = ControlledExecutor(tmp_path).execute(file_request())
    assert result["status"] == "SUCCEEDED"
    assert result["relative_path"] == "controlled_execution/hello.py"
    assert result["before_exists"] is False and result["after_exists"] is True
    assert result["changed"] is True and result["after_sha256"]
    assert (tmp_path / "controlled_execution" / "hello.py").read_text() == 'print("hello")\n'
    audits = list((tmp_path / "data" / "audit").glob("AUD-AGV2-*.json"))
    assert audits
    assert json.loads(audits[0].read_text())["decision"] == "auto_approve"


def test_file_write_preserves_exact_lf_payload_bytes_and_hash(tmp_path):
    payload = "first\nsecond\n"
    result = ControlledExecutor(tmp_path).execute(file_request(content=payload))
    expected = payload.encode("utf-8")
    target = tmp_path / "controlled_execution" / "hello.py"
    assert target.read_bytes() == expected
    assert result["approved_payload_sha256"] == sha256(expected).hexdigest()
    assert result["after_sha256"] == sha256(expected).hexdigest()


def test_observed_file_evidence_is_the_only_verified_source(tmp_path):
    request = file_request()
    observed = ControlledExecutor(tmp_path).execute(request)
    output, _ = apply_execution_truth_contract(
        "development_worker", {"changed_files": ["controlled_execution/hello.py"]},
        {"verified_changed_files": [observed["relative_path"]]},
    )
    assert output["verified_changed_files"] == ["controlled_execution/hello.py"]
    claims_only, _ = apply_execution_truth_contract(
        "development_worker", {"changed_files": ["unobserved.py"]}
    )
    assert claims_only["verified_changed_files"] == []


@pytest.mark.parametrize("path,classification", [
    (r"C:\\outside.py", "INVALID_PATH"),
    ("../outside.py", "WORKSPACE_ESCAPE"),
    (".git/config.txt", "GIT_METADATA_TARGET"),
    ("controlled_execution/program.exe", "UNSUPPORTED_SUFFIX"),
    ("controlled_execution/.env", "SECRET_TARGET_OR_CONTENT"),
])
def test_unsafe_file_targets_are_denied(tmp_path, path, classification):
    result = ControlledExecutionPolicy(tmp_path).classify(file_request(path))
    assert result.decision == "DENY"
    assert result.classification == classification


def test_existing_source_replacement_requires_human_approval(tmp_path):
    target = tmp_path / "controlled_execution" / "hello.py"
    target.parent.mkdir(); target.write_text("old")
    result = ControlledExecutor(tmp_path).execute(file_request())
    assert result["status"] == "WAITING_APPROVAL"
    assert target.read_text() == "old"


@pytest.mark.parametrize("argv,classification", [
    (["powershell", "-Command", "Get-Date"], "SHELL_INVOCATION"),
    (["python", "--version", "&&", "whoami"], "COMMAND_COMPOSITION"),
    (["curl", "https://example.com"], "NETWORK_COMMAND"),
    (["git", "reset", "--hard"], "UNSUPPORTED_EXECUTABLE"),
    (["python", "-c", "print(1)"], "UNSUPPORTED_COMMAND"),
])
def test_unsafe_commands_are_denied(tmp_path, argv, classification):
    result = ControlledExecutionPolicy(tmp_path).classify(command_request(argv))
    assert result.decision == "DENY"
    assert result.classification == classification


def test_sandbox_python_with_nontrivial_code_is_not_executable(tmp_path):
    target = tmp_path / "controlled_execution" / "unsafe.py"
    target.parent.mkdir(); target.write_text("import os\nos.system('whoami')\n")
    result = ControlledExecutionPolicy(tmp_path).classify(
        command_request(["python", "controlled_execution/unsafe.py"])
    )
    assert result.decision == "DENY"
    assert result.classification == "UNSUPPORTED_COMMAND"


def test_file_content_is_bounded_and_secret_content_is_denied(tmp_path):
    policy = ControlledExecutionPolicy(tmp_path)
    assert policy.classify(file_request(content="x" * 65537)).classification == "INVALID_TEXT_CONTENT"
    secret = "sk-" + "must-never-be-written"
    assert policy.classify(file_request(content=secret)).classification == "SECRET_TARGET_OR_CONTENT"


def test_allowlisted_command_runs_with_shell_false_and_records_exit_code(tmp_path):
    calls = []
    def runner(argv, **kwargs):
        calls.append((argv, kwargs))
        return SimpleNamespace(returncode=0, stdout="Python test\n", stderr="")
    result = ControlledExecutor(tmp_path, runner=runner).execute(command_request(["python", "--version"]))
    assert result["status"] == "SUCCEEDED" and result["exit_code"] == 0
    assert calls[0][1]["shell"] is False
    assert result["argv"] == ["python", "--version"]


def test_timeout_is_runtime_evidence(tmp_path):
    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired(args[0], kwargs["timeout"], output="partial")
    result = ControlledExecutor(tmp_path, timeout_seconds=0.01, runner=timeout).execute(
        command_request(["python", "--version"])
    )
    assert result["status"] == "FAILED"
    assert result["exit_code"] == 124 and result["timed_out"] is True


def test_only_actual_command_execution_populates_verified_tests(tmp_path):
    claim, _ = apply_execution_truth_contract(
        "qa_worker", {"tests_run": ["python --version"], "passed": 1}
    )
    assert claim["verified_test_executions"] == []
    observed = ControlledExecutor(tmp_path).execute(command_request(["python", "--version"]))
    verified, _ = apply_execution_truth_contract(
        "qa_worker", {"tests_run": ["python --version"], "passed": 1},
        {"verified_test_executions": [observed]},
    )
    assert verified["verified_test_executions"][0]["exit_code"] == 0


def test_execution_evidence_redacts_secret_output(tmp_path):
    secret = "sk-" + "sensitive-output-value"
    def runner(*args, **kwargs):
        return SimpleNamespace(returncode=1, stdout=secret, stderr="Authorization" + ": Bearer hidden")
    result = ControlledExecutor(tmp_path, runner=runner).execute(command_request(["python", "--version"]))
    rendered = json.dumps(result)
    persisted = next((tmp_path / "data" / "execution_evidence").glob("*.json")).read_text()
    assert secret not in rendered + persisted
    assert "hidden" not in rendered + persisted


def test_deterministic_controlled_runtime_produces_verified_evidence(tmp_path):
    session = RealWorkerRuntime(tmp_path).run(
        "[controlled-execution-mvp] print Hello", live=False,
        enable_controlled_execution=True,
    )
    assert session.status == "completed"
    assert session.execution_verification["status"] == "VERIFIED"
    assert session.execution_verification["verified_changed_files"] == [
        "controlled_execution/hello_from_afde.py"
    ]
    executions = session.execution_verification["verified_test_executions"]
    assert len(executions) == 1 and executions[0]["exit_code"] == 0
    assert executions[0]["argv"] == ["python", "controlled_execution/hello_from_afde.py"]
    assert (tmp_path / "controlled_execution" / "hello_from_afde.py").is_file()


def test_controlled_execution_remains_disabled_by_default(tmp_path):
    session = RealWorkerRuntime(tmp_path).run("[controlled-execution-mvp]", live=False)
    assert session.status == "completed"
    assert session.execution_verification["status"] == "NOT_VERIFIED"
    assert not (tmp_path / "controlled_execution" / "hello_from_afde.py").exists()
