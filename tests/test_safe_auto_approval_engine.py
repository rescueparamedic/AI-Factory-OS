import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from approval_guardian import (
    ApprovalDecision, ApprovalGuardian, ApprovalResult,
)
from real_worker_runtime import RealWorkerRuntime
from real_worker_runtime.approval_resume import (
    RuntimeApprovalStore, action_fingerprint,
)
from real_worker_runtime.controlled_execution import (
    ControlledExecutor, ExecutionRequest, RuntimeApprovalContext,
    build_runtime_approval_context, context_fingerprint,
)
from real_worker_runtime.errors import RuntimeSessionError
from real_worker_runtime.provider_bridge import ProviderBridge


def _file_request(path="controlled_execution/auto.txt", content="safe\n"):
    return ExecutionRequest.file_write(
        path, content, "development_worker", "AFDE-3.1 test",
    )


def _command_request():
    return ExecutionRequest.command_run(
        ["python", "--version"], "qa_worker", "AFDE-3.1 test",
    )


def _context(root, **changes):
    values = {
        "cwd": str(root), "repository": str(root), "branch": "feature/test",
        "environment": "local", "runtime_task_id": "TASK-test",
        "runtime_session_id": "RWS-test", "stage": "development",
        "actor": "development_worker", "metadata": {"revision": 0},
    }
    values.update(changes)
    return RuntimeApprovalContext(**values)


def _approval(decision, rule_id="AGV2-S004", reason="classified"):
    return ApprovalResult(
        decision=decision, risk_level="low", rule_id=rule_id,
        reason=reason, normalized_command="normalized", requires_human=(
            decision is ApprovalDecision.ASK_USER
        ),
    )


def test_central_boundary_reuses_canonical_guardian_and_decision_model(tmp_path):
    executor = ControlledExecutor(tmp_path)

    assert isinstance(executor.guardian, ApprovalGuardian)
    assert set(ApprovalDecision) == {
        ApprovalDecision.AUTO_APPROVE,
        ApprovalDecision.ASK_USER,
        ApprovalDecision.DENY,
    }


def test_equivalent_requests_and_contexts_have_deterministic_fingerprints(tmp_path):
    first = _file_request()
    second = _file_request()
    context = _context(tmp_path)

    assert first.request_id != second.request_id
    assert action_fingerprint(first) == action_fingerprint(second)
    assert context_fingerprint(context) == context_fingerprint(_context(tmp_path))
    assert context_fingerprint(context) != context_fingerprint(
        _context(tmp_path, branch="feature/changed"),
    )


def test_auto_approve_records_evidence_before_side_effect_and_executes(tmp_path):
    executor = ControlledExecutor(tmp_path)
    target = tmp_path / "controlled_execution" / "auto.txt"
    evaluated_before_write = []

    class Guardian:
        def evaluate(self, request):
            evaluated_before_write.append(not target.exists())
            return _approval(ApprovalDecision.AUTO_APPROVE)

    executor.guardian = Guardian()
    result = executor.execute(_file_request(), _context(tmp_path))

    assert evaluated_before_write == [True]
    assert result["status"] == "SUCCEEDED"
    assert result["decision"] == "auto_approve"
    assert result["rule_id"] == "AGV2-S004"
    assert result["action_fingerprint"]
    assert result["context_fingerprint"]
    assert result["runtime_task_id"] == "TASK-test"
    assert target.read_text(encoding="utf-8") == "safe\n"


def test_auto_approved_execution_failure_is_not_approval_failure(tmp_path):
    executor = ControlledExecutor(
        tmp_path,
        runner=lambda *args, **kwargs: SimpleNamespace(
            returncode=7, stdout="", stderr="execution failed",
        ),
    )
    result = executor.execute(
        _command_request(), _context(tmp_path, stage="qa", actor="qa_worker"),
    )

    assert result["decision"] == "auto_approve"
    assert result["status"] == "FAILED"
    assert result["exit_code"] == 7


