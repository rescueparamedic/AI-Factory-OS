from dataclasses import FrozenInstanceError, dataclass, replace
from pathlib import Path

import pytest

import afde
import afde.production_adapter_runtime_execution as execution_package
from afde.knowledge import KnowledgeFoundationProvider
from afde.production_adapter_creation import (
    ProductionAdapterConfigurationKey,
    ProductionAdapterConfigurationMetadata,
    ProductionAdapterInstance,
)
from afde.production_adapter_invocation import InvocationTargetResult
from afde.production_adapter_runtime_execution import (
    InvalidProductionAdapterRuntimeExecutionAuthorityError,
    InvalidProductionAdapterRuntimeExecutionRequestError,
    InvalidProductionAdapterRuntimeExecutionResultError,
    ProductionAdapterRuntimeCreationCallError,
    ProductionAdapterRuntimeExecutionAuthority,
    ProductionAdapterRuntimeExecutionIdentityMismatchError,
    ProductionAdapterRuntimeExecutionRequest,
    ProductionAdapterRuntimeExecutionService,
    ProductionAdapterRuntimeInvocationCallError,
)
from afde.production_adapter_runtime_startup_integration import (
    build_production_adapter_runtime_startup_composition,
)
from afde.runtime_integration import RuntimeIntegrationPolicy, RuntimeProjection
from afde.tool_adapter_contract import ToolAdapterRequest
from afde.tool_catalog import (
    AdapterAvailability,
    CostClassification,
    ExecutionContract,
    PrivacyClassification,
    RuntimeCompatibility,
    ToolAdapterDescriptor,
)


ROOT = Path(__file__).resolve().parents[1]
ADAPTER_ID = "adapter.runtime_execution_fixture"
CAPABILITY_ID = "CAP-RUNTIMEEXECUTIONFIXTURE-0001"


def _descriptor():
    return ToolAdapterDescriptor(
        adapter_id=ADAPTER_ID,
        display_name="Runtime Execution Fixture",
        version="1.0.0",
        supported_capability_ids=(CAPABILITY_ID,),
        availability=AdapterAvailability.AVAILABLE,
        runtime_compatibility=RuntimeCompatibility.COMPATIBLE,
        execution_contract=ExecutionContract.CONTROLLED_RUNTIME,
        privacy_classification=PrivacyClassification.LOCAL,
        cost_classification=CostClassification.NO_COST,
        credentials_required=False,
        description="Runtime execution foundation fixture.",
        metadata_references=("fixture:runtime-execution",),
    )


@dataclass(frozen=True)
class FakeEntryPoint:
    name: str
    value: str
    descriptor: ToolAdapterDescriptor

    def load(self):
        return self.descriptor


class FakeDiscoverySource:
    def __init__(self, descriptor):
        self.descriptor = descriptor

    def entry_points(self, group):
        return (FakeEntryPoint("runtime", "fake:runtime", self.descriptor),)


class FakeFactory:
    def __init__(self, *, failure=None):
        self.adapter_id = ADAPTER_ID
        self.failure = failure
        self.contexts = []

    def create(self, context):
        self.contexts.append(context)
        if self.failure is not None:
            raise self.failure
        return ProductionAdapterInstance(
            adapter_id=context.adapter_id,
            creation_metadata_references=(
                "CREATION-REFERENCE-RUNTIME-EXECUTION-001",
            ),
        )


class FakeInvocationTarget:
    def __init__(self, *, failure=None):
        self.adapter_id = ADAPTER_ID
        self.failure = failure
        self.requests = []

    def invoke(self, request):
        self.requests.append(request)
        if self.failure is not None:
            raise self.failure
        return InvocationTargetResult(
            adapter_id=self.adapter_id,
            result_metadata_references=(
                "INVOCATION-RESULT-REFERENCE-RUNTIME-EXECUTION-001",
            ),
        )


def _policy():
    return RuntimeIntegrationPolicy(
        projection_version="1.0.0",
        required_runtime_compatibility=RuntimeCompatibility.COMPATIBLE,
        required_execution_contract=ExecutionContract.CONTROLLED_RUNTIME,
    )


def _startup(*, factory=None, target=None):
    descriptor = _descriptor()
    factory = factory or FakeFactory()
    target = target or FakeInvocationTarget()
    startup = build_production_adapter_runtime_startup_composition(
        knowledge_provider=KnowledgeFoundationProvider(ROOT),
        runtime_policy=_policy(),
        adapter_id=ADAPTER_ID,
        discovery_source=FakeDiscoverySource(descriptor),
        factory=factory,
        credential_readiness_evidence=None,
        configuration_metadata=(
            ProductionAdapterConfigurationMetadata(
                key=ProductionAdapterConfigurationKey.PROFILE_REFERENCE,
                reference="CONFIG-REFERENCE-RUNTIME-EXECUTION-PROFILE",
            ),
        ),
        invocation_target=target,
    )
    return startup, factory, target


