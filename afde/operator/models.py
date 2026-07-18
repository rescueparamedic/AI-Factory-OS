"""Public result contracts for the operator workflow."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


OPERATOR_STATUSES = {
    "running", "waiting_approval", "blocked", "completed", "failed",
}


@dataclass(frozen=True)
class PreflightCheck:
    name: str
    status: str
    summary: str
    details: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.status not in {"PASS", "WARN", "FAIL"}:
            raise ValueError("preflight status must be PASS, WARN, or FAIL")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PreflightResult:
    status: str
    blocking: bool
    provider: str
    workspace: str
    checks: tuple[PreflightCheck, ...]

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["checks"] = [item.to_dict() for item in self.checks]
        return value


@dataclass(frozen=True)
class OperatorResult:
    status: str
    session_id: str | None
    request: str
    provider: str
    approval_id: str | None
    summary: str
    next_action: str
    evidence: tuple[dict[str, Any], ...] = ()
    dashboard_hint: str = ""
    history_hint: str = ""

    def __post_init__(self) -> None:
        if self.status not in OPERATOR_STATUSES:
            raise ValueError(f"unsupported operator status: {self.status}")

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["evidence"] = [dict(item) for item in self.evidence]
        return value
