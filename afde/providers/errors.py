"""Provider-boundary failures with credential-safe messages."""


class AIProviderError(RuntimeError):
    pass


class ProviderConfigurationError(AIProviderError):
    pass


class LiveAPIBlockedError(ProviderConfigurationError):
    pass


class ProviderRequestError(AIProviderError):
    """Sanitized provider failure with allowlisted transport diagnostics."""

    def __init__(
        self, message: str, *, category: str = "provider_request",
        status_code: int | None = None, request_id: str | None = None,
        retryable: bool = True,
    ) -> None:
        super().__init__(message)
        self.category = category
        self.status_code = status_code
        self.request_id = request_id
        self.retryable = retryable


class ProviderResponseError(AIProviderError):
    pass
