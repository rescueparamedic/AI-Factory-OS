from dataclasses import FrozenInstanceError

import pytest

from afde.planner import ExecutionPlan, ExecutionTask
from afde.planner_resolution import (
    IntegrationStatus,
    InvalidPlannerResolutionRequestError,
    PlannerCapabilityResolutionRequest,
)
from afde.resolver import CapabilityRequirement


def _plan():
    return ExecutionPlan(
        "PLAN-ABCDEF0123456789",
        "Resolve capability",
        "2026-07-24T00:00:00+09:00",
        tasks=[
            ExecutionTask(
                "TASK-ABCDEF0123456789-01",
                "Prepare",
                "Prepare structured input",
                "high",
            ),
        ],
    )


def test_request_defensively_freezes_existing_planner_context():
    plan = _plan()
    request = PlannerCapabilityResolutionRequest(
        planning_result=plan,
        capability_requirement=CapabilityRequirement(
            capability_id="CAP-RESOLVER-0001"
        ),
    )
    plan.tasks[0].title = "mutated"

    assert request.planning_result["tasks"][0]["title"] == "Prepare"
    with pytest.raises(TypeError):
        request.planning_result["goal"] = "changed"
    with pytest.raises(FrozenInstanceError):
        request.capability_id = "CAP-KNOW-0001"


def test_request_rejects_ambiguous_and_invalid_structured_input():
    requirement = CapabilityRequirement(capability_id="CAP-KNOW-0001")
    with pytest.raises(
        InvalidPlannerResolutionRequestError, match="cannot be combined",
    ):
        PlannerCapabilityResolutionRequest(
            planning_result={"plan_id": "PLAN-1"},
            capability_requirement=requirement,
            capability_id="CAP-RESOLVER-0001",
        )
    with pytest.raises(
        InvalidPlannerResolutionRequestError, match="planning_result",
    ):
        PlannerCapabilityResolutionRequest(planning_result=None)
    with pytest.raises(
        InvalidPlannerResolutionRequestError, match="structured as a mapping",
    ):
        PlannerCapabilityResolutionRequest(planning_result="infer a plan")


def test_integration_status_contract_is_bounded():
    assert tuple(status.value for status in IntegrationStatus) == (
        "resolved",
        "unresolved",
        "blocked",
        "decision_required",
    )
