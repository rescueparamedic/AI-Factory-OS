"""Caller-supplied production adapter credential readiness assessment."""
from __future__ import annotations

from afde.tool_catalog import ToolAdapterDescriptor

from .errors import (
    CredentialReadinessIdentityMismatchError,
    InvalidCredentialReadinessDescriptorError,
    InvalidCredentialReadinessEvidenceError,
)
from .models import (
    CredentialReadinessEvidence,
    CredentialReadinessStatus,
    ProductionAdapterCredentialReadinessResult,
)


class ProductionAdapterCredentialReadinessService:
    """Assess declared readiness without accessing credential material."""

    def assess(
        self,
        descriptor: ToolAdapterDescriptor,
        evidence: CredentialReadinessEvidence | None = None,
    ) -> ProductionAdapterCredentialReadinessResult:
        """Return readiness from descriptor metadata and explicit evidence."""

        if type(descriptor) is not ToolAdapterDescriptor:
            raise InvalidCredentialReadinessDescriptorError(
                "descriptor must be exactly one ToolAdapterDescriptor"
            )
        if (
            evidence is not None
            and type(evidence) is not CredentialReadinessEvidence
        ):
            raise InvalidCredentialReadinessEvidenceError(
                "evidence must be CredentialReadinessEvidence or None"
            )
        if (
            evidence is not None
            and evidence.adapter_id != descriptor.adapter_id
        ):
            raise CredentialReadinessIdentityMismatchError(
                "evidence adapter identity does not match descriptor"
            )

        if not descriptor.credentials_required:
            status = CredentialReadinessStatus.NOT_REQUIRED
        elif evidence is not None and evidence.ready:
            status = CredentialReadinessStatus.READY
        else:
            status = CredentialReadinessStatus.NOT_READY

        evidence_reference = (
            evidence.evidence_reference
            if evidence is not None
            else None
        )
        evidence_source = (
            evidence.source
            if evidence is not None
            else None
        )
        return ProductionAdapterCredentialReadinessResult(
            descriptor=descriptor,
            adapter_id=descriptor.adapter_id,
            credentials_required=descriptor.credentials_required,
            status=status,
            evidence_ready=(
                evidence.ready
                if evidence is not None
                else None
            ),
            evidence_reference=evidence_reference,
            evidence_source=evidence_source,
            trace=(
                f"01.descriptor.accepted:{descriptor.adapter_id}",
                "02.credentials.required:"
                f"{str(descriptor.credentials_required).lower()}",
                f"03.evidence.present:{str(evidence is not None).lower()}",
                f"04.readiness.status:{status.value}",
                "05.authority.denied",
            ),
            runtime_allowed=False,
            execution_allowed=False,
        )
