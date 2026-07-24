"""Application service composing Planner context with an injected Resolver."""
from __future__ import annotations

from typing import Protocol

from afde.resolver import (
    CapabilityRequirement,
    CapabilityResolutionError,
    CapabilityResolutionResult,
)

from .errors import (
    InvalidPlannerResolutionRequestError,
    MissingCapabilityRequirementError,
    PlannerResolutionIntegrationError,
)
from .models import (
    IntegrationStatus,
    PlannerCapabilityResolutionRequest,
    PlannerCapabilityResolutionResult,
)


class CapabilityResolutionPort(Protocol):
    """The only Resolver behavior required by the integration service."""

    def resolve(
        self, requirement: CapabilityRequirement,
    ) -> CapabilityResolutionResult: ...


class PlannerResolutionService:
    """Resolve one explicit requirement without orchestration or execution."""

    def __init__(self, resolver: CapabilityResolutionPort) -> None:
        if not callable(getattr(resolver, "resolve", None)):
            raise TypeError("resolver must provide resolve(requirement)")
        self._resolver = resolver

    def resolve(
        self, request: PlannerCapabilityResolutionRequest,
    ) -> PlannerCapabilityResolutionResult:
        if not isinstance(request, PlannerCapabilityResolutionRequest):
            raise InvalidPlannerResolutionRequestError(
                "request must be a PlannerCapabilityResolutionRequest"
            )
        requirement = self._requirement(request)
        try:
            resolution = self._resolver.resolve(requirement)
        except CapabilityResolutionError as exc:
            raise PlannerResolutionIntegrationError(
                "capability resolution failed"
            ) from exc
        if not isinstance(resolution, CapabilityResolutionResult):
            raise PlannerResolutionIntegrationError(
                "resolver returned an invalid result"
            )

        return PlannerCapabilityResolutionResult(
            planner_context=request.planning_result,
            capability_requirement=requirement,
            capability_resolution_result=resolution,
            integration_status=IntegrationStatus(
                resolution.resolution_status.value
            ),
            decision_required=resolution.decision_required,
            gaps=resolution.gaps,
            ordered_rationale=resolution.trace,
            runtime_allowed=False,
        )

    @staticmethod
    def _requirement(
        request: PlannerCapabilityResolutionRequest,
    ) -> CapabilityRequirement:
        if request.capability_requirement is not None:
            return request.capability_requirement
        if request.capability_id is None:
            raise MissingCapabilityRequirementError(
                "an explicit capability requirement or capability_id "
                "is required"
            )
        try:
            return CapabilityRequirement(
                capability_id=request.capability_id,
                requested_scope=request.requested_scope,
                minimum_maturity=request.minimum_maturity,
                require_operational=request.require_operational,
                constraints=request.constraints,
            )
        except CapabilityResolutionError as exc:
            raise InvalidPlannerResolutionRequestError(
                "inline capability requirement is invalid"
            ) from exc
