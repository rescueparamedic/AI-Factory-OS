"""Domain errors for the non-executable Tool Adapter contract."""


class ToolAdapterContractError(RuntimeError):
    """Base error for Tool Adapter contract failures."""


class InvalidToolAdapterRequestError(ToolAdapterContractError, ValueError):
    """Raised when a Tool Adapter request is malformed or inconsistent."""


class InvalidToolAdapterResultError(ToolAdapterContractError, ValueError):
    """Raised when a Tool Adapter result or error is inconsistent."""
