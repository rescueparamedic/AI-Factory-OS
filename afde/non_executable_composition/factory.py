"""Explicit constructor composition for non-executable AFDE capabilities."""
from __future__ import annotations

from collections.abc import Iterable

from afde.execution_path import ExecutionPathService
from afde.planner_resolution import PlannerResolutionService
from afde.resolver import CapabilityResolver, KnowledgeProvider
from afde.runtime_integration import (
    RuntimeIntegrationPolicy,
    RuntimeIntegrationService,
)
from afde.tool_adapter_contract import ToolAdapterContractService
from afde.tool_catalog import ToolAdapterCatalog, ToolAdapterDescriptor
from afde.tool_selection import ToolAdapterSelectionService

from .models import NonExecutableComposition


_KNOWLEDGE_PROVIDER_METHODS = (
    "get_capability",
    "capability_context",
    "gaps",
    "get_knowledge",
    "get_document",
    "reference_priority",
)


def build_non_executable_composition(
    *,
    knowledge_provider: KnowledgeProvider,
    adapter_descriptors: Iterable[ToolAdapterDescriptor],
    runtime_policy: RuntimeIntegrationPolicy,
) -> NonExecutableComposition:
    """Construct the seven services without invoking operational behavior."""

    if any(
        not callable(getattr(knowledge_provider, name, None))
        for name in _KNOWLEDGE_PROVIDER_METHODS
    ):
        raise TypeError(
            "knowledge_provider must implement the read-only "
            "KnowledgeProvider boundary"
        )
    if not isinstance(runtime_policy, RuntimeIntegrationPolicy):
        raise TypeError("runtime_policy must be a RuntimeIntegrationPolicy")

    capability_resolver = CapabilityResolver(knowledge_provider)
    planner_resolution = PlannerResolutionService(capability_resolver)
    tool_adapter_catalog = ToolAdapterCatalog(adapter_descriptors)
    tool_adapter_selection = ToolAdapterSelectionService(
        tool_adapter_catalog
    )
    execution_path = ExecutionPathService(tool_adapter_catalog)
    runtime_integration = RuntimeIntegrationService(runtime_policy)
    tool_adapter_contract = ToolAdapterContractService(tool_adapter_catalog)

    return NonExecutableComposition(
        capability_resolver=capability_resolver,
        planner_resolution=planner_resolution,
        tool_adapter_catalog=tool_adapter_catalog,
        tool_adapter_selection=tool_adapter_selection,
        execution_path=execution_path,
        runtime_integration=runtime_integration,
        tool_adapter_contract=tool_adapter_contract,
        runtime_allowed=False,
        execution_allowed=False,
    )
