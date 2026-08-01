"""Immutable contracts for explicit production adapter invocation."""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Protocol

from afde.production_adapter_availability import (
    ProductionAdapterAvailabilityResult,
)
from afde.production_adapter_creation import (
    ProductionAdapterCreationResult,
    ProductionAdapterInstance,
)
from afde.production_adapter_credential_readiness import (
    CredentialReadinessStatus,
    ProductionAdapterCredentialReadinessResult,
)
from afde.tool_adapter_contract import (
    ToolAdapterBinding,
    ToolAdapterRequest,
)
from afde.tool_catalog import ToolAdapterDescriptor

from .errors import (
    InvalidInvocationRequestError,
    InvalidInvocationResultError,
    InvalidInvocationTargetResultError,
    InvocationAuthorityViolationError,
    ProductionAdapterInvocationIdentityMismatchError,
)


INVOCATION_REFERENCE_PATTERN = re.compile(
    r"^INVOCATION-REFERENCE-[A-Z0-9][A-Z0-9._-]{0,63}$"
)
INVOCATION_RESULT_REFERENCE_PATTERN = re.compile(
    r"^INVOCATION-RESULT-REFERENCE-[A-Z0-9][A-Z0-9._-]{0,63}$"
)


@dataclass(frozen=True)
class InvocationRequest:
    """Exact immutable identity chain presented to one explicit target."""

    adapter_id: str
    descriptor: ToolAdapterDescriptor
    creation_result: ProductionAdapterCreationResult
    instance: ProductionAdapterInstance
    tool_adapter_request: ToolAdapterRequest
    binding: ToolAdapterBinding
    availability: ProductionAdapterAvailabilityResult
    credential_readiness: ProductionAdapterCredentialReadinessResult
    invocation_metadata_references: tuple[str, ...] = ()
    runtime_allowed: bool = False
    execution_allowed: bool = False

    def __post_init__(self) -> None:
        _request_types(self)
        context = self.creation_result.context
        if (
            self.creation_result.instance is not self.instance
            or context.descriptor is not self.descriptor
            or context.availability is not self.availability
            or context.credential_readiness is not self.credential_readiness
            or context.binding is not self.binding
        ):
            raise ProductionAdapterInvocationIdentityMismatchError(
                "request objects conflict with the creation identity chain"
            )
        if (
            self.adapter_id != self.descriptor.adapter_id
            or self.adapter_id != context.adapter_id
            or self.adapter_id != self.instance.adapter_id
            or self.adapter_id != self.creation_result.factory_adapter_id
            or self.adapter_id != self.availability.descriptor.adapter_id
            or self.adapter_id != self.credential_readiness.adapter_id
            or self.adapter_id != self.tool_adapter_request.adapter_id
            or self.adapter_id != self.binding.adapter_id
        ):
            raise ProductionAdapterInvocationIdentityMismatchError(
                "request adapter identities conflict"
            )
        if (
            self.binding.descriptor is not self.descriptor
            or self.binding.projection_id
            != self.tool_adapter_request.projection_id
            or self.binding.path_id != self.tool_adapter_request.path_id
            or self.binding.capability_id
            != self.tool_adapter_request.capability_id
            or self.binding.adapter_version != self.descriptor.version
        ):
            raise ProductionAdapterInvocationIdentityMismatchError(
                "request binding identity conflicts"
            )
        references = _references(
            self.invocation_metadata_references,
            INVOCATION_REFERENCE_PATTERN,
            InvalidInvocationRequestError,
            "invocation metadata",
        )
        _authority(
            self.runtime_allowed,
            self.execution_allowed,
        )
        object.__setattr__(
            self,
            "invocation_metadata_references",
            references,
        )


@dataclass(frozen=True)
class InvocationTargetResult:
    """Metadata-only target return with no Runtime execution authority."""

    adapter_id: str
    result_metadata_references: tuple[str, ...]
    runtime_allowed: bool = False
    execution_allowed: bool = False

    def __post_init__(self) -> None:
        _identity(
            self.adapter_id,
            InvalidInvocationTargetResultError,
            "target result adapter_id",
        )
        references = _references(
            self.result_metadata_references,
            INVOCATION_RESULT_REFERENCE_PATTERN,
            InvalidInvocationTargetResultError,
            "target result metadata",
        )
        _authority(
            self.runtime_allowed,
            self.execution_allowed,
        )
        object.__setattr__(
            self,
            "result_metadata_references",
            references,
        )


