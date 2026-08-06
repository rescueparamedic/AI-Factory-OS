from inspect import Parameter, signature

import afde.production_adapter_runtime_event_collection as collection_package
from afde.production_adapter_runtime_event_collection import (
    ProductionAdapterRuntimeEvent,
    ProductionAdapterRuntimeEventCollectionRequest,
    ProductionAdapterRuntimeEventCollectionService,
)
from afde.production_adapter_runtime_event_stream import (
    ProductionAdapterRuntimeEventStreamRequest,
    ProductionAdapterRuntimeEventStreamResult,
    ProductionAdapterRuntimeEventStreamService,
    ProductionAdapterRuntimeEventStreamSnapshot,
    ProductionAdapterRuntimeEventStreamState,
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
    assert tuple(
        signature(ProductionAdapterRuntimeEventStreamService.open).parameters
    ) == ("self", "opened_at")
    assert tuple(
        signature(ProductionAdapterRuntimeEventStreamService.append).parameters
    ) == ("self", "event")
    assert tuple(
        signature(ProductionAdapterRuntimeEventStreamService.close).parameters
    ) == ("self", "closed_at")
    assert (
        signature(ProductionAdapterRuntimeEventStreamService.open)
        .parameters["opened_at"]
        .kind
        is Parameter.KEYWORD_ONLY
    )
    assert (
        signature(ProductionAdapterRuntimeEventStreamService.close)
        .parameters["closed_at"]
        .kind
        is Parameter.KEYWORD_ONLY
    )


def test_new_public_models_keep_keyword_only_constructor_contracts():
    expected_fields = {
        ProductionAdapterRuntimeEventStreamRequest: ("events", "streamed_at"),
        ProductionAdapterRuntimeEventStreamResult: (
            "events",
            "event_count",
            "streamed_at",
        ),
        ProductionAdapterRuntimeEventStreamSnapshot: (
            "events",
            "count",
            "opened_at",
            "closed_at",
            "state",
        ),
    }

    for model_type, field_names in expected_fields.items():
        parameters = signature(model_type).parameters
        assert tuple(parameters) == field_names
        assert all(
            parameter.kind is Parameter.KEYWORD_ONLY
            for parameter in parameters.values()
        )


def test_existing_collection_remains_a_point_in_time_tuple_contract():
    event = ProductionAdapterRuntimeEvent(
        event_id="RUNTIME-EVENT-COMPAT-001",
        adapter_id="adapter.compatibility",
        event_type="adapter.compatibility.event",
        occurred_at="2026-08-05T19:00:00+09:00",
    )
    request = ProductionAdapterRuntimeEventCollectionRequest(
        events=(event,),
        collected_at="2026-08-05T20:00:00+09:00",
    )

    result = ProductionAdapterRuntimeEventCollectionService().collect(request)

    assert result.events is request.events
    assert result.events[0] is event
    assert result.event_count == 1
    assert not hasattr(
        ProductionAdapterRuntimeEventCollectionService,
        "open",
    )
    assert set(ProductionAdapterRuntimeEventStreamState) == {
        ProductionAdapterRuntimeEventStreamState.CREATED,
        ProductionAdapterRuntimeEventStreamState.OPEN,
        ProductionAdapterRuntimeEventStreamState.CLOSED,
    }
