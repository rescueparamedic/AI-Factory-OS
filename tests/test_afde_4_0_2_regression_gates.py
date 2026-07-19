"""AFDE-4.0.2 release-gate regression validation.

These tests describe existing Beta contracts across component boundaries. They
must not introduce product behavior or call a paid/external Provider.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from real_worker_runtime import RealWorkerRuntime, RuntimeDashboard
from real_worker_runtime.errors import RuntimeSessionError


REPOSITORY_ROOT = Path(__file__).parents[1]


def _pause_runtime(root: Path):
    fixture = root / "tests" / "fixtures" / "afde_2_7_approval_target.txt"
    fixture.parent.mkdir(parents=True)
    fixture.write_text("approval_state=baseline\n", encoding="utf-8")
    test_file = root / "tests" / "test_afde_2_7_fixture.py"
    test_file.write_text(
        "from pathlib import Path\n"
        "def test_state():\n"
        " p=Path(__file__).parent/'fixtures'/'afde_2_7_approval_target.txt'\n"
        " assert p.read_text() in {'approval_state=baseline\\n','approval_state=approved\\n'}\n",
        encoding="utf-8",
    )
    session = RealWorkerRuntime(root).run(
        "[approval-resume-mvp]", live=False,
        enable_controlled_execution=True,
    )
    return fixture, session, session.pending_approval["approval_request_id"]


def _events(root: Path, session_id: str) -> list[dict]:
    path = root / "data" / "runtime_sessions" / session_id / "events.jsonl"
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def _run_cli(*arguments: str) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment.pop("OPENAI_API_KEY", None)
    environment["AI_FACTORY_RUN_LIVE_OPENAI_TESTS"] = "0"
    return subprocess.run(
        [sys.executable, "-m", "afde.cli", *arguments],
        cwd=REPOSITORY_ROOT, env=environment, capture_output=True, text=True,
        check=False,
    )


def test_release_gate_runtime_cancel_is_consistent_and_auditable(tmp_path):
    fixture, waiting, approval_id = _pause_runtime(tmp_path)

    cancelled = RealWorkerRuntime(tmp_path).cancel(waiting.session_id)
    persisted = RealWorkerRuntime(tmp_path).status(waiting.session_id)
    snapshot = RuntimeDashboard(tmp_path).snapshot(waiting.session_id)
    events = _events(tmp_path, waiting.session_id)

    assert cancelled["status"] == persisted["status"] == "cancelled"
    assert snapshot["runtime_status"] == "Cancelled"
    assert any(
        event["event_type"] == "SESSION_CANCELLED"
        and event["status"] == "cancelled"
        for event in events
    )
    with pytest.raises(RuntimeSessionError):
        RealWorkerRuntime(tmp_path).approval_approve(approval_id)
    assert fixture.read_text(encoding="utf-8") == "approval_state=baseline\n"


@pytest.mark.parametrize("operation", ["status", "report", "cancel"])
def test_release_gate_runtime_session_boundary_rejects_traversal(
    tmp_path, operation,
):
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "session.json").write_text(
        json.dumps({"status": "running", "sentinel": "outside-boundary"}),
        encoding="utf-8",
    )
    (outside / "final_report.md").write_text(
        "outside-boundary", encoding="utf-8",
    )

    runtime = RealWorkerRuntime(tmp_path)
    with pytest.raises((RuntimeSessionError, ValueError)):
        getattr(runtime, operation)("../../outside")

    assert json.loads((outside / "session.json").read_text(encoding="utf-8")) == {
        "status": "running", "sentinel": "outside-boundary",
    }


@pytest.mark.parametrize(
    "session_id",
    [".", "..", "RWS/session", r"RWS\session", "C:\\outside\\RWS-session"],
)
def test_release_gate_runtime_session_boundary_rejects_invalid_ids(
    tmp_path, session_id,
):
    with pytest.raises(RuntimeSessionError):
        RealWorkerRuntime(tmp_path).status(session_id)


def test_release_gate_cli_process_exit_code_contract(tmp_path):
    completed = _run_cli(
        "execute", "--request", "AFDE-4.0.2 exit-code regression",
        "--provider", "mock", "--workspace", str(tmp_path / "success"),
        "--json",
    )
    invalid = _run_cli(
        "execute", "--request", "invalid provider regression",
        "--provider", "unsupported", "--workspace", str(tmp_path / "invalid"),
        "--json",
    )
    preflight = _run_cli(
        "operator-preflight", "--workspace", str(tmp_path / "missing"),
        "--json",
    )
    missing = _run_cli(
        "runtime-history", "--session-id", "RWS-missing",
        "--workspace", str(tmp_path), "--json",
    )
    corrupt_root = tmp_path / "corrupt"
    corrupt_session = corrupt_root / "data" / "runtime_sessions" / "RWS-corrupt"
    corrupt_session.mkdir(parents=True)
    (corrupt_session / "session.json").write_text("{broken", encoding="utf-8")
    runtime_failure = _run_cli(
        "runtime-status", "--session-id", "RWS-corrupt",
        "--workspace", str(corrupt_root),
    )
    blocked_workspace = tmp_path / "workspace-is-a-file"
    blocked_workspace.write_text("not a directory", encoding="utf-8")
    evidence_failure = _run_cli(
        "execute", "--request", "evidence failure regression",
        "--provider", "mock", "--workspace", str(blocked_workspace), "--json",
    )

    results = {
        0: completed, 2: invalid, 3: preflight, 4: missing,
        5: runtime_failure, 7: evidence_failure,
    }
    for expected, process in results.items():
        assert process.returncode == expected, process.stdout + process.stderr
        assert "Traceback" not in process.stdout + process.stderr


def test_release_gate_runtime_evidence_is_cross_file_consistent(tmp_path):
    session = RealWorkerRuntime(tmp_path).run(
        "AFDE-4.0.2 evidence consistency", live=False,
    )
    directory = tmp_path / "data" / "runtime_sessions" / session.session_id
    persisted = json.loads((directory / "session.json").read_text(encoding="utf-8"))
    index = json.loads((directory / "artifact_index.json").read_text(encoding="utf-8"))
    events = _events(tmp_path, session.session_id)
    report = (directory / "final_report.md").read_text(encoding="utf-8")

    assert persisted["session_id"] == session.session_id
    assert persisted["status"] == session.status == "completed"
    assert index == persisted["artifacts"]
    assert all(
        Path(item["path"]).is_file()
        and Path(item["path"]).resolve().is_relative_to(directory.resolve())
        for item in index
    )
    assert events[-1]["event"] == "RUNTIME_COMPLETED"
    assert events[-1]["session_id"] == session.session_id
    assert events[-1]["detail"] == persisted["status"]
    assert session.session_id in report
    assert persisted["status"].upper() in report.upper()
