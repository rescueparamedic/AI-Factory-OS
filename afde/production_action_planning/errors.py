"""Typed fail-closed errors for governed Production Action Planning."""


class ProductionActionPlanningError(RuntimeError):
    """Base error for the non-executable planning boundary."""


class InvalidProductionActionPlanningRequestError(
    ProductionActionPlanningError,
    ValueError,
):
    """Raised when ordinary product inputs are invalid."""


class ProductionActionPlanningGitContextError(ProductionActionPlanningError):
    """Raised when a trusted Git worktree and branch cannot be established."""


class ProductionActionPlanningProviderConfigurationError(
    ProductionActionPlanningError,
):
    """Raised when the selected planning provider is not safely configured."""


class ProductionActionPlanningProviderRequestError(
    ProductionActionPlanningError,
):
    """Raised when the planning provider request fails."""


class InvalidProductionActionProposalError(
    ProductionActionPlanningError,
    ValueError,
):
    """Raised when provider output does not match the strict proposal schema."""


class UnsupportedProductionActionTypeError(
    InvalidProductionActionProposalError,
):
    """Raised when a proposal names an action outside the read-only allowlist."""


class UnsafeProductionFileReadTargetError(
    ProductionActionPlanningError,
    ValueError,
):
    """Raised when a FILE_READ target violates governed read policy."""


class ProductionToolActionValidationError(ProductionActionPlanningError):
    """Raised when canonical ToolAction validation rejects hydrated context."""
