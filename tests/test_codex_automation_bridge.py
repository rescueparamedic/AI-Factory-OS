from pathlib import Path
from types import SimpleNamespace
import json

import pytest

from real_worker_runtime import CodexAutomationBridge, RealWorkerRuntime
from real_worker_runtime.controlled_execution import (
    ControlledExecutor, RuntimeApprovalContext,
)
from real_worker_runtime.tool_actions import (
    ToolAction, ToolActionType, ToolActionValidationError,
)


def action(root: Path, action_type="FILE_WRITE", **overrides):
    value = {
        "action_id": "TA-test-1", "action_type": action_type,
        "source_worker": "development_worker", "purpose": "bounded test action",
        "target": "controlled_execution/bridge.txt",
        "arguments": {"content": "bridge\n"}, "cwd": str(root),
        "repository": str(root), "branch": "", "runtime_task_id": "TASK-1",
        "runtime_session_id": "RWS-1", "stage": "development", "revision": 0,
        "preconditions": {}, "expected_result": {"status": "SUCCEEDED"},
        "metadata": {},
    }
    value.update(overrides)
    return value


def context(root: Path, **overrides):
    value = {
        "cwd": str(root), "repository": str(root), "branch": "",
        "environment": "local", "runtime_task_id": "TASK-1",
        "runtime_session_id": "RWS-1", "stage": "development",
        "actor": "development_worker", "metadata": {"revision": 0},
    }
    value.update(overrides)
    return RuntimeApprovalContext(**value)


def test_contract_supports_only_the_bounded_action_types(tmp_path):
    for item in ToolActionType:
        parsed = ToolAction.from_value(action(tmp_path, item.value))
        assert parsed.action_type is item
    with pytest.raises(ToolActionValidationError, match="unsupported"):
        ToolAction.from_value(action(tmp_path, "MERGE"))


def test_contract_rejects_missing_unknown_and_malformed_fields(tmp_path):
    missing = action(tmp_path); missing.pop("purpose")
    with pytest.raises(ToolActionValidationError, match="missing"):
        ToolAction.from_value(missing)
    with pytest.raises(ToolActionValidationError, match="unknown"):
        ToolAction.from_value({**action(tmp_path), "raw_shell": "echo unsafe"})
    with pytest.raises(ToolActionValidationError, match="revision"):
        ToolAction.from_value(action(tmp_path, revision="0"))
    with pytest.raises(ToolActionValidationError, match="action_id"):
        ToolAction.from_value(action(tmp_path, action_id="../escape"))


def test_fingerprint_is_deterministic_and_payload_bound(tmp_path):
    first = ToolAction.from_value(action(tmp_path))
    assert first.fingerprint == ToolAction.from_value(action(tmp_path)).fingerprint
    changed = ToolAction.from_value(action(tmp_path, arguments={"content": "different\n"}))
    assert first.fingerprint != changed.fingerprint


def test_auto_write_has_changed_file_evidence_and_duplicate_is_blocked(tmp_path):
    bridge = CodexAutomationBridge(tmp_path)
    first = bridge.execute(action(tmp_path), context(tmp_path))
    assert first.status == "SUCCEEDED"
    assert first.evidence["changed"] is True
    assert first.evidence["after_sha256"]
    assert (tmp_path / "controlled_execution" / "bridge.txt").read_text() == "bridge\n"
    second = bridge.execute(action(tmp_path), context(tmp_path))
    assert second.status == "DUPLICATE"
    assert bridge.status("TA-test-1")["result"]["status"] == "SUCCEEDED"
    record = json.dumps(bridge.status("TA-test-1"))
    assert "bridge\\n" not in record
    assert "content_sha256" in record
    assert len((tmp_path / "data" / "tool_action_evidence" / "ledger.jsonl").read_text().splitlines()) == 2


def test_context_mismatch_and_workspace_escape_fail_closed(tmp_path):
    mismatch = CodexAutomationBridge(tmp_path).execute(
        action(tmp_path), context(tmp_path, runtime_task_id="OTHER"),
    )
    assert mismatch.status == "DENIED"
    escaped = CodexAutomationBridge(tmp_path).execute(
        action(tmp_path, action_id="TA-escape", target="../escape.txt"), context(tmp_path),
    )
    assert escaped.status == "DENIED"
    assert not (tmp_path.parent / "escape.txt").exists()


def test_existing_file_asks_and_exact_action_is_returned(tmp_path):
    target = tmp_path / "controlled_execution" / "bridge.txt"
    target.parent.mkdir(); target.write_text("old\n")
    result = CodexAutomationBridge(tmp_path).execute(action(tmp_path), context(tmp_path))
    assert result.status == "WAITING_APPROVAL"
    assert result.execution_request.request_id == "TA-test-1"
    assert target.read_text() == "old\n"


