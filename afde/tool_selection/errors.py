"""Domain errors for deterministic Tool Adapter selection."""


class ToolAdapterSelectionError(RuntimeError):
    """Base error for selection boundary failures."""


class InvalidToolAdapterSelectionRequestError(
    ToolAdapterSelectionError, ValueError,
):
    """Raised when structured selection input is invalid."""


class InvalidAdapterCandidateError(ToolAdapterSelectionError, ValueError):
    """Raised when injected adapter metadata is invalid."""


class AdapterCandidateSourceError(ToolAdapterSelectionError):
    """Raised when the injected candidate source cannot provide a snapshot."""
