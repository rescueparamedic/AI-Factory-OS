"""Concrete Production Adapter binding for the existing Codex bridge."""

from .adapter import (
    CODEX_AUTOMATION_BRIDGE_ADAPTER_ID,
    CodexAutomationBridgeProductionFactory,
    CodexAutomationBridgeProductionInvocationTarget,
)

__all__ = [
    "CODEX_AUTOMATION_BRIDGE_ADAPTER_ID",
    "CodexAutomationBridgeProductionFactory",
    "CodexAutomationBridgeProductionInvocationTarget",
]
