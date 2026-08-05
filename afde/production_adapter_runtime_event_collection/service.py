"""Synchronous stateless collection of caller-supplied Runtime events."""
from __future__ import annotations

from .errors import InvalidProductionAdapterRuntimeEventCollectionRequestError
from .models import (
    ProductionAdapterRuntimeEventCollectionRequest,
    ProductionAdapterRuntimeEventCollectionResult,
    _events,
    _timestamp,
)


class ProductionAdapterRuntimeEventCollectionService:
    """Validate one request and return its ordered events without side effects."""

    def collect(
        self,
        request: ProductionAdapterRuntimeEventCollectionRequest,
    ) -> ProductionAdapterRuntimeEventCollectionResult:
        """Return a deterministic point-in-time collection result."""

        error = InvalidProductionAdapterRuntimeEventCollectionRequestError
        if type(request) is not ProductionAdapterRuntimeEventCollectionRequest:
            raise error(
                "request must be exactly one "
                "ProductionAdapterRuntimeEventCollectionRequest"
            )
        events = _events(request.events, error)
        _timestamp(request.collected_at, error, "collected_at")
        return ProductionAdapterRuntimeEventCollectionResult(
            events=events,
            event_count=len(events),
            collected_at=request.collected_at,
        )
