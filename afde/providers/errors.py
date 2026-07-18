"""Provider-boundary failures with credential-safe messages."""


class AIProviderError(RuntimeError):
    pass


class ProviderConfigurationError(AIProviderError):
    pass


class LiveAPIBlockedError(ProviderConfigurationError):
    pass


class ProviderRequestError(AIProviderError):
    pass


class ProviderResponseError(AIProviderError):
    pass
