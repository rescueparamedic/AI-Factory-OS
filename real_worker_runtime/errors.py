import json


class RuntimeErrorBase(Exception): pass
class ProviderConfigurationError(RuntimeErrorBase): pass
class ProviderAuthenticationError(RuntimeErrorBase): pass
class ProviderRateLimitError(RuntimeErrorBase): pass
class ProviderTimeoutError(RuntimeErrorBase): pass
class ProviderResponseError(RuntimeErrorBase): pass
class ProviderBadRequestError(ProviderResponseError):
    def __init__(self, diagnostics):
        self.diagnostics = diagnostics
        super().__init__(json.dumps(diagnostics, ensure_ascii=False, sort_keys=True))
class RuntimeSessionError(RuntimeErrorBase): pass
class InvalidTaskTransition(RuntimeErrorBase, ValueError): pass
class InvalidPipelineTransition(RuntimeErrorBase, ValueError): pass
