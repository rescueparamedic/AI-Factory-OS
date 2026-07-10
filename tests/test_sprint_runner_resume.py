from __future__ import annotations

import json

import pytest

from approval_guardian import ApprovalDecision, ApprovalResult
from sprint_auto_runner import SprintAutoRunner
from sprint_auto_runner.errors import SprintResumeError, SprintRunnerError
from sprint_auto_runner.step_executor import ExecutionResult


def write_definition(path, command="git merge feature/test"):
    path.write_text(json.dumps({
        "sprint_id": "SPR-R", "title": "Resume", "version": "1",
        "steps": [{"step_id": "S1", "name": "approval", "command": command}],
    }))
    return path


class AskGuardian:
    def evaluate(self, request):
        return ApprovalResult(ApprovalDecision.ASK_USER, "high", "AGV2-A001", "approval required", request.command, True)


class DenyGuardian:
    def evaluate(self, request):
        return ApprovalResult(ApprovalDecision.DENY, "critical", "AGV2-D001", "denied", request.command, False)


class Executor:
    def __init__(self):
        self.calls = 0

    def execute(self, step, cwd):
        self.calls += 1
        return ExecutionResult(0, "ok", "", 1, "start", "end")


def approval(step_id="S1"):
    return {"step_id": step_id, "decision": "approved", "approved_by": "user", "reason": "reviewed"}


def test_approved_waiting_step_resumes(tmp_path):
    executor = Executor()
    runner = SprintAutoRunner(tmp_path, AskGuardian(), executor)
    waiting = runner.start(write_definition(tmp_path / "s.json"))
    resumed = runner.resume(waiting.run_id, approval())
    assert resumed.status == "completed"
    assert executor.calls == 1


def test_resume_without_approval_is_rejected(tmp_path):
    runner = SprintAutoRunner(tmp_path, AskGuardian(), Executor())
    waiting = runner.start(write_definition(tmp_path / "s.json"))
    with pytest.raises(SprintResumeError, match="explicitly approve"):
        runner.resume(waiting.run_id, {"step_id": "S1", "decision": "rejected", "approved_by": "user"})


def test_cannot_skip_waiting_step(tmp_path):
    runner = SprintAutoRunner(tmp_path, AskGuardian(), Executor())
    waiting = runner.start(write_definition(tmp_path / "s.json"))
    with pytest.raises(SprintResumeError, match="currently waiting"):
        runner.resume(waiting.run_id, approval("S2"))


def test_definition_change_invalidates_approval(tmp_path):
    path = write_definition(tmp_path / "s.json")
    runner = SprintAutoRunner(tmp_path, AskGuardian(), Executor())
    waiting = runner.start(path)
    write_definition(path, command="git merge feature/other")
    with pytest.raises(SprintResumeError, match="definition changed"):
        runner.resume(waiting.run_id, approval())


def test_context_change_invalidates_approval(tmp_path):
    runner = SprintAutoRunner(tmp_path, AskGuardian(), Executor())
    waiting = runner.start(write_definition(tmp_path / "s.json"))
    waiting.pending_approval["context_fingerprint"] = "changed"
    runner.store.save(waiting)
    with pytest.raises(SprintResumeError, match="context changed"):
        runner.resume(waiting.run_id, approval())


def test_actual_branch_change_invalidates_approval(tmp_path, monkeypatch):
    runner = SprintAutoRunner(tmp_path, AskGuardian(), Executor())
    waiting = runner.start(write_definition(tmp_path / "s.json"))
    original_git = runner._git

    def changed_git(*arguments):
        if arguments == ("branch", "--show-current"):
            return "feature/changed"
        return original_git(*arguments)

    monkeypatch.setattr(runner, "_git", changed_git)
    with pytest.raises(SprintResumeError, match="context changed"):
        runner.resume(waiting.run_id, approval())


def test_reevaluated_deny_blocks_resume(tmp_path):
    runner = SprintAutoRunner(tmp_path, AskGuardian(), Executor())
    waiting = runner.start(write_definition(tmp_path / "s.json"))
    runner.bridge.guardian = DenyGuardian()
    blocked = runner.resume(waiting.run_id, approval())
    assert blocked.status == "blocked"
    assert runner.executor.calls == 0


def test_cancel_waiting_run(tmp_path):
    runner = SprintAutoRunner(tmp_path, AskGuardian(), Executor())
    waiting = runner.start(write_definition(tmp_path / "s.json"))
    cancelled = runner.cancel(waiting.run_id)
    assert cancelled.status == "cancelled"
    assert cancelled.pending_approval is None


def test_cannot_cancel_terminal_run(tmp_path):
    runner = SprintAutoRunner(tmp_path, DenyGuardian(), Executor())
    blocked = runner.start(write_definition(tmp_path / "s.json", "git reset --hard"))
    with pytest.raises(SprintRunnerError, match="terminal"):
        runner.cancel(blocked.run_id)