def _request(*, factory=None, target=None):
    startup, factory, target = _startup(factory=factory, target=target)
    projection = RuntimeProjection(
        projection_id="RUNTIMEPROJ-0000000000000066",
        projection_version="1.0.0",
        path_id="EXECPATH-0000000000000066",
        sequence=1,
        adapter_id=ADAPTER_ID,
        capability_id=CAPABILITY_ID,
        adapter_version=startup.descriptor.version,
        availability=startup.descriptor.availability,
        runtime_compatibility=startup.descriptor.runtime_compatibility,
        execution_contract=startup.descriptor.execution_contract,
        privacy_classification=startup.descriptor.privacy_classification,
        cost_classification=startup.descriptor.cost_classification,
        credentials_required=startup.descriptor.credentials_required,
        metadata_references=startup.descriptor.metadata_references,
        runtime_ready=True,
    )
    tool_request = ToolAdapterRequest(projection)
    binding = startup.production_composition.tool_adapter_contract.bind(
        tool_request
    ).binding
    authority = ProductionAdapterRuntimeExecutionAuthority(
        authority_reference="RUNTIME-EXECUTION-AUTHORITY-AFDE-6.6-001",
        adapter_id=binding.adapter_id,
        projection_id=binding.projection_id,
        path_id=binding.path_id,
        capability_id=binding.capability_id,
        binding_id=binding.binding_id,
    )
    request = ProductionAdapterRuntimeExecutionRequest(
        startup_composition=startup,
        tool_adapter_request=tool_request,
        binding=binding,
        authority=authority,
        invocation_metadata_references=(
            "INVOCATION-REFERENCE-RUNTIME-EXECUTION-001",
        ),
    )
    return request, factory, target


def test_authorized_runtime_execution_reuses_creation_and_invocation_once():
    request, factory, target = _request()

    result = ProductionAdapterRuntimeExecutionService().execute(request)

    assert factory.contexts == [result.creation_result.context]
    assert factory.contexts[0].binding is request.binding
    assert target.requests == [result.invocation_result.request]
    assert result.invocation_result.request.creation_result is result.creation_result
    assert result.invocation_result.request.tool_adapter_request is (
        request.tool_adapter_request
    )
    assert result.invocation_result.request.binding is request.binding
    assert result.creation_result.factory_adapter_id == ADAPTER_ID
    assert result.invocation_result.target_adapter_id == ADAPTER_ID
    assert result.runtime_allowed is False
    assert result.execution_allowed is False
    assert result.creation_result.runtime_allowed is False
    assert result.invocation_result.runtime_allowed is False
    assert result.trace[-1] == "07.authority.not_propagated"


def test_authority_is_immutable_explicit_and_execution_scoped():
    request, _, _ = _request()
    authority = request.authority

    assert authority.runtime_allowed is True
    assert authority.execution_allowed is True
    with pytest.raises(FrozenInstanceError):
        authority.binding_id = "changed"
    with pytest.raises(InvalidProductionAdapterRuntimeExecutionAuthorityError):
        replace(authority, runtime_allowed=False)
    with pytest.raises(InvalidProductionAdapterRuntimeExecutionAuthorityError):
        replace(authority, execution_allowed=False)
    with pytest.raises(InvalidProductionAdapterRuntimeExecutionAuthorityError):
        replace(authority, authority_reference="secret value")


def test_mismatched_authority_fails_before_factory_or_target_behavior():
    request, factory, target = _request()

    with pytest.raises(ProductionAdapterRuntimeExecutionIdentityMismatchError):
        replace(
            request,
            authority=replace(
                request.authority,
                binding_id="ADAPTERBIND-FFFFFFFFFFFFFFFF",
            ),
        )

    assert factory.contexts == []
    assert target.requests == []


def test_invalid_request_fails_closed_before_behavior():
    request, factory, target = _request()
    with pytest.raises(InvalidProductionAdapterRuntimeExecutionRequestError):
        ProductionAdapterRuntimeExecutionService().execute(object())
    with pytest.raises(InvalidProductionAdapterRuntimeExecutionRequestError):
        replace(request, invocation_metadata_references=("secret value",))
    assert factory.contexts == []
    assert target.requests == []


def test_creation_and_invocation_failures_are_stage_specific():
    factory = FakeFactory(failure=RuntimeError("creation failure"))
    request, factory, target = _request(factory=factory)
    with pytest.raises(ProductionAdapterRuntimeCreationCallError) as creation:
        ProductionAdapterRuntimeExecutionService().execute(request)
    assert isinstance(creation.value.__cause__, RuntimeError)
    assert len(factory.contexts) == 1
    assert target.requests == []

    target = FakeInvocationTarget(failure=RuntimeError("invocation failure"))
    request, factory, target = _request(target=target)
    with pytest.raises(ProductionAdapterRuntimeInvocationCallError) as invocation:
        ProductionAdapterRuntimeExecutionService().execute(request)
    assert invocation.value.__cause__ is not None
    assert len(factory.contexts) == 1
    assert len(target.requests) == 1


def test_result_is_immutable_and_does_not_regrant_authority():
    request, _, _ = _request()
    result = ProductionAdapterRuntimeExecutionService().execute(request)

    with pytest.raises(FrozenInstanceError):
        result.trace = ()
    with pytest.raises(InvalidProductionAdapterRuntimeExecutionResultError):
        replace(result, runtime_allowed=True)
    with pytest.raises(InvalidProductionAdapterRuntimeExecutionResultError):
        replace(result, execution_allowed=True)


def test_public_contract_is_additive_and_package_scoped():
    assert not hasattr(afde, "ProductionAdapterRuntimeExecutionService")
    assert not hasattr(afde, "ProductionAdapterRuntimeExecutionAuthority")
    assert execution_package.__all__ == [
        "InvalidProductionAdapterRuntimeExecutionAuthorityError",
        "InvalidProductionAdapterRuntimeExecutionRequestError",
        "InvalidProductionAdapterRuntimeExecutionResultError",
        "ProductionAdapterRuntimeCreationCallError",
        "ProductionAdapterRuntimeExecutionAuthority",
        "ProductionAdapterRuntimeExecutionError",
        "ProductionAdapterRuntimeExecutionIdentityMismatchError",
        "ProductionAdapterRuntimeExecutionRequest",
        "ProductionAdapterRuntimeExecutionResult",
        "ProductionAdapterRuntimeExecutionService",
        "ProductionAdapterRuntimeInvocationCallError",
    ]