@pytest.mark.parametrize("path", [
    "../outside.txt", ".git/config.txt", "controlled_execution/.env",
])
def test_controlled_execution_deny_overrides_and_never_writes(tmp_path, path):
    result = ControlledExecutor(tmp_path).execute(
        _file_request(path), _context(tmp_path),
    )

    assert result["status"] == "DENIED"
    assert result["decision"] == "deny"
    assert not (tmp_path.parent / "outside.txt").exists()


def test_guardian_deny_overrides_safe_controlled_policy(tmp_path):
    executor = ControlledExecutor(tmp_path)
    executor.guardian = SimpleNamespace(
        evaluate=lambda request: _approval(
            ApprovalDecision.DENY, "AGV2-D004", "denied",
        ),
    )

    result = executor.execute(_file_request(), _context(tmp_path))

    assert result["status"] == "DENIED"
    assert result["rule_id"] == "AGV2-D004"
    assert not (tmp_path / "controlled_execution" / "auto.txt").exists()


def test_controlled_ask_user_cannot_be_weakened_by_guardian_auto_approve(tmp_path):
    target = tmp_path / "controlled_execution" / "auto.txt"
    target.parent.mkdir(parents=True)
    target.write_text("existing\n", encoding="utf-8")
    executor = ControlledExecutor(tmp_path)
    executor.guardian = SimpleNamespace(
        evaluate=lambda request: _approval(ApprovalDecision.AUTO_APPROVE),
    )

    result = executor.execute(_file_request(), _context(tmp_path))

    assert result["status"] == "WAITING_APPROVAL"
    assert result["decision"] == "ask_user"
    assert result["rule_id"] == "CE-EXISTING_FILE_REPLACEMENT"
    assert target.read_text(encoding="utf-8") == "existing\n"


@pytest.mark.parametrize("failure", ["exception", "malformed", "unknown"])
def test_guardian_failure_or_invalid_decision_fails_closed(tmp_path, failure):
    executor = ControlledExecutor(tmp_path)

    class Guardian:
        def evaluate(self, request):
            if failure == "exception":
                raise RuntimeError("token=must-not-leak")
            if failure == "malformed":
                return None
            return SimpleNamespace(decision="allow")

    executor.guardian = Guardian()
    result = executor.execute(_file_request(), _context(tmp_path))

    assert result["status"] == "DENIED"
    assert result["error_code"] == "RUNTIME_CONTROLLED_EXECUTION_BLOCKED"
    assert "must-not-leak" not in json.dumps(result)
    assert not (tmp_path / "controlled_execution" / "auto.txt").exists()


def test_context_normalization_failure_is_blocked(tmp_path):
    context = _context(tmp_path, repository=str(tmp_path / "other"))
    result = ControlledExecutor(tmp_path).execute(_file_request(), context)

    assert result["status"] == "DENIED"
    assert result["policy_classification"] == "CONTEXT_OR_POLICY_FAILURE"


def test_mandatory_pre_execution_evidence_failure_prevents_side_effect(
    tmp_path, monkeypatch,
):
    executor = ControlledExecutor(tmp_path)

    def fail_record(evidence):
        raise OSError("audit unavailable")

    monkeypatch.setattr(executor, "_persist_raw", fail_record)
    result = executor.execute(_file_request(), _context(tmp_path))

    assert result["status"] == "DENIED"
    assert result["policy_classification"] == "AUDIT_RECORD_FAILURE"
    assert not (tmp_path / "controlled_execution" / "auto.txt").exists()


def test_deny_audit_failure_still_fails_closed_without_side_effect(tmp_path, monkeypatch):
    executor = ControlledExecutor(tmp_path)
    monkeypatch.setattr(
        executor, "_persist_raw",
        lambda evidence: (_ for _ in ()).throw(OSError("audit unavailable")),
    )

    result = executor.execute(_file_request("../outside.txt"), _context(tmp_path))

    assert result["status"] == "DENIED"
    assert result["policy_classification"] == "AUDIT_RECORD_FAILURE"
    assert not (tmp_path.parent / "outside.txt").exists()


