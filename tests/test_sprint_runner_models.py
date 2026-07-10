from dataclasses import FrozenInstanceError

import pytest

from sprint_auto_runner.models import RunStatus, SprintDefinition, SprintRun, SprintStep, StepResult, StepStatus


def test_run_status_values_are_stable():
    assert {item.value for item in RunStatus} == {
        "created", "running", "waiting_approval", "blocked", "failed", "completed", "cancelled"
    }


def test_step_status_values_are_stable():
    assert "auto_approved" in {item.value for item in StepStatus}
    assert "denied" in {item.value for item in StepStatus}


def test_sprint_step_defaults():
    step = SprintStep("S1", "status", "git status")
    assert step.cwd == "."
    assert step.timeout_seconds == 60
    assert step.expected_exit_codes == (0,)


def test_sprint_step_is_immutable():
    step = SprintStep("S1", "status", "git status")
    with pytest.raises(FrozenInstanceError):
        step.command = "other"


def test_step_result_defaults_to_pending():
    assert StepResult("S1").status == "pending"


def test_definition_keeps_tuple_steps():
    step = SprintStep("S1", "status", "git status")
    definition = SprintDefinition("SPR", "Title", "1", (step,), "sprint.json", "abc")
    assert definition.steps == (step,)


def test_run_serializes_nested_step_results():
    run = SprintRun("R1", "SPR", "feature/x", "created", 0, "now", "now", None, "", "token", "s.json", "fp", "sha", [StepResult("S1")])
    assert run.to_dict()["step_results"][0]["step_id"] == "S1"
