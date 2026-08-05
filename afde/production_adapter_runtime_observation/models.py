"""Immutable contracts for one point-in-time Runtime observation."""
from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from typing import cast

from afde.production_adapter_worker_execution import (
    ProductionAdapterWorkerExecutionResult,
)

from .errors import (
    InvalidProductionAdapterRuntimeObservationIdentityError,
    InvalidProductionAdapterRuntimeObservationResultError,
    ProductionAdapterRuntimeObservationIdentityMismatchError,
)

OBSERVATION_ID_PATTERN = re.compile(
    r"^RUNTIME-OBSERVATION-[A-Z0-9][A-Z0-9._-]{0,63}$"
)
WORKER_ID_PATTERN = re.compile(r"^[a-z][a-z0-9_]{0,63}$")


@dataclass(frozen=True)
class ProductionAdapterRuntimeObservationIdentity:
    """Caller-issued identity bound to one completed execution identity chain."""

    observation_id: str
    worker_id: str
    adapter_id: str
    projection_id: str
    path_id: str
    capability_id: str
    binding_id: str

    def __post_init__(self) -> None:
        error = InvalidProductionAdapterRuntimeObservationIdentityError
        if (
            not isinstance(self.observation_id, str)
            or not OBSERVATION_ID_PATTERN.fullmatch(self.observation_id)
        ):
            raise error("observation_id must be a safe Runtime observation identity")
        if (
            not isinstance(self.worker_id, str)
            or not WORKER_ID_PATTERN.fullmatch(self.worker_id)
        ):
            raise error("worker_id must be an exact Worker identity")
        for name, value in (
            ("adapter_id", self.adapter_id),
            ("projection_id", self.projection_id),
            ("path_id", self.path_id),
            ("capability_id", self.capability_id),
            ("binding_id", self.binding_id),
        ):
            if (
                not isinstance(value, str)
                or not value
                or value != value.strip()
            ):
                raise error(f"{name} must be an exact non-empty identity")


@dataclass(frozen=True)
class ProductionAdapterRuntimeObservationResult:
    """Validated point-in-time view of one existing completed execution result."""

    identity: ProductionAdapterRuntimeObservationIdentity
    worker_execution_result: ProductionAdapterWorkerExecutionResult
    execution_status: str
    trace: tuple[str, ...]
    runtime_allowed: bool = False
    execution_allowed: bool = False

    def __post_init__(self) -> None:
        error = InvalidProductionAdapterRuntimeObservationResultError
        if type(self.identity) is not ProductionAdapterRuntimeObservationIdentity:
            raise error("identity contract type is invalid")
        if type(
            self.worker_execution_result
        ) is not ProductionAdapterWorkerExecutionResult:
            raise error("worker_execution_result contract type is invalid")

        source = self.worker_execution_result
        runtime_result = source.runtime_execution_result
        identity = self.identity
        if (
            identity.worker_id != source.worker_id
            or identity.adapter_id != runtime_result.adapter_id
            or identity.projection_id != runtime_result.projection_id
            or identity.path_id != runtime_result.path_id
            or identity.capability_id != runtime_result.capability_id
            or identity.binding_id != runtime_result.binding_id
        ):
            raise ProductionAdapterRuntimeObservationIdentityMismatchError(
                "observation identity conflicts with execution evidence"
            )
        if (
            self.execution_status != source.worker_result.execution_status
            or self.execution_status != "completed"
        ):
            raise error("execution_status conflicts with completed execution evidence")
        trace = _strings(self.trace, error)
        if not trace:
            raise error("trace must not be empty")
        if self.runtime_allowed is not False or self.execution_allowed is not False:
            raise error("observation cannot grant Runtime or execution authority")
        object.__setattr__(self, "trace", trace)


def _strings(
    values: object,
    error_type: type[Exception],
) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)) or not isinstance(values, Iterable):
        raise error_type("trace must be a tuple")
    snapshot: tuple[object, ...] = tuple(values)
    if any(
        not isinstance(item, str) or not item or item != item.strip()
        for item in snapshot
    ):
        raise error_type("trace contains invalid strings")
    return cast(tuple[str, ...], snapshot)
