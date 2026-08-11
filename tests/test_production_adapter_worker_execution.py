from dataclasses import dataclass, replace
from pathlib import Path
from uuid import uuid4

import pytest

import afde
import afde.production_adapter_worker_execution as worker_package
from afde.knowledge import KnowledgeFoundationProvider
from afde.production_adapter_creation import ProductionAdapterInstance
from afde.production_adapter_invocation import InvocationTargetResult
from afde.production_adapter_runtime_execution import (
    ProductionAdapterRuntimeExecutionAuthority,
    ProductionAdapterRuntimeExecutionAuthorityReuseError,
    ProductionAdapterRuntimeExecutionRequest,
    ProductionAdapterRuntimeExecutionService,
)
from afde.production_adapter_runtime_startup_integration import (
    build_production_adapter_runtime_startup_composition,
)
from afde.production_adapter_worker_execution import (
    InvalidProductionAdapterWorkerExecutionRequestError,
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
from real_worker_runtime.models import ExecutionInput, WorkerExecutionResult

ROOT = Path(__file__).resolve().parents[1]
ADAPTER_ID = "adapter.worker_execution_fixture"
CAPABILITY_ID = "CAP-WORKEREXECUTIONFIXTURE-0001"


def _descriptor():
    return ToolAdapterDescriptor(
        adapter_id=ADAPTER_ID,
        display_name="Worker Execution Fixture",
        version="1.0.0",
        supported_capability_ids=(CAPABILITY_ID,),
        availability=AdapterAvailability.AVAILABLE,
        runtime_compatibility=RuntimeCompatibility.COMPATIBLE,
        execution_contract=ExecutionContract.CONTROLLED_RUNTIME,
        privacy_classification=PrivacyClassification.LOCAL,
        cost_classification=CostClassification.NO_COST,
        credentials_required=False,
        description="Worker execution foundation fixture.",
        metadata_references=("fixture:worker-execution",),
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
        return (FakeEntryPoint("worker", "fake:worker", self.descriptor),)


class FakeFactory:
    def __init__(self):
        self.adapter_id = ADAPTER_ID
        self.contexts = []

    def create(self, context):
        self.contexts.append(context)
        return ProductionAdapterInstance(
            adapter_id=context.adapter_id,
            creation_metadata_references=(
                "CREATION-REFERENCE-WORKER-EXECUTION-001",
            ),
        )


class FakeInvocationTarget:
    def __init__(self):
        self.adapter_id = ADAPTER_ID
        self.requests = []

    def invoke(self, request):
        self.requests.append(request)
        return InvocationTargetResult(
            adapter_id=self.adapter_id,
            result_metadata_references=(
                "INVOCATION-RESULT-REFERENCE-WORKER-EXECUTION-001",
            ),
        )


class RecordingRuntimeExecutionService(
    ProductionAdapterRuntimeExecutionService
):
    def __init__(self):
        self.requests = []

    def execute(self, request):
        self.requests.append(request)
        return super().execute(request)


def _worker_input(worker_id="development_worker"):
    return ExecutionInput(
        plan_id="PLAN-WORKER-EXECUTION-001",
        task_id="TASK-WORKER-EXECUTION-001",
        worker_id=worker_id,
        instruction="invoke the bounded Production Adapter request",
        provider="not-selected",
        model="not-selected",
        execution_mode="production_adapter_runtime",
        metadata={"source": "afde-6.7"},
    )


def _runtime_request():
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
        projection_id="RUNTIMEPROJ-0000000000000067",
        projection_version="1.0.0",
        path_id="EXECPATH-0000000000000067",
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
        authority_reference=(
            f"RUNTIME-EXECUTION-AUTHORITY-{uuid4().hex.upper()}"
        ),
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
            "INVOCATION-REFERENCE-WORKER-EXECUTION-001",
        ),
    )
    return request, factory, target


def _request(worker_id="development_worker"):
    runtime_request, factory, target = _runtime_request()
    return (
        ProductionAdapterWorkerExecutionRequest(
            worker_input=_worker_input(worker_id),
            startup_composition=runtime_request.startup_composition,
            tool_adapter_request=runtime_request.tool_adapter_request,
            binding=runtime_request.binding,
            authority=runtime_request.authority,
            invocation_metadata_references=(
                runtime_request.invocation_metadata_references
            ),
        ),
        factory,
        target,
    )


