from dataclasses import FrozenInstanceError, is_dataclass, replace
from datetime import datetime
from types import MappingProxyType

import pytest

import afde
import afde.production_adapter_runtime_event_collection as collection_package
from afde.production_adapter_runtime_event_collection import (
    InvalidProductionAdapterRuntimeEventCollectionRequestError,
    InvalidProductionAdapterRuntimeEventCollectionResultError,
    InvalidProductionAdapterRuntimeEventError,
    ProductionAdapterRuntimeEvent,
    ProductionAdapterRuntimeEventCollectionRequest,
    ProductionAdapterRuntimeEventCollectionResult,
    ProductionAdapterRuntimeEventCollectionService,
)

COLLECTED_AT = "2026-08-05T18:30:00+09:00"


def _event(index=1, **overrides):
    values = {
        "event_id": f"RUNTIME-EVENT-AFDE-6.10-{index:03d}",
        "adapter_id": "adapter.runtime_event_collection_fixture",
        "event_type": f"adapter.event.{index}",
        "occurred_at": f"2026-08-05T18:2{index}:00+09:00",
        "payload": {
            "sequence": index,
            "accepted": True,
            "labels": ["runtime", "adapter"],
            "context": {"source": "caller"},
        },
    }
    values.update(overrides)
    return ProductionAdapterRuntimeEvent(**values)


def _request(*events):
    return ProductionAdapterRuntimeEventCollectionRequest(
        events=tuple(events),
        collected_at=COLLECTED_AT,
    )


def test_collects_one_runtime_event_with_exact_order_and_count():
    event = _event()
    request = _request(event)

    result = ProductionAdapterRuntimeEventCollectionService().collect(request)

    assert result.events == (event,)
    assert result.events is request.events
    assert result.event_count == 1
    assert result.collected_at == COLLECTED_AT
    assert datetime.fromisoformat(result.collected_at).tzinfo is not None


def test_collects_multiple_events_without_sorting_or_mutation():
    third = _event(3)
    first = _event(1)
    second = _event(2)
    request = _request(third, first, second)

    result = ProductionAdapterRuntimeEventCollectionService().collect(request)

    assert result.events == (third, first, second)
    assert result.event_count == 3
    assert request.events == (third, first, second)


def test_empty_collection_is_a_valid_deterministic_snapshot():
    request = _request()

    result = ProductionAdapterRuntimeEventCollectionService().collect(request)

    assert result.events == ()
    assert result.event_count == 0
    assert result.collected_at == COLLECTED_AT


def test_models_are_immutable_and_payload_is_defensively_frozen():
    payload = {
        "nested": {"value": "original"},
        "items": [1, {"enabled": True}],
    }
    event = _event(payload=payload)
    request = _request(event)
    result = ProductionAdapterRuntimeEventCollectionService().collect(request)

    payload["nested"]["value"] = "changed"
    payload["items"].append(2)

    assert isinstance(event.payload, MappingProxyType)
    assert isinstance(event.payload["nested"], MappingProxyType)
    assert event.payload["nested"]["value"] == "original"
    assert event.payload["items"] == (1, MappingProxyType({"enabled": True}))
    with pytest.raises(TypeError):
        event.payload["new"] = "forbidden"
    for instance, field_name, value in (
        (event, "event_type", "changed"),
        (request, "events", ()),
        (result, "event_count", 0),
    ):
        with pytest.raises(FrozenInstanceError):
            setattr(instance, field_name, value)


def test_public_models_are_frozen_slotted_and_have_no_instance_dict():
    event = _event()
    request = _request(event)
    result = ProductionAdapterRuntimeEventCollectionService().collect(request)

    for model_type, instance in (
        (ProductionAdapterRuntimeEvent, event),
        (ProductionAdapterRuntimeEventCollectionRequest, request),
        (ProductionAdapterRuntimeEventCollectionResult, result),
    ):
        assert is_dataclass(model_type)
        assert model_type.__dataclass_params__.frozen is True
        assert "__slots__" in model_type.__dict__
        assert not hasattr(instance, "__dict__")
        with pytest.raises((AttributeError, TypeError)):
            setattr(instance, "unexpected", "forbidden")


def test_public_models_reject_positional_construction():
    event = _event()
    with pytest.raises(TypeError):
        ProductionAdapterRuntimeEvent(
            event.event_id,
            event.adapter_id,
            event.event_type,
            event.occurred_at,
            event.payload,
        )
    with pytest.raises(TypeError):
        ProductionAdapterRuntimeEventCollectionRequest(
            (event,),
            COLLECTED_AT,
        )
    with pytest.raises(TypeError):
        ProductionAdapterRuntimeEventCollectionResult(
            (event,),
            1,
            COLLECTED_AT,
        )


