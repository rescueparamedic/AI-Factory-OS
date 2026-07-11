from __future__ import annotations

import json

import pytest

from sprint_auto_runner.errors import SprintDefinitionError
from sprint_auto_runner.loader import SprintDefinitionLoader


def write_definition(path, **overrides):
    data = {
        "sprint_id": "SPR-1",
        "title": "Demo",
        "version": "1.0",
        "steps": [{"step_id": "S1", "name": "Status", "command": "git status"}],
        **overrides,
    }
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_load_valid_definition(tmp_path):
    definition = SprintDefinitionLoader().load(write_definition(tmp_path / "sprint.json"))
    assert definition.sprint_id == "SPR-1"
    assert definition.steps[0].command == "git status"
    assert len(definition.fingerprint) == 64


@pytest.mark.parametrize("missing", ["sprint_id", "title", "version", "steps"])
def test_missing_required_field(tmp_path, missing):
    path = write_definition(tmp_path / "sprint.json")
    data = json.loads(path.read_text())
    del data[missing]
    path.write_text(json.dumps(data))
    with pytest.raises(SprintDefinitionError, match="missing required field"):
        SprintDefinitionLoader().load(path)


def test_duplicate_step_id_is_rejected(tmp_path):
    steps = [
        {"step_id": "S1", "name": "one", "command": "git status"},
        {"step_id": "S1", "name": "two", "command": "git diff"},
    ]
    with pytest.raises(SprintDefinitionError, match="duplicate"):
        SprintDefinitionLoader().load(write_definition(tmp_path / "sprint.json", steps=steps))


@pytest.mark.parametrize("command", ["", "   "])
def test_empty_command_is_rejected(tmp_path, command):
    steps = [{"step_id": "S1", "name": "bad", "command": command}]
    with pytest.raises(SprintDefinitionError, match="command"):
        SprintDefinitionLoader().load(write_definition(tmp_path / "sprint.json", steps=steps))


@pytest.mark.parametrize("timeout", [0, -1, 86401, "60", True])
def test_invalid_timeout_is_rejected(tmp_path, timeout):
    steps = [{"step_id": "S1", "name": "bad", "command": "git status", "timeout_seconds": timeout}]
    with pytest.raises(SprintDefinitionError, match="timeout"):
        SprintDefinitionLoader().load(write_definition(tmp_path / "sprint.json", steps=steps))


def test_unknown_environment_is_rejected(tmp_path):
    steps = [{"step_id": "S1", "name": "bad", "command": "git status", "environment": "space"}]
    with pytest.raises(SprintDefinitionError, match="environment"):
        SprintDefinitionLoader().load(write_definition(tmp_path / "sprint.json", steps=steps))


def test_malformed_json_has_clear_error(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text("{")
    with pytest.raises(SprintDefinitionError, match="invalid sprint JSON"):
        SprintDefinitionLoader().load(path)


def test_definition_change_changes_fingerprint(tmp_path):
    path = write_definition(tmp_path / "sprint.json")
    first = SprintDefinitionLoader().load(path).fingerprint
    write_definition(path, title="Changed")
    assert SprintDefinitionLoader().load(path).fingerprint != first
