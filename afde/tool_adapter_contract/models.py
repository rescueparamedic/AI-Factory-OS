"""Immutable contracts for non-executable Tool Adapter binding validation."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import re

from afde.runtime_integration import RuntimeProjection
from afde.tool_catalog import ToolAdapterDescriptor

from .errors import (
    InvalidToolAdapterRequestError,
    InvalidToolAdapterResultError,
)


PROJECTION_ID_PATTERN = re.compile(r"^RUNTIMEPROJ-[A-F0-9]{16}$")
PATH_ID_PATTERN = re.compile(r"^EXECPATH-[A-F0-9]{16}$")
CAPABILITY_ID_PATTERN = re.compile(
    r"^CAP-[A-Z0-9]+(?:-[A-Z0-9]+)*-[0-9]{4}$"
)
BINDING_ID_PATTERN = re.compile(r"^ADAPTERBIND-[A-F0-9]{16}$")


class ToolAdapterContractStatus(str, Enum):
    """Validation outcomes; neither grants execution authority."""

    VALIDATED = "validated"
    REJECTED = "rejected"


class ToolAdapterErrorCode(str, Enum):
    """Deterministic fail-closed validation categories."""

    DUPLICATE = "duplicate"
    MALFORMED = "malformed"
    MISMATCH = "mismatch"
    UNREGISTERED = "unregistered"


@dataclass(frozen=True)
class ToolAdapterRequest:
    """One immutable Runtime Projection presented for adapter binding."""

    projection: RuntimeProjection
    projection_id: str = field(init=False)
    path_id: str = field(init=False)
    capability_id: str = field(init=False)
    adapter_id: str = field(init=False)
    runtime_allowed: bool = False
    execution_allowed: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.projection, RuntimeProjection):
            raise InvalidToolAdapterRequestError(
                "projection must be a RuntimeProjection"
            )
        if not self.projection.runtime_ready:
            raise InvalidToolAdapterRequestError(
                "Runtime projection must be structurally ready"
            )
        _prohibit_authority(
            self.runtime_allowed,
            self.execution_allowed,
            InvalidToolAdapterRequestError,
        )
        object.__setattr__(
            self, "projection_id", self.projection.projection_id,
        )
        object.__setattr__(self, "path_id", self.projection.path_id)
        object.__setattr__(
            self, "capability_id", self.projection.capability_id,
        )
        object.__setattr__(self, "adapter_id", self.projection.adapter_id)


@dataclass(frozen=True)
class ToolAdapterBinding:
    """Deterministic metadata proving an exact descriptor binding."""

    binding_id: str
    projection_id: str
    path_id: str
    capability_id: str
    adapter_id: str
    adapter_version: str
    descriptor: ToolAdapterDescriptor
    runtime_allowed: bool = False
    execution_allowed: bool = False

    def __post_init__(self) -> None:
        if (
            not isinstance(self.binding_id, str)
            or not BINDING_ID_PATTERN.fullmatch(self.binding_id)
        ):
            raise InvalidToolAdapterResultError("binding_id is invalid")
        _validate_identities(
            self.projection_id,
            self.path_id,
            self.capability_id,
            self.adapter_id,
        )
        if not isinstance(self.descriptor, ToolAdapterDescriptor):
            raise InvalidToolAdapterResultError("descriptor is invalid")
        if (
            self.adapter_id != self.descriptor.adapter_id
            or self.capability_id
            not in self.descriptor.supported_capability_ids
            or self.adapter_version != self.descriptor.version
        ):
            raise InvalidToolAdapterResultError(
                "binding conflicts with adapter descriptor"
            )
        _prohibit_authority(
            self.runtime_allowed,
            self.execution_allowed,
            InvalidToolAdapterResultError,
        )


@dataclass(frozen=True)
class ToolAdapterError:
    """Immutable structured failure preserving the requested identity."""

    code: ToolAdapterErrorCode
    message: str
    projection_id: str
    path_id: str
    capability_id: str
    adapter_id: str
    runtime_allowed: bool = False
    execution_allowed: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.code, ToolAdapterErrorCode):
            raise InvalidToolAdapterResultError("error code is invalid")
        if (
            not isinstance(self.message, str)
            or not self.message
            or self.message != self.message.strip()
        ):
            raise InvalidToolAdapterResultError("error message is invalid")
        _validate_identities(
            self.projection_id,
            self.path_id,
            self.capability_id,
            self.adapter_id,
        )
        _prohibit_authority(
            self.runtime_allowed,
            self.execution_allowed,
            InvalidToolAdapterResultError,
        )


@dataclass(frozen=True)
class ToolAdapterResult:
    """Immutable binding result with deterministic trace and no authority."""

    status: ToolAdapterContractStatus
    projection_id: str
    path_id: str
    capability_id: str
    adapter_id: str
    binding: ToolAdapterBinding | None
    errors: tuple[ToolAdapterError, ...]
    trace: tuple[str, ...]
    runtime_allowed: bool = False
    execution_allowed: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.status, ToolAdapterContractStatus):
            raise InvalidToolAdapterResultError("status is invalid")
        _validate_identities(
            self.projection_id,
            self.path_id,
            self.capability_id,
            self.adapter_id,
        )
        errors = _tuple_of(
            self.errors, ToolAdapterError, "errors",
        )
        trace = _strings(self.trace, "trace")
        validated = self.status is ToolAdapterContractStatus.VALIDATED
        if validated:
            if (
                not isinstance(self.binding, ToolAdapterBinding)
                or errors
                or self.projection_id != self.binding.projection_id
                or self.path_id != self.binding.path_id
                or self.capability_id != self.binding.capability_id
                or self.adapter_id != self.binding.adapter_id
            ):
                raise InvalidToolAdapterResultError(
                    "validated Tool Adapter result is inconsistent"
                )
        elif self.binding is not None or not errors:
            raise InvalidToolAdapterResultError(
                "rejected Tool Adapter result is inconsistent"
            )
        if any(
            error.projection_id != self.projection_id
            or error.path_id != self.path_id
            or error.capability_id != self.capability_id
            or error.adapter_id != self.adapter_id
            for error in errors
        ):
            raise InvalidToolAdapterResultError(
                "error identity conflicts with result"
            )
        _prohibit_authority(
            self.runtime_allowed,
            self.execution_allowed,
            InvalidToolAdapterResultError,
        )
        object.__setattr__(self, "errors", errors)
        object.__setattr__(self, "trace", trace)


def _validate_identities(
    projection_id: object,
    path_id: object,
    capability_id: object,
    adapter_id: object,
) -> None:
    patterns = (
        ("projection_id", projection_id, PROJECTION_ID_PATTERN),
        ("path_id", path_id, PATH_ID_PATTERN),
        ("capability_id", capability_id, CAPABILITY_ID_PATTERN),
    )
    for name, value, pattern in patterns:
        if not isinstance(value, str) or not pattern.fullmatch(value):
            raise InvalidToolAdapterResultError(f"{name} is invalid")
    if (
        not isinstance(adapter_id, str)
        or not adapter_id
        or adapter_id != adapter_id.strip()
    ):
        raise InvalidToolAdapterResultError("adapter_id is invalid")


def _tuple_of(values: object, item_type: type, name: str) -> tuple:
    if isinstance(values, (str, bytes)):
        raise InvalidToolAdapterResultError(f"{name} must be a sequence")
    try:
        snapshot = tuple(values)
    except TypeError as exc:
        raise InvalidToolAdapterResultError(
            f"{name} must be a sequence"
        ) from exc
    if any(not isinstance(item, item_type) for item in snapshot):
        raise InvalidToolAdapterResultError(f"{name} contains invalid values")
    return snapshot


def _strings(values: object, name: str) -> tuple[str, ...]:
    snapshot = _tuple_of(values, str, name)
    if any(not item or item != item.strip() for item in snapshot):
        raise InvalidToolAdapterResultError(f"{name} contains invalid values")
    return snapshot


def _prohibit_authority(
    runtime_allowed: bool,
    execution_allowed: bool,
    error_type: type[ValueError],
) -> None:
    if not isinstance(runtime_allowed, bool) or runtime_allowed:
        raise error_type("Tool Adapter contract cannot allow Runtime")
    if not isinstance(execution_allowed, bool) or execution_allowed:
        raise error_type("Tool Adapter contract cannot allow execution")
