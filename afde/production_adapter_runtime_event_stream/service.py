"""Finite synchronous lifecycle for caller-supplied Runtime events."""

from __future__ import annotations

from afde.production_adapter_runtime_event_collection import (
    ProductionAdapterRuntimeEvent,
)

from .errors import (
    InvalidProductionAdapterRuntimeEventStreamEventError,
    InvalidProductionAdapterRuntimeEventStreamRequestError,
    InvalidProductionAdapterRuntimeEventStreamTimestampError,
    InvalidProductionAdapterRuntimeEventStreamTransitionError,
)
from .models import (
    ProductionAdapterRuntimeEventStreamRequest,
    ProductionAdapterRuntimeEventStreamResult,
    ProductionAdapterRuntimeEventStreamSnapshot,
    ProductionAdapterRuntimeEventStreamState,
    _events,
    _timestamp,
)


class ProductionAdapterRuntimeEventStreamService:
    """Own one CREATED to OPEN to CLOSED in-memory stream lifecycle."""

    __slots__ = ("_events", "_opened_at", "_snapshot", "_state")

    def __init__(self) -> None:
        self._state = ProductionAdapterRuntimeEventStreamState.CREATED
        self._events: tuple[ProductionAdapterRuntimeEvent, ...] = ()
        self._opened_at: str | None = None
        self._snapshot: ProductionAdapterRuntimeEventStreamSnapshot | None = None

    @property
    def state(self) -> ProductionAdapterRuntimeEventStreamState:
        """Return the current lifecycle state without exposing mutation."""

        return self._state

    @property
    def snapshot(self) -> ProductionAdapterRuntimeEventStreamSnapshot | None:
        """Return the final immutable snapshot after close, otherwise None."""

        return self._snapshot

    def open(self, *, opened_at: str) -> None:
        """Transition one newly created stream to OPEN."""

        if self._state is not ProductionAdapterRuntimeEventStreamState.CREATED:
            raise InvalidProductionAdapterRuntimeEventStreamTransitionError(
                "open requires CREATED state"
            )
        _timestamp(
            opened_at,
            InvalidProductionAdapterRuntimeEventStreamTimestampError,
            "opened_at",
        )
        self._opened_at = opened_at
        self._state = ProductionAdapterRuntimeEventStreamState.OPEN

    def append(self, event: ProductionAdapterRuntimeEvent) -> None:
        """Append one exact Runtime event while preserving order and identity."""

        if self._state is not ProductionAdapterRuntimeEventStreamState.OPEN:
            raise InvalidProductionAdapterRuntimeEventStreamTransitionError(
                "append requires OPEN state"
            )
        if type(event) is not ProductionAdapterRuntimeEvent:
            raise InvalidProductionAdapterRuntimeEventStreamEventError(
                "event must be exactly one ProductionAdapterRuntimeEvent"
            )
        self._events = (*self._events, event)

    def close(
        self,
        *,
        closed_at: str,
    ) -> ProductionAdapterRuntimeEventStreamSnapshot:
        """Transition an open stream to CLOSED and return its final snapshot."""

        if self._state is not ProductionAdapterRuntimeEventStreamState.OPEN:
            raise InvalidProductionAdapterRuntimeEventStreamTransitionError(
                "close requires OPEN state"
            )
        error = InvalidProductionAdapterRuntimeEventStreamTimestampError
        closed = _timestamp(closed_at, error, "closed_at")
        if self._opened_at is None:  # Defensive invariant; OPEN always sets it.
            raise error("OPEN stream must have opened_at")
        opened = _timestamp(self._opened_at, error, "opened_at")
        if closed < opened:
            raise error("closed_at must not precede opened_at")
        snapshot = ProductionAdapterRuntimeEventStreamSnapshot(
            events=self._events,
            count=len(self._events),
            opened_at=self._opened_at,
            closed_at=closed_at,
            state=ProductionAdapterRuntimeEventStreamState.CLOSED,
        )
        self._snapshot = snapshot
        self._state = ProductionAdapterRuntimeEventStreamState.CLOSED
        return snapshot

    def stream(
        self,
        request: ProductionAdapterRuntimeEventStreamRequest,
    ) -> ProductionAdapterRuntimeEventStreamResult:
        """Preserve the original one-shot contract as a compatibility helper."""

        error = InvalidProductionAdapterRuntimeEventStreamRequestError
        if type(request) is not ProductionAdapterRuntimeEventStreamRequest:
            raise error(
                "request must be exactly one ProductionAdapterRuntimeEventStreamRequest"
            )
        events = _events(request.events, error)
        _timestamp(request.streamed_at, error, "streamed_at")
        lifecycle = type(self)()
        lifecycle.open(opened_at=request.streamed_at)
        for event in events:
            lifecycle.append(event)
        lifecycle.close(closed_at=request.streamed_at)
        return ProductionAdapterRuntimeEventStreamResult(
            events=events,
            event_count=len(events),
            streamed_at=request.streamed_at,
        )
