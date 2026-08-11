"""Application-level composition for governed Production result finalization."""
from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
import re
from uuid import uuid4

from afde.production_adapter_runtime_event_collection import (
    ProductionAdapterRuntimeEvent,
    ProductionAdapterRuntimeEventCollectionRequest,
    ProductionAdapterRuntimeEventCollectionService,
)
from afde.production_adapter_runtime_event_stream import (
    ProductionAdapterRuntimeEventStreamRequest,
    ProductionAdapterRuntimeEventStreamService,
)
from afde.production_adapter_runtime_observation import (
    ProductionAdapterRuntimeObservationIdentity,
    ProductionAdapterRuntimeObservationService,
)
from afde.production_orchestration import ProductionOrchestrationStatus
from afde.production_planner_worker_dispatch import (
    ProductionPlannerWorkerDispatcher,
)
from real_worker_runtime.runtime_history import RuntimeHistoryStore

from .errors import InvalidProductionGovernedResultFinalizationRequestError
from .models import (
    ProductionGovernedEvidenceSnapshot,
    ProductionGovernedOperationalResult,
    ProductionGovernedResultFinalizationRequest,
    ProductionGovernedResultStatus,
)

_SESSION_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")
_OBSERVATION_ID = re.compile(r"^RUNTIME-OBSERVATION-[A-Z0-9][A-Z0-9._-]{0,63}$")


def _session_id() -> str:
    return f"production-finalization-{uuid4().hex}"


def _observation_id() -> str:
    return f"RUNTIME-OBSERVATION-{uuid4().hex.upper()}"


def _event_id() -> str:
    return f"PRODUCTION-FINALIZATION-EVENT-{uuid4().hex.upper()}"


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


