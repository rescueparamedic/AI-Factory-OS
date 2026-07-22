"""Read-only Product Layer projections over existing Operator results."""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass
from typing import Any

from afde.operator.models import OPERATOR_STATUSES


@dataclass(frozen=True)
class ProductRunView:
    """Immutable, non-persisted view of an existing Runtime session."""

    status: str
    goal: str
    provider: str
    session_id: str | None = None
    current_activity: str | None = None
    approval_id: str | None = None
    next_action: str | None = None
    evidence_references: tuple[str, ...] = ()
    history_hint: str | None = None
    dashboard_hint: str | None = None
    error: str | None = None

    def __post_init__(self) -> None:
        if self.status not in OPERATOR_STATUSES:
            raise ValueError(f"unsupported product status: {self.status}")
        for field_name in ("goal", "provider"):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{field_name} must not be empty")
        if isinstance(self.evidence_references, (str, bytes, Mapping)):
            raise TypeError("evidence_references must be a sequence of strings")
        references = tuple(self.evidence_references)
        if any(not isinstance(reference, str) for reference in references):
            raise TypeError("evidence_references must contain only strings")
        object.__setattr__(self, "evidence_references", references)

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["evidence_references"] = list(self.evidence_references)
        return value
