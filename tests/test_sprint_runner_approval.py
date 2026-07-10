from __future__ import annotations

import json

from approval_guardian import ApprovalDecision, ApprovalResult
from sprint_auto_runner import SprintAutoRunner


def definition(path, command):
    path.write_text(json.dumps({
        "sprint_id": "SPR-A", "title": "Approval", "version": "1",
        "steps": [{"step_id": "S1", "name": "step", "command": command}],
    }))
    return path


class FixedGuardian:
    def __init__(self, decision):
        self.decision = ApprovalDecision(decision)

    def evaluate(self, request):
        return ApprovalResult(
            self.decision,
            "low" if self.decision is ApprovalDecision.AUTO_APPROVE else "high",
            {ApprovalDecision.AUTO_APPROVE: "AGV2-S002", ApprovalDecision.ASK_USER: "AGV2-A001", ApprovalDecision.DENY: "AGV2-D001"}[self.decision],
            "test decision",
            request.command,
            self.decision is ApprovalDecision.ASK_USER,
        )


class CountingExecutor:
    calls = 0

    def execute(self, step, cwd):
        from sprint_auto_runner.step_executor import ExecutionResult
        self.calls += 1
        return ExecutionResult(0, "ok", "", 1, "start", "end")


def test_auto_approve_executes(tmp_path):
    executor = CountingExecutor()
    run = SprintAutoRunner(tmp_path, FixedGuardian("auto_approve"), executor).start(definition(tmp_path / "s.json", "pytest"))
    assert run.status == "completed"
    assert executor.calls == 1


def test_ask_user_never_executes(tmp_path):
    executor = CountingExecutor()
    run = SprintAutoRunner(tmp_path, FixedGuardian("ask_user"), executor).start(definition(tmp_path / "s.json", "git merge feature/test"))
    assert run.status == "waiting_approval"
    assert run.step_results[0].status == "waiting_approval"
    assert executor.calls == 0
    assert run.pending_approval["rule_id"] == "AGV2-A001"


def test_deny_blocks_without_execution(tmp_path):
    executor = CountingExecutor()
    run = SprintAutoRunner(tmp_path, FixedGuardian("deny"), executor).start(definition(tmp_path / "s.json", "git reset --hard"))
    assert run.status == "blocked"
    assert run.step_results[0].status == "denied"
    assert executor.calls == 0


def test_guardian_exception_fails_closed(tmp_path):
    class BrokenGuardian:
        def evaluate(self, request):
            raise RuntimeError("broken")

    executor = CountingExecutor()
    run = SprintAutoRunner(tmp_path, BrokenGuardian(), executor).start(definition(tmp_path / "s.json", "pytest"))
    assert run.status == "blocked"
    assert executor.calls == 0


def test_audit_failure_stops_safe_step(tmp_path, monkeypatch):
    runner = SprintAutoRunner(tmp_path, FixedGuardian("auto_approve"), CountingExecutor())
    monkeypatch.setattr(runner.audit, "record", lambda *args, **kwargs: (_ for _ in ()).throw(OSError("no audit")))
    run = runner.start(definition(tmp_path / "s.json", "pytest"))
    assert run.status == "waiting_approval"
    assert runner.executor.calls == 0


def test_runner_overlay_denies_direct_develop_push(tmp_path):
    executor = CountingExecutor()
    run = SprintAutoRunner(tmp_path, FixedGuardian("ask_user"), executor).start(
        definition(tmp_path / "s.json", "git push origin develop")
    )
    assert run.status == "blocked"
    assert run.step_results[0].rule_id == "AGV2-D001"
    assert executor.calls == 0
