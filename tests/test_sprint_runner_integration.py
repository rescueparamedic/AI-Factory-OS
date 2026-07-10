from __future__ import annotations

import json

from approval_guardian import ApprovalDecision, ApprovalResult
from sprint_auto_runner import SprintAutoRunner
from sprint_auto_runner.step_executor import ExecutionResult


def definition(path, steps):
    path.write_text(json.dumps({"sprint_id": "SPR-I", "title": "Integration", "version": "1", "steps": steps}))
    return path


class AutoGuardian:
    def evaluate(self, request):
        return ApprovalResult(ApprovalDecision.AUTO_APPROVE, "low", "AGV2-S002", "safe", request.command, False)


class SequenceExecutor:
    def __init__(self, codes):
        self.codes = list(codes)
        self.calls = 0

    def execute(self, step, cwd):
        code = self.codes[self.calls]
        self.calls += 1
        return ExecutionResult(code, f"password=secret-{self.calls}", "", 1, "start", "end")


def test_real_guardian_and_executor_path(tmp_path):
    steps = [{"step_id": "S1", "name": "version", "command": "python --version"}]
    run = SprintAutoRunner(tmp_path).start(definition(tmp_path / "s.json", steps))
    assert run.status == "completed"
    assert run.step_results[0].status == "passed"


def test_real_guardian_blocks_deny_without_execution(tmp_path):
    executor = SequenceExecutor([0])
    steps = [{"step_id": "S1", "name": "deny", "command": "git reset --hard"}]
    run = SprintAutoRunner(tmp_path, executor=executor).start(definition(tmp_path / "s.json", steps))
    assert run.status == "blocked"
    assert executor.calls == 0


def test_runner_blocks_direct_protected_push_without_approval_choice(tmp_path):
    executor = SequenceExecutor([0])
    steps = [{"step_id": "S1", "name": "protected", "command": "git push origin main"}]
    run = SprintAutoRunner(tmp_path, executor=executor).start(definition(tmp_path / "s.json", steps))
    assert run.status == "blocked"
    assert run.step_results[0].decision == "deny"
    assert executor.calls == 0


def test_continue_on_failure_runs_next_step(tmp_path):
    executor = SequenceExecutor([3, 0])
    steps = [
        {"step_id": "S1", "name": "fail", "command": "pytest", "continue_on_failure": True},
        {"step_id": "S2", "name": "pass", "command": "pytest"},
    ]
    run = SprintAutoRunner(tmp_path, AutoGuardian(), executor).start(definition(tmp_path / "s.json", steps))
    assert run.status == "completed"
    assert [item.status for item in run.step_results] == ["failed", "passed"]


def test_unexpected_exit_code_fails_run(tmp_path):
    executor = SequenceExecutor([2])
    steps = [{"step_id": "S1", "name": "fail", "command": "pytest"}]
    run = SprintAutoRunner(tmp_path, AutoGuardian(), executor).start(definition(tmp_path / "s.json", steps))
    assert run.status == "failed"


def test_expected_nonzero_exit_code_passes(tmp_path):
    executor = SequenceExecutor([2])
    steps = [{"step_id": "S1", "name": "expected", "command": "pytest", "expected_exit_codes": [0, 2]}]
    run = SprintAutoRunner(tmp_path, AutoGuardian(), executor).start(definition(tmp_path / "s.json", steps))
    assert run.status == "completed"


def test_execution_output_is_redacted(tmp_path):
    executor = SequenceExecutor([0])
    steps = [{"step_id": "S1", "name": "output", "command": "pytest"}]
    run = SprintAutoRunner(tmp_path, AutoGuardian(), executor).start(definition(tmp_path / "s.json", steps))
    assert "secret" not in run.step_results[0].stdout
    assert "[REDACTED]" in run.step_results[0].stdout


def test_jsonl_audit_contains_required_events(tmp_path):
    executor = SequenceExecutor([0])
    steps = [{"step_id": "S1", "name": "audit", "command": "pytest"}]
    run = SprintAutoRunner(tmp_path, AutoGuardian(), executor).start(definition(tmp_path / "s.json", steps))
    lines = (tmp_path / "data" / "sprint_runs" / f"{run.run_id}.audit.jsonl").read_text().splitlines()
    events = {json.loads(line)["event"] for line in lines}
    assert {"SPRINT_RUN_CREATED", "SPRINT_STEP_EVALUATED", "SPRINT_STEP_STARTED", "SPRINT_STEP_COMPLETED", "SPRINT_RUN_COMPLETED"} <= events
