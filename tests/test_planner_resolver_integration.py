from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from afde.knowledge import KnowledgeFoundationProvider, KnowledgeGap
from afde.planner_resolution import (
    IntegrationStatus,
    MissingCapabilityRequirementError,
    PlannerCapabilityResolutionRequest,
    PlannerResolutionIntegrationError,
    PlannerResolutionService,
)
from afde.resolver import (
    CapabilityRequirement,
    CapabilityResolutionError,
    CapabilityResolutionResult,
    CapabilityResolver,
    ResolutionStatus,
)


ROOT = Path(__file__).resolve().parents[1]


class StubResolver:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def resolve(self, requirement):
        self.calls.append(requirement)
        return self.result


def _resolution(status, *, decision_required=False):
    requirement = CapabilityRequirement(capability_id="CAP-NONE-9999")
    gap = KnowledgeGap(
        gap_type="capability_gap",
        subject_id="CAP-NONE-9999",
        message="capability needs validation",
    )
    return CapabilityResolutionResult(
        requirement=requirement,
        capability=None,
        resolution_status=status,
        eligible=status is ResolutionStatus.RESOLVED,
        matched_scope=None,
        required_knowledge=(),
        required_capabilities=(),
        source_documents=(),
        reference_priority=("constitutional",),
        gaps=(gap,),
        rejection_reasons=(gap.message,),
        decision_required=decision_required,
        trace=("01.capability.checked", f"11.resolution.{status.value}"),
    )


@pytest.mark.parametrize("status", tuple(ResolutionStatus))
def test_resolver_status_context_gaps_and_rationale_are_preserved(status):
    resolution = _resolution(
        status,
        decision_required=status is ResolutionStatus.DECISION_REQUIRED,
    )
    resolver = StubResolver(resolution)
    requirement = resolution.requirement
    result = PlannerResolutionService(resolver).resolve(
        PlannerCapabilityResolutionRequest(
            planning_result={"plan_id": "PLAN-1", "goal": "Resolve"},
            capability_requirement=requirement,
        )
    )

    assert resolver.calls == [requirement]
    assert result.integration_status is IntegrationStatus(status.value)
    assert result.capability_resolution_result is resolution
    assert result.gaps is resolution.gaps
    assert result.ordered_rationale == resolution.trace
    assert result.planner_context["plan_id"] == "PLAN-1"
    assert result.decision_required is resolution.decision_required
    assert result.runtime_allowed is False
    with pytest.raises(FrozenInstanceError):
        result.runtime_allowed = True


def test_inline_explicit_requirement_is_constructed_deterministically():
    expected = _resolution(ResolutionStatus.UNRESOLVED)
    resolver = StubResolver(expected)
    request = PlannerCapabilityResolutionRequest(
        planning_result={"plan_id": "PLAN-1"},
        capability_id="CAP-NONE-9999",
        requested_scope="architecture.planner_resolution",
        minimum_maturity="M3",
        constraints={"region": ["kr"]},
    )

    PlannerResolutionService(resolver).resolve(request)
    requirement = resolver.calls[0]

    assert requirement.capability_id == "CAP-NONE-9999"
    assert requirement.requested_scope == "architecture.planner_resolution"
    assert requirement.minimum_maturity == "M3"
    assert requirement.constraints["region"] == ("kr",)


def test_missing_requirement_fails_closed_without_calling_resolver():
    resolver = StubResolver(_resolution(ResolutionStatus.RESOLVED))
    request = PlannerCapabilityResolutionRequest(
        planning_result={"plan_id": "PLAN-1"}
    )

    with pytest.raises(MissingCapabilityRequirementError):
        PlannerResolutionService(resolver).resolve(request)

    assert resolver.calls == []


def test_resolver_infrastructure_error_is_wrapped_with_cause():
    class FailingResolver:
        def resolve(self, requirement):
            raise CapabilityResolutionError("registry invalid")

    request = PlannerCapabilityResolutionRequest(
        planning_result={"plan_id": "PLAN-1"},
        capability_requirement=CapabilityRequirement(
            capability_id="CAP-KNOW-0001"
        ),
    )

    with pytest.raises(PlannerResolutionIntegrationError) as captured:
        PlannerResolutionService(FailingResolver()).resolve(request)

    assert isinstance(captured.value.__cause__, CapabilityResolutionError)


def test_same_structured_input_produces_equal_output():
    resolution = _resolution(ResolutionStatus.BLOCKED)
    service = PlannerResolutionService(StubResolver(resolution))
    request = PlannerCapabilityResolutionRequest(
        planning_result={"plan_id": "PLAN-1"},
        capability_requirement=resolution.requirement,
    )

    assert service.resolve(request) == service.resolve(request)


def test_real_registered_planner_resolution_capability_resolves_at_m3():
    service = PlannerResolutionService(
        CapabilityResolver(KnowledgeFoundationProvider(ROOT))
    )
    result = service.resolve(PlannerCapabilityResolutionRequest(
        planning_result={"plan_id": "PLAN-1", "goal": "Resolve capability"},
        capability_requirement=CapabilityRequirement(
            capability_id="CAP-PLANRES-0001",
            minimum_maturity="M3",
        ),
    ))

    assert result.integration_status is IntegrationStatus.RESOLVED
    assert result.capability_resolution_result.capability.maturity == "M3"
    assert result.runtime_allowed is False
