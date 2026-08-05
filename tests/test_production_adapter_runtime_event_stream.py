from dataclasses import FrozenInstanceError, is_dataclass, replace
from datetime import datetime

import pytest

import afde
import afde.production_adapter_runtime_event_stream as stream_package
from afde.production_adapter_runtime_event_collection import (
    ProductionAdapterRuntimeEvent,
)
from afde.production_adapter_runtime_event_stream import (
    InvalidProductionAdapterRuntimeEventStreamRequestError,
    InvalidProductionAdapterRuntimeEventStreamResultError,
    ProductionAdapterRuntimeEventStreamRequest,
    ProductionAdapterRuntimeEventStreamResult,
    ProductionAdapterRuntimeEventStreamService,
)

STREAMED_AT = "2026-08-05T20:00:00+09:00"


def _event(index=1):
    return ProductionAdapterRuntimeEvent(
        event_id=f"RUNTIME-EVENT-AFDE-6.11-{index:03d}",
        adapter_id="adapter.runtime_event_stream_fixture",
        event_type=f"adapter.stream.event.{index}",
        occurred_at=f"2026-08-05T19:5{index}:00+09:00",
        payload={"sequence": index, "source": "caller"},
    )


def _request(*events):
    return ProductionAdapterRuntimeEventStreamRequest(
        events=tuple(events),
        streamed_at=STREAMED_AT,
    )


def test_streams_one_runtime_event_with_exact_order_and_count():
    event = _event()
    request = _request(event)

    result = ProductionAdapterRuntimeEventStreamService().stream(request)

    assert result.events == (event,)
    assert result.events is request.events
    assert result.event_count == 1
    assert result.streamed_at == STREAMED_AT
    assert datetime.fromisoformat(result.streamed_at).tzinfo is not None


def test_streams_multiple_events_without_sorting_or_mutation():
    third = _event(3)
    first = _event(1)
    second = _event(2)
    request = _request(third, first, second)

    result = ProductionAdapterRuntimeEventStreamService().stream(request)

    assert result.events == (third, first, second)
    assert result.event_count == 3
    assert request.events == (third, first, second)


def test_empty_stream_is_a_valid_deterministic_result():
    result = ProductionAdapterRuntimeEventStreamService().stream(_request())

    assert result.events == ()
    assert result.event_count == 0
    assert result.streamed_at == STREAMED_AT


def test_models_are_frozen_slotted_keyword_only_and_have_no_instance_dict():
    request = _request(_event())
    result = ProductionAdapterRuntimeEventStreamService().stream(request)

    for model_type, instance in (
        (ProductionAdapterRuntimeEventStreamRequest, request),
        (ProductionAdapterRuntimeEventStreamResult, result),
    ):
        assert is_dataclass(model_type)
        assert model_type.__dataclass_params__.frozen is True
        assert "__slots__" in model_type.__dict__
        assert not hasattr(instance, "__dict__")
        with pytest.raises((AttributeError, TypeError)):
            instance.unexpected = "forbidden"

    with pytest.raises(FrozenInstanceError):
        request.events = ()
    with pytest.raises(FrozenInstanceError):
        result.event_count = 0
    with pytest.raises(TypeError):
        ProductionAdapterRuntimeEventStreamRequest((_event(),), STREAMED_AT)
    with pytest.raises(TypeError):
        ProductionAdapterRuntimeEventStreamResult((_event(),), 1, STREAMED_AT)


def test_service_is_stateless_and_same_request_is_deterministic():
    request = _request(_event(1), _event(2))
    service = ProductionAdapterRuntimeEventStreamService()

    first = service.stream(request)
    second = service.stream(request)

    assert first == second
    assert first is not second
    assert service.__dict__ == {}


@pytest.mark.parametrize("invalid", [None, object(), (), [_event()]])
def test_invalid_request_type_is_rejected(invalid):
    with pytest.raises(
        InvalidProductionAdapterRuntimeEventStreamRequestError,
        match="exactly one",
    ):
        ProductionAdapterRuntimeEventStreamService().stream(invalid)


@pytest.mark.parametrize("invalid_events", [[_event()], set(), "event"])
def test_invalid_event_stream_shape_is_rejected(invalid_events):
    with pytest.raises(
        InvalidProductionAdapterRuntimeEventStreamRequestError,
        match="tuple",
    ):
        ProductionAdapterRuntimeEventStreamRequest(
            events=invalid_events,
            streamed_at=STREAMED_AT,
        )


@pytest.mark.parametrize("invalid_event", [None, object(), "event"])
def test_invalid_event_type_is_rejected(invalid_event):
    with pytest.raises(
        InvalidProductionAdapterRuntimeEventStreamRequestError,
        match="ProductionAdapterRuntimeEvent",
    ):
        _request(invalid_event)


@pytest.mark.parametrize(
    "timestamp",
    ["", "invalid", "2026-08-05T20:00:00", None, 123],
)
def test_invalid_stream_timestamp_is_rejected(timestamp):
    with pytest.raises(
        InvalidProductionAdapterRuntimeEventStreamRequestError,
        match="timezone-aware ISO timestamp",
    ):
        ProductionAdapterRuntimeEventStreamRequest(
            events=(_event(),),
            streamed_at=timestamp,
        )


def test_result_rejects_count_stream_and_timestamp_conflicts():
    result = ProductionAdapterRuntimeEventStreamService().stream(_request(_event()))

    for changes in (
        {"event_count": 0},
        {"event_count": True},
        {"events": [_event()]},
        {"events": (object(),)},
        {"streamed_at": "not-a-time"},
    ):
        with pytest.raises(InvalidProductionAdapterRuntimeEventStreamResultError):
            replace(result, **changes)


def test_public_contract_is_additive_and_package_scoped():
    assert stream_package.__all__ == [
        "InvalidProductionAdapterRuntimeEventStreamRequestError",
        "InvalidProductionAdapterRuntimeEventStreamResultError",
        "ProductionAdapterRuntimeEventStreamError",
        "ProductionAdapterRuntimeEventStreamRequest",
        "ProductionAdapterRuntimeEventStreamResult",
        "ProductionAdapterRuntimeEventStreamService",
    ]
    assert not hasattr(afde, "ProductionAdapterRuntimeEventStreamRequest")
    assert not hasattr(afde, "ProductionAdapterRuntimeEventStreamService")
    assert ProductionAdapterRuntimeEventStreamResult.__module__ == (
        "afde.production_adapter_runtime_event_stream.models"
    )
