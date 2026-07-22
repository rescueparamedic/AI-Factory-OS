from __future__ import annotations

import pytest

from afde.operator.models import OperatorResult
from afde.product.presenter import project_operator_result


def operator_result(status: str, **overrides) -> OperatorResult:
    values = {
        "status": status,
        "session_id": "RWS-product-1",
        "request": "Create a release summary",
        "provider": "mock",
        "approval_id": None,
        "summary": "Existing Operator summary",
        "next_action": "",
        "evidence": (),
        "dashboard_hint": "",
        "history_hint": "",
    }
    values.update(overrides)
    return OperatorResult(**values)


def test_completed_projection_preserves_existing_references():
    result = operator_result(
        "completed",
        evidence=(
            {"type": "artifact", "reference": "artifacts/result.py"},
            {"type": "runtime_history", "reference": "12 persisted events"},
        ),
        history_hint="runtime-history --session-id RWS-product-1",
        dashboard_hint="runtime-dashboard --session-id RWS-product-1",
    )

    view = project_operator_result(result)

    assert view.status == result.status
    assert view.session_id == result.session_id
    assert view.goal == result.request
    assert view.current_activity == result.summary
    assert view.evidence_references == (
        "artifacts/result.py",
        "12 persisted events",
    )
    assert view.history_hint == result.history_hint
    assert view.dashboard_hint == result.dashboard_hint
    assert view.error is None


def test_waiting_approval_projection_preserves_exact_next_action():
    result = operator_result(
        "waiting_approval",
        approval_id="APR-product-1",
        next_action=(
            "python -m afde.cli operator-approve "
            "--session-id RWS-product-1 --approval-id APR-product-1"
        ),
    )

    view = project_operator_result(result)

    assert view.status == "waiting_approval"
    assert view.approval_id == "APR-product-1"
    assert view.next_action == result.next_action


def test_failed_and_missing_optional_projection():
    result = operator_result(
        "failed",
        session_id=None,
        summary="Existing failure meaning",
    )

    view = project_operator_result(result)

    assert view.status == "failed"
    assert view.session_id is None
    assert view.next_action is None
    assert view.history_hint is None
    assert view.dashboard_hint is None
    assert view.evidence_references == ()
    assert view.error == "Existing failure meaning"


def test_presenter_does_not_accept_or_invent_product_status():
    with pytest.raises(ValueError, match="unsupported operator status"):
        operator_result("product_complete")
