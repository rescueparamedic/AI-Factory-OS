from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from afde.product.models import ProductRunView


def test_product_run_view_is_frozen_and_has_explicit_defaults():
    view = ProductRunView(status="running", goal="Build a feature", provider="mock")

    assert view.session_id is None
    assert view.current_activity is None
    assert view.approval_id is None
    assert view.next_action is None
    assert view.evidence_references == ()
    assert view.history_hint is None
    assert view.dashboard_hint is None
    assert view.error is None
    with pytest.raises(FrozenInstanceError):
        view.status = "completed"


def test_product_run_view_validates_required_values():
    with pytest.raises(ValueError, match="unsupported product status"):
        ProductRunView(status="invented", goal="Goal", provider="mock")
    with pytest.raises(ValueError, match="goal must not be empty"):
        ProductRunView(status="running", goal=" ", provider="mock")
    with pytest.raises(ValueError, match="provider must not be empty"):
        ProductRunView(status="running", goal="Goal", provider="")


def test_product_run_view_copies_mutable_sequences_and_serializes_fresh_lists():
    source = ["evidence/a.json"]
    view = ProductRunView(
        status="completed",
        goal="Goal",
        provider="mock",
        evidence_references=source,
    )
    source.append("evidence/b.json")

    first = view.to_dict()
    second = view.to_dict()
    first["evidence_references"].append("mutated")

    assert view.evidence_references == ("evidence/a.json",)
    assert second["evidence_references"] == ["evidence/a.json"]
    with pytest.raises(TypeError, match="sequence of strings"):
        ProductRunView(
            status="completed",
            goal="Goal",
            provider="mock",
            evidence_references="not-a-sequence",
        )
    with pytest.raises(TypeError, match="sequence of strings"):
        ProductRunView(
            status="completed",
            goal="Goal",
            provider="mock",
            evidence_references={"mutable": "mapping"},
        )
