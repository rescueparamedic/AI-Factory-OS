from dataclasses import FrozenInstanceError, replace

import pytest

import afde
import afde.production_adapter_availability as availability_package
from afde.production_adapter_availability import (
    InvalidAvailabilityDescriptorError,
    InvalidAvailabilityResultError,
    ProductionAdapterAvailabilityService,
)
from afde.tool_catalog import (
    AdapterAvailability,
    CostClassification,
    ExecutionContract,
    PrivacyClassification,
    RuntimeCompatibility,
    ToolAdapterDescriptor,
)


def _descriptor(**overrides):
    values = {
        "adapter_id": "adapter.availability_fixture",
        "display_name": "Availability Fixture",
        "version": "1.0.0",
        "supported_capability_ids": ("CAP-AVAILABILITYFIXTURE-0001",),
        "availability": AdapterAvailability.AVAILABLE,
        "runtime_compatibility": RuntimeCompatibility.COMPATIBLE,
        "execution_contract": ExecutionContract.CONTROLLED_RUNTIME,
        "privacy_classification": PrivacyClassification.LOCAL,
        "cost_classification": CostClassification.NO_COST,
        "credentials_required": False,
        "description": "Availability metadata fixture.",
        "metadata_references": ("fixture:availability",),
    }
    values.update(overrides)
    return ToolAdapterDescriptor(**values)


@pytest.mark.parametrize(
    "availability, expected",
    [
        (AdapterAvailability.AVAILABLE, True),
        (AdapterAvailability.UNAVAILABLE, False),
    ],
)
def test_assesses_exact_existing_availability_metadata(
    availability,
    expected,
):
    descriptor = _descriptor(availability=availability)

    result = ProductionAdapterAvailabilityService().assess(descriptor)

    assert result.descriptor is descriptor
    assert result.availability is availability
    assert result.available is expected
    assert result.runtime_allowed is False
    assert result.execution_allowed is False
    assert result.trace == (
        "01.descriptor.accepted:adapter.availability_fixture",
        f"02.availability.metadata:{availability.value}",
        f"03.availability.available:{str(expected).lower()}",
        "04.authority.denied",
    )


def test_assessment_is_deterministic_and_immutable():
    descriptor = _descriptor()
    service = ProductionAdapterAvailabilityService()

    first = service.assess(descriptor)
    second = service.assess(descriptor)

    assert first == second
    with pytest.raises(FrozenInstanceError):
        first.available = False


def test_credential_metadata_is_not_evaluated():
    descriptor = _descriptor(credentials_required=True)

    result = ProductionAdapterAvailabilityService().assess(descriptor)

    assert result.available is True
    assert result.availability is AdapterAvailability.AVAILABLE


@pytest.mark.parametrize("invalid", [None, object(), (_descriptor(),)])
def test_invalid_descriptor_fails_closed_with_typed_error(invalid):
    with pytest.raises(
        InvalidAvailabilityDescriptorError,
        match="exactly one",
    ):
        ProductionAdapterAvailabilityService().assess(invalid)


def test_result_rejects_metadata_conflicts_and_authority():
    result = ProductionAdapterAvailabilityService().assess(_descriptor())

    with pytest.raises(
        InvalidAvailabilityResultError,
        match="availability conflicts",
    ):
        replace(result, availability=AdapterAvailability.UNAVAILABLE)
    with pytest.raises(
        InvalidAvailabilityResultError,
        match="available conflicts",
    ):
        replace(result, available=False)
    with pytest.raises(
        InvalidAvailabilityResultError,
        match="cannot grant",
    ):
        replace(result, runtime_allowed=True)
    with pytest.raises(
        InvalidAvailabilityResultError,
        match="cannot grant",
    ):
        replace(result, execution_allowed=True)
    with pytest.raises(
        InvalidAvailabilityResultError,
        match="iterable",
    ):
        replace(result, trace="not-a-trace")


def test_public_contract_is_additive_and_package_scoped():
    assert availability_package.__all__ == [
        "InvalidAvailabilityDescriptorError",
        "InvalidAvailabilityResultError",
        "ProductionAdapterAvailabilityError",
        "ProductionAdapterAvailabilityResult",
        "ProductionAdapterAvailabilityService",
    ]
    assert not hasattr(afde, "ProductionAdapterAvailabilityService")
    assert not hasattr(afde, "ProductionAdapterAvailabilityResult")
