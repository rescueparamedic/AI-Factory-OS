from __future__ import annotations

from hashlib import sha256

from afde.operator import OperatorService
from real_worker_runtime import RuntimeDashboard, RuntimeHistoryStore

from test_operator_service import prepare_workspace


def _digest(path):
    return sha256(path.read_bytes()).hexdigest()


def test_canonical_network_free_operator_acceptance_flow(tmp_path):
    fixture = prepare_workspace(tmp_path)
    service = OperatorService(tmp_path)

    preflight = service.preflight("mock")
    assert preflight.blocking is False

    waiting = service.run("Implement the AFDE operator acceptance proof", "mock")
    session_dir = tmp_path / "data" / "runtime_sessions" / waiting.session_id
    assert waiting.status == "waiting_approval"
    assert waiting.approval_id
    assert fixture.read_text(encoding="utf-8") == "approval_state=baseline\n"

    approved = service.approve(waiting.session_id, waiting.approval_id)
    assert (
        f"operator-resume --session-id {waiting.session_id}"
        in approved.next_action
    )
    completed = service.resume(waiting.session_id)

    assert completed.status == "completed"
    assert fixture.read_text(encoding="utf-8") == "approval_state=approved\n"
    assert completed.evidence
    history = RuntimeHistoryStore(tmp_path).events(waiting.session_id)
    assert history
    assert all(item["session_id"] == waiting.session_id for item in history)

    session_path = session_dir / "session.json"
    events_path = session_dir / "events.jsonl"
    before = (_digest(session_path), _digest(events_path))
    status = service.status(waiting.session_id)
    history_again = RuntimeHistoryStore(tmp_path).events(waiting.session_id)
    dashboard = RuntimeDashboard(tmp_path).snapshot(waiting.session_id)
    after = (_digest(session_path), _digest(events_path))

    assert status.status == "completed"
    assert history_again == history
    assert dashboard["session_id"] == waiting.session_id
    assert dashboard["history_summary"]["read_only"] is True
    assert after == before


def test_acceptance_reject_path_never_changes_target(tmp_path):
    fixture = prepare_workspace(tmp_path)
    service = OperatorService(tmp_path)
    waiting = service.run("Demonstrate the operator reject path")

    blocked = service.reject(
        waiting.session_id, waiting.approval_id, "Acceptance rejection proof",
    )

    assert blocked.status == "blocked"
    assert fixture.read_text(encoding="utf-8") == "approval_state=baseline\n"
