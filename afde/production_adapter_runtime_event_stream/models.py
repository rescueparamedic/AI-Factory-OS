"""Immutable public contracts for a synchronous bounded Runtime event stream."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import cast

from afde.production_adapter_runtime_event_collection import (
    ProductionAdapterRuntimeEvent,
)

from .errors import (
    InvalidProductionAdapterRuntimeEventStreamRequestError,
    InvalidProductionAdapterRuntimeEventStreamResultError,
)


class ProductionAdapterRuntimeEventStreamState(str, Enum):
    """Explicit lifecycle state for one finite in-memory stream."""

    CREATED = "CREATED"
    OPEN = "OPEN"
    CLOSED = "CLOSED"


@dataclass(frozen=True, slots=True, kw_only=True)
class ProductionAdapterRuntimeEventStreamRequest:
    """Explicit ordered Runtime events and caller-issued stream timestamp."""

    events: tuple[ProductionAdapterRuntimeEvent, ...]
    streamed_at: str

    def __post_init__(self) -> None:
        error = InvalidProductionAdapterRuntimeEventStreamRequestError
        _events(self.events, error)
        _timestamp(self.streamed_at, error, "streamed_at")


@dataclass(frozen=True, slots=True, kw_only=True)
class ProductionAdapterRuntimeEventStreamResult:
    """Bounded in-memory stream view with no subscription or storage semantics."""

    events: tuple[ProductionAdapterRuntimeEvent, ...]
    event_count: int
    streamed_at: str

    def __post_init__(self) -> None:
        error = InvalidProductionAdapterRuntimeEventStreamResultError
        events = _events(self.events, error)
        if (
            isinstance(self.event_count, bool)
            or not isinstance(self.event_count, int)
            or self.event_count != len(events)
        ):
            raise error("event_count must equal the streamed event count")
        _timestamp(self.streamed_at, error, "streamed_at")


@dataclass(frozen=True, slots=True, kw_only=True)
class ProductionAdapterRuntimeEventStreamSnapshot:
    """Immutable final view returned when an open stream is closed."""

    events: tuple[ProductionAdapterRuntimeEvent, ...]
    count: int
    opened_at: str
    closed_at: str
    state: ProductionAdapterRuntimeEventStreamState

    def __post_init__(self) -> None:
        error = InvalidProductionAdapterRuntimeEventStreamResultError
        events = _events(self.events, error)
        if (
            isinstance(self.count, bool)
            or not isinstance(self.count, int)
            or self.count != len(events)
        ):
            raise error("count must equal the streamed event count")
        opened_at = _timestamp(self.opened_at, error, "opened_at")
        closed_at = _timestamp(self.closed_at, error, "closed_at")
        if closed_at < opened_at:
            raise error("closed_at must not precede opened_at")
        if self.state is not ProductionAdapterRuntimeEventStreamState.CLOSED:
            raise error("snapshot state must be CLOSED")


def _events(
    values: object,
    error_type: type[Exception],
) -> tuple[ProductionAdapterRuntimeEvent, ...]:
    if not isinstance(values, tuple):
        raise error_type("events must be a tuple")
    if any(type(item) is not ProductionAdapterRuntimeEvent for item in values):
        raise error_type(
            "events must contain only ProductionAdapterRuntimeEvent values"
        )
    return cast(tuple[ProductionAdapterRuntimeEvent, ...], values)


def _timestamp(
    value: object,
    error_type: type[Exception],
    field_name: str,
) -> datetime:
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
    return parsed