def test_ask_user_runtime_preserves_exact_context_and_visible_pause(tmp_path):
    fixture = _prepare_approval_root(tmp_path)
    session = RealWorkerRuntime(tmp_path).run(
        "[approval-resume-mvp]", live=False, enable_controlled_execution=True,
    )
    pending = session.pending_approval
    record = RuntimeApprovalStore(tmp_path).load(pending["approval_request_id"])

    assert session.status == "waiting_approval"
    assert session.runtime_tasks[0]["lifecycle_status"] == "waiting_approval"
    assert pending["error_code"] == "RUNTIME_APPROVAL_REQUIRED"
    assert pending["next_action"] == "resume requires exact approval"
    assert record["context_fingerprint"]
    assert record["normalized_context"]["runtime_session_id"] == session.session_id
    assert fixture.read_text(encoding="utf-8") == "approval_state=baseline\n"


def test_changed_branch_context_invalidates_pending_approval(tmp_path, monkeypatch):
    fixture = _prepare_approval_root(tmp_path)
    runtime = RealWorkerRuntime(tmp_path)
    paused = runtime.run(
        "[approval-resume-mvp]", live=False, enable_controlled_execution=True,
    )
    approval_id = paused.pending_approval["approval_request_id"]

    def changed_context(root, **values):
        context = build_runtime_approval_context(root, **values)
        return RuntimeApprovalContext(
            **{**context.normalized(), "branch": "feature/changed-after-approval"}
        )

    monkeypatch.setattr(
        "real_worker_runtime.runtime.build_runtime_approval_context",
        changed_context,
    )
    with pytest.raises(RuntimeSessionError, match="context changed"):
        runtime.approval_approve(approval_id)

    record = RuntimeApprovalStore(tmp_path).load(approval_id)
    assert record["status"] == "PENDING"
    assert record["revalidation_result"] == "mismatch"
    assert fixture.read_text(encoding="utf-8") == "approval_state=baseline\n"


def test_valid_exact_resume_records_actor_revalidation_and_consumption(tmp_path):
    fixture = _prepare_approval_root(tmp_path)
    runtime = RealWorkerRuntime(tmp_path)
    paused = runtime.run(
        "[approval-resume-mvp]", live=False, enable_controlled_execution=True,
    )
    approval_id = paused.pending_approval["approval_request_id"]
    resumed = runtime.approval_approve(approval_id)
    record = RuntimeApprovalStore(tmp_path).load(approval_id)

    assert resumed.status == "completed"
    assert record["status"] == "CONSUMED"
    assert record["approved_by"] == "Product Owner"
    assert record["revalidation_result"] == "matched"
    assert record["revalidated_at"] and record["consumed_at"]
    assert fixture.read_text(encoding="utf-8") == "approval_state=approved\n"


def test_fingerprints_and_evidence_do_not_expose_secret_content(tmp_path):
    secret = "sk-" + "never-expose-this-value"
    request = _file_request(content=secret)
    result = ControlledExecutor(tmp_path).execute(request, _context(tmp_path))
    rendered = json.dumps(result)

    assert result["status"] == "DENIED"
    assert secret not in rendered
    assert len(action_fingerprint(request)) == 64
    assert secret not in action_fingerprint(request)


def _prepare_approval_root(root: Path) -> Path:
    fixture = root / "tests" / "fixtures" / "afde_2_7_approval_target.txt"
    fixture.parent.mkdir(parents=True)
    fixture.write_text("approval_state=baseline\n", encoding="utf-8")
    (root / "tests" / "test_afde_2_7_fixture.py").write_text(
        "from pathlib import Path\n"
        "def test_state():\n"
        " p=Path(__file__).parent/'fixtures'/'afde_2_7_approval_target.txt'\n"
        " assert p.read_text() == 'approval_state=approved\\n'\n",
        encoding="utf-8",
    )
    return fixture