def test_worker_execution_preserves_identity_and_exact_runtime_results():
    request, factory, target = _request()
    runtime_service = RecordingRuntimeExecutionService()

    result = ProductionAdapterWorkerExecutionService(
        runtime_service
    ).execute(request)

    assert len(runtime_service.requests) == 1
    assembled = runtime_service.requests[0]
    assert assembled.startup_composition is request.startup_composition
    assert assembled.tool_adapter_request is request.tool_adapter_request
    assert assembled.binding is request.binding
    assert assembled.authority is request.authority
    assert result.worker_id == request.worker_input.worker_id
    assert type(result.worker_result) is WorkerExecutionResult
    assert result.worker_result.worker_id == request.worker_input.worker_id
    assert result.worker_result.execution_status == "completed"
    assert result.runtime_execution_result.creation_result is (
        target.requests[0].creation_result
    )
    assert result.runtime_execution_result.invocation_result.request is (
        target.requests[0]
    )
    assert factory.contexts == [target.requests[0].creation_result.context]
    assert len(target.requests) == 1


@pytest.mark.parametrize("worker_id", ["", " development_worker", "BAD-ID"])
def test_missing_or_invalid_worker_identity_fails_closed(worker_id):
    runtime_request, factory, target = _runtime_request()
    with pytest.raises(InvalidProductionAdapterWorkerExecutionRequestError):
        ProductionAdapterWorkerExecutionRequest(
            worker_input=_worker_input(worker_id),
            startup_composition=runtime_request.startup_composition,
            tool_adapter_request=runtime_request.tool_adapter_request,
            binding=runtime_request.binding,
            authority=runtime_request.authority,
        )
    assert factory.contexts == []
    assert target.requests == []


def test_worker_registry_is_not_used_to_complete_identity(monkeypatch):
    request, factory, target = _request("unregistered_worker")

    def reject_registry_lookup(self):
        raise AssertionError("Worker Registry lookup is forbidden")

    monkeypatch.setattr(
        "real_worker_runtime.worker_registry.WorkerRegistry.list",
        reject_registry_lookup,
    )
    result = ProductionAdapterWorkerExecutionService().execute(request)

    assert result.worker_id == "unregistered_worker"
    assert len(factory.contexts) == 1
    assert len(target.requests) == 1


def test_legacy_service_keeps_existing_non_identity_field_semantics():
    request, _, target = _request()
    legacy_input = replace(
        request.worker_input,
        plan_id="",
        task_id="",
        provider="",
        model="",
        execution_mode="",
    )
    legacy_request = replace(request, worker_input=legacy_input)

    result = ProductionAdapterWorkerExecutionService().execute(legacy_request)

    assert result.worker_result.plan_id == ""
    assert result.worker_result.task_id == ""
    assert result.worker_result.provider == ""
    assert len(target.requests) == 1


def test_existing_runtime_execution_error_propagates_unchanged():
    request, factory, target = _request()
    ProductionAdapterRuntimeExecutionService().execute(
        request.build_runtime_execution_request()
    )
    service = RecordingRuntimeExecutionService()

    with pytest.raises(
        ProductionAdapterRuntimeExecutionAuthorityReuseError
    ) as captured:
        ProductionAdapterWorkerExecutionService(service).execute(request)

    assert type(captured.value) is ProductionAdapterRuntimeExecutionAuthorityReuseError
    assert len(service.requests) == 1
    assert service.requests[0].authority is request.authority
    assert len(factory.contexts) == 1
    assert len(target.requests) == 1


def test_provider_bridge_is_never_selected_or_called(monkeypatch):
    request, _, _ = _request()

    def forbidden(*args, **kwargs):
        raise AssertionError("ProviderBridge use is forbidden")

    monkeypatch.setattr(
        "real_worker_runtime.provider_bridge.ProviderBridge.select",
        forbidden,
    )
    monkeypatch.setattr(
        "real_worker_runtime.provider_bridge.ProviderBridge.generate",
        forbidden,
    )

    result = ProductionAdapterWorkerExecutionService().execute(request)
    assert result.worker_result.provider == "not-selected"


def test_public_contract_is_additive_and_package_scoped():
    assert not hasattr(afde, "ProductionAdapterWorkerExecutionService")
    assert worker_package.__all__ == [
        "InvalidProductionAdapterWorkerExecutionRequestError",
        "InvalidProductionAdapterWorkerExecutionResultError",
        "ProductionAdapterWorkerExecutionError",
        "ProductionAdapterWorkerExecutionIdentityMismatchError",
        "ProductionAdapterWorkerExecutionRequest",
        "ProductionAdapterWorkerExecutionResult",
        "ProductionAdapterWorkerExecutionService",
        "ProductionAdapterWorkerResultProjector",
    ]
