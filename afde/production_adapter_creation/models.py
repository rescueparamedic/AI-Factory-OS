"""Immutable contracts for non-executable production adapter creation."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import re
from typing import Protocol

from afde.production_adapter_availability import (
    ProductionAdapterAvailabilityResult,
)
from afde.production_adapter_credential_readiness import (
    CredentialReadinessStatus,
    ProductionAdapterCredentialReadinessResult,
)
from afde.tool_adapter_contract import ToolAdapterBinding
from afde.tool_catalog import ToolAdapterDescriptor

from .errors import (
    InvalidProductionAdapterCreationContextError,
    InvalidProductionAdapterCreationResultError,
    InvalidProductionAdapterInstanceError,
    ProductionAdapterCreationIdentityMismatchError,
)


CONFIGURATION_REFERENCE_PATTERN = re.compile(
    r"^CONFIG-REFERENCE-[A-Z0-9][A-Z0-9._-]{0,63}$"
)
CREATION_REFERENCE_PATTERN = re.compile(
    r"^CREATION-REFERENCE-[A-Z0-9][A-Z0-9._-]{0,63}$"
)


class ProductionAdapterConfigurationKey(str, Enum):
    """Small allowlist for non-sensitive creation configuration metadata."""

    PROFILE_REFERENCE = "profile_reference"
    DEPLOYMENT_REFERENCE = "deployment_reference"


@dataclass(frozen=True)
class ProductionAdapterConfigurationMetadata:
    """One allowlisted configuration reference containing no secret value."""

    key: ProductionAdapterConfigurationKey
    reference: str

    def __post_init__(self) -> None:
        if not isinstance(self.key, ProductionAdapterConfigurationKey):
            raise InvalidProductionAdapterCreationContextError(
                "configuration key is not allowlisted"
            )
        if (
            not isinstance(self.reference, str)
            or not CONFIGURATION_REFERENCE_PATTERN.fullmatch(
                self.reference
            )
        ):
            raise InvalidProductionAdapterCreationContextError(
                "configuration reference must be a safe opaque reference"
            )


@dataclass(frozen=True)
class ProductionAdapterInstance:
    """Minimal inert adapter instance contract with no behavior methods."""

    adapter_id: str
    creation_metadata_references: tuple[str, ...]
    runtime_allowed: bool = False
    execution_allowed: bool = False

    def __post_init__(self) -> None:
        _identity(
            self.adapter_id,
            InvalidProductionAdapterInstanceError,
            "instance adapter_id",
        )
        references = _references(
            self.creation_metadata_references,
            CREATION_REFERENCE_PATTERN,
            InvalidProductionAdapterInstanceError,
            "creation metadata",
        )
        _authority(
            self.runtime_allowed,
            self.execution_allowed,
            InvalidProductionAdapterInstanceError,
        )
        object.__setattr__(
            self,
            "creation_metadata_references",
            references,
        )


class ProductionAdapterFactory(Protocol):
    """Caller-supplied factory for one exact adapter identity."""

    @property
    def adapter_id(self) -> str: ...

    def create(
        self,
        context: ProductionAdapterCreationContext,
    ) -> ProductionAdapterInstance: ...


@dataclass(frozen=True)
class ProductionAdapterCreationContext:
    """Validated metadata supplied to one explicit factory."""

    adapter_id: str
    descriptor: ToolAdapterDescriptor
    availability: ProductionAdapterAvailabilityResult
    credential_readiness: ProductionAdapterCredentialReadinessResult
    configuration_metadata: tuple[
        ProductionAdapterConfigurationMetadata,
        ...
    ] = ()
    binding: ToolAdapterBinding | None = None
    runtime_allowed: bool = False
    execution_allowed: bool = False

    def __post_init__(self) -> None:
        if type(self.descriptor) is not ToolAdapterDescriptor:
            raise InvalidProductionAdapterCreationContextError(
                "descriptor must be exactly one ToolAdapterDescriptor"
            )
        _identity(
            self.adapter_id,
            InvalidProductionAdapterCreationContextError,
            "context adapter_id",
        )
        if self.adapter_id != self.descriptor.adapter_id:
            raise ProductionAdapterCreationIdentityMismatchError(
                "context adapter identity conflicts with descriptor"
            )
        if type(
            self.availability
        ) is not ProductionAdapterAvailabilityResult:
            raise InvalidProductionAdapterCreationContextError(
                "availability result is invalid"
            )
        if (
            self.availability.descriptor is not self.descriptor
            or self.availability.descriptor.adapter_id != self.adapter_id
        ):
            raise ProductionAdapterCreationIdentityMismatchError(
                "availability identity conflicts with descriptor"
            )
        if type(
            self.credential_readiness
        ) is not ProductionAdapterCredentialReadinessResult:
            raise InvalidProductionAdapterCreationContextError(
                "credential readiness result is invalid"
            )
        if (
            self.credential_readiness.descriptor is not self.descriptor
            or self.credential_readiness.adapter_id != self.adapter_id
        ):
            raise ProductionAdapterCreationIdentityMismatchError(
                "credential readiness identity conflicts with descriptor"
            )
        configuration = _configuration(self.configuration_metadata)
        if self.binding is not None:
            if type(self.binding) is not ToolAdapterBinding:
                raise InvalidProductionAdapterCreationContextError(
                    "binding must be ToolAdapterBinding or None"
                )
            if (
                self.binding.descriptor is not self.descriptor
                or self.binding.adapter_id != self.adapter_id
            ):
                raise ProductionAdapterCreationIdentityMismatchError(
                    "binding identity conflicts with descriptor"
                )
        _authority(
            self.runtime_allowed,
            self.execution_allowed,
            InvalidProductionAdapterCreationContextError,
        )
        object.__setattr__(
            self,
            "configuration_metadata",
            configuration,
        )


@dataclass(frozen=True)
class ProductionAdapterCreationResult:
    """Immutable successful creation result without invocation authority."""

    context: ProductionAdapterCreationContext
    instance: ProductionAdapterInstance
    factory_adapter_id: str
    trace: tuple[str, ...]
    runtime_allowed: bool = False
    execution_allowed: bool = False

    def __post_init__(self) -> None:
        if type(self.context) is not ProductionAdapterCreationContext:
            raise InvalidProductionAdapterCreationResultError(
                "context is invalid"
            )
        if type(self.instance) is not ProductionAdapterInstance:
            raise InvalidProductionAdapterCreationResultError(
                "instance is invalid"
            )
        if (
            self.factory_adapter_id != self.context.adapter_id
            or self.instance.adapter_id != self.context.adapter_id
        ):
            raise InvalidProductionAdapterCreationResultError(
                "creation result identities conflict"
            )
        if not self.context.availability.available:
            raise InvalidProductionAdapterCreationResultError(
                "creation result requires available descriptor metadata"
            )
        expected_readiness = (
            CredentialReadinessStatus.READY
            if self.context.descriptor.credentials_required
            else CredentialReadinessStatus.NOT_REQUIRED
        )
        if (
            self.context.credential_readiness.status
            is not expected_readiness
        ):
            raise InvalidProductionAdapterCreationResultError(
                "creation result requires accepted credential readiness"
            )
        trace = _strings(
            self.trace,
            InvalidProductionAdapterCreationResultError,
            "trace",
        )
        _authority(
            self.runtime_allowed,
            self.execution_allowed,
            InvalidProductionAdapterCreationResultError,
        )
        object.__setattr__(self, "trace", trace)


def _configuration(
    values: object,
) -> tuple[ProductionAdapterConfigurationMetadata, ...]:
    if isinstance(values, (str, bytes)):
        raise InvalidProductionAdapterCreationContextError(
            "configuration_metadata must be a tuple"
        )
    try:
        snapshot = tuple(values)
    except TypeError as exc:
        raise InvalidProductionAdapterCreationContextError(
            "configuration_metadata must be a tuple"
        ) from exc
    if any(
        type(item) is not ProductionAdapterConfigurationMetadata
        for item in snapshot
    ):
        raise InvalidProductionAdapterCreationContextError(
            "configuration metadata contains an invalid item"
        )
    keys = tuple(item.key.value for item in snapshot)
    if len(keys) != len(set(keys)):
        raise InvalidProductionAdapterCreationContextError(
            "configuration metadata contains duplicate keys"
        )
    if keys != tuple(sorted(keys)):
        raise InvalidProductionAdapterCreationContextError(
            "configuration metadata must use deterministic key ordering"
        )
    return snapshot


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
        not isinstance(item, str) or not item
        for item in snapshot
    ):
        raise error_type(f"{field_name} must contain non-empty strings")
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
    error_type: type[Exception],
) -> None:
    if (
        not isinstance(runtime_allowed, bool)
        or runtime_allowed
        or not isinstance(execution_allowed, bool)
        or execution_allowed
    ):
        raise error_type(
            "creation cannot grant Runtime or execution authority"
        )
