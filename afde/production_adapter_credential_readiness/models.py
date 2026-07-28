"""Immutable contracts for caller-supplied credential readiness metadata."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import re

from afde.tool_catalog import ToolAdapterDescriptor

from .errors import (
    InvalidCredentialReadinessEvidenceError,
    InvalidCredentialReadinessResultError,
)


EVIDENCE_REFERENCE_PATTERN = re.compile(
    r"^CRED-EVIDENCE-[A-Z0-9][A-Z0-9._-]{0,63}$"
)


class CredentialReadinessStatus(str, Enum):
    """Declared credential readiness outcomes."""

    NOT_REQUIRED = "not_required"
    READY = "ready"
    NOT_READY = "not_ready"


class CredentialReadinessEvidenceSource(str, Enum):
    """Allowlisted caller-declared evidence source metadata."""

    CALLER_ASSERTION = "caller_assertion"
    GOVERNED_RECORD_REFERENCE = "governed_record_reference"


@dataclass(frozen=True)
class CredentialReadinessEvidence:
    """Caller assertion containing no credential or secret material."""

    adapter_id: str
    ready: bool
    evidence_reference: str
    source: CredentialReadinessEvidenceSource

    def __post_init__(self) -> None:
        if (
            not isinstance(self.adapter_id, str)
            or not self.adapter_id
            or self.adapter_id != self.adapter_id.strip()
        ):
            raise InvalidCredentialReadinessEvidenceError(
                "evidence adapter_id must be an exact non-empty identity"
            )
        if not isinstance(self.ready, bool):
            raise InvalidCredentialReadinessEvidenceError(
                "evidence ready must be a boolean"
            )
        if (
            not isinstance(self.evidence_reference, str)
            or not EVIDENCE_REFERENCE_PATTERN.fullmatch(
                self.evidence_reference
            )
        ):
            raise InvalidCredentialReadinessEvidenceError(
                "evidence_reference must be a safe opaque reference"
            )
        if not isinstance(
            self.source,
            CredentialReadinessEvidenceSource,
        ):
            raise InvalidCredentialReadinessEvidenceError(
                "evidence source metadata is invalid"
            )


@dataclass(frozen=True)
class ProductionAdapterCredentialReadinessResult:
    """Metadata-only readiness result with no Runtime authority."""

    descriptor: ToolAdapterDescriptor
    adapter_id: str
    credentials_required: bool
    status: CredentialReadinessStatus
    evidence_ready: bool | None
    evidence_reference: str | None
    evidence_source: CredentialReadinessEvidenceSource | None
    trace: tuple[str, ...]
    runtime_allowed: bool = False
    execution_allowed: bool = False

    def __post_init__(self) -> None:
        if type(self.descriptor) is not ToolAdapterDescriptor:
            raise InvalidCredentialReadinessResultError(
                "descriptor must be exactly one ToolAdapterDescriptor"
            )
        if self.adapter_id != self.descriptor.adapter_id:
            raise InvalidCredentialReadinessResultError(
                "result adapter identity conflicts with descriptor metadata"
            )
        if (
            not isinstance(self.credentials_required, bool)
            or self.credentials_required
            is not self.descriptor.credentials_required
        ):
            raise InvalidCredentialReadinessResultError(
                "credentials_required conflicts with descriptor metadata"
            )
        if not isinstance(self.status, CredentialReadinessStatus):
            raise InvalidCredentialReadinessResultError(
                "readiness status is invalid"
            )
        evidence_present = self.evidence_reference is not None
        if (
            evidence_present != (self.evidence_ready is not None)
            or evidence_present != (self.evidence_source is not None)
        ):
            raise InvalidCredentialReadinessResultError(
                "evidence fields must be present together"
        )
        if evidence_present and (
            not isinstance(self.evidence_ready, bool)
            or not isinstance(self.evidence_reference, str)
            or not EVIDENCE_REFERENCE_PATTERN.fullmatch(
                self.evidence_reference
            )
            or not isinstance(
                self.evidence_source,
                CredentialReadinessEvidenceSource,
            )
        ):
            raise InvalidCredentialReadinessResultError(
                "result evidence metadata is invalid"
            )
        if not self.credentials_required:
            expected_status = CredentialReadinessStatus.NOT_REQUIRED
        else:
            expected_status = (
                CredentialReadinessStatus.READY
                if evidence_present and self.evidence_ready
                else CredentialReadinessStatus.NOT_READY
            )
        if self.status is not expected_status:
            raise InvalidCredentialReadinessResultError(
                "readiness status conflicts with descriptor and "
                "evidence metadata"
            )
        if isinstance(self.trace, (str, bytes)):
            raise InvalidCredentialReadinessResultError(
                "trace must be an iterable of strings"
            )
        try:
            trace = tuple(self.trace)
        except TypeError as exc:
            raise InvalidCredentialReadinessResultError(
                "trace must be an iterable of strings"
            ) from exc
        if (
            not trace
            or any(
                not isinstance(item, str) or not item
                for item in trace
            )
        ):
            raise InvalidCredentialReadinessResultError(
                "trace must contain non-empty strings"
            )
        if (
            not isinstance(self.runtime_allowed, bool)
            or self.runtime_allowed
            or not isinstance(self.execution_allowed, bool)
            or self.execution_allowed
        ):
            raise InvalidCredentialReadinessResultError(
                "readiness cannot grant Runtime or execution authority"
            )
        object.__setattr__(self, "trace", trace)
