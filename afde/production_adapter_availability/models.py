"""Immutable production Tool Adapter availability metadata result."""
from __future__ import annotations

from dataclasses import dataclass

from afde.tool_catalog import AdapterAvailability, ToolAdapterDescriptor

from .errors import InvalidAvailabilityResultError


@dataclass(frozen=True)
class ProductionAdapterAvailabilityResult:
    """One descriptor's declared availability without operational authority."""

    descriptor: ToolAdapterDescriptor
    availability: AdapterAvailability
    available: bool
    trace: tuple[str, ...]
    runtime_allowed: bool = False
    execution_allowed: bool = False

    def __post_init__(self) -> None:
        if type(self.descriptor) is not ToolAdapterDescriptor:
            raise InvalidAvailabilityResultError(
                "descriptor must be exactly one ToolAdapterDescriptor"
            )
        if not isinstance(self.availability, AdapterAvailability):
            raise InvalidAvailabilityResultError(
                "availability must be AdapterAvailability metadata"
            )
        if self.availability is not self.descriptor.availability:
            raise InvalidAvailabilityResultError(
                "availability conflicts with descriptor metadata"
            )
        expected = self.availability is AdapterAvailability.AVAILABLE
        if not isinstance(self.available, bool) or self.available != expected:
            raise InvalidAvailabilityResultError(
                "available conflicts with AdapterAvailability metadata"
            )
        if isinstance(self.trace, (str, bytes)):
            raise InvalidAvailabilityResultError(
                "trace must be an iterable of strings"
            )
        try:
            trace = tuple(self.trace)
        except TypeError as exc:
            raise InvalidAvailabilityResultError(
                "trace must be an iterable of strings"
            ) from exc
        if any(
            not isinstance(item, str) or not item
            for item in trace
        ):
            raise InvalidAvailabilityResultError(
                "trace must contain non-empty strings"
            )
        if not trace:
            raise InvalidAvailabilityResultError(
                "trace must not be empty"
            )
        if (
            not isinstance(self.runtime_allowed, bool)
            or self.runtime_allowed
            or not isinstance(self.execution_allowed, bool)
            or self.execution_allowed
        ):
            raise InvalidAvailabilityResultError(
                "availability assessment cannot grant Runtime or "
                "execution authority"
            )
        object.__setattr__(self, "trace", trace)
