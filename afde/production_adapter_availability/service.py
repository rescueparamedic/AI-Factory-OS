"""Metadata-only production Tool Adapter availability assessment."""
from __future__ import annotations

from afde.tool_catalog import AdapterAvailability, ToolAdapterDescriptor

from .errors import InvalidAvailabilityDescriptorError
from .models import ProductionAdapterAvailabilityResult


class ProductionAdapterAvailabilityService:
    """Project existing declared availability without probing behavior."""

    def assess(
        self,
        descriptor: ToolAdapterDescriptor,
    ) -> ProductionAdapterAvailabilityResult:
        """Return the descriptor's exact declared availability."""

        if type(descriptor) is not ToolAdapterDescriptor:
            raise InvalidAvailabilityDescriptorError(
                "descriptor must be exactly one ToolAdapterDescriptor"
            )

        availability = descriptor.availability
        available = availability is AdapterAvailability.AVAILABLE
        return ProductionAdapterAvailabilityResult(
            descriptor=descriptor,
            availability=availability,
            available=available,
            trace=(
                f"01.descriptor.accepted:{descriptor.adapter_id}",
                f"02.availability.metadata:{availability.value}",
                f"03.availability.available:{str(available).lower()}",
                "04.authority.denied",
            ),
            runtime_allowed=False,
            execution_allowed=False,
        )
