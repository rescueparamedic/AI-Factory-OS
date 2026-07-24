"""Domain errors for non-executable Runtime Integration."""


class RuntimeIntegrationError(RuntimeError):
    """Base error for Runtime Integration failures."""


class InvalidRuntimeIntegrationRequestError(RuntimeIntegrationError, ValueError):
    """Raised when structured Runtime Integration input is invalid."""


class InvalidRuntimeProjectionError(RuntimeIntegrationError, ValueError):
    """Raised when a Runtime projection is internally inconsistent."""
