from inspect import signature

from afde.production_adapter_runtime_execution import (
    ProductionAdapterRuntimeExecutionService,
)
from afde.production_adapter_worker_execution import (
    ProductionAdapterWorkerExecutionService,
)
from real_worker_runtime.execution_adapter import SingleWorkerExecutionAdapter


def test_existing_runtime_execution_signature_remains_unchanged():
    execution = signature(ProductionAdapterRuntimeExecutionService.execute)
    assert tuple(execution.parameters) == ("self", "request")


def test_existing_worker_execution_signatures_remain_unchanged():
    constructor = signature(SingleWorkerExecutionAdapter.__init__)
    assert tuple(constructor.parameters) == (
        "self",
        "worker_id",
        "executor",
        "registry",
    )
    execute = signature(SingleWorkerExecutionAdapter.execute)
    assert tuple(execute.parameters) == ("self", "value")


def test_new_worker_execution_signature_is_separate():
    execution = signature(ProductionAdapterWorkerExecutionService.execute)
    assert tuple(execution.parameters) == ("self", "request")
