"""Immutable contracts for governed, non-executable Production Action Planning."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from real_worker_runtime.tool_actions import ToolAction

from .errors import (
    InvalidProductionActionPlanningRequestError,
    InvalidProductionActionProposalError,
)


MAX_REQUEST_CHARACTERS = 1000
_ALLOWED_PLAN_ACTION_TYPES = frozenset({
    "FILE_READ", "GIT_STATUS", "GIT_DIFF",
})


@dataclass(frozen=True)
class ProductionActionPlanningRequest:
    """Ordinary caller inputs with no execution identity or credential fields."""

    workspace: Path
    request: str

    def __post_init__(self) -> None:
        try:
            workspace = Path(self.workspace).expanduser().resolve(strict=True)
        except (OSError, TypeError, ValueError) as exc:
            raise InvalidProductionActionPlanningRequestError(
                "workspace must be an existing directory"
            ) from exc
        if not workspace.is_dir():
            raise InvalidProductionActionPlanningRequestError(
                "workspace must be an existing directory"
            )
        if not isinstance(self.request, str):
            raise InvalidProductionActionPlanningRequestError(
                "request must be a string"
            )
        request = self.request.strip()
        if not request:
            raise InvalidProductionActionPlanningRequestError(
                "request must not be empty"
            )
        if len(request) > MAX_REQUEST_CHARACTERS:
            raise InvalidProductionActionPlanningRequestError(
                "request must not exceed 1000 characters"
            )
        object.__setattr__(self, "workspace", workspace)
        object.__setattr__(self, "request", request)


@dataclass(frozen=True)
class ProductionActionPlan:
    """Exactly one validated ToolAction and no Runtime execution authority."""

    capability_id: str
    task_id: str
    worker_id: str
    runtime_session_id: str
    runtime_provider: str
    runtime_model: str
    execution_mode: str
    planning_provider: str
    planning_model: str
    tool_action: ToolAction
    runtime_allowed: bool = False
    execution_allowed: bool = False

    def __post_init__(self) -> None:
        identities = (
            self.capability_id,
            self.task_id,
            self.worker_id,
            self.runtime_session_id,
            self.runtime_provider,
            self.runtime_model,
            self.execution_mode,
            self.planning_provider,
            self.planning_model,
        )
        if any(
            not isinstance(value, str)
            or not value
            or value != value.strip()
            for value in identities
        ):
            raise InvalidProductionActionProposalError(
                "plan identities must be exact non-empty strings"
            )
        if type(self.tool_action) is not ToolAction:
            raise InvalidProductionActionProposalError(
                "plan must contain exactly one existing ToolAction"
            )
        if self.tool_action.runtime_task_id != self.task_id:
            raise InvalidProductionActionProposalError(
                "plan task identity must match ToolAction context"
            )
        if self.tool_action.runtime_session_id != self.runtime_session_id:
            raise InvalidProductionActionProposalError(
                "plan session identity must match ToolAction context"
            )
        if self.tool_action.source_worker != self.worker_id:
            raise InvalidProductionActionProposalError(
                "plan worker identity must match ToolAction context"
            )
        if self.capability_id != "CAP-TOOLADAPTER-CONTRACT-0001":
            raise InvalidProductionActionProposalError(
                "plan must use the approved existing capability"
            )
        if self.worker_id != "development_worker":
            raise InvalidProductionActionProposalError(
                "plan must use the fixed planning worker"
            )
        if (
            self.runtime_provider != "codex_automation_bridge"
            or self.runtime_model != "controlled-runtime"
            or self.execution_mode != "production_adapter_runtime"
        ):
            raise InvalidProductionActionProposalError(
                "plan must use fixed future Production Runtime metadata"
            )
        if self.tool_action.action_type.value not in _ALLOWED_PLAN_ACTION_TYPES:
            raise InvalidProductionActionProposalError(
                "plan ToolAction must be in the read-only action allowlist"
            )
        if self.tool_action.metadata.get("capability_id") != self.capability_id:
            raise InvalidProductionActionProposalError(
                "plan capability must match ToolAction provenance"
            )
        if (
            self.tool_action.metadata.get("planning_provider")
            != self.planning_provider
            or self.tool_action.metadata.get("planning_model")
            != self.planning_model
        ):
            raise InvalidProductionActionProposalError(
                "plan provider metadata must match ToolAction provenance"
            )
        if (
            not isinstance(self.runtime_allowed, bool)
            or self.runtime_allowed
            or not isinstance(self.execution_allowed, bool)
            or self.execution_allowed
        ):
            raise InvalidProductionActionProposalError(
                "plan cannot grant Runtime or execution authority"
            )
