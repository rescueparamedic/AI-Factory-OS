"""Product presentation derived only from existing Operator projections."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from afde.operator.models import OperatorResult

from .models import ProductRunView


def project_operator_result(result: OperatorResult) -> ProductRunView:
    """Convert an Operator result without changing its status or next action."""
    references = tuple(
        str(item.get("reference"))
        for item in result.evidence
        if isinstance(item, Mapping) and item.get("reference") is not None
    )
    return ProductRunView(
        status=result.status,
        session_id=result.session_id,
        goal=result.request,
        provider=result.provider,
        current_activity=_optional(result.summary),
        approval_id=result.approval_id,
        next_action=_optional(result.next_action),
        evidence_references=references,
        history_hint=_optional(result.history_hint),
        dashboard_hint=_optional(result.dashboard_hint),
        error=result.summary if result.status == "failed" else None,
    )


def _optional(value: Any) -> str | None:
    return str(value) if value not in (None, "") else None
