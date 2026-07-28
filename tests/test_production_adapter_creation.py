from dataclasses import FrozenInstanceError, replace

import pytest

import afde
import afde.production_adapter_creation as creation_package
from afde.production_adapter_availability import (
    ProductionAdapterAvailabilityService,
)
from afde.production_adapter_creation import (
    AdapterUnavailableForCreationError,
    CredentialNotReadyForCreationError,
    DuplicateProductionAdapterFactoryError,
    InvalidProductionAdapterCreationContextError,
    InvalidProductionAdapterCreationResultError,
    InvalidProductionAdapterFactoryError,
    InvalidProductionAdapterInstanceError,
    ProductionAdapterConfigurationKey,
    ProductionAdapterConfigurationMetadata,
    ProductionAdapterCreationContext,
    ProductionAdapterCreationIdentityMismatchError,
    ProductionAdapterCreationService,
    ProductionAdapterFactoryCreationError,
    ProductionAdapterFactoryNotFoundError,
    ProductionAdapterInstance,
)
from afde.production_adapter_credential_readiness import (
    CredentialReadinessEvidence,
    CredentialReadinessEvidenceSource,
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
        "adapter_id": "adapter.creation_fixture",
        "display_name": "Creation Fixture",
        "version": "1.0.0",
        "supported_capability_ids": ("CAP-CREATIONFIXTURE-0001",),
        "availability": AdapterAvailability.AVAILABLE,
        "runtime_compatibility": RuntimeCompatibility.COMPATIBLE,
        "execution_contract": ExecutionContract.CONTROLLED_RUNTIME,
        "privacy_classification": PrivacyClassification.LOCAL,
        "cost_classification": CostClassification.NO_COST,
        "credentials_required": False,
        "description": "Creation metadata fixture.",
        "metadata_references": ("fixture:creation",),
    }
    values.update(overrides)
    return ToolAdapterDescriptor(**values)


def _context(descriptor=None, *, evidence=None, configuration=()):
    descriptor = descriptor or _descriptor()
    availability = ProductionAdapterAvailabilityService().assess(descriptor)
    readiness = ProductionAdapterCredentialReadinessService().assess(
        descriptor,
        evidence,
    )
    return ProductionAdapterCreationContext(
        adapter_id=descriptor.adapter_id,
        descriptor=descriptor,
        availability=availability,
        credential_readiness=readiness,
        configuration_metadata=configuration,
        binding=None,
        runtime_allowed=False,
        execution_allowed=False,
    )


class FakeFactory:
    def __init__(
        self,
        adapter_id="adapter.creation_fixture",
        *,
        returned=None,
        failure=None,
    ):
        self.adapter_id = adapter_id
        self.returned = returned
        self.failure = failure
        self.contexts = []

    def create(self, context):
        self.contexts.append(context)
        if self.failure is not None:
            raise self.failure
        if self.returned is not None:
            return self.returned
        return ProductionAdapterInstance(
            adapter_id=context.adapter_id,
            creation_metadata_references=(
                "CREATION-REFERENCE-FAKE-001",
            ),
            runtime_allowed=False,
            execution_allowed=False,
        )


def _ready_evidence(descriptor):
    return CredentialReadinessEvidence(
        adapter_id=descriptor.adapter_id,
        ready=True,
        evidence_reference="CRED-EVIDENCE-CREATION-001",
        source=CredentialReadinessEvidenceSource.CALLER_ASSERTION,
    )


def test_valid_factory_creates_one_inert_instance():
    context = _context()
    factory = FakeFactory()
    service = ProductionAdapterCreationService((factory,))

    result = service.create(context)

    assert service.factory_ids == ("adapter.creation_fixture",)
    assert factory.contexts == [context]
    assert result.context is context
    assert result.instance.adapter_id == context.adapter_id
    assert result.factory_adapter_id == context.adapter_id
    assert result.instance.creation_metadata_references == (
        "CREATION-REFERENCE-FAKE-001",
    )
    assert result.runtime_allowed is False
    assert result.execution_allowed is False
    assert result.instance.runtime_allowed is False
    assert result.instance.execution_allowed is False
    for method in (
        "invoke",
        "execute",
        "run",
        "start",
        "connect",
        "call",
        "dispatch",
    ):
        assert not hasattr(result.instance, method)


