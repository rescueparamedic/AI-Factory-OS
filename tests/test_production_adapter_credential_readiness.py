from dataclasses import FrozenInstanceError, replace

import pytest

import afde
import afde.production_adapter_credential_readiness as readiness_package
from afde.production_adapter_credential_readiness import (
    CredentialReadinessEvidence,
    CredentialReadinessEvidenceSource,
    CredentialReadinessIdentityMismatchError,
    CredentialReadinessStatus,
    InvalidCredentialReadinessDescriptorError,
    InvalidCredentialReadinessEvidenceError,
    InvalidCredentialReadinessResultError,
    ProductionAdapterCredentialReadinessService,
)
from afde.tool_catalog import (
    AdapterAvailability,
    CostClassification,
    ExecutionContract,
    PrivacyClassification,
    RuntimeCompatibility,
    ToolAdapterDescriptor,
)


def _descriptor(**overrides):
    values = {
        "adapter_id": "adapter.readiness_fixture",
        "display_name": "Readiness Fixture",
        "version": "1.0.0",
        "supported_capability_ids": ("CAP-READINESSFIXTURE-0001",),
        "availability": AdapterAvailability.AVAILABLE,
        "runtime_compatibility": RuntimeCompatibility.COMPATIBLE,
        "execution_contract": ExecutionContract.CONTROLLED_RUNTIME,
        "privacy_classification": PrivacyClassification.LOCAL,
        "cost_classification": CostClassification.NO_COST,
        "credentials_required": True,
        "description": "Credential readiness metadata fixture.",
        "metadata_references": ("fixture:readiness",),
    }
    values.update(overrides)
    return ToolAdapterDescriptor(**values)


def _evidence(**overrides):
    values = {
        "adapter_id": "adapter.readiness_fixture",
        "ready": True,
        "evidence_reference": "CRED-EVIDENCE-READY-001",
        "source": CredentialReadinessEvidenceSource.CALLER_ASSERTION,
    }
    values.update(overrides)
    return CredentialReadinessEvidence(**values)


def test_credentials_not_required_is_not_required():
    descriptor = _descriptor(credentials_required=False)

    result = ProductionAdapterCredentialReadinessService().assess(
        descriptor
    )

    assert result.descriptor is descriptor
    assert result.adapter_id == descriptor.adapter_id
    assert result.credentials_required is False
    assert result.status is CredentialReadinessStatus.NOT_REQUIRED
    assert result.evidence_ready is None
    assert result.evidence_reference is None
    assert result.evidence_source is None
    assert result.runtime_allowed is False
    assert result.execution_allowed is False


def test_required_with_explicit_ready_evidence_is_ready():
    descriptor = _descriptor()
    evidence = _evidence()

    result = ProductionAdapterCredentialReadinessService().assess(
        descriptor,
        evidence,
    )

    assert result.status is CredentialReadinessStatus.READY
    assert result.evidence_ready is True
    assert result.evidence_reference == evidence.evidence_reference
    assert result.evidence_source is evidence.source
    assert result.trace == (
        "01.descriptor.accepted:adapter.readiness_fixture",
        "02.credentials.required:true",
        "03.evidence.present:true",
        "04.readiness.status:ready",
        "05.authority.denied",
    )


def test_required_without_evidence_is_normal_fail_closed_not_ready():
    result = ProductionAdapterCredentialReadinessService().assess(
        _descriptor()
    )

    assert result.status is CredentialReadinessStatus.NOT_READY
    assert result.evidence_ready is None
    assert result.evidence_reference is None
    assert result.evidence_source is None


def test_required_with_explicit_not_ready_evidence_is_not_ready():
    evidence = _evidence(
        ready=False,
        evidence_reference="CRED-EVIDENCE-NOT-READY-001",
    )

    result = ProductionAdapterCredentialReadinessService().assess(
        _descriptor(),
        evidence,
    )

    assert result.status is CredentialReadinessStatus.NOT_READY
    assert result.evidence_ready is False
    assert result.evidence_reference == evidence.evidence_reference
    assert result.evidence_source is evidence.source


def test_result_is_deterministic_immutable_and_preserves_identity():
    descriptor = _descriptor()
    evidence = _evidence()
    service = ProductionAdapterCredentialReadinessService()

    first = service.assess(descriptor, evidence)
    second = service.assess(descriptor, evidence)

    assert first == second
    assert first.descriptor is descriptor
    assert first.adapter_id == descriptor.adapter_id
    with pytest.raises(FrozenInstanceError):
        first.status = CredentialReadinessStatus.NOT_READY


