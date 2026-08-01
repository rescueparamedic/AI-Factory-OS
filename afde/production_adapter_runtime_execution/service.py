"""Authorized Runtime boundary composed from existing adapter capabilities."""
from __future__ import annotations

from threading import Lock

from afde.production_adapter_creation import ProductionAdapterCreationContext
from afde.production_adapter_invocation import InvocationRequest

from .errors import (
    InvalidProductionAdapterRuntimeExecutionRequestError,
    ProductionAdapterRuntimeCreationCallError,
    ProductionAdapterRuntimeExecutionAuthorityReuseError,
    ProductionAdapterRuntimeInvocationCallError,
)
from .models import (
    ProductionAdapterRuntimeExecutionAuthority,
    ProductionAdapterRuntimeExecutionRequest,
    ProductionAdapterRuntimeExecutionResult,
)


class _AuthorityConsumptionLedger:
    """Process-local atomic guard with no Runtime lifecycle integration."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._consumed: set[str] = set()

    def consume(
        self,
        authority: ProductionAdapterRuntimeExecutionAuthority,
    ) -> None:
        identity = authority.authority_reference
        with self._lock:
            if identity in self._consumed:
                raise ProductionAdapterRuntimeExecutionAuthorityReuseError(
                    "Runtime execution authority has already been consumed"
                )
            self._consumed.add(identity)


_AUTHORITY_CONSUMPTION_LEDGER = _AuthorityConsumptionLedger()


class ProductionAdapterRuntimeExecutionService:
    """Execute one authorized create-and-invoke operation without lifecycle mutation."""

    def execute(
        self,
        request: ProductionAdapterRuntimeExecutionRequest,
    ) -> ProductionAdapterRuntimeExecutionResult:
        """Validate authority, then reuse the existing creation and invocation boundaries."""

        if type(request) is not ProductionAdapterRuntimeExecutionRequest:
            raise InvalidProductionAdapterRuntimeExecutionRequestError(
                "request must be exactly one ProductionAdapterRuntimeExecutionRequest"
            )
        _AUTHORITY_CONSUMPTION_LEDGER.consume(request.authority)
        startup = request.startup_composition
        creation_context = ProductionAdapterCreationContext(
            adapter_id=startup.creation_context.adapter_id,
            descriptor=startup.creation_context.descriptor,
            availability=startup.creation_context.availability,
            credential_readiness=startup.creation_context.credential_readiness,
            configuration_metadata=(
                startup.creation_context.configuration_metadata
            ),
            binding=request.binding,
            runtime_allowed=False,
            execution_allowed=False,
        )
        try:
            creation_result = startup.creation_service.create(creation_context)
        except Exception as exc:
            raise ProductionAdapterRuntimeCreationCallError(
                "production adapter creation failed at the Runtime boundary"
            ) from exc

        invocation_request = InvocationRequest(
            adapter_id=startup.adapter_id,
            descriptor=startup.descriptor,
            creation_result=creation_result,
            instance=creation_result.instance,
            tool_adapter_request=request.tool_adapter_request,
            binding=request.binding,
            availability=startup.availability,
            credential_readiness=startup.credential_readiness,
            invocation_metadata_references=(
                request.invocation_metadata_references
            ),
            runtime_allowed=False,
            execution_allowed=False,
        )
        try:
            invocation_result = startup.invocation_service.invoke(
                invocation_request,
                startup.invocation_target,
            )
        except Exception as exc:
            raise ProductionAdapterRuntimeInvocationCallError(
                "production adapter invocation failed at the Runtime boundary"
            ) from exc

        return ProductionAdapterRuntimeExecutionResult(
            adapter_id=request.binding.adapter_id,
            projection_id=request.binding.projection_id,
            path_id=request.binding.path_id,
            capability_id=request.binding.capability_id,
            binding_id=request.binding.binding_id,
            creation_result=creation_result,
            invocation_result=invocation_result,
            trace=(
                "01.runtime.authority.consumed",
                "02.startup.composition.accepted",
                "03.binding.identity.validated",
                "04.adapter.created",
                "05.adapter.invoked",
                "06.execution.completed",
                "07.authority.not_propagated",
            ),
            runtime_allowed=False,
            execution_allowed=False,
        )
