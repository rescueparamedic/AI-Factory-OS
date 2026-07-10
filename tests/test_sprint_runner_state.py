from __future__ import annotations

import json

import pytest

from sprint_auto_runner.errors import SprintStateError
from sprint_auto_runner.models import SprintRun, StepResult
from sprint_auto_runner.state_store import SprintStateStore


def run_state():
    return SprintRun("RUN-1", "SPR", "feature/x", "created", 0, "a", "a", None, "", "token", "s.json", "fp", "sha", [StepResult("S1")])


def test_save_and_load_round_trip(tmp_path):
    store = SprintStateStore(tmp_path)
    store.save(run_state())
    assert store.load("RUN-1").step_results[0].step_id == "S1"


def test_state_path_is_under_data(tmp_path):
    assert SprintStateStore(tmp_path).path_for("RUN-1") == tmp_path / "data" / "sprint_runs" / "RUN-1.json"


def test_invalid_run_id_is_rejected(tmp_path):
    with pytest.raises(SprintStateError, match="invalid run_id"):
        SprintStateStore(tmp_path).load("../escape")


def test_missing_state_is_clear(tmp_path):
    with pytest.raises(SprintStateError, match="run not found"):
        SprintStateStore(tmp_path).load("MISSING")


def test_corrupt_state_fails_closed(tmp_path):
    store = SprintStateStore(tmp_path)
    store.path_for("BROKEN").write_text("{")
    with pytest.raises(SprintStateError, match="unreadable"):
        store.load("BROKEN")
