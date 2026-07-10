from __future__ import annotations

import sys

from sprint_auto_runner.models import SprintStep
from sprint_auto_runner.step_executor import StepExecutor


def step(command, **kwargs):
    return SprintStep("S1", "exec", command, **kwargs)


PYTHON = f'"{sys.executable}"'


def test_success_exit_code(tmp_path):
    result = StepExecutor().execute(step(f'{PYTHON} -c "print(123)"'), str(tmp_path))
    assert result.exit_code == 0
    assert "123" in result.stdout


def test_failure_exit_code(tmp_path):
    result = StepExecutor().execute(step(f'{PYTHON} -c "raise SystemExit(7)"'), str(tmp_path))
    assert result.exit_code == 7


def test_timeout_is_captured(tmp_path):
    result = StepExecutor().execute(step(f'{PYTHON} -c "import time; time.sleep(2)"', timeout_seconds=1), str(tmp_path))
    assert result.exit_code == 124
    assert result.timed_out is True


def test_stdout_and_stderr_are_captured(tmp_path):
    command = f'{PYTHON} -c "import sys; print(\'out\'); print(\'err\', file=sys.stderr)"'
    result = StepExecutor().execute(step(command), str(tmp_path))
    assert "out" in result.stdout
    assert "err" in result.stderr


def test_process_start_failure_is_clear(tmp_path):
    result = StepExecutor().execute(step("definitely_missing_executable_234"), str(tmp_path))
    assert result.exit_code == 127
    assert "Process start failed" in result.stderr


def test_chained_commands_are_executed_without_shell(tmp_path):
    command = f'{PYTHON} -c "print(1)" && {PYTHON} -c "print(2)"'
    result = StepExecutor().execute(step(command), str(tmp_path))
    assert result.exit_code == 0
    assert "1" in result.stdout and "2" in result.stdout


def test_duration_is_recorded(tmp_path):
    assert StepExecutor().execute(step(f'{PYTHON} --version'), str(tmp_path)).duration_ms >= 0
