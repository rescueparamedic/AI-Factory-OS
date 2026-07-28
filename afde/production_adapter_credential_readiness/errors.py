"""Typed failures for production adapter credential readiness metadata."""


class ProductionAdapterCredentialReadinessError(RuntimeError):
    """Base error for credential readiness metadata assessment."""


class InvalidCredentialReadinessDescriptorError(
    ProductionAdapterCredentialReadinessError,
    TypeError,
):
    """Raised when assessment receives an invalid adapter descriptor."""


class InvalidCredentialReadinessEvidenceError(
    ProductionAdapterCredentialReadinessError,
    ValueError,
):
    """Raised when caller-supplied readiness evidence is malformed."""


class CredentialReadinessIdentityMismatchError(
    ProductionAdapterCredentialReadinessError,
    ValueError,
):
    """Raised when evidence names a different adapter identity."""


class InvalidCredentialReadinessResultError(
    ProductionAdapterCredentialReadinessError,
    ValueError,
):
    """Raised when a readiness result violates metadata invariants."""
