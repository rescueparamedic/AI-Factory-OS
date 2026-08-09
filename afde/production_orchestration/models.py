"""Immutable public contracts for production Planner-to-Runtime orchestration."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Any, Mapping

from afde.production_adapter_runtime_execution import (
    ProductionAdapterRuntimeExecutionResult,
)

from .errors import (
    InvalidProductionOrchestrationRequestError,
    InvalidProductionOrchestrationResultError,
)


class ProductionOrchestrationStatus(str, Enum):
    """Small fail-closed outcome model for one orchestration attempt."""

    COMPLETED = "completed"
    BLOCKED = "blocked"
    REJECTED = "rejected"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True)
class ProductionOrchestrationRequest:
    """Minimum governed Planner input and execution metadata references."""

    goal: str
    capability_id: str
    requested_scope: str | None = None
    minimum_maturity: str | None = None
    require_operational: bool = False
    constraints: Mapping[str, Any] = field(default_factory=dict)
    invocation_metadata_references: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        error = InvalidProductionOrchestrationRequestError
        for name in ("goal", "capability_id"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise error(f"{name} must be a non-empty string")
        for name in ("requested_scope", "minimum_maturity"):
            value = getattr(self, name)
            if value is not None and (
                not isinstance(value, str) or not value.strip()
            ):
                raise error(f"{name} must be a non-empty string or None")
        if not isinstance(self.require_operational, bool):
            raise error("require_operational must be a boolean")
        if not isinstance(self.constraints, Mapping):
            raise error("constraints must be a mapping")
        frozen: dict[str, Any] = {}
        for key, value in self.constraints.items():
            if not isinstance(key, str) or not key.strip():
                raise error("constraint keys must be non-empty strings")
            frozen[key.strip()] = _freeze(value)
        references = _strings(
            self.invocation_metadata_references,
            "invocation_metadata_references",
            error,
        )
        object.__setattr__(self, "goal", self.goal.strip())
        object.__setattr__(self, "capability_id", self.capability_id.strip())
        object.__setattr__(self, "constraints", MappingProxyType(frozen))
        object.__setattr__(self, "invocation_metadata_references", references)


@dataclass(frozen=True)
class ProductionOrchestrationResult:
    """Top-level outcome retaining identities but never execution authority."""

    status: ProductionOrchestrationStatus
    capability_id: str | None
    adapter_id: str | None
    path_id: str | None
    projection_id: str | None
    binding_id: str | None
    runtime_execution_result: ProductionAdapterRuntimeExecutionResult | None
    blocked_reason: str | None
    trace: tuple[str, ...]
    runtime_allowed: bool = False
    execution_allowed: bool = False

    def __post_init__(self) -> None:
        error = InvalidProductionOrchestrationResultError
        if not isinstance(self.status, ProductionOrchestrationStatus):
            raise error("status is invalid")
        for name in (
            "capability_id", "adapter_id", "path_id", "projection_id",
            "binding_id", "blocked_reason",
        ):
            value = getattr(self, name)
            if value is not None and (
                not isinstance(value, str) or not value.strip()
            ):
                raise error(f"{name} must be a non-empty string or None")
        completed = self.status is ProductionOrchestrationStatus.COMPLETED
        if completed != isinstance(
            self.runtime_execution_result,
            ProductionAdapterRuntimeExecutionResult,
        ):
            raise error("Runtime execution result conflicts with status")
        if completed:
            execution = self.runtime_execution_result
            assert execution is not None
            if (
                self.blocked_reason is not None
                or self.capability_id != execution.capability_id
                or self.adapter_id != execution.adapter_id
                or self.path_id != execution.path_id
                or self.projection_id != execution.projection_id
                or self.binding_id != execution.binding_id
            ):
                raise error("completed orchestration identities conflict")
        elif self.blocked_reason is None:
            raise error("non-completed orchestration requires a reason")
        trace = _strings(self.trace, "trace", error)
        if not trace:
            raise error("trace must not be empty")
        if self.runtime_allowed is not False or self.execution_allowed is not False:
            raise error("orchestration result cannot propagate execution authority")
        object.__setattr__(self, "trace", trace)


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({
            str(key): _freeze(item) for key, item in value.items()
        })
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    if isinstance(value, set):
        return frozenset(_freeze(item) for item in value)
    return value


def _strings(values: object, name: str, error: type[Exception]) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)):
        raise error(f"{name} must be a tuple of strings")
    try:
        snapshot = tuple(values)
    except TypeError as exc:
        raise error(f"{name} must be a tuple of strings") from exc
    if any(not isinstance(item, str) or not item.strip() for item in snapshot):
        raise error(f"{name} contains an invalid string")
    return snapshot
