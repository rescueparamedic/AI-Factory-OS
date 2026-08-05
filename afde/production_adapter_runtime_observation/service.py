"""Point-in-time observation over existing Production Adapter execution evidence."""
from __future__ import annotations

from afde.production_adapter_worker_execution import (
    ProductionAdapterWorkerExecutionResult,
)

from .errors import InvalidProductionAdapterRuntimeObservationSourceError
from .models import (
    ProductionAdapterRuntimeObservationIdentity,
    ProductionAdapterRuntimeObservationResult,
)


class ProductionAdapterRuntimeObservationService:
    """Validate and project one supplied result without collection or storage."""

    def observe(
        self,
        identity: ProductionAdapterRuntimeObservationIdentity,
        worker_execution_result: ProductionAdapterWorkerExecutionResult,
    ) -> ProductionAdapterRuntimeObservationResult:
        """Return one immutable observation of existing completion evidence."""

        if type(identity) is not ProductionAdapterRuntimeObservationIdentity:
            raise InvalidProductionAdapterRuntimeObservationSourceError(
                "identity must be exactly one ProductionAdapterRuntimeObservationIdentity"
            )
        if type(
            worker_execution_result
        ) is not ProductionAdapterWorkerExecutionResult:
            raise InvalidProductionAdapterRuntimeObservationSourceError(
                "worker_execution_result must be exactly one "
                "ProductionAdapterWorkerExecutionResult"
            )
        return ProductionAdapterRuntimeObservationResult(
            identity=identity,
            worker_execution_result=worker_execution_result,
            execution_status=worker_execution_result.worker_result.execution_status,
            trace=(
                f"01.observation.identity.accepted:{identity.observation_id}",
                f"02.worker.identity.validated:{identity.worker_id}",
                f"03.adapter.identity.validated:{identity.adapter_id}",
                "04.execution.evidence.observed",
                "05.authority.denied",
            ),
            runtime_allowed=False,
            execution_allowed=False,
        )
