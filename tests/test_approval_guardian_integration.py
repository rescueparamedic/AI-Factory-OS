from __future__ import annotations

import json

from afde.cli import main
from approval_guardian.adapters import ExecPolicyAdapter


def test_cli_auto_approve_response_schema(capsys, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    main(["approval-check", "--command", "git status", "--branch", "feature/test"])
    result = json.loads(capsys.readouterr().out)
    assert result["decision"] == "auto_approve"
    assert result["requires_human"] is False
    assert result["rule_id"] == "AGV2-S001"


def test_cli_ask_user_stops_automatic_progress(capsys, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    main(["approval-check", "--command", "git push origin main", "--branch", "feature/test"])
    result = json.loads(capsys.readouterr().out)
    assert result["decision"] == "ask_user"
    assert result["requires_human"] is True


def test_cli_deny_has_no_human_override_choice(capsys, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    main(["approval-check", "--command", "git reset --hard", "--branch", "feature/test"])
    result = json.loads(capsys.readouterr().out)
    assert result["decision"] == "deny"
    assert result["requires_human"] is False


def test_exec_policy_adapter_preserves_v1_decisions():
    adapter = ExecPolicyAdapter()
    assert adapter.adapt("allow", "git status").decision.value == "auto_approve"
    assert adapter.adapt("prompt", "git push").decision.value == "ask_user"
    assert adapter.adapt("forbidden", "git clean -fd").decision.value == "deny"
    assert adapter.adapt("unexpected", "unknown").decision.value == "ask_user"
