from inspect import signature
from pathlib import Path

import afde.production_adapter_runtime_observation as observation_package
from afde.knowledge import KnowledgeRegistryLoader
from afde.production_adapter_runtime_event_collection import (
    ProductionAdapterRuntimeEventCollectionService,
)
from afde.production_adapter_runtime_execution import (
    ProductionAdapterRuntimeExecutionService,
)
from afde.production_adapter_runtime_observation import (
    ProductionAdapterRuntimeObservationService,
)
from afde.production_adapter_worker_execution import (
    ProductionAdapterWorkerExecutionService,
)

ROOT = Path(__file__).resolve().parents[1]


def test_existing_public_execution_and_observation_signatures_are_unchanged():
    assert tuple(
        signature(ProductionAdapterRuntimeExecutionService.execute).parameters
    ) == ("self", "request")
    assert tuple(
        signature(ProductionAdapterWorkerExecutionService.execute).parameters
    ) == ("self", "request")
    assert tuple(
        signature(ProductionAdapterRuntimeObservationService.observe).parameters
    ) == ("self", "identity", "worker_execution_result")


def test_existing_observation_import_path_and_exports_are_unchanged():
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
    assert ProductionAdapterRuntimeObservationService.__module__ == (
        "afde.production_adapter_runtime_observation.service"
    )


def test_new_collection_operation_is_a_separate_additive_contract():
    assert tuple(
        signature(ProductionAdapterRuntimeEventCollectionService.collect).parameters
    ) == ("self", "request")


def test_existing_registry_entries_remain_and_new_capability_is_additive():
    capability_ids = {
        item.capability_id
        for item in KnowledgeRegistryLoader(ROOT).load().capabilities
    }

    assert {
        "CAP-PRODUCTIONADAPTERRUNTIMEEXECUTION-0001",
        "CAP-PRODUCTIONADAPTERWORKEREXECUTION-0001",
        "CAP-PRODUCTIONADAPTERRUNTIMEOBSERVATION-0001",
        "CAP-PRODUCTIONADAPTERRUNTIMEEVENTCOLLECTION-0001",
    }.issubset(capability_ids)
