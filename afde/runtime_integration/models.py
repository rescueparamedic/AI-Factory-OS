"""Immutable contracts for non-executable Runtime Integration."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import re

from afde.execution_path import (
    ExecutionPathResult,
    RuntimeHandoffProjection,
)
from afde.tool_catalog import (
    AdapterAvailability,
    CostClassification,
    ExecutionContract,
    PrivacyClassification,
    RuntimeCompatibility,
)

from .errors import (
    InvalidRuntimeIntegrationRequestError,
    InvalidRuntimeProjectionError,
)


PROJECTION_ID_PATTERN = re.compile(r"^RUNTIMEPROJ-[A-F0-9]{16}$")
PATH_ID_PATTERN = re.compile(r"^EXECPATH-[A-F0-9]{16}$")
CAPABILITY_ID_PATTERN = re.compile(r"^CAP-[A-Z0-9]+-[0-9]{4}$")
VERSION_PATTERN = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")


class RuntimeIntegrationStatus(str, Enum):
    """Structural Runtime Integration outcomes."""

    READY = "ready"
    BLOCKED = "blocked"


@dataclass(frozen=True)
class RuntimeIntegrationPolicy:
    """Injected deterministic policy; it performs no live Runtime checks."""

    projection_version: str
    required_runtime_compatibility: RuntimeCompatibility
    required_execution_contract: ExecutionContract

    def __post_init__(self) -> None:
        if (
            not isinstance(self.projection_version, str)
            or not VERSION_PATTERN.fullmatch(self.projection_version)
        ):
            raise InvalidRuntimeIntegrationRequestError(
                "projection_version must be semantic version metadata"
            )
        if not isinstance(
            self.required_runtime_compatibility, RuntimeCompatibility,
        ):
            raise InvalidRuntimeIntegrationRequestError(
                "required_runtime_compatibility is invalid"
            )
        if not isinstance(
            self.required_execution_contract, ExecutionContract,
        ):
            raise InvalidRuntimeIntegrationRequestError(
                "required_execution_contract is invalid"
            )


@dataclass(frozen=True)
class RuntimeIntegrationRequest:
    """One immutable Execution Path result accepted for projection."""

    execution_path: ExecutionPathResult

    def __post_init__(self) -> None:
        if not isinstance(self.execution_path, ExecutionPathResult):
            raise InvalidRuntimeIntegrationRequestError(
                "execution_path must be an ExecutionPathResult"
            )


@dataclass(frozen=True)
class RuntimeProjection:
    """Read-only Runtime-ready metadata with no execution authority."""

    projection_id: str
    projection_version: str
    path_id: str
    sequence: int
    adapter_id: str
    capability_id: str
    adapter_version: str
    availability: AdapterAvailability
    runtime_compatibility: RuntimeCompatibility
    execution_contract: ExecutionContract
    privacy_classification: PrivacyClassification
    cost_classification: CostClassification
    credentials_required: bool
    metadata_references: tuple[str, ...]
    runtime_ready: bool
    runtime_allowed: bool = False
    execution_allowed: bool = False

    def __post_init__(self) -> None:
        if (
            not isinstance(self.projection_id, str)
            or not PROJECTION_ID_PATTERN.fullmatch(self.projection_id)
        ):
            raise InvalidRuntimeProjectionError("projection_id is invalid")
        if (
            not isinstance(self.path_id, str)
            or not PATH_ID_PATTERN.fullmatch(self.path_id)
        ):
            raise InvalidRuntimeProjectionError("path_id is invalid")
        if (
            not isinstance(self.projection_version, str)
            or not VERSION_PATTERN.fullmatch(self.projection_version)
        ):
            raise InvalidRuntimeProjectionError(
                "projection_version is invalid"
            )
        if not isinstance(self.sequence, int) or self.sequence != 1:
            raise InvalidRuntimeProjectionError(
                "Runtime projection sequence must be one"
            )
        try:
            source = RuntimeHandoffProjection(
                sequence=self.sequence,
                adapter_id=self.adapter_id,
                capability_id=self.capability_id,
                adapter_version=self.adapter_version,
                availability=self.availability,
                runtime_compatibility=self.runtime_compatibility,
                execution_contract=self.execution_contract,
                privacy_classification=self.privacy_classification,
                cost_classification=self.cost_classification,
                credentials_required=self.credentials_required,
                metadata_references=tuple(self.metadata_references),
                handoff_ready=self.runtime_ready,
                runtime_allowed=False,
                execution_allowed=False,
            )
        except Exception as exc:
            raise InvalidRuntimeProjectionError(
                "Runtime projection metadata is invalid"
            ) from exc
        if not isinstance(self.runtime_ready, bool) or not self.runtime_ready:
            raise InvalidRuntimeProjectionError(
                "Runtime projection must be structurally ready"
            )
        _prohibit_authority(self.runtime_allowed, self.execution_allowed)
        object.__setattr__(self, "adapter_id", source.adapter_id)
        object.__setattr__(self, "capability_id", source.capability_id)
        object.__setattr__(
            self, "metadata_references", source.metadata_references,
        )


@dataclass(frozen=True)
class RuntimeIntegrationResult:
    """Immutable Runtime readiness result; never executable authority."""

    status: RuntimeIntegrationStatus
    runtime_ready: bool
    projection: RuntimeProjection | None
    path_id: str | None
    capability_id: str
    adapter_id: str | None
    blocked_reasons: tuple[str, ...]
    path_trace: tuple[str, ...]
    trace: tuple[str, ...]
    runtime_allowed: bool = False
    execution_allowed: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.status, RuntimeIntegrationStatus):
            raise InvalidRuntimeIntegrationRequestError("status is invalid")
        if (
            not isinstance(self.capability_id, str)
            or not CAPABILITY_ID_PATTERN.fullmatch(self.capability_id)
        ):
            raise InvalidRuntimeIntegrationRequestError(
                "capability_id is invalid"
            )
        for name in ("blocked_reasons", "path_trace", "trace"):
            object.__setattr__(
                self, name, _snapshot_strings(getattr(self, name), name),
            )
        ready = self.status is RuntimeIntegrationStatus.READY
        if not isinstance(self.runtime_ready, bool) or self.runtime_ready != ready:
            raise InvalidRuntimeIntegrationRequestError(
                "runtime_ready conflicts with status"
            )
        if ready:
            if (
                not isinstance(self.projection, RuntimeProjection)
                or self.path_id != self.projection.path_id
                or self.adapter_id != self.projection.adapter_id
                or self.capability_id != self.projection.capability_id
                or self.blocked_reasons
            ):
                raise InvalidRuntimeIntegrationRequestError(
                    "ready Runtime result is inconsistent"
                )
        elif (
            self.projection is not None
            or self.path_id is not None
            or self.adapter_id is not None
            or not self.blocked_reasons
        ):
            raise InvalidRuntimeIntegrationRequestError(
                "blocked Runtime result is inconsistent"
            )
        _prohibit_authority(self.runtime_allowed, self.execution_allowed)


def _snapshot_strings(values: object, field_name: str) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)):
        raise InvalidRuntimeIntegrationRequestError(
            f"{field_name} must be a sequence of strings"
        )
    try:
        snapshot = tuple(values)
    except TypeError as exc:
        raise InvalidRuntimeIntegrationRequestError(
            f"{field_name} must be a sequence of strings"
        ) from exc
    if any(not isinstance(item, str) or not item for item in snapshot):
        raise InvalidRuntimeIntegrationRequestError(
            f"{field_name} contains an invalid value"
        )
    return snapshot


def _prohibit_authority(
    runtime_allowed: bool, execution_allowed: bool,
) -> None:
    if not isinstance(runtime_allowed, bool) or runtime_allowed:
        raise InvalidRuntimeIntegrationRequestError(
            "Runtime Integration cannot allow Runtime execution"
        )
    if not isinstance(execution_allowed, bool) or execution_allowed:
        raise InvalidRuntimeIntegrationRequestError(
            "Runtime Integration cannot allow execution"
        )
