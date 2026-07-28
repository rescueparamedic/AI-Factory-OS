from dataclasses import FrozenInstanceError, replace

import pytest

import afde
import afde.production_adapter_invocation as invocation_package
from afde.production_adapter_availability import (
    ProductionAdapterAvailabilityService,
)
from afde.production_adapter_creation import (
    ProductionAdapterCreationContext,
    ProductionAdapterCreationService,
    ProductionAdapterInstance,
)
from afde.production_adapter_credential_readiness import (
    CredentialReadinessStatus,
    ProductionAdapterCredentialReadinessService,
)
from afde.production_adapter_invocation import (
    AdapterUnavailableForInvocationError,
    CredentialNotReadyForInvocationError,
    InvalidInvocationRequestError,
    InvalidInvocationResultError,
    InvalidInvocationTargetError,
    InvalidInvocationTargetResultError,
    InvocationAuthorityViolationError,
    InvocationRequest,
    InvocationService,
    InvocationTargetCallError,
    InvocationTargetResult,
    ProductionAdapterInvocationIdentityMismatchError,
)
from afde.runtime_integration import RuntimeProjection
from afde.tool_adapter_contract import (
    ToolAdapterContractService,
    ToolAdapterRequest,
)
from afde.tool_catalog import (
    AdapterAvailability,
    CostClassification,
    ExecutionContract,
    PrivacyClassification,
    RuntimeCompatibility,
    ToolAdapterCatalog,
    ToolAdapterDescriptor,
)


CAPABILITY_ID = "CAP-INVOCATIONFIXTURE-0001"


def _descriptor(**overrides):
    values = {
        "adapter_id": "adapter.invocation_fixture",
        "display_name": "Invocation Fixture",
        "version": "1.0.0",
        "supported_capability_ids": (CAPABILITY_ID,),
        "availability": AdapterAvailability.AVAILABLE,
        "runtime_compatibility": RuntimeCompatibility.COMPATIBLE,
        "execution_contract": ExecutionContract.CONTROLLED_RUNTIME,
        "privacy_classification": PrivacyClassification.LOCAL,
        "cost_classification": CostClassification.NO_COST,
        "credentials_required": False,
        "description": "Invocation metadata fixture.",
        "metadata_references": ("fixture:invocation",),
    }
    values.update(overrides)
    return ToolAdapterDescriptor(**values)


class FakeFactory:
    def __init__(self, adapter_id="adapter.invocation_fixture"):
        self.adapter_id = adapter_id

    def create(self, context):
        return ProductionAdapterInstance(
            adapter_id=context.adapter_id,
            creation_metadata_references=(
                "CREATION-REFERENCE-INVOCATION-001",
            ),
        )


class FakeInvocationTarget:
    """Test-only explicit target; no Provider, network, or Runtime access."""

    def __init__(
        self,
        adapter_id="adapter.invocation_fixture",
        *,
        returned=None,
        failure=None,
    ):
        self.adapter_id = adapter_id
        self.returned = returned
        self.failure = failure
        self.requests = []

    def invoke(self, request):
        self.requests.append(request)
        if self.failure is not None:
            raise self.failure
        if self.returned is not None:
            return self.returned
        return InvocationTargetResult(
            adapter_id=self.adapter_id,
            result_metadata_references=(
                "INVOCATION-RESULT-REFERENCE-FAKE-001",
            ),
        )