def test_creation_succeeds_for_required_credentials_only_when_ready():
    descriptor = _descriptor(credentials_required=True)
    context = _context(
        descriptor,
        evidence=_ready_evidence(descriptor),
    )

    result = ProductionAdapterCreationService((
        FakeFactory(descriptor.adapter_id),
    )).create(context)

    assert result.instance.adapter_id == descriptor.adapter_id
    assert result.context.credential_readiness.status.value == "ready"


def test_context_configuration_is_allowlisted_immutable_metadata():
    configuration = (
        ProductionAdapterConfigurationMetadata(
            key=ProductionAdapterConfigurationKey.DEPLOYMENT_REFERENCE,
            reference="CONFIG-REFERENCE-DEPLOYMENT-001",
        ),
        ProductionAdapterConfigurationMetadata(
            key=ProductionAdapterConfigurationKey.PROFILE_REFERENCE,
            reference="CONFIG-REFERENCE-PROFILE-001",
        ),
    )
    context = _context(configuration=configuration)

    assert context.configuration_metadata == configuration
    with pytest.raises(FrozenInstanceError):
        context.adapter_id = "adapter.changed"


def test_factory_snapshot_is_deterministic_and_duplicate_fails_closed():
    alpha = FakeFactory("adapter.alpha")
    zeta = FakeFactory("adapter.zeta")

    service = ProductionAdapterCreationService((zeta, alpha))

    assert service.factory_ids == ("adapter.alpha", "adapter.zeta")
    with pytest.raises(DuplicateProductionAdapterFactoryError):
        ProductionAdapterCreationService((
            FakeFactory("adapter.same"),
            FakeFactory("adapter.same"),
        ))


@pytest.mark.parametrize("invalid", [None, object(), (object(),)])
def test_invalid_factory_input_fails_closed(invalid):
    with pytest.raises(InvalidProductionAdapterFactoryError):
        ProductionAdapterCreationService(invalid)


def test_missing_factory_fails_closed():
    with pytest.raises(ProductionAdapterFactoryNotFoundError):
        ProductionAdapterCreationService(()).create(_context())


def test_factory_identity_change_fails_closed():
    factory = FakeFactory()
    service = ProductionAdapterCreationService((factory,))
    factory.adapter_id = "adapter.changed"

    with pytest.raises(
        ProductionAdapterCreationIdentityMismatchError,
        match="factory identity",
    ):
        service.create(_context())


def test_context_descriptor_identity_mismatch_fails_closed():
    descriptor = _descriptor()
    availability = ProductionAdapterAvailabilityService().assess(descriptor)
    readiness = ProductionAdapterCredentialReadinessService().assess(
        descriptor
    )

    with pytest.raises(
        ProductionAdapterCreationIdentityMismatchError,
        match="context adapter identity",
    ):
        ProductionAdapterCreationContext(
            adapter_id="adapter.different",
            descriptor=descriptor,
            availability=availability,
            credential_readiness=readiness,
        )


def test_malformed_descriptor_and_context_fail_closed():
    descriptor = _descriptor()
    availability = ProductionAdapterAvailabilityService().assess(descriptor)
    readiness = ProductionAdapterCredentialReadinessService().assess(
        descriptor
    )

    with pytest.raises(
        InvalidProductionAdapterCreationContextError,
        match="descriptor",
    ):
        ProductionAdapterCreationContext(
            adapter_id=descriptor.adapter_id,
            descriptor=object(),
            availability=availability,
            credential_readiness=readiness,
        )
    with pytest.raises(
        InvalidProductionAdapterCreationContextError,
        match="context must",
    ):
        ProductionAdapterCreationService((FakeFactory(),)).create(object())


def test_availability_identity_mismatch_fails_closed():
    descriptor = _descriptor()
    other = _descriptor(adapter_id="adapter.other")

    with pytest.raises(
        ProductionAdapterCreationIdentityMismatchError,
        match="availability identity",
    ):
        ProductionAdapterCreationContext(
            adapter_id=descriptor.adapter_id,
            descriptor=descriptor,
            availability=(
                ProductionAdapterAvailabilityService().assess(other)
            ),
            credential_readiness=(
                ProductionAdapterCredentialReadinessService().assess(
                    descriptor
                )
            ),
        )


def test_unavailable_adapter_fails_closed_before_factory_call():
    descriptor = _descriptor(
        availability=AdapterAvailability.UNAVAILABLE
    )
    factory = FakeFactory(descriptor.adapter_id)

    with pytest.raises(AdapterUnavailableForCreationError):
        ProductionAdapterCreationService((factory,)).create(
            _context(descriptor)
        )

    assert factory.contexts == []