class ProductionGovernedResultFinalizer:
    """Compose existing Production services once, then persist their result."""

    def __init__(
        self,
        *,
        dispatcher: ProductionPlannerWorkerDispatcher,
        history_store: RuntimeHistoryStore,
        observation_service: ProductionAdapterRuntimeObservationService | None = None,
        collection_service: ProductionAdapterRuntimeEventCollectionService | None = None,
        stream_service: ProductionAdapterRuntimeEventStreamService | None = None,
        session_id_provider: Callable[[], str] = _session_id,
        observation_id_provider: Callable[[], str] = _observation_id,
        event_id_provider: Callable[[], str] = _event_id,
        timestamp_provider: Callable[[], str] = _timestamp,
    ) -> None:
        if not isinstance(dispatcher, ProductionPlannerWorkerDispatcher):
            raise TypeError("dispatcher must use the existing Production boundary")
        if not isinstance(history_store, RuntimeHistoryStore):
            raise TypeError("history_store must use RuntimeHistoryStore")
        self._dispatcher = dispatcher
        self._history = history_store
        self._observation = observation_service or ProductionAdapterRuntimeObservationService()
        self._collection = collection_service or ProductionAdapterRuntimeEventCollectionService()
        self._stream = stream_service or ProductionAdapterRuntimeEventStreamService()
        self._session_id_provider = session_id_provider
        self._observation_id_provider = observation_id_provider
        self._event_id_provider = event_id_provider
        self._timestamp_provider = timestamp_provider

    def finalize(
        self,
        request: ProductionGovernedResultFinalizationRequest,
    ) -> ProductionGovernedOperationalResult:
        if type(request) is not ProductionGovernedResultFinalizationRequest:
            raise InvalidProductionGovernedResultFinalizationRequestError(
                "request must be exactly one finalization request"
            )

        # Validate all caller-injectable generated values before Runtime execution.
        session_id = self._session_id_provider()
        observation_id = self._observation_id_provider()
        event_id = self._event_id_provider()
        timestamp = self._timestamp_provider()
        self._validate_generated(session_id, observation_id, event_id, timestamp)

        dispatch = self._dispatcher.dispatch(request.dispatch_request)
        orchestration = dispatch.orchestration_result
        identities = {
            "plan_id": orchestration.plan_id,
            "task_id": request.dispatch_request.task_id,
            "worker_id": request.dispatch_request.worker_id,
            "capability_id": orchestration.capability_id,
            "adapter_id": orchestration.adapter_id,
            "path_id": orchestration.path_id,
            "projection_id": orchestration.projection_id,
            "binding_id": orchestration.binding_id,
        }
        if dispatch.status is not ProductionOrchestrationStatus.COMPLETED:
            identities["worker_id"] = None
            return self._stopped_result(
                session_id=session_id,
                timestamp=timestamp,
                event_id=event_id,
                dispatch=dispatch,
                identities=identities,
            )

        worker = dispatch.worker_execution_result
        assert worker is not None
        runtime = worker.runtime_execution_result
        try:
            observation = self._observation.observe(
                ProductionAdapterRuntimeObservationIdentity(
                    observation_id=observation_id,
                    worker_id=worker.worker_id,
                    adapter_id=runtime.adapter_id,
                    projection_id=runtime.projection_id,
                    path_id=runtime.path_id,
                    capability_id=runtime.capability_id,
                    binding_id=runtime.binding_id,
                ),
                worker,
            )
            payload = {
                "session_id": session_id,
                "observation_id": observation.identity.observation_id,
                "plan_id": worker.worker_result.plan_id,
                "task_id": worker.worker_result.task_id,
                "worker_id": observation.identity.worker_id,
                "capability_id": observation.identity.capability_id,
                "adapter_id": observation.identity.adapter_id,
                "path_id": observation.identity.path_id,
                "projection_id": observation.identity.projection_id,
                "binding_id": observation.identity.binding_id,
                "execution_status": observation.execution_status,
            }
            event = ProductionAdapterRuntimeEvent(
                event_id=event_id,
                adapter_id=observation.identity.adapter_id,
                event_type="production.runtime.execution.completed",
                occurred_at=timestamp,
                payload=payload,
            )
            collection = self._collection.collect(
                ProductionAdapterRuntimeEventCollectionRequest(
                    events=(event,), collected_at=timestamp
                )
            )
            stream = self._stream.stream(
                ProductionAdapterRuntimeEventStreamRequest(
                    events=collection.events, streamed_at=timestamp
                )
            )
            history_value = {
                "event_id": event.event_id,
                "session_id": session_id,
                "timestamp": timestamp,
                "event_type": "PRODUCTION_GOVERNED_RESULT_FINALIZED",
                "actor": "production_governed_result_finalizer",
                "status": "completed",
                "worker_id": worker.worker_id,
                "task_id": worker.worker_result.task_id,
                "metadata": dict(event.payload),
            }
            history_record = self._history.append(history_value)
            history_summary = self._history.summary(session_id)
            persisted = history_summary.get("events", ())
            if (
                history_summary.get("event_count") != 1
                or not isinstance(persisted, (list, tuple))
                or len(persisted) != 1
                or persisted[0].get("event_id") != event.event_id
                or persisted[0].get("session_id") != session_id
            ):
                raise RuntimeError("durable history summary did not re-query the record")
            evidence = ProductionGovernedEvidenceSnapshot(
                worker_execution_result=worker,
                observation_result=observation,
                collection_result=collection,
                stream_result=stream,
                history_record=history_record,
            )
            return ProductionGovernedOperationalResult(
                session_id=session_id,
                status=ProductionGovernedResultStatus.COMPLETED,
                dispatch_result=dispatch,
                execution_outcome=observation.execution_status,
                history_record=history_record,
                history_summary=history_summary,
                evidence=evidence,
                **identities,
            )
        except Exception as exc:
            return self._failed_result(
                session_id=session_id,
                timestamp=timestamp,
                event_id=event_id,
                dispatch=dispatch,
                identities=identities,
                failure_type=type(exc).__name__,
            )

    def _stopped_result(self, *, session_id, timestamp, event_id, dispatch, identities):
        status = ProductionGovernedResultStatus(dispatch.status.value)
        return self._persist_non_success(
            session_id=session_id,
            timestamp=timestamp,
            event_id=event_id,
            dispatch=dispatch,
            identities=identities,
            status=status,
            outcome=dispatch.status.value,
            failure_type=None,
        )

    def _failed_result(self, *, session_id, timestamp, event_id, dispatch, identities, failure_type):
        return self._persist_non_success(
            session_id=session_id,
            timestamp=timestamp,
            event_id=event_id,
            dispatch=dispatch,
            identities=identities,
            status=ProductionGovernedResultStatus.FINALIZATION_FAILED,
            outcome="finalization_failed",
            failure_type=failure_type,
        )

    def _persist_non_success(
        self, *, session_id, timestamp, event_id, dispatch, identities,
        status, outcome, failure_type,
    ):
        metadata = {
            key: value for key, value in identities.items()
            if value is not None and key not in {"task_id", "worker_id"}
        }
        metadata["dispatch_status"] = dispatch.status.value
        if failure_type:
            metadata["failure_type"] = failure_type
        value = {
            "event_id": event_id,
            "session_id": session_id,
            "timestamp": timestamp,
            "event_type": "PRODUCTION_GOVERNED_FINALIZATION_STOPPED",
            "actor": "production_governed_result_finalizer",
            "status": outcome,
            "task_id": identities["task_id"],
            "metadata": metadata,
        }
        # A requested Worker identity is not evidence that a Worker result exists.
        if dispatch.worker_execution_result is not None:
            value["worker_id"] = identities["worker_id"]
        try:
            record = self._history.append(value)
            summary = self._history.summary(session_id)
        except Exception as persistence_error:
            record = None
            summary = None
            status = ProductionGovernedResultStatus.FINALIZATION_FAILED
            outcome = "finalization_failed"
            failure_type = type(persistence_error).__name__
        return ProductionGovernedOperationalResult(
            session_id=session_id,
            status=status,
            dispatch_result=dispatch,
            execution_outcome=outcome,
            history_record=record,
            history_summary=summary,
            evidence=None,
            finalization_error=(
                f"finalization failed safely: {failure_type}"
                if failure_type else None
            ),
            **identities,
        )

    @staticmethod
    def _validate_generated(session_id, observation_id, event_id, timestamp):
        error = InvalidProductionGovernedResultFinalizationRequestError
        if not isinstance(session_id, str) or not _SESSION_ID.fullmatch(session_id):
            raise error("generated session_id is invalid")
        if not isinstance(observation_id, str) or not _OBSERVATION_ID.fullmatch(observation_id):
            raise error("generated observation_id is invalid")
        if not isinstance(event_id, str) or not event_id or event_id != event_id.strip():
            raise error("generated event_id is invalid")
        if not isinstance(timestamp, str) or not timestamp or timestamp != timestamp.strip():
            raise error("generated timestamp is invalid")
        try:
            parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        except (OverflowError, ValueError):
            raise error("generated timestamp must be timezone-aware ISO") from None
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise error("generated timestamp must be timezone-aware ISO")