def _request(descriptor=None):
    descriptor = descriptor or _descriptor()
    projection = RuntimeProjection(
        projection_id="RUNTIMEPROJ-0000000000000001",
        projection_version="1.0.0",
        path_id="EXECPATH-0000000000000001",
        sequence=1,
        adapter_id=descriptor.adapter_id,
        capability_id=CAPABILITY_ID,
        adapter_version=descriptor.version,
        availability=descriptor.availability,
        runtime_compatibility=descriptor.runtime_compatibility,
        execution_contract=descriptor.execution_contract,
        privacy_classification=descriptor.privacy_classification,
        cost_classification=descriptor.cost_classification,
        credentials_required=descriptor.credentials_required,
        metadata_references=descriptor.metadata_references,
        runtime_ready=True,
    )
    tool_request = ToolAdapterRequest(projection)
    contract = ToolAdapterContractService(
        ToolAdapterCatalog((descriptor,))
    ).bind(tool_request)
    availability = ProductionAdapterAvailabilityService().assess(
        descriptor
    )
    readiness = ProductionAdapterCredentialReadinessService().assess(
        descriptor
    )
    context = ProductionAdapterCreationContext(
        adapter_id=descriptor.adapter_id,
        descriptor=descriptor,
        availability=availability,
        credential_readiness=readiness,
        binding=contract.binding,
    )
    creation = ProductionAdapterCreationService((
        FakeFactory(descriptor.adapter_id),
    )).create(context)
    return InvocationRequest(
        adapter_id=descriptor.adapter_id,
        descriptor=descriptor,
        creation_result=creation,
        instance=creation.instance,
        tool_adapter_request=tool_request,
        binding=contract.binding,
        availability=availability,
        credential_readiness=readiness,
        invocation_metadata_references=(
            "INVOCATION-REFERENCE-REQUEST-001",
        ),
    )


def test_fake_target_returns_one_immutable_non_authoritative_result():
    request = _request()
    target = FakeInvocationTarget()

    result = InvocationService().invoke(request, target)

    assert target.requests == [request]
    assert result.request is request
    assert result.target_result.adapter_id == request.adapter_id
    assert result.target_result.result_metadata_references == (
        "INVOCATION-RESULT-REFERENCE-FAKE-001",
    )
    assert result.runtime_allowed is False
    assert result.execution_allowed is False
    assert result.target_result.runtime_allowed is False
    assert result.target_result.execution_allowed is False
    with pytest.raises(FrozenInstanceError):
        result.target_adapter_id = "adapter.changed"


def test_instance_contract_remains_inert():
    instance = _request().instance

    for method in (
        "invoke",
        "execute",
        "run",
        "start",
        "connect",
        "call",
        "dispatch",
    ):
        assert not hasattr(instance, method)


@pytest.mark.parametrize("invalid", [None, object(), "request"])
def test_creation_result_or_request_type_errors_fail_closed(invalid):
    request = _request()
    if invalid == "request":
        with pytest.raises(InvalidInvocationRequestError):
            InvocationService().invoke(object(), FakeInvocationTarget())
        return
    with pytest.raises(InvalidInvocationRequestError):
        replace(request, creation_result=invalid)


def test_corrupted_instance_type_fails_closed_before_target_call():
    request = _request()
    target = FakeInvocationTarget()
    object.__setattr__(request, "instance", object())

    with pytest.raises(InvalidInvocationRequestError, match="instance"):
        InvocationService().invoke(request, target)

    assert target.requests == []


def test_corrupted_creation_contract_fails_closed_before_target_call():
    request = _request()
    target = FakeInvocationTarget()
    object.__setattr__(request, "creation_result", object())

    with pytest.raises(InvalidInvocationRequestError, match="creation result"):
        InvocationService().invoke(request, target)

    assert target.requests == []


def test_request_identity_chain_mismatch_fails_closed():
    request = _request()

    with pytest.raises(
        ProductionAdapterInvocationIdentityMismatchError,
        match="adapter identities",
    ):
        replace(request, adapter_id="adapter.different")
    with pytest.raises(
        ProductionAdapterInvocationIdentityMismatchError,
        match="request objects",
    ):
        replace(
            request,
            instance=ProductionAdapterInstance(
                adapter_id=request.adapter_id,
                creation_metadata_references=(),
            ),
        )


def test_target_identity_and_shape_fail_closed_before_call():
    request = _request()
    mismatched = FakeInvocationTarget("adapter.different")

    with pytest.raises(
        ProductionAdapterInvocationIdentityMismatchError,
        match="target adapter identity",
    ):
        InvocationService().invoke(request, mismatched)
    with pytest.raises(InvalidInvocationTargetError):
        InvocationService().invoke(request, object())

    assert mismatched.requests == []