class InvocationTarget(Protocol):
    """Caller-supplied target for one exact adapter identity."""

    @property
    def adapter_id(self) -> str: ...

    def invoke(self, request: InvocationRequest) -> InvocationTargetResult: ...


@dataclass(frozen=True)
class InvocationResult:
    """Validated invocation result without Runtime or execution authority."""

    request: InvocationRequest
    target_result: InvocationTargetResult
    target_adapter_id: str
    trace: tuple[str, ...]
    runtime_allowed: bool = False
    execution_allowed: bool = False

    def __post_init__(self) -> None:
        if type(self.request) is not InvocationRequest:
            raise InvalidInvocationResultError("request is invalid")
        if type(self.target_result) is not InvocationTargetResult:
            raise InvalidInvocationResultError("target result is invalid")
        if (
            self.target_adapter_id != self.request.adapter_id
            or self.target_result.adapter_id != self.request.adapter_id
        ):
            raise InvalidInvocationResultError(
                "invocation result identities conflict"
            )
        trace = _strings(
            self.trace,
            InvalidInvocationResultError,
            "trace",
        )
        if not trace:
            raise InvalidInvocationResultError("trace must not be empty")
        _authority(
            self.runtime_allowed,
            self.execution_allowed,
        )
        object.__setattr__(self, "trace", trace)


def _request_types(request: InvocationRequest) -> None:
    checks = (
        ("descriptor", request.descriptor, ToolAdapterDescriptor),
        (
            "creation_result",
            request.creation_result,
            ProductionAdapterCreationResult,
        ),
        ("instance", request.instance, ProductionAdapterInstance),
        (
            "tool_adapter_request",
            request.tool_adapter_request,
            ToolAdapterRequest,
        ),
        ("binding", request.binding, ToolAdapterBinding),
        (
            "availability",
            request.availability,
            ProductionAdapterAvailabilityResult,
        ),
        (
            "credential_readiness",
            request.credential_readiness,
            ProductionAdapterCredentialReadinessResult,
        ),
    )
    for name, value, expected in checks:
        if type(value) is not expected:
            raise InvalidInvocationRequestError(
                f"{name} must be exactly one {expected.__name__}"
            )
    _identity(
        request.adapter_id,
        InvalidInvocationRequestError,
        "request adapter_id",
    )


def expected_credential_readiness(
    descriptor: ToolAdapterDescriptor,
) -> CredentialReadinessStatus:
    """Return the only accepted readiness state for the descriptor."""

    return (
        CredentialReadinessStatus.READY
        if descriptor.credentials_required
        else CredentialReadinessStatus.NOT_REQUIRED
    )


def _references(
    values: object,
    pattern: re.Pattern[str],
    error_type: type[Exception],
    field_name: str,
) -> tuple[str, ...]:
    references = _strings(values, error_type, field_name)
    if any(not pattern.fullmatch(item) for item in references):
        raise error_type(
            f"{field_name} must contain safe opaque references"
        )
    if len(references) != len(set(references)):
        raise error_type(f"{field_name} contains duplicate references")
    if references != tuple(sorted(references)):
        raise error_type(
            f"{field_name} must use deterministic ordering"
        )
    return references


def _strings(
    values: object,
    error_type: type[Exception],
    field_name: str,
) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)):
        raise error_type(f"{field_name} must be a tuple")
    try:
        snapshot = tuple(values)
    except TypeError as exc:
        raise error_type(f"{field_name} must be a tuple") from exc
    if any(
        not isinstance(item, str)
        or not item
        or item != item.strip()
        for item in snapshot
    ):
        raise error_type(f"{field_name} contains invalid strings")
    return snapshot


def _identity(
    value: object,
    error_type: type[Exception],
    field_name: str,
) -> None:
    if (
        not isinstance(value, str)
        or not value
        or value != value.strip()
    ):
        raise error_type(f"{field_name} must be an exact identity")


def _authority(
    runtime_allowed: object,
    execution_allowed: object,
) -> None:
    if (
        not isinstance(runtime_allowed, bool)
        or runtime_allowed
        or not isinstance(execution_allowed, bool)
        or execution_allowed
    ):
        raise InvocationAuthorityViolationError(
            "invocation cannot grant Runtime or execution authority"
        )