def test_credential_readiness_identity_mismatch_fails_closed():
    descriptor = _descriptor()
    other = _descriptor(adapter_id="adapter.other")

    with pytest.raises(
        ProductionAdapterCreationIdentityMismatchError,
        match="credential readiness identity",
    ):
        ProductionAdapterCreationContext(
            adapter_id=descriptor.adapter_id,
            descriptor=descriptor,
            availability=(
                ProductionAdapterAvailabilityService().assess(descriptor)
            ),
            credential_readiness=(
                ProductionAdapterCredentialReadinessService().assess(other)
            ),
        )


def test_required_not_ready_fails_closed_before_factory_call():
    descriptor = _descriptor(credentials_required=True)
    factory = FakeFactory(descriptor.adapter_id)

    with pytest.raises(CredentialNotReadyForCreationError):
        ProductionAdapterCreationService((factory,)).create(
            _context(descriptor)
        )

    assert factory.contexts == []


def test_factory_failure_invalid_return_and_identity_fail_closed():
    context = _context()

    with pytest.raises(ProductionAdapterFactoryCreationError):
        ProductionAdapterCreationService((
            FakeFactory(failure=RuntimeError("factory failure")),
        )).create(context)
    with pytest.raises(InvalidProductionAdapterInstanceError):
        ProductionAdapterCreationService((
            FakeFactory(returned=object()),
        )).create(context)
    with pytest.raises(
        ProductionAdapterCreationIdentityMismatchError,
        match="instance identity",
    ):
        ProductionAdapterCreationService((
            FakeFactory(
                returned=ProductionAdapterInstance(
                    adapter_id="adapter.different",
                    creation_metadata_references=(),
                )
            ),
        )).create(context)


def test_creation_result_is_immutable_and_rejects_invariant_violations():
    result = ProductionAdapterCreationService((FakeFactory(),)).create(
        _context()
    )

    with pytest.raises(FrozenInstanceError):
        result.instance = None
    with pytest.raises(
        InvalidProductionAdapterCreationResultError,
        match="identities conflict",
    ):
        replace(result, factory_adapter_id="adapter.different")
    with pytest.raises(
        InvalidProductionAdapterCreationResultError,
        match="cannot grant",
    ):
        replace(result, runtime_allowed=True)
    with pytest.raises(
        InvalidProductionAdapterCreationResultError,
        match="cannot grant",
    ):
        replace(result, execution_allowed=True)
    unavailable = _context(_descriptor(
        availability=AdapterAvailability.UNAVAILABLE
    ))
    with pytest.raises(
        InvalidProductionAdapterCreationResultError,
        match="available descriptor",
    ):
        replace(result, context=unavailable)
    not_ready = _context(_descriptor(credentials_required=True))
    with pytest.raises(
        InvalidProductionAdapterCreationResultError,
        match="credential readiness",
    ):
        replace(result, context=not_ready)


def test_configuration_and_instance_metadata_reject_unsafe_shapes():
    with pytest.raises(
        InvalidProductionAdapterCreationContextError,
        match="opaque",
    ):
        ProductionAdapterConfigurationMetadata(
            key=ProductionAdapterConfigurationKey.PROFILE_REFERENCE,
            reference="invalid-reference",
        )
    with pytest.raises(
        InvalidProductionAdapterInstanceError,
        match="opaque",
    ):
        ProductionAdapterInstance(
            adapter_id="adapter.creation_fixture",
            creation_metadata_references=("invalid-reference",),
        )


def test_public_contract_is_additive_and_package_scoped():
    assert not hasattr(afde, "ProductionAdapterCreationService")
    assert not hasattr(afde, "ProductionAdapterFactory")
    assert creation_package.__all__ == [
        "AdapterUnavailableForCreationError",
        "CredentialNotReadyForCreationError",
        "DuplicateProductionAdapterFactoryError",
        "InvalidProductionAdapterCreationContextError",
        "InvalidProductionAdapterCreationResultError",
        "InvalidProductionAdapterFactoryError",
        "InvalidProductionAdapterInstanceError",
        "ProductionAdapterConfigurationKey",
        "ProductionAdapterConfigurationMetadata",
        "ProductionAdapterCreationContext",
        "ProductionAdapterCreationError",
        "ProductionAdapterCreationIdentityMismatchError",
        "ProductionAdapterCreationResult",
        "ProductionAdapterCreationService",
        "ProductionAdapterFactory",
        "ProductionAdapterFactoryCreationError",
        "ProductionAdapterFactoryNotFoundError",
        "ProductionAdapterInstance",
    ]
