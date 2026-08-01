"""Package-scoped non-Runtime production adapter invocation contract."""

from .errors import (
    AdapterUnavailableForInvocationError,
    CredentialNotReadyForInvocationError,
    InvalidInvocationRequestError,
    InvalidInvocationResultError,
    InvalidInvocationTargetError,
    InvalidInvocationTargetResultError,
    InvocationAuthorityViolationError,
    InvocationTargetCallError,
    ProductionAdapterInvocationError,
    ProductionAdapterInvocationIdentityMismatchError,
)
from .models import (
    InvocationRequest,
    InvocationResult,
    InvocationTarget,
    InvocationTargetResult,
)
from .service import InvocationService

__all__ = [
    "AdapterUnavailableForInvocationError",
    "CredentialNotReadyForInvocationError",
    "InvalidInvocationRequestError",
    "InvalidInvocationResultError",
    "InvalidInvocationTargetError",
    "InvalidInvocationTargetResultError",
    "InvocationAuthorityViolationError",
    "InvocationRequest",
    "InvocationResult",
    "InvocationService",
    "InvocationTarget",
    "InvocationTargetCallError",
    "InvocationTargetResult",
    "ProductionAdapterInvocationError",
    "ProductionAdapterInvocationIdentityMismatchError",
]
