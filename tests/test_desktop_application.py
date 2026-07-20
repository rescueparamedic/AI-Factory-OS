import json
from pathlib import Path
import subprocess

import pytest

from afde.desktop import (
    DesktopExecutionError,
    DesktopExecutionService,
    DesktopStatus,
    view_state,
)


def _payload(workspace: Path, **values):
    session_id = values.pop("session_id", "RWS-BETA-desktop")
    relative = Path("data") / "runtime_sessions" / session_id / "execution_evidence.json"
    path = workspace / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{}", encoding="utf-8")
    return {
        "status": "completed",
        "session_id": session_id,
        "provider": "mock",
        "execution_mode": "deterministic_mock",
        "evidence_path": relative.as_posix(),
        "exit_code": 0,
        **values,
    }


def _completed(payload, *, returncode=0, stderr=""):
    return subprocess.CompletedProcess(
        args=["python"], returncode=returncode,
        stdout=json.dumps(payload), stderr=stderr,
    )


def test_valid_workspace_and_request_build_mock_only_command(tmp_path):
    service = DesktopExecutionService()
    request = service.validate(str(tmp_path), "Read-only readiness review")

    command = service.build_command(request)

    assert request.workspace == tmp_path.resolve()
    assert command[:4] == (command[0], "-m", "afde.cli", "execute")
    assert command[command.index("--provider") + 1] == "mock"
    assert "--allow-live-api" not in command
    assert "openai" not in command


def test_desktop_environment_disables_live_provider(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-never-forward")
    monkeypatch.setenv("AI_FACTORY_RUN_LIVE_OPENAI_TESTS", "1")

    environment = DesktopExecutionService().safe_environment()

    assert environment["OPENAI_API_KEY"] == ""
    assert environment["AI_FACTORY_RUN_LIVE_OPENAI_TESTS"] == "0"


def test_success_json_extracts_session_and_absolute_evidence(tmp_path):
    payload = _payload(tmp_path)
    service = DesktopExecutionService()

    result = service.parse_completed(tmp_path, _completed(payload))

    assert result.session_id == "RWS-BETA-desktop"
    assert result.provider == "mock"
    assert result.execution_mode == "deterministic_mock"
    assert result.evidence_path.is_absolute()
    assert result.evidence_path.is_file()
    assert result.exit_code == 0


def test_execute_uses_runner_without_live_options(tmp_path):
    observed = {}
    payload = _payload(tmp_path)

    def runner(command, **kwargs):
        observed["command"] = command
        observed["kwargs"] = kwargs
        return _completed(payload)

    result = DesktopExecutionService(runner=runner).execute(
        str(tmp_path), "Assess the repository",
    )

    assert result.session_id == payload["session_id"]
    assert observed["command"][observed["command"].index("--provider") + 1] == "mock"
    assert observed["kwargs"]["env"]["OPENAI_API_KEY"] == ""
    assert observed["kwargs"]["env"]["AI_FACTORY_RUN_LIVE_OPENAI_TESTS"] == "0"


def test_service_executes_official_mock_cli(tmp_path):
    result = DesktopExecutionService().execute(
        str(tmp_path), "Create one bounded Desktop integration result",
    )

    assert result.status == "completed"
    assert result.provider == "mock"
    assert result.execution_mode == "deterministic_mock"
    assert result.session_id.startswith("RWS-BETA-")
    assert result.evidence_path.is_file()


@pytest.mark.parametrize(
    ("workspace", "goal", "message"),
    [("", "goal", "Workspace"), (None, "goal", "Workspace"), ("valid", "", "Request")],
)
def test_invalid_inputs_are_blocked(tmp_path, workspace, goal, message):
    selected = str(tmp_path) if workspace == "valid" else workspace

    with pytest.raises(DesktopExecutionError, match=message):
        DesktopExecutionService().validate(selected, goal)


def test_missing_workspace_is_blocked(tmp_path):
    missing = tmp_path / "missing"

    with pytest.raises(DesktopExecutionError, match="not found"):
        DesktopExecutionService().validate(str(missing), "goal")


def test_nonzero_exit_preserves_failure_contract(tmp_path):
    payload = {
        "status": "failed",
        "exit_code": 5,
        "error": {"message": "bounded failure", "category": "execution"},
        "cause": "Runtime failed during worker.",
        "next_action": "Inspect Evidence.",
    }

    with pytest.raises(DesktopExecutionError) as captured:
        DesktopExecutionService().parse_completed(
            tmp_path, _completed(payload, returncode=5),
        )

    assert captured.value.exit_code == 5
    assert captured.value.error == "bounded failure"
    assert captured.value.next_action == "Inspect Evidence."


def test_invalid_json_is_reported(tmp_path):
    completed = subprocess.CompletedProcess(
        args=["python"], returncode=0, stdout="not-json", stderr="",
    )

    with pytest.raises(DesktopExecutionError, match="invalid JSON"):
        DesktopExecutionService().parse_completed(tmp_path, completed)


def test_missing_session_id_is_reported(tmp_path):
    payload = _payload(tmp_path)
    payload.pop("session_id")

    with pytest.raises(DesktopExecutionError, match="incomplete"):
        DesktopExecutionService().parse_completed(tmp_path, _completed(payload))


def test_zero_exit_failed_status_is_rejected(tmp_path):
    payload = _payload(tmp_path, status="failed")

    with pytest.raises(DesktopExecutionError, match="did not complete"):
        DesktopExecutionService().parse_completed(tmp_path, _completed(payload))


def test_non_mock_result_is_rejected(tmp_path):
    payload = _payload(tmp_path, provider="openai")

    with pytest.raises(DesktopExecutionError, match="provider boundary"):
        DesktopExecutionService().parse_completed(tmp_path, _completed(payload))


def test_missing_evidence_is_reported(tmp_path):
    payload = _payload(tmp_path)
    (tmp_path / payload["evidence_path"]).unlink()

    with pytest.raises(DesktopExecutionError, match="not found"):
        DesktopExecutionService().parse_completed(tmp_path, _completed(payload))


def test_open_evidence_uses_default_file_boundary(tmp_path):
    path = tmp_path / "execution_evidence.json"
    path.write_text("{}", encoding="utf-8")
    opened = []

    DesktopExecutionService().open_evidence(path, opener=opened.append)

    assert opened == [str(path.resolve())]
    assert path.read_text(encoding="utf-8") == "{}"


def test_desktop_view_states_cover_mvp_transitions():
    idle = view_state(DesktopStatus.IDLE)
    validating = view_state(DesktopStatus.VALIDATING)
    running = view_state(DesktopStatus.RUNNING)
    completed = view_state(DesktopStatus.COMPLETED, evidence_available=True)
    failed = view_state(DesktopStatus.FAILED)

    assert idle.run_enabled and idle.inputs_enabled
    assert not idle.open_evidence_enabled
    assert not validating.inputs_enabled and validating.progress_active
    assert not running.run_enabled and running.progress_active
    assert completed.run_enabled and completed.open_evidence_enabled
    assert failed.run_enabled and not failed.open_evidence_enabled
