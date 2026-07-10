from __future__ import annotations

import json

from afde.cli import main


def definition(path, command="git status"):
    path.write_text(json.dumps({
        "sprint_id": "SPR-CLI", "title": "CLI", "version": "1",
        "steps": [{"step_id": "S1", "name": "step", "command": command}],
    }))
    return path


def output(capsys):
    return json.loads(capsys.readouterr().out)


def test_validate_json_output(tmp_path, capsys, monkeypatch):
    monkeypatch.chdir(tmp_path)
    main(["sprint-validate", "--file", str(definition(tmp_path / "s.json")), "--json"])
    assert output(capsys)["status"] == "valid"


def test_dry_run_json_output(tmp_path, capsys, monkeypatch):
    monkeypatch.chdir(tmp_path)
    main(["sprint-run", "--file", str(definition(tmp_path / "s.json")), "--dry-run", "--json"])
    result = output(capsys)
    assert result["mode"] == "dry_run"
    assert result["steps"][0]["decision"] == "auto_approve"


def test_run_and_status_json_output(tmp_path, capsys, monkeypatch):
    monkeypatch.chdir(tmp_path)
    path = definition(tmp_path / "s.json", "python --version")
    main(["sprint-run", "--file", str(path), "--json"])
    created = output(capsys)
    assert created["status"] == "completed"
    main(["sprint-status", "--run-id", created["run_id"], "--json"])
    assert output(capsys)["run_id"] == created["run_id"]


def test_waiting_run_can_be_cancelled(tmp_path, capsys, monkeypatch):
    monkeypatch.chdir(tmp_path)
    path = definition(tmp_path / "s.json", "git merge feature/test")
    main(["sprint-run", "--file", str(path), "--json"])
    waiting = output(capsys)
    assert waiting["status"] == "waiting_approval"
    main(["sprint-cancel", "--run-id", waiting["run_id"], "--json"])
    assert output(capsys)["status"] == "cancelled"


def test_waiting_run_resume_cli(tmp_path, capsys, monkeypatch):
    monkeypatch.chdir(tmp_path)
    path = definition(tmp_path / "s.json", "git merge feature/test")
    main(["sprint-run", "--file", str(path), "--json"])
    waiting = output(capsys)
    # The command is intentionally not resumed: merge stays approval-sensitive.
    assert waiting["pending_approval"]["step_id"] == "S1"


def test_human_validate_output(tmp_path, capsys, monkeypatch):
    monkeypatch.chdir(tmp_path)
    main(["sprint-validate", "--file", str(definition(tmp_path / "s.json"))])
    assert "Sprint Auto Runner" in capsys.readouterr().out
