"""Construct the official static production Tool Adapter Registry."""
from __future__ import annotations

from afde.operational_adapter_registry import OperationalAdapterRegistry
from afde.tool_catalog import (
    AdapterAvailability,
    CostClassification,
    ExecutionContract,
    PrivacyClassification,
    RuntimeCompatibility,
    ToolAdapterDescriptor,
)


def build_production_adapter_registry() -> OperationalAdapterRegistry:
    """Return an independent Registry with approved production metadata."""

    descriptor = ToolAdapterDescriptor(
        adapter_id="adapter.codex_automation_bridge",
        display_name="Codex Automation Bridge",
        version="1.0.0",
        supported_capability_ids=("CAP-TOOLADAPTER-CONTRACT-0001",),
        availability=AdapterAvailability.AVAILABLE,
        runtime_compatibility=RuntimeCompatibility.COMPATIBLE,
        execution_contract=ExecutionContract.CONTROLLED_RUNTIME,
        privacy_classification=PrivacyClassification.EXTERNAL,
        cost_classification=CostClassification.NO_COST,
        credentials_required=True,
        description=(
            "Static production registration metadata for the existing "
            "Codex Automation Bridge."
        ),
        metadata_references=(
            "real_worker_runtime/automation_bridge.py",
            "real_worker_runtime/tool_actions.py",
            "docs/reports/AFDE_3_2_CODEX_AUTOMATION_BRIDGE_REPORT.md",
        ),
    )
    return OperationalAdapterRegistry((descriptor,))
