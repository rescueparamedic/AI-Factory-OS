"""Synchronous stateless projection of caller-supplied Runtime events."""

from __future__ import annotations

from .errors import InvalidProductionAdapterRuntimeEventStreamRequestError
from .models import (
    ProductionAdapterRuntimeEventStreamRequest,
    ProductionAdapterRuntimeEventStreamResult,
    _events,
    _timestamp,
)


class ProductionAdapterRuntimeEventStreamService:
    """Validate one bounded request and preserve its exact event order."""

    def stream(
        self,
        request: ProductionAdapterRuntimeEventStreamRequest,
    ) -> ProductionAdapterRuntimeEventStreamResult:
        """Return a deterministic bounded stream result without side effects."""

        error = InvalidProductionAdapterRuntimeEventStreamRequestError
        if type(request) is not ProductionAdapterRuntimeEventStreamRequest:
            raise error(
                "request must be exactly one ProductionAdapterRuntimeEventStreamRequest"
            )
        events = _events(request.events, error)
        _timestamp(request.streamed_at, error, "streamed_at")
        return ProductionAdapterRuntimeEventStreamResult(
            events=events,
            event_count=len(events),
            streamed_at=request.streamed_at,
        )
