from __future__ import annotations

import subprocess

from afde.operator import OperatorPreflight


def _repository(path):
    subprocess.run(
        ["git", "init", "-q"], cwd=path, check=True,
        capture_output=True, text=True,
    )


def test_mock_preflight_passes_in_clean_repository(tmp_path):
    _repository(tmp_path)

    result = OperatorPreflight(tmp_path, "mock").run()

    assert result.blocking is False
    assert result.status == "PASS"
    assert {item.name for item in result.checks} >= {
        "runtime_availability", "workspace", "repository", "provider",
        "live_provider_opt_in", "controlled_execution", "runtime_data_path",
        "credential_output",
    }


def test_preflight_reports_dirty_repository_without_mutating_it(tmp_path):
    _repository(tmp_path)
    marker = tmp_path / "operator-marker.txt"
    marker.write_text("unchanged\n", encoding="utf-8")
    before = marker.read_bytes()

    result = OperatorPreflight(tmp_path, "mock").run()

    repository = next(item for item in result.checks if item.name == "repository")
    assert repository.status == "WARN"
    assert repository.details["working_tree"] == "dirty"
    assert marker.read_bytes() == before


def test_unknown_and_unopted_live_providers_block(tmp_path, monkeypatch):
    _repository(tmp_path)
    unknown = OperatorPreflight(tmp_path, "unknown").run()
    assert unknown.blocking is True
    assert next(item for item in unknown.checks if item.name == "provider").status == "FAIL"

    monkeypatch.setenv("OPENAI_API_KEY", "test-only-not-rendered")
    live = OperatorPreflight(tmp_path, "openai", allow_live_api=False).run()
    assert live.blocking is True
    assert next(
        item for item in live.checks if item.name == "live_provider_opt_in"
    ).status == "FAIL"
    assert "test-only-not-rendered" not in str(live.to_dict())


def test_windows_workspace_projection_uses_resolved_path(tmp_path):
    _repository(tmp_path)

    result = OperatorPreflight(str(tmp_path), "mock").run()

    assert result.workspace == str(tmp_path.resolve())
    assert result.to_dict()["workspace"] == str(tmp_path.resolve())