def test_public_models_accept_explicit_keyword_construction():
    event = ProductionAdapterRuntimeEvent(
        event_id="RUNTIME-EVENT-AFDE-6.10-KEYWORD",
        adapter_id="adapter.runtime_event_collection_fixture",
        event_type="adapter.event.keyword",
        occurred_at="2026-08-05T18:20:00+09:00",
        payload={"construction": "keyword-only"},
    )
    request = ProductionAdapterRuntimeEventCollectionRequest(
        events=(event,),
        collected_at=COLLECTED_AT,
    )
    result = ProductionAdapterRuntimeEventCollectionResult(
        events=request.events,
        event_count=1,
        collected_at=request.collected_at,
    )

    assert result.events == (event,)
    assert result.event_count == 1


def test_service_is_stateless_and_same_request_is_deterministic():
    request = _request(_event(1), _event(2))
    service = ProductionAdapterRuntimeEventCollectionService()

    first = service.collect(request)
    second = service.collect(request)

    assert first == second
    assert first is not second
    assert service.__dict__ == {}


@pytest.mark.parametrize("invalid", [None, object(), (), [_event()]])
def test_invalid_request_type_is_rejected(invalid):
    with pytest.raises(
        InvalidProductionAdapterRuntimeEventCollectionRequestError,
        match="exactly one",
    ):
        ProductionAdapterRuntimeEventCollectionService().collect(invalid)


@pytest.mark.parametrize("invalid_events", [[_event()], set(), "event"])
def test_invalid_event_collection_shape_is_rejected(invalid_events):
    with pytest.raises(
        InvalidProductionAdapterRuntimeEventCollectionRequestError,
        match="tuple",
    ):
        ProductionAdapterRuntimeEventCollectionRequest(
            events=invalid_events,
            collected_at=COLLECTED_AT,
        )


@pytest.mark.parametrize("invalid_event", [None, object(), "event"])
def test_invalid_event_type_is_rejected(invalid_event):
    with pytest.raises(
        InvalidProductionAdapterRuntimeEventCollectionRequestError,
        match="ProductionAdapterRuntimeEvent",
    ):
        _request(invalid_event)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("event_id", ""),
        ("event_id", " event"),
        ("adapter_id", ""),
        ("adapter_id", "adapter "),
        ("event_type", ""),
        ("event_type", None),
    ],
)
def test_empty_or_inexact_event_identifiers_are_rejected(field, value):
    with pytest.raises(
        InvalidProductionAdapterRuntimeEventError,
        match=field,
    ):
        _event(**{field: value})


@pytest.mark.parametrize(
    "timestamp",
    ["", "not-a-time", "2026-08-05T18:20:00", None, 123],
)
def test_invalid_event_timestamp_is_rejected(timestamp):
    with pytest.raises(
        InvalidProductionAdapterRuntimeEventError,
        match="timezone-aware ISO timestamp",
    ):
        _event(occurred_at=timestamp)


@pytest.mark.parametrize(
    "payload",
    [
        None,
        [],
        {"": "value"},
        {"bad ": "value"},
        {"unsupported": object()},
        {"unsupported": {1, 2}},
        {"not_finite": float("nan")},
        {"not_finite": float("inf")},
    ],
)
def test_invalid_payload_is_rejected(payload):
    with pytest.raises(InvalidProductionAdapterRuntimeEventError):
        _event(payload=payload)


def test_cyclic_payload_is_rejected_without_leaking_recursion_error():
    payload = {}
    payload["self"] = payload

    with pytest.raises(
        InvalidProductionAdapterRuntimeEventError,
        match="cycles",
    ):
        _event(payload=payload)


@pytest.mark.parametrize(
    "timestamp",
    ["", "invalid", "2026-08-05T18:30:00", None],
)
def test_invalid_collection_timestamp_is_rejected(timestamp):
    with pytest.raises(
        InvalidProductionAdapterRuntimeEventCollectionRequestError,
        match="timezone-aware ISO timestamp",
    ):
        ProductionAdapterRuntimeEventCollectionRequest(
            events=(_event(),),
            collected_at=timestamp,
        )


def test_result_rejects_count_collection_and_timestamp_conflicts():
    result = ProductionAdapterRuntimeEventCollectionService().collect(
        _request(_event())
    )

    for changes in (
        {"event_count": 0},
        {"event_count": True},
        {"events": [_event()]},
        {"events": (object(),)},
        {"collected_at": "not-a-time"},
    ):
        with pytest.raises(InvalidProductionAdapterRuntimeEventCollectionResultError):
            replace(result, **changes)


def test_public_contract_is_additive_and_package_scoped():
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
    assert not hasattr(afde, "ProductionAdapterRuntimeEvent")
    assert not hasattr(afde, "ProductionAdapterRuntimeEventCollectionService")
    assert ProductionAdapterRuntimeEventCollectionResult.__module__ == (
        "afde.production_adapter_runtime_event_collection.models"
    )