def test_unavailable_metadata_fails_closed_before_target_call():
    request = _request()
    target = FakeInvocationTarget()
    object.__setattr__(request.availability, "available", False)
    object.__setattr__(
        request.availability,
        "availability",
        AdapterAvailability.UNAVAILABLE,
    )

    with pytest.raises(AdapterUnavailableForInvocationError):
        InvocationService().invoke(request, target)

    assert target.requests == []


def test_required_credential_not_ready_fails_closed_before_target_call():
    request = _request()
    target = FakeInvocationTarget()
    object.__setattr__(request.descriptor, "credentials_required", True)
    object.__setattr__(
        request.credential_readiness,
        "credentials_required",
        True,
    )
    object.__setattr__(
        request.credential_readiness,
        "status",
        CredentialReadinessStatus.NOT_READY,
    )

    with pytest.raises(CredentialNotReadyForInvocationError):
        InvocationService().invoke(request, target)

    assert target.requests == []


def test_authority_violation_fails_closed_before_target_call():
    request = _request()
    target = FakeInvocationTarget()
    object.__setattr__(request.instance, "execution_allowed", True)

    with pytest.raises(InvocationAuthorityViolationError):
        InvocationService().invoke(request, target)

    assert target.requests == []
    with pytest.raises(InvocationAuthorityViolationError):
        replace(_request(), runtime_allowed=True)


def test_target_internal_exception_is_typed_and_chained():
    target = FakeInvocationTarget(failure=RuntimeError("sensitive detail"))

    with pytest.raises(InvocationTargetCallError) as captured:
        InvocationService().invoke(_request(), target)

    assert isinstance(captured.value.__cause__, RuntimeError)
    assert "sensitive detail" not in str(captured.value)


def test_target_return_type_identity_and_authority_fail_closed():
    request = _request()
    with pytest.raises(InvalidInvocationTargetResultError):
        InvocationService().invoke(
            request,
            FakeInvocationTarget(returned=object()),
        )
    with pytest.raises(
        ProductionAdapterInvocationIdentityMismatchError,
        match="target result identity",
    ):
        InvocationService().invoke(
            request,
            FakeInvocationTarget(
                returned=InvocationTargetResult(
                    adapter_id="adapter.different",
                    result_metadata_references=(),
                )
            ),
        )
    invalid_authority = InvocationTargetResult(
        adapter_id=request.adapter_id,
        result_metadata_references=(),
    )
    object.__setattr__(invalid_authority, "runtime_allowed", True)
    with pytest.raises(InvocationAuthorityViolationError):
        InvocationService().invoke(
            request,
            FakeInvocationTarget(returned=invalid_authority),
        )


def test_result_and_reference_invariants_fail_closed():
    result = InvocationService().invoke(
        _request(),
        FakeInvocationTarget(),
    )

    with pytest.raises(InvalidInvocationResultError):
        replace(result, target_adapter_id="adapter.different")
    with pytest.raises(InvalidInvocationRequestError, match="opaque"):
        replace(
            _request(),
            invocation_metadata_references=("unsafe",),
        )
    with pytest.raises(
        InvalidInvocationTargetResultError,
        match="opaque",
    ):
        InvocationTargetResult(
            adapter_id="adapter.invocation_fixture",
            result_metadata_references=("unsafe",),
        )


def test_public_contract_is_additive_and_package_scoped():
    assert not hasattr(afde, "InvocationService")
    assert not hasattr(afde, "InvocationTarget")
    assert invocation_package.__all__ == [
        "AdapterUnavailableForInvocationError",
        "CredentialNotReadyForInvocationError",
        "InvalidInvocationRequestError",
        "InvalidInvocationResultError",
        "InvalidInvocationTargetError",
        "InvalidInvocationTargetResultError",
        "InvocationAuthorityViolationError",
        "InvocationRequest",
        "InvocationResult",
        "InvocationService",
        "InvocationTarget",
        "InvocationTargetCallError",
        "InvocationTargetResult",
        "ProductionAdapterInvocationError",
        "ProductionAdapterInvocationIdentityMismatchError",
    ]
