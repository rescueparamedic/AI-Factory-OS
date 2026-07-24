"""Errors raised at the Planner-to-Resolver integration boundary."""


class PlannerResolutionIntegrationError(RuntimeError):
    """Planner context could not be safely integrated with resolution."""


class InvalidPlannerResolutionRequestError(
    PlannerResolutionIntegrationError, ValueError,
):
    """A structured integration request is invalid."""


class MissingCapabilityRequirementError(
    InvalidPlannerResolutionRequestError,
):
    """No explicit capability requirement was supplied."""
