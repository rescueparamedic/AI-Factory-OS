"""Credential-readiness adaptation for additive Runtime projection."""
from __future__ import annotations

from afde.execution_path import ExecutionPathResult, ExecutionPathStatus
from afde.production_adapter_credential_readiness import (
    CredentialReadinessStatus,
    ProductionAdapterCredentialReadinessResult,
)
from afde.runtime_integration import RuntimePrerequisiteSatisfaction
from afde.runtime_integration import RuntimePrerequisiteType

from .errors import (
    InvalidProductionAdapterRuntimeStartupRequestError,
    ProductionAdapterRuntimeStartupIdentityMismatchError,
    ProductionAdapterRuntimeStartupPrerequisiteError,
)


def adapt_credential_readiness_to_runtime_prerequisite_satisfaction(
    *,
    execution_path: ExecutionPathResult,
    credential_readiness: ProductionAdapterCredentialReadinessResult,
) -> RuntimePrerequisiteSatisfaction:
    """Return opaque path-bound satisfaction from canonical READY metadata."""

    if type(execution_path) is not ExecutionPathResult:
        raise InvalidProductionAdapterRuntimeStartupRequestError(
            "execution_path must be exactly one ExecutionPathResult"
        )
    if type(credential_readiness) is not ProductionAdapterCredentialReadinessResult:
        raise InvalidProductionAdapterRuntimeStartupRequestError(
            "credential_readiness must use the canonical readiness result"
        )
    descriptor = credential_readiness.descriptor
    if (
        execution_path.status is not ExecutionPathStatus.PREREQUISITES_REQUIRED
        or not execution_path.path_constructed
        or execution_path.runtime_handoff_ready
        or execution_path.path_id is None
        or execution_path.adapter_id is None
        or len(execution_path.steps) != 1
        or not execution_path.steps[0].credentials_required
        or execution_path.steps[0].handoff_ready
    ):
        raise ProductionAdapterRuntimeStartupPrerequisiteError(
            "Execution Path does not contain one pending credential prerequisite"
        )
    if (
        not descriptor.credentials_required
        or credential_readiness.status is not CredentialReadinessStatus.READY
        or credential_readiness.evidence_ready is not True
        or credential_readiness.evidence_reference is None
    ):
        raise ProductionAdapterRuntimeStartupPrerequisiteError(
            "credential readiness must be READY with governed evidence"
        )
    step = execution_path.steps[0]
    if (
        descriptor.adapter_id != credential_readiness.adapter_id
        or descriptor.adapter_id != execution_path.adapter_id
        or descriptor.adapter_id != step.adapter_id
        or execution_path.capability_id != step.capability_id
        or execution_path.capability_id not in descriptor.supported_capability_ids
        or descriptor.version != step.adapter_version
    ):
        raise ProductionAdapterRuntimeStartupIdentityMismatchError(
            "descriptor, readiness, path, adapter, and Capability identities must agree"
        )
    return RuntimePrerequisiteSatisfaction(
        prerequisite_type=RuntimePrerequisiteType.CREDENTIAL_READINESS,
        satisfied=True,
        path_id=execution_path.path_id,
        adapter_id=execution_path.adapter_id,
        capability_id=execution_path.capability_id,
        evidence_reference=credential_readiness.evidence_reference,
    )
