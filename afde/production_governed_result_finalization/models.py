"""Immutable contracts for one governed Production operational result."""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from typing import Any

from afde.production_adapter_runtime_event_collection import (
    ProductionAdapterRuntimeEventCollectionResult,
)
from afde.production_adapter_runtime_event_stream import (
    ProductionAdapterRuntimeEventStreamResult,
)
from afde.production_adapter_runtime_observation import (
    ProductionAdapterRuntimeObservationResult,
)
from afde.production_adapter_worker_execution import (
    ProductionAdapterWorkerExecutionResult,
)
from afde.production_planner_worker_dispatch import (
    ProductionPlannerWorkerDispatchRequest,
    ProductionPlannerWorkerDispatchResult,
)

from .errors import InvalidProductionGovernedResultFinalizationRequestError


class ProductionGovernedResultStatus(str, Enum):
    """Fail-closed final status after every required governance stage."""

    COMPLETED = "completed"
    BLOCKED = "blocked"
    REJECTED = "rejected"
    UNAVAILABLE = "unavailable"
    FINALIZATION_FAILED = "finalization_failed"


@dataclass(frozen=True, slots=True, kw_only=True)
class ProductionGovernedResultFinalizationRequest:
    """The existing Production dispatch request, without duplicated inputs."""

    dispatch_request: ProductionPlannerWorkerDispatchRequest

    def __post_init__(self) -> None:
        if type(self.dispatch_request) is not ProductionPlannerWorkerDispatchRequest:
            raise InvalidProductionGovernedResultFinalizationRequestError(
                "dispatch_request must be exactly one existing Production request"
            )


@dataclass(frozen=True, slots=True, kw_only=True)
class ProductionGovernedEvidenceSnapshot:
    """Small authority-free snapshot of the exact successful caller chain."""

    worker_execution_result: ProductionAdapterWorkerExecutionResult
    observation_result: ProductionAdapterRuntimeObservationResult
    collection_result: ProductionAdapterRuntimeEventCollectionResult
    stream_result: ProductionAdapterRuntimeEventStreamResult
    history_record: Mapping[str, Any]

    def __post_init__(self) -> None:
        expected = (
            (self.worker_execution_result, ProductionAdapterWorkerExecutionResult),
            (self.observation_result, ProductionAdapterRuntimeObservationResult),
            (self.collection_result, ProductionAdapterRuntimeEventCollectionResult),
            (self.stream_result, ProductionAdapterRuntimeEventStreamResult),
        )
        if any(type(value) is not contract for value, contract in expected):
            raise TypeError("evidence snapshot contains an invalid contract")
        if self.observation_result.worker_execution_result is not self.worker_execution_result:
            raise ValueError("observation must reference the exact Worker result")
        if self.stream_result.events is not self.collection_result.events:
            raise ValueError("stream must receive the exact collected event tuple")
        object.__setattr__(self, "history_record", _freeze(self.history_record))


@dataclass(frozen=True, slots=True, kw_only=True)
class ProductionGovernedOperationalResult:
    """Externally inspectable outcome with no Runtime execution authority."""

    session_id: str
    status: ProductionGovernedResultStatus
    dispatch_result: ProductionPlannerWorkerDispatchResult | None
    plan_id: str | None
    task_id: str
    worker_id: str | None
    capability_id: str | None
    adapter_id: str | None
    path_id: str | None
    projection_id: str | None
    binding_id: str | None
    execution_outcome: str
    history_record: Mapping[str, Any] | None
    evidence: ProductionGovernedEvidenceSnapshot | None
    finalization_error: str | None = None
    runtime_allowed: bool = False
    execution_allowed: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.status, ProductionGovernedResultStatus):
            raise TypeError("status is invalid")
        if self.runtime_allowed is not False or self.execution_allowed is not False:
            raise ValueError("final result cannot grant Runtime or execution authority")
        if self.status is ProductionGovernedResultStatus.COMPLETED:
            if (
                self.dispatch_result is None
                or self.evidence is None
                or self.history_record is None
                or self.finalization_error is not None
            ):
                raise ValueError("completed final result requires all governed evidence")
        elif self.evidence is not None:
            raise ValueError("non-completed final result cannot expose completed evidence")
        if self.history_record is not None:
            object.__setattr__(self, "history_record", _freeze(self.history_record))


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({str(key): _freeze(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    return value
