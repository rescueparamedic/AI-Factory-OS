"""Fail-closed Capability Resolver errors."""


class CapabilityResolutionError(RuntimeError):
    """The resolver could not safely evaluate a capability requirement."""


class CapabilityNotFoundError(CapabilityResolutionError, LookupError):
    """A requested capability identifier is not registered."""


class InvalidCapabilityRequirementError(CapabilityResolutionError, ValueError):
    """A structured capability requirement is invalid."""
