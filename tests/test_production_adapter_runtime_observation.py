from dataclasses import FrozenInstanceError, dataclass, replace
from pathlib import Path
from uuid import uuid4

import pytest

import afde
import afde.production_adapter_runtime_observation as observation_package
from afde.knowledge import KnowledgeFoundationProvider
from afde.production_adapter_creation import ProductionAdapterInstance
from afde.production_adapter_invocation import InvocationTargetResult
from afde.production_adapter_runtime_execution import (
    ProductionAdapterRuntimeExecutionAuthority,
)
from afde.production_adapter_runtime_observation import (
    InvalidProductionAdapterRuntimeObservationIdentityError,
    InvalidProductionAdapterRuntimeObservationResultError,
    InvalidProductionAdapterRuntimeObservationSourceError,
    ProductionAdapterRuntimeObservationIdentity,
    ProductionAdapterRuntimeObservationIdentityMismatchError,
    ProductionAdapterRuntimeObservationService,
)
from afde.production_adapter_runtime_startup_integration import (
    build_production_adapter_runtime_startup_composition,
)
from afde.production_adapter_worker_execution import (
    ProductionAdapterWorkerExecutionRequest,
    ProductionAdapterWorkerExecutionService,
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
from real_worker_runtime.models import ExecutionInput

ROOT = Path(__file__).resolve().parents[1]
ADAPTER_ID = "adapter.runtime_observation_fixture"
CAPABILITY_ID = "CAP-RUNTIMEOBSERVATIONFIXTURE-0001"


def _descriptor():
    return ToolAdapterDescriptor(
        adapter_id=ADAPTER_ID,
        display_name="Runtime Observation Fixture",
        version="1.0.0",
        supported_capability_ids=(CAPABILITY_ID,),
        availability=AdapterAvailability.AVAILABLE,
        runtime_compatibility=RuntimeCompatibility.COMPATIBLE,
        execution_contract=ExecutionContract.CONTROLLED_RUNTIME,
        privacy_classification=PrivacyClassification.LOCAL,
        cost_classification=CostClassification.NO_COST,
        credentials_required=False,
        description="Runtime observation foundation fixture.",
        metadata_references=("fixture:runtime-observation",),
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
        return (FakeEntryPoint("observation", "fake:observation", self.descriptor),)


class FakeFactory:
    def __init__(self):
        self.adapter_id = ADAPTER_ID
        self.calls = 0

    def create(self, context):
        self.calls += 1
        return ProductionAdapterInstance(
            adapter_id=context.adapter_id,
            creation_metadata_references=(
                "CREATION-REFERENCE-RUNTIME-OBSERVATION-001",
            ),
        )


class FakeInvocationTarget:
    def __init__(self):
        self.adapter_id = ADAPTER_ID
        self.calls = 0

    def invoke(self, request):
        self.calls += 1
        return InvocationTargetResult(
            adapter_id=self.adapter_id,
            result_metadata_references=(
                "INVOCATION-RESULT-REFERENCE-RUNTIME-OBSERVATION-001",
            ),
        )


def _completed_execution():
    descriptor = _descriptor()
    factory = FakeFactory()
    target = FakeInvocationTarget()
    startup = build_production_adapter_runtime_startup_composition(
        knowledge_provider=KnowledgeFoundationProvider(ROOT),
        runtime_policy=RuntimeIntegrationPolicy(
            projection_version="1.0.0",
            required_runtime_compatibility=RuntimeCompatibility.COMPATIBLE,
            required_execution_contract=ExecutionContract.CONTROLLED_RUNTIME,
        ),
        adapter_id=ADAPTER_ID,
        discovery_source=FakeDiscoverySource(descriptor),
        factory=factory,
        credential_readiness_evidence=None,
        configuration_metadata=(),
        invocation_target=target,
    )
    projection = RuntimeProjection(
        projection_id="RUNTIMEPROJ-0000000000000069",
        projection_version="1.0.0",
        path_id="EXECPATH-0000000000000069",
        sequence=1,
        adapter_id=ADAPTER_ID,
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
    binding = startup.production_composition.tool_adapter_contract.bind(
        tool_request
    ).binding
    authority = ProductionAdapterRuntimeExecutionAuthority(
        authority_reference=f"RUNTIME-EXECUTION-AUTHORITY-{uuid4().hex.upper()}",
        adapter_id=binding.adapter_id,
        projection_id=binding.projection_id,
        path_id=binding.path_id,
        capability_id=binding.capability_id,
        binding_id=binding.binding_id,
    )
    request = ProductionAdapterWorkerExecutionRequest(
        worker_input=ExecutionInput(
            plan_id="PLAN-RUNTIME-OBSERVATION-001",
            task_id="TASK-RUNTIME-OBSERVATION-001",
            worker_id="observation_worker",
            instruction="produce bounded observation source evidence",
            provider="not-selected",
            model="not-selected",
            execution_mode="production_adapter_runtime",
            metadata={"source": "afde-6.9"},
        ),
        startup_composition=startup,
        tool_adapter_request=tool_request,
        binding=binding,
        authority=authority,
        invocation_metadata_references=(
            "INVOCATION-REFERENCE-RUNTIME-OBSERVATION-001",
        ),
    )
    result = ProductionAdapterWorkerExecutionService().execute(request)
    assert factory.calls == 1
    assert target.calls == 1
    return result, factory, target


def _identity(source, **overrides):
    runtime_result = source.runtime_execution_result
    values = {
        "observation_id": "RUNTIME-OBSERVATION-AFDE-6.9-001",
        "worker_id": source.worker_id,
        "adapter_id": runtime_result.adapter_id,
        "projection_id": runtime_result.projection_id,
        "path_id": runtime_result.path_id,
        "capability_id": runtime_result.capability_id,
        "binding_id": runtime_result.binding_id,
    }
    values.update(overrides)
    return ProductionAdapterRuntimeObservationIdentity(**values)


def test_observes_one_existing_result_without_reexecution_or_collection():
    source, factory, target = _completed_execution()
    identity = _identity(source)

    result = ProductionAdapterRuntimeObservationService().observe(
        identity,
        source,
    )

    assert result.identity is identity
    assert result.worker_execution_result is source
    assert result.execution_status == "completed"
    assert result.runtime_allowed is False
    assert result.execution_allowed is False
    assert result.trace == (
        "01.observation.identity.accepted:RUNTIME-OBSERVATION-AFDE-6.9-001",
        "02.worker.identity.validated:observation_worker",
        f"03.adapter.identity.validated:{ADAPTER_ID}",
        "04.execution.evidence.observed",
        "05.authority.denied",
    )
    assert factory.calls == 1
    assert target.calls == 1
    assert not hasattr(result, "events")
    assert not hasattr(result, "history")
    assert not hasattr(result, "health")


def test_observation_is_deterministic_immutable_and_stateless():
    source, _, _ = _completed_execution()
    identity = _identity(source)
    service = ProductionAdapterRuntimeObservationService()

    first = service.observe(identity, source)
    second = service.observe(identity, source)

    assert first == second
    assert service.__dict__ == {}
    with pytest.raises(FrozenInstanceError):
        first.execution_status = "changed"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("observation_id", "bad-observation"),
        ("worker_id", "BAD-WORKER"),
        ("adapter_id", " adapter"),
        ("projection_id", ""),
        ("path_id", None),
        ("capability_id", "CAPABILITY "),
        ("binding_id", object()),
    ],
)
def test_invalid_observation_identity_fails_closed(field, value):
    source, _, _ = _completed_execution()
    with pytest.raises(InvalidProductionAdapterRuntimeObservationIdentityError):
        _identity(source, **{field: value})


@pytest.mark.parametrize(
    "field",
    [
        "worker_id",
        "adapter_id",
        "projection_id",
        "path_id",
        "capability_id",
        "binding_id",
    ],
)
def test_execution_identity_mismatch_fails_closed(field):
    source, factory, target = _completed_execution()
    identity = replace(_identity(source), **{field: "mismatched_identity"})

    with pytest.raises(
        ProductionAdapterRuntimeObservationIdentityMismatchError,
        match="conflicts",
    ):
        ProductionAdapterRuntimeObservationService().observe(identity, source)

    assert factory.calls == 1
    assert target.calls == 1


@pytest.mark.parametrize("invalid", [None, object(), "completed"])
def test_invalid_observation_source_fails_closed(invalid):
    source, _, _ = _completed_execution()
    service = ProductionAdapterRuntimeObservationService()

    with pytest.raises(InvalidProductionAdapterRuntimeObservationSourceError):
        service.observe(_identity(source), invalid)
    with pytest.raises(InvalidProductionAdapterRuntimeObservationSourceError):
        service.observe(invalid, source)


def test_result_rejects_status_trace_and_authority_conflicts():
    source, _, _ = _completed_execution()
    result = ProductionAdapterRuntimeObservationService().observe(
        _identity(source),
        source,
    )

    for changes in (
        {"execution_status": "running"},
        {"trace": ()},
        {"trace": "not-a-trace"},
        {"runtime_allowed": True},
        {"execution_allowed": True},
    ):
        with pytest.raises(InvalidProductionAdapterRuntimeObservationResultError):
            replace(result, **changes)


def test_public_contract_is_additive_and_package_scoped():
    assert observation_package.__all__ == [
        "InvalidProductionAdapterRuntimeObservationIdentityError",
        "InvalidProductionAdapterRuntimeObservationResultError",
        "InvalidProductionAdapterRuntimeObservationSourceError",
        "ProductionAdapterRuntimeObservationError",
        "ProductionAdapterRuntimeObservationIdentity",
        "ProductionAdapterRuntimeObservationIdentityMismatchError",
        "ProductionAdapterRuntimeObservationResult",
        "ProductionAdapterRuntimeObservationService",
    ]
    assert not hasattr(afde, "ProductionAdapterRuntimeObservationService")
    assert not hasattr(afde, "ProductionAdapterRuntimeObservationResult")