def test_file_read_is_guarded_bounded_and_evidenced(tmp_path):
    target = tmp_path / "notes.txt"; target.write_text("hello\n")
    value = action(
        tmp_path, "FILE_READ", target="notes.txt", arguments={},
    )
    result = CodexAutomationBridge(tmp_path).execute(value, context(tmp_path))
    assert result.status == "SUCCEEDED"
    assert result.evidence["content"] == "hello\n"
    assert result.evidence["content_sha256"]


def test_command_test_and_git_adapters_use_controlled_executor(tmp_path):
    calls = []
    def runner(argv, **kwargs):
        calls.append(argv)
        return SimpleNamespace(returncode=0, stdout="ok\n", stderr="")
    bridge = CodexAutomationBridge(tmp_path, ControlledExecutor(tmp_path, runner=runner))
    command = action(
        tmp_path, "COMMAND_RUN", action_id="TA-command", source_worker="qa_worker",
        stage="qa", arguments={"argv": ["python", "--version"]}, target="python",
    )
    qa_context = context(tmp_path, actor="qa_worker", stage="qa")
    assert bridge.execute(command, qa_context).status == "SUCCEEDED"
    test_run = action(
        tmp_path, "TEST_RUN", action_id="TA-test-run", source_worker="qa_worker",
        stage="qa", arguments={"argv": ["python", "-m", "pytest", "-q"]}, target="pytest",
    )
    assert bridge.execute(test_run, qa_context).status == "SUCCEEDED"
    git_status = action(
        tmp_path, "GIT_STATUS", action_id="TA-git", arguments={}, target="repository",
    )
    assert bridge.execute(git_status, context(tmp_path)).status == "SUCCEEDED"
    assert calls[0][0] and calls[2] == ["git", "status", "--short"]


def test_git_mutations_are_exact_feature_branch_operations(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "real_worker_runtime.controlled_execution._git_branch", lambda root: "feature/bridge",
    )
    calls = []
    def runner(argv, **kwargs):
        calls.append(argv)
        return SimpleNamespace(returncode=0, stdout="ok\n", stderr="")
    bridge = CodexAutomationBridge(tmp_path, ControlledExecutor(tmp_path, runner=runner))
    git_context = context(tmp_path, branch="feature/bridge")
    operations = [
        action(tmp_path, "GIT_ADD", action_id="TA-add", branch="feature/bridge", target="paths", arguments={"paths": ["safe.txt"]}),
        action(tmp_path, "GIT_COMMIT", action_id="TA-commit", branch="feature/bridge", target="repository", arguments={"message": "feat: safe"}),
        action(tmp_path, "GIT_PUSH_FEATURE", action_id="TA-push", branch="feature/bridge", target="feature/bridge", arguments={}),
    ]
    assert [bridge.execute(item, git_context).status for item in operations] == ["SUCCEEDED"] * 3
    assert calls == [
        ["git", "add", "--", "safe.txt"],
        ["git", "commit", "-m", "feat: safe"],
        ["git", "push", "origin", "feature/bridge"],
    ]
    broad = action(tmp_path, "GIT_ADD", action_id="TA-broad", branch="feature/bridge", target="paths", arguments={"paths": ["."]})
    protected = action(tmp_path, "GIT_PUSH_FEATURE", action_id="TA-protected", branch="feature/bridge", target="develop", arguments={})
    assert bridge.execute(broad, git_context).status == "DENIED"
    assert bridge.execute(protected, git_context).status == "DENIED"


def test_test_adapter_rejects_non_pytest_command(tmp_path):
    result = CodexAutomationBridge(tmp_path).execute(
        action(tmp_path, "TEST_RUN", arguments={"argv": ["python", "--version"]}),
        context(tmp_path),
    )
    assert result.status == "DENIED"


@pytest.mark.parametrize("marker,status", [
    ("auto", "completed"), ("ask", "waiting_approval"), ("deny", "blocked"),
])
def test_mock_runtime_structured_action_paths(tmp_path, marker, status):
    session = RealWorkerRuntime(tmp_path).run(
        f"[tool-action-{marker}]", live=False, enable_controlled_execution=True,
    )
    assert session.status == status, session.to_dict()
    evidence = list((tmp_path / "data" / "tool_action_evidence").glob("*.json"))
    assert evidence


def test_structured_actions_are_canonical_over_legacy_proposals(tmp_path):
    from real_worker_runtime.runtime import _execute_proposals
    bridge = CodexAutomationBridge(tmp_path)
    output = {
        "actions": [],
        "proposed_file_writes": [{
            "relative_path": "controlled_execution/legacy.txt",
            "content": "legacy\n", "purpose": "must not run",
        }],
    }
    _execute_proposals(bridge.executor, "development_worker", output, tmp_path, context(tmp_path), bridge)
    assert not (tmp_path / "controlled_execution" / "legacy.txt").exists()