@pytest.mark.parametrize("invalid", [None, object(), (_descriptor(),)])
def test_invalid_descriptor_fails_closed_with_typed_error(invalid):
    with pytest.raises(
        InvalidCredentialReadinessDescriptorError,
        match="exactly one",
    ):
        ProductionAdapterCredentialReadinessService().assess(invalid)


@pytest.mark.parametrize("invalid", [object(), {}, (_evidence(),)])
def test_invalid_readiness_input_fails_closed_with_typed_error(invalid):
    with pytest.raises(
        InvalidCredentialReadinessEvidenceError,
        match="Evidence or None",
    ):
        ProductionAdapterCredentialReadinessService().assess(
            _descriptor(),
            invalid,
        )


@pytest.mark.parametrize(
    "overrides, message",
    [
        ({"adapter_id": ""}, "adapter_id"),
        ({"ready": 1}, "boolean"),
        ({"evidence_reference": "invalid-reference"}, "opaque"),
        ({"source": "caller_assertion"}, "source"),
    ],
)
def test_malformed_evidence_contract_is_rejected(overrides, message):
    with pytest.raises(
        InvalidCredentialReadinessEvidenceError,
        match=message,
    ):
        _evidence(**overrides)


def test_descriptor_identity_mismatch_fails_closed():
    evidence = _evidence(adapter_id="adapter.different")

    with pytest.raises(
        CredentialReadinessIdentityMismatchError,
        match="does not match",
    ):
        ProductionAdapterCredentialReadinessService().assess(
            _descriptor(),
            evidence,
        )


def test_result_rejects_identity_status_evidence_and_authority_conflicts():
    ready = ProductionAdapterCredentialReadinessService().assess(
        _descriptor(),
        _evidence(),
    )
    not_required = ProductionAdapterCredentialReadinessService().assess(
        _descriptor(credentials_required=False)
    )

    with pytest.raises(
        InvalidCredentialReadinessResultError,
        match="identity conflicts",
    ):
        replace(ready, adapter_id="adapter.different")
    with pytest.raises(
        InvalidCredentialReadinessResultError,
        match="credentials_required conflicts",
    ):
        replace(ready, credentials_required=False)
    with pytest.raises(
        InvalidCredentialReadinessResultError,
        match="present together",
    ):
        replace(
            ready,
            evidence_ready=None,
        )
    with pytest.raises(
        InvalidCredentialReadinessResultError,
        match="status conflicts",
    ):
        replace(
            not_required,
            status=CredentialReadinessStatus.READY,
        )
    with pytest.raises(
        InvalidCredentialReadinessResultError,
        match="status conflicts",
    ):
        replace(ready, evidence_ready=False)
    with pytest.raises(
        InvalidCredentialReadinessResultError,
        match="cannot grant",
    ):
        replace(ready, runtime_allowed=True)
    with pytest.raises(
        InvalidCredentialReadinessResultError,
        match="cannot grant",
    ):
        replace(ready, execution_allowed=True)


def test_contract_representation_contains_only_safe_metadata():
    evidence = _evidence()
    result = ProductionAdapterCredentialReadinessService().assess(
        _descriptor(),
        evidence,
    )

    assert evidence.evidence_reference in repr(evidence)
    assert evidence.evidence_reference in repr(result)
    assert "ready=True" in repr(evidence)
    assert result.trace[2] == "03.evidence.present:true"


def test_public_contract_is_additive_and_package_scoped():
    assert readiness_package.__all__ == [
        "CredentialReadinessEvidence",
        "CredentialReadinessEvidenceSource",
        "CredentialReadinessIdentityMismatchError",
        "CredentialReadinessStatus",
        "InvalidCredentialReadinessDescriptorError",
        "InvalidCredentialReadinessEvidenceError",
        "InvalidCredentialReadinessResultError",
        "ProductionAdapterCredentialReadinessError",
        "ProductionAdapterCredentialReadinessResult",
        "ProductionAdapterCredentialReadinessService",
    ]
    assert not hasattr(
        afde,
        "ProductionAdapterCredentialReadinessService",
    )
    assert not hasattr(afde, "CredentialReadinessEvidence")
