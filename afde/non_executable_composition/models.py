"""Immutable container for the non-executable AFDE capability composition."""
from __future__ import annotations

from dataclasses import dataclass

from afde.execution_path import ExecutionPathService
from afde.planner_resolution import PlannerResolutionService
from afde.resolver import CapabilityResolver
from afde.runtime_integration import RuntimeIntegrationService
from afde.tool_adapter_contract import ToolAdapterContractService
from afde.tool_catalog import ToolAdapterCatalog
from afde.tool_selection import ToolAdapterSelectionService


@dataclass(frozen=True)
class NonExecutableComposition:
    """Seven constructed capability services with no execution facade."""

    capability_resolver: CapabilityResolver
    planner_resolution: PlannerResolutionService
    tool_adapter_catalog: ToolAdapterCatalog
    tool_adapter_selection: ToolAdapterSelectionService
    execution_path: ExecutionPathService
    runtime_integration: RuntimeIntegrationService
    tool_adapter_contract: ToolAdapterContractService
    runtime_allowed: bool = False
    execution_allowed: bool = False

    def __post_init__(self) -> None:
        expected = (
            (
                "capability_resolver",
                self.capability_resolver,
                CapabilityResolver,
            ),
            (
                "planner_resolution",
                self.planner_resolution,
                PlannerResolutionService,
            ),
            (
                "tool_adapter_catalog",
                self.tool_adapter_catalog,
                ToolAdapterCatalog,
            ),
            (
                "tool_adapter_selection",
                self.tool_adapter_selection,
                ToolAdapterSelectionService,
            ),
            ("execution_path", self.execution_path, ExecutionPathService),
            (
                "runtime_integration",
                self.runtime_integration,
                RuntimeIntegrationService,
            ),
            (
                "tool_adapter_contract",
                self.tool_adapter_contract,
                ToolAdapterContractService,
            ),
        )
        for name, value, expected_type in expected:
            if not isinstance(value, expected_type):
                raise TypeError(f"{name} must be a {expected_type.__name__}")
        catalog = self.tool_adapter_catalog
        if (
            self.tool_adapter_selection._candidate_source is not catalog
            or self.execution_path._catalog is not catalog
            or self.tool_adapter_contract._lookup is not catalog
        ):
            raise ValueError(
                "Selection, Execution Path, and Tool Adapter Contract "
                "must share one ToolAdapterCatalog"
            )
        if not isinstance(self.runtime_allowed, bool) or self.runtime_allowed:
            raise ValueError("composition cannot allow Runtime")
        if (
            not isinstance(self.execution_allowed, bool)
            or self.execution_allowed
        ):
            raise ValueError("composition cannot allow execution")
