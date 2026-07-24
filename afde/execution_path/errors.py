"""Domain errors for non-executable Execution Path construction."""


class ExecutionPathError(RuntimeError):
    """Base error for Execution Path failures."""


class InvalidExecutionPathRequestError(ExecutionPathError, ValueError):
    """Raised when structured Execution Path input is invalid."""


class InvalidExecutionPathMetadataError(ExecutionPathError, ValueError):
    """Raised when selection and Catalog metadata conflict."""


class ExecutionPathSourceError(ExecutionPathError):
    """Raised when the injected Catalog metadata source fails."""
