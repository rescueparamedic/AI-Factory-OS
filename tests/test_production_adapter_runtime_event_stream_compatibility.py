from inspect import Parameter, signature

import afde.production_adapter_runtime_event_collection as collection_package
from afde.production_adapter_runtime_event_collection import (
    ProductionAdapterRuntimeEventCollectionService,
)
from afde.production_adapter_runtime_event_stream import (
    ProductionAdapterRuntimeEventStreamRequest,
    ProductionAdapterRuntimeEventStreamResult,
    ProductionAdapterRuntimeEventStreamService,
)
from afde.production_adapter_runtime_execution import (
    ProductionAdapterRuntimeExecutionService,
)
from afde.production_adapter_runtime_observation import (
    ProductionAdapterRuntimeObservationService,
)


def test_existing_runtime_public_signatures_are_unchanged():
    assert tuple(
        signature(ProductionAdapterRuntimeEventCollectionService.collect).parameters
    ) == ("self", "request")
    assert tuple(
        signature(ProductionAdapterRuntimeObservationService.observe).parameters
    ) == ("self", "identity", "worker_execution_result")
    assert tuple(
        signature(ProductionAdapterRuntimeExecutionService.execute).parameters
    ) == ("self", "request")


def test_existing_event_collection_exports_are_unchanged():
    assert collection_package.__all__ == [
        "InvalidProductionAdapterRuntimeEventCollectionRequestError",
        "InvalidProductionAdapterRuntimeEventCollectionResultError",
        "InvalidProductionAdapterRuntimeEventError",
        "ProductionAdapterRuntimeEvent",
        "ProductionAdapterRuntimeEventCollectionError",
        "ProductionAdapterRuntimeEventCollectionRequest",
        "ProductionAdapterRuntimeEventCollectionResult",
        "ProductionAdapterRuntimeEventCollectionService",
    ]


def test_new_stream_operation_is_a_separate_additive_contract():
    assert tuple(
        signature(ProductionAdapterRuntimeEventStreamService.stream).parameters
    ) == ("self", "request")


def test_new_public_models_keep_keyword_only_constructor_contracts():
    expected_fields = {
        ProductionAdapterRuntimeEventStreamRequest: ("events", "streamed_at"),
        ProductionAdapterRuntimeEventStreamResult: (
            "events",
            "event_count",
            "streamed_at",
        ),
    }

    for model_type, field_names in expected_fields.items():
        parameters = signature(model_type).parameters
        assert tuple(parameters) == field_names
        assert all(
            parameter.kind is Parameter.KEYWORD_ONLY
            for parameter in parameters.values()
        )
