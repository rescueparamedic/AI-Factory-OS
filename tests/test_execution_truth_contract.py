import json

from real_worker_runtime import RealWorkerRuntime
from real_worker_runtime.execution_truth import (
    UNVERIFIED_FILE_CHANGE_CLAIM,
    UNVERIFIED_TEST_EXECUTION_CLAIM,
    apply_execution_truth_contract,
)


def test_development_file_claim_is_proposed_not_verified():
    output, findings = apply_execution_truth_contract("development_worker", {
        "implementation_summary": "Claimed creation",
        "changed_files": ["hello.py"],
        "commands_requested": ["python hello.py"],
        "artifacts": ["hello.py"],
    })
    assert output["proposed_files"] == ["hello.py"]
    assert output["verified_changed_files"] == []
    assert "changed_files" not in output
    assert findings == [{
        "classification": UNVERIFIED_FILE_CHANGE_CLAIM,
        "claimed_items": ["hello.py"],
    }]


def test_qa_pass_claim_is_not_verified_execution():
    output, findings = apply_execution_truth_contract("qa_worker", {
        "tests_run": ["python -m pytest"], "passed": 2, "failed": 0,
        "issues": [], "recommendation": "PASS",
    })
    assert output["claimed_test_commands"] == ["python -m pytest"]
    assert output["claimed_test_results"]["passed"] == 2
    assert output["verified_test_executions"] == []
    assert "passed" not in output and "tests_run" not in output
    assert findings[0]["classification"] == UNVERIFIED_TEST_EXECUTION_CLAIM


def test_mock_runtime_completes_orchestration_without_execution_verification(tmp_path):
    session = RealWorkerRuntime(tmp_path).run("demo", live=False)
    assert session.status == "completed"
    assert session.execution_verification["status"] == "NOT_VERIFIED"
    assert UNVERIFIED_TEST_EXECUTION_CLAIM in session.execution_verification["findings"]
    qa = next(item["output"] for item in session.results if item["worker_id"] == "qa_worker")
    assert qa["verified_test_executions"] == []
    assert any(item["classification"] == UNVERIFIED_TEST_EXECUTION_CLAIM
               for item in session.truth_contract_findings)


def test_artifacts_and_report_separate_claims_from_runtime_evidence(tmp_path):
    session = RealWorkerRuntime(tmp_path).run("demo", live=False)
    root = tmp_path / "data" / "runtime_sessions" / session.session_id
    implementation = json.loads((root / "implementation.json").read_text())
    qa = json.loads((root / "qa_report.json").read_text())
    report = (root / "final_report.md").read_text()
    assert implementation["verified_changed_files"] == []
    assert qa["verified_test_executions"] == []
    assert "Execution verification: **NOT_VERIFIED**" in report
    assert "Provider QA Claims" in report
    assert "Provider Documentation Claim (Not Runtime Verification)" in report
    assert "Runtime-verified test executions: []" in report
    assert "tests executed successfully" not in report.lower()


def test_messages_are_worker_output_records_not_false_handoffs(tmp_path):
    session = RealWorkerRuntime(tmp_path).run("demo", live=False)
    assert len(session.messages) == 5
    assert all(item["message_type"] == "WORKER_OUTPUT" for item in session.messages)
    assert all(item["to_worker"] == "runtime" for item in session.messages)
    assert [item["from_worker"] for item in session.messages] == [
        "pm_worker", "planning_worker", "development_worker", "qa_worker",
        "documentation_worker",
    ]
