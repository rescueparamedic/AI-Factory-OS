from inspect import signature

from afde.production_adapter_runtime_execution import (
    ProductionAdapterRuntimeExecutionService,
)
from afde.production_adapter_runtime_observation import (
    ProductionAdapterRuntimeObservationService,
)
from afde.production_adapter_worker_execution import (
    ProductionAdapterWorkerExecutionService,
)


def test_existing_execution_signatures_remain_unchanged():
    runtime_execution = signature(ProductionAdapterRuntimeExecutionService.execute)
    worker_execution = signature(ProductionAdapterWorkerExecutionService.execute)

    assert tuple(runtime_execution.parameters) == ("self", "request")
    assert tuple(worker_execution.parameters) == ("self", "request")


def test_observation_contract_is_a_separate_additive_signature():
    observation = signature(ProductionAdapterRuntimeObservationService.observe)

    assert tuple(observation.parameters) == (
        "self",
        "identity",
        "worker_execution_result",
    )
