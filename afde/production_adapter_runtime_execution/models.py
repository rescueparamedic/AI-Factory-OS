"""Immutable contracts for authorized production adapter Runtime execution."""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
import re
from typing import cast

from afde.production_adapter_creation import ProductionAdapterCreationResult
from afde.production_adapter_invocation import InvocationResult
from afde.production_adapter_runtime_startup_integration import (
    ProductionAdapterRuntimeStartupComposition,
)
from afde.tool_adapter_contract import ToolAdapterBinding, ToolAdapterRequest

from .errors import (
    InvalidProductionAdapterRuntimeExecutionAuthorityError,
    InvalidProductionAdapterRuntimeExecutionRequestError,
    InvalidProductionAdapterRuntimeExecutionResultError,
    ProductionAdapterRuntimeExecutionIdentityMismatchError,
)


AUTHORITY_REFERENCE_PATTERN = re.compile(
    r"^RUNTIME-EXECUTION-AUTHORITY-[A-Z0-9][A-Z0-9._-]{0,63}$"
)
INVOCATION_REFERENCE_PATTERN = re.compile(
    r"^INVOCATION-REFERENCE-[A-Z0-9][A-Z0-9._-]{0,63}$"
)


@dataclass(frozen=True)
class ProductionAdapterRuntimeExecutionAuthority:
    """Runtime-issued authority bound to one exact adapter binding identity."""

    authority_reference: str
    adapter_id: str
    projection_id: str
    path_id: str
    capability_id: str
    binding_id: str
    runtime_allowed: bool = True
    execution_allowed: bool = True

    def __post_init__(self) -> None:
        error = InvalidProductionAdapterRuntimeExecutionAuthorityError
        if (
            not isinstance(self.authority_reference, str)
            or not AUTHORITY_REFERENCE_PATTERN.fullmatch(
                self.authority_reference
            )
        ):
            raise error("authority_reference must be a safe Runtime reference")
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
        if self.runtime_allowed is not True or self.execution_allowed is not True:
            raise error(
                "Runtime execution authority must explicitly allow Runtime and execution"
            )


@dataclass(frozen=True)
class ProductionAdapterRuntimeExecutionRequest:
    """One authorized request linked to the validated startup composition."""

    startup_composition: ProductionAdapterRuntimeStartupComposition
    tool_adapter_request: ToolAdapterRequest
    binding: ToolAdapterBinding
    authority: ProductionAdapterRuntimeExecutionAuthority
    invocation_metadata_references: tuple[str, ...] = ()
    runtime_allowed: bool = False
    execution_allowed: bool = False

    def __post_init__(self) -> None:
        error = InvalidProductionAdapterRuntimeExecutionRequestError
        exact_types = (
            (
                "startup_composition",
                self.startup_composition,
                ProductionAdapterRuntimeStartupComposition,
            ),
            ("tool_adapter_request", self.tool_adapter_request, ToolAdapterRequest),
            ("binding", self.binding, ToolAdapterBinding),
            (
                "authority",
                self.authority,
                ProductionAdapterRuntimeExecutionAuthority,
            ),
        )
        for name, value, expected in exact_types:
            if type(value) is not expected:
                raise error(f"{name} contract type is invalid")

        startup = self.startup_composition
        binding = self.binding
        tool_request = self.tool_adapter_request
        authority = self.authority
        if (
            binding.descriptor is not startup.descriptor
            or binding.projection_id != tool_request.projection_id
            or binding.path_id != tool_request.path_id
            or binding.capability_id != tool_request.capability_id
            or binding.adapter_version != startup.descriptor.version
        ):
            raise ProductionAdapterRuntimeExecutionIdentityMismatchError(
                "binding conflicts with startup or Tool Adapter request"
            )
        expected_identities = (
            startup.adapter_id,
            startup.descriptor.adapter_id,
            tool_request.adapter_id,
            binding.adapter_id,
            authority.adapter_id,
        )
        if any(item != startup.adapter_id for item in expected_identities):
            raise ProductionAdapterRuntimeExecutionIdentityMismatchError(
                "execution adapter identities conflict"
            )
        if (
            authority.projection_id != binding.projection_id
            or authority.path_id != binding.path_id
            or authority.capability_id != binding.capability_id
            or authority.binding_id != binding.binding_id
        ):
            raise ProductionAdapterRuntimeExecutionIdentityMismatchError(
                "Runtime authority is not bound to the requested execution identity"
            )
        references = _references(
            self.invocation_metadata_references,
            INVOCATION_REFERENCE_PATTERN,
            error,
        )
        _deny_result_authority(
            self.runtime_allowed,
            self.execution_allowed,
            error,
            "request",
        )
        object.__setattr__(self, "invocation_metadata_references", references)


@dataclass(frozen=True)
class ProductionAdapterRuntimeExecutionResult:
    """Completed execution evidence that does not propagate Runtime authority."""

    request: ProductionAdapterRuntimeExecutionRequest
    creation_result: ProductionAdapterCreationResult
    invocation_result: InvocationResult
    trace: tuple[str, ...]
    runtime_allowed: bool = False
    execution_allowed: bool = False

    def __post_init__(self) -> None:
        error = InvalidProductionAdapterRuntimeExecutionResultError
        if type(self.request) is not ProductionAdapterRuntimeExecutionRequest:
            raise error("request contract type is invalid")
        if type(self.creation_result) is not ProductionAdapterCreationResult:
            raise error("creation_result contract type is invalid")
        if type(self.invocation_result) is not InvocationResult:
            raise error("invocation_result contract type is invalid")
        startup = self.request.startup_composition
        invocation_request = self.invocation_result.request
        if (
            self.creation_result is not invocation_request.creation_result
            or self.creation_result.context.binding is not self.request.binding
            or invocation_request.tool_adapter_request
            is not self.request.tool_adapter_request
            or invocation_request.binding is not self.request.binding
            or self.creation_result.context.descriptor is not startup.descriptor
            or self.creation_result.factory_adapter_id != startup.adapter_id
            or self.invocation_result.target_adapter_id != startup.adapter_id
        ):
            raise error("execution result conflicts with the request identity chain")
        trace = _strings(self.trace, error, "trace")
        if not trace:
            raise error("trace must not be empty")
        _deny_result_authority(
            self.runtime_allowed,
            self.execution_allowed,
            error,
            "result",
        )
        object.__setattr__(self, "trace", trace)


def _references(
    values: object,
    pattern: re.Pattern[str],
    error_type: type[Exception],
) -> tuple[str, ...]:
    references = _strings(values, error_type, "invocation metadata")
    if any(not pattern.fullmatch(item) for item in references):
        raise error_type(
            "invocation metadata must contain safe opaque references"
        )
    if len(references) != len(set(references)):
        raise error_type("invocation metadata contains duplicate references")
    if references != tuple(sorted(references)):
        raise error_type("invocation metadata must use deterministic ordering")
    return references


def _strings(
    values: object,
    error_type: type[Exception],
    field_name: str,
) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)) or not isinstance(values, Iterable):
        raise error_type(f"{field_name} must be a tuple")
    snapshot: tuple[object, ...] = tuple(values)
    if any(
        not isinstance(item, str) or not item or item != item.strip()
        for item in snapshot
    ):
        raise error_type(f"{field_name} contains invalid strings")
    return cast(tuple[str, ...], snapshot)


def _deny_result_authority(
    runtime_allowed: object,
    execution_allowed: object,
    error_type: type[Exception],
    field_name: str,
) -> None:
    if runtime_allowed is not False or execution_allowed is not False:
        raise error_type(
            f"execution {field_name} cannot propagate Runtime authority"
        )
