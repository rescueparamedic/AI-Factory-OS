"""Immutable public contracts for synchronous Runtime event collection."""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from math import isfinite
from types import MappingProxyType
from typing import cast

from .errors import (
    InvalidProductionAdapterRuntimeEventCollectionRequestError,
    InvalidProductionAdapterRuntimeEventCollectionResultError,
    InvalidProductionAdapterRuntimeEventError,
)


@dataclass(frozen=True)
class ProductionAdapterRuntimeEvent:
    """One caller-supplied Runtime event with deeply immutable payload data."""

    event_id: str
    adapter_id: str
    event_type: str
    occurred_at: str
    payload: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        error = InvalidProductionAdapterRuntimeEventError
        _identity(self.event_id, error, "event_id")
        _identity(self.adapter_id, error, "adapter_id")
        _identity(self.event_type, error, "event_type")
        _timestamp(self.occurred_at, error, "occurred_at")
        try:
            payload = _freeze_mapping(self.payload, set())
        except InvalidProductionAdapterRuntimeEventError:
            raise
        except Exception:
            raise error("payload must contain supported immutable data") from None
        object.__setattr__(self, "payload", payload)


@dataclass(frozen=True)
class ProductionAdapterRuntimeEventCollectionRequest:
    """Explicit ordered Runtime events and caller-issued collection timestamp."""

    events: tuple[ProductionAdapterRuntimeEvent, ...]
    collected_at: str

    def __post_init__(self) -> None:
        error = InvalidProductionAdapterRuntimeEventCollectionRequestError
        _events(self.events, error)
        _timestamp(self.collected_at, error, "collected_at")


@dataclass(frozen=True)
class ProductionAdapterRuntimeEventCollectionResult:
    """Point-in-time collection result with no stream or history semantics."""

    events: tuple[ProductionAdapterRuntimeEvent, ...]
    event_count: int
    collected_at: str

    def __post_init__(self) -> None:
        error = InvalidProductionAdapterRuntimeEventCollectionResultError
        events = _events(self.events, error)
        if (
            isinstance(self.event_count, bool)
            or not isinstance(self.event_count, int)
            or self.event_count != len(events)
        ):
            raise error("event_count must equal the collected event count")
        _timestamp(self.collected_at, error, "collected_at")


def _events(
    values: object,
    error_type: type[Exception],
) -> tuple[ProductionAdapterRuntimeEvent, ...]:
    if not isinstance(values, tuple):
        raise error_type("events must be a tuple")
    if any(type(item) is not ProductionAdapterRuntimeEvent for item in values):
        raise error_type("events must contain only ProductionAdapterRuntimeEvent values")
    return cast(tuple[ProductionAdapterRuntimeEvent, ...], values)


def _identity(
    value: object,
    error_type: type[Exception],
    field_name: str,
) -> None:
    if (
        not isinstance(value, str)
        or not value
        or value != value.strip()
    ):
        raise error_type(f"{field_name} must be an exact non-empty identity")


def _timestamp(
    value: object,
    error_type: type[Exception],
    field_name: str,
) -> None:
    if not isinstance(value, str) or not value or value != value.strip():
        raise error_type(f"{field_name} must be a timezone-aware ISO timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        offset = parsed.utcoffset()
    except (OverflowError, ValueError):
        raise error_type(
            f"{field_name} must be a timezone-aware ISO timestamp"
        ) from None
    if parsed.tzinfo is None or offset is None:
        raise error_type(f"{field_name} must be a timezone-aware ISO timestamp")


def _freeze_mapping(
    value: object,
    active: set[int],
) -> Mapping[str, object]:
    error = InvalidProductionAdapterRuntimeEventError
    if not isinstance(value, Mapping):
        raise error("payload must be a mapping")
    identity = id(value)
    if identity in active:
        raise error("payload must not contain cycles")
    active.add(identity)
    try:
        frozen: dict[str, object] = {}
        for key, item in value.items():
            if not isinstance(key, str) or not key or key != key.strip():
                raise error("payload keys must be exact non-empty strings")
            frozen[key] = _freeze_value(item, active)
        return MappingProxyType(frozen)
    finally:
        active.remove(identity)


def _freeze_value(value: object, active: set[int]) -> object:
    error = InvalidProductionAdapterRuntimeEventError
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not isfinite(value):
            raise error("payload numbers must be finite")
        return value
    if isinstance(value, Mapping):
        return _freeze_mapping(value, active)
    if isinstance(value, (list, tuple)):
        identity = id(value)
        if identity in active:
            raise error("payload must not contain cycles")
        active.add(identity)
        try:
            return tuple(_freeze_value(item, active) for item in value)
        finally:
            active.remove(identity)
    raise error("payload contains an unsupported value")
