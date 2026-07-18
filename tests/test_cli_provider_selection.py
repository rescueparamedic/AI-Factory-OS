import json
from types import SimpleNamespace

import pytest

from afde import cli
from real_worker_runtime.errors import ProviderConfigurationError
from real_worker_runtime.runtime import RealWorkerRuntime
from tests.test_real_worker_runtime_openai import WorkerResponses


def test_factory_demo_forwards_provider_model_and_live_opt_in(
    tmp_path, monkeypatch, capsys,
):
    calls = []

    class Runtime:
        def __init__(self, root):
            self.root = root

        def run(self, *args, **kwargs):
            calls.append((args, kwargs))
            return SimpleNamespace(
                to_dict=lambda: {"status": "completed"},
                session_id="RWS-test", status="completed", messages=[],
                progress=100, artifacts=[], pending_approval=None,
            )

    monkeypatch.setattr(cli, "RealWorkerRuntime", Runtime)
    monkeypatch.chdir(tmp_path)

    cli.main([
        "factory-demo", "--request", "provider selection",
        "--provider", "openai", "--model", "test-model",
        "--allow-live-api", "--no-live", "--json",
    ])

    assert json.loads(capsys.readouterr().out)["status"] == "completed"
    positional, keyword = calls[0]
    assert positional[1] == "openai"
    assert positional[5] == "test-model"
    assert positional[6] is True
    assert keyword["enable_controlled_execution"] is False


def test_factory_demo_blocks_live_api_without_flag(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-placeholder")
    monkeypatch.chdir(tmp_path)

    with pytest.raises(ProviderConfigurationError, match="opt-in"):
        cli.main([
            "factory-demo", "--request", "blocked", "--provider", "openai",
            "--no-live", "--json",
        ])


def test_live_runtime_records_provider_evidence(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-placeholder")
    client = SimpleNamespace(responses=WorkerResponses())

    session = RealWorkerRuntime(tmp_path).run(
        "provider evidence", provider="openai", model="test-model",
        live=False, allow_live_api=True, openai_client=client,
    )

    assert session.execution_verification["provider"] == "openai"
    assert session.execution_verification["model"] == "test-model"
    assert session.execution_verification["execution_mode"] == "live"
    events = (
        tmp_path / "data" / "runtime_sessions" / session.session_id / "events.jsonl"
    ).read_text(encoding="utf-8")
    selected = next(
        json.loads(line) for line in events.splitlines()
        if json.loads(line)["event"] == "PROVIDER_SELECTED"
    )
    assert selected["metadata"] == {
        "provider": "openai", "model": "test-model", "execution_mode": "live",
    }
