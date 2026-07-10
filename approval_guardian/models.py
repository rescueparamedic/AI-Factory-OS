from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping


class ApprovalDecision(str, Enum):
    AUTO_APPROVE = "auto_approve"
    ASK_USER = "ask_user"
    DENY = "deny"


@dataclass(frozen=True)
class ApprovalRequest:
    command: str
    cwd: str | None = None
    actor: str | None = None
    task_id: str | None = None
    branch: str | None = None
    environment: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ApprovalResult:
    decision: ApprovalDecision
    risk_level: str
    rule_id: str
    reason: str
    normalized_command: str
    requires_human: bool
