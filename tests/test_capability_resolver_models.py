from dataclasses import FrozenInstanceError

import pytest

from afde.resolver import (
    CapabilityRequirement,
    InvalidCapabilityRequirementError,
    ResolutionStatus,
)


def test_requirement_is_structured_and_deeply_immutable():
    source = {"policy": {"regions": ["kr", "us"]}}
    requirement = CapabilityRequirement(
        capability_id="CAP-KNOW-0001",
        requested_scope="architecture.knowledge_foundation",
        minimum_maturity="M3",
        required_knowledge_ids=("KNW-KNOW-0001",),
        constraints=source,
    )
    source["policy"]["regions"].append("eu")

    assert requirement.constraints["policy"]["regions"] == ("kr", "us")
    with pytest.raises(TypeError):
        requirement.constraints["new"] = "value"
    with pytest.raises(TypeError):
        requirement.constraints["policy"]["regions"] += ("eu",)
    with pytest.raises(FrozenInstanceError):
        requirement.minimum_maturity = "M4"


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({}, "capability_id is required"),
        ({"capability_id": "invalid"}, "invalid capability_id"),
        (
            {"capability_id": "CAP-KNOW-0001", "requested_scope": " "},
            "requested_scope",
        ),
        (
            {"capability_id": "CAP-KNOW-0001", "minimum_maturity": "M9"},
            "minimum_maturity",
        ),
        (
            {
                "capability_id": "CAP-KNOW-0001",
                "require_operational": "yes",
            },
            "require_operational",
        ),
        (
            {
                "capability_id": "CAP-KNOW-0001",
                "required_knowledge_ids": ["KNW-KNOW-0001"],
            },
            "must be a tuple",
        ),
        (
            {
                "capability_id": "CAP-KNOW-0001",
                "required_knowledge_ids": (
                    "KNW-KNOW-0001",
                    "KNW-KNOW-0001",
                ),
            },
            "duplicate",
        ),
        (
            {"capability_id": "CAP-KNOW-0001", "constraints": ()},
            "constraints must be a mapping",
        ),
    ],
)
def test_invalid_requirements_fail_closed(kwargs, message):
    with pytest.raises(InvalidCapabilityRequirementError, match=message):
        CapabilityRequirement(**kwargs)


def test_resolution_status_values_are_bounded():
    assert tuple(item.value for item in ResolutionStatus) == (
        "resolved",
        "unresolved",
        "blocked",
        "decision_required",
    )
