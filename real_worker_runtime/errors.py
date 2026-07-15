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
class OrchestrationError(RuntimeSessionError): pass
class RevisionLimitExceeded(OrchestrationError): pass
class RoleExecutionError(OrchestrationError): pass
class InvalidRoleResult(RoleExecutionError): pass
class InvalidTaskTransition(RuntimeErrorBase, ValueError):
    error_code = "RUNTIME_ILLEGAL_TRANSITION"
class InvalidPipelineTransition(RuntimeErrorBase, ValueError): pass
