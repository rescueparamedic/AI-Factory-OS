"""Credential-safe human and JSON presentation for operator results."""
from __future__ import annotations

import json
from typing import Any

from approval_guardian.audit import redact_command

from .models import OperatorResult, PreflightResult


def safe_text(value: Any) -> str:
    return redact_command(str(value or ""))


def render_json(value: OperatorResult | PreflightResult) -> str:
    return json.dumps(value.to_dict(), ensure_ascii=False, indent=2)


def render_preflight(value: PreflightResult) -> str:
    lines = [
        "AI Factory OS - Operator Preflight",
        f"Result: {value.status}",
        f"Provider: {value.provider}",
        f"Workspace: {value.workspace}",
    ]
    for check in value.checks:
        lines.append(f"[{check.status}] {check.name}: {safe_text(check.summary)}")
    if value.blocking:
        lines.append("Next: resolve FAIL checks, then rerun this exact preflight command.")
    return "\n".join(lines)


def render_result(value: OperatorResult) -> str:
    lines = [
        "AI Factory OS - Operator Workflow",
        f"Status: {value.status}",
        f"Session ID: {value.session_id or '-'}",
        f"Provider: {value.provider}",
        f"Summary: {safe_text(value.summary)}",
    ]
    if value.approval_id:
        lines.append(f"Approval ID: {value.approval_id}")
    if value.next_action:
        lines.append(f"Next: {value.next_action}")
    if value.evidence:
        lines.append("Evidence:")
        for item in value.evidence:
            lines.append(f"- {safe_text(item.get('type'))}: {safe_text(item.get('reference'))}")
    if value.history_hint:
        lines.append(f"History: {value.history_hint}")
    if value.dashboard_hint:
        lines.append(f"Dashboard: {value.dashboard_hint}")
    return "\n".join(lines)
