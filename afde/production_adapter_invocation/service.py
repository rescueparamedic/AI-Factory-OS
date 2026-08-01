"""Explicit caller-target boundary for adapter invocation."""
from __future__ import annotations

from afde.production_adapter_availability import (
    ProductionAdapterAvailabilityResult,
)
from afde.production_adapter_creation import (
    ProductionAdapterCreationContext,
    ProductionAdapterCreationResult,
    ProductionAdapterInstance,
)
from afde.production_adapter_credential_readiness import (
    CredentialReadinessStatus,
    ProductionAdapterCredentialReadinessResult,
)
from afde.tool_adapter_contract import (
    ToolAdapterBinding,
    ToolAdapterRequest,
)
from afde.tool_catalog import AdapterAvailability, ToolAdapterDescriptor

from .errors import (
    AdapterUnavailableForInvocationError,
    CredentialNotReadyForInvocationError,
    InvalidInvocationRequestError,
    InvalidInvocationTargetError,
    InvalidInvocationTargetResultError,
    InvocationAuthorityViolationError,
    InvocationTargetCallError,
    ProductionAdapterInvocationIdentityMismatchError,
)
from .models import (
    InvocationRequest,
    InvocationResult,
    InvocationTarget,
    InvocationTargetResult,
    expected_credential_readiness,
)


class InvocationService:
    """Validate and call one explicit target without Runtime integration."""

    def invoke(
        self,
        request: InvocationRequest,
        target: InvocationTarget,
    ) -> InvocationResult:
        """Call the supplied target after all metadata checks pass."""

        if type(request) is not InvocationRequest:
            raise InvalidInvocationRequestError(
                "request must be exactly one InvocationRequest"
            )
        self._validate_request(request)
        try:
            target_adapter_id = getattr(target, "adapter_id", None)
            target_invoke = getattr(target, "invoke", None)
        except Exception as exc:
            raise InvalidInvocationTargetError(
                "target contract could not be inspected"
            ) from exc
        if (
            not isinstance(target_adapter_id, str)
            or not target_adapter_id
            or target_adapter_id != target_adapter_id.strip()
            or not callable(target_invoke)
        ):
            raise InvalidInvocationTargetError(
                "target must declare an exact adapter identity and invoke"
            )
        if target_adapter_id != request.adapter_id:
            raise ProductionAdapterInvocationIdentityMismatchError(
                "target adapter identity conflicts with request"
            )
        try:
            target_result = target.invoke(request)
        except Exception as exc:
            raise InvocationTargetCallError(
                "caller-supplied target raised during invocation"
            ) from exc
        if type(target_result) is not InvocationTargetResult:
            raise InvalidInvocationTargetResultError(
                "target must return exactly one InvocationTargetResult"
            )
        if target_result.adapter_id != request.adapter_id:
            raise ProductionAdapterInvocationIdentityMismatchError(
                "target result identity conflicts with request"
            )
        if (
            target_result.runtime_allowed
            or target_result.execution_allowed
        ):
            raise InvocationAuthorityViolationError(
                "target result cannot grant Runtime or execution authority"
            )
        return InvocationResult(
            request=request,
            target_result=target_result,
            target_adapter_id=target_adapter_id,
            trace=(
                f"01.request.accepted:{request.adapter_id}",
                "02.creation.identity.validated",
                "03.binding.identity.validated",
                "04.availability.accepted",
                "05.credential_readiness.accepted",
                "06.target.identity.validated",
                "07.target.result.validated",
                "08.authority.denied",
            ),
            runtime_allowed=False,
            execution_allowed=False,
        )

    @staticmethod
    def _validate_request(request: InvocationRequest) -> None:
        creation = request.creation_result
        if type(creation) is not ProductionAdapterCreationResult:
            raise InvalidInvocationRequestError(
                "creation result contract type is invalid"
            )
        exact_types = (
            (
                "creation context",
                creation.context,
                ProductionAdapterCreationContext,
            ),
            (
                "creation instance",
                creation.instance,
                ProductionAdapterInstance,
            ),
            ("request instance", request.instance, ProductionAdapterInstance),
            ("descriptor", request.descriptor, ToolAdapterDescriptor),
            (
                "Tool Adapter request",
                request.tool_adapter_request,
                ToolAdapterRequest,
            ),
            ("binding", request.binding, ToolAdapterBinding),
            (
                "availability",
                request.availability,
                ProductionAdapterAvailabilityResult,
            ),
            (
                "credential readiness",
                request.credential_readiness,
                ProductionAdapterCredentialReadinessResult,
            ),
        )
        for name, value, expected in exact_types:
            if type(value) is not expected:
                raise InvalidInvocationRequestError(
                    f"{name} contract type is invalid"
                )
        if creation.instance is not request.instance:
            raise ProductionAdapterInvocationIdentityMismatchError(
                "creation result instance conflicts with request"
            )
        authority_values = (
            request.runtime_allowed,
            request.execution_allowed,
            request.instance.runtime_allowed,
            request.instance.execution_allowed,
            creation.runtime_allowed,
            creation.execution_allowed,
            request.tool_adapter_request.runtime_allowed,
            request.tool_adapter_request.execution_allowed,
            request.binding.runtime_allowed,
            request.binding.execution_allowed,
            request.availability.runtime_allowed,
            request.availability.execution_allowed,
            request.credential_readiness.runtime_allowed,
            request.credential_readiness.execution_allowed,
        )
        if any(value is not False for value in authority_values):
            raise InvocationAuthorityViolationError(
                "identity chain cannot grant Runtime or execution authority"
            )
        if (
            request.availability.availability
            is not AdapterAvailability.AVAILABLE
            or not request.availability.available
        ):
            raise AdapterUnavailableForInvocationError(
                "adapter availability does not permit invocation"
            )
        expected = expected_credential_readiness(request.descriptor)
        if request.credential_readiness.status is not expected:
            raise CredentialNotReadyForInvocationError(
                "credential readiness does not permit invocation"
            )
        if (
            expected is CredentialReadinessStatus.READY
            and request.credential_readiness.evidence_ready is not True
        ):
            raise CredentialNotReadyForInvocationError(
                "required credential readiness lacks ready evidence"
            )
