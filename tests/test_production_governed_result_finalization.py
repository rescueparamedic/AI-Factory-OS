from pathlib import Path
from types import SimpleNamespace

import pytest

from afde.production_governed_result_finalization import (
    InvalidProductionGovernedResultFinalizationRequestError,
    ProductionGovernedResultFinalizationRequest,
    ProductionGovernedResultFinalizer,
    ProductionGovernedResultStatus,
)
from afde.production_orchestration import (
    ProductionOrchestrationStatus,
    ProductionPlannerRuntimeOrchestrator,
)
from afde.production_planner_worker_dispatch import (
    ProductionPlannerWorkerDispatcher,
)
from real_worker_runtime.runtime_history import RuntimeHistoryStore
from real_worker_runtime.tool_actions import ToolActionType
from test_production_orchestration import (
    BindingAuthorityProvider,
    _action,
    _startup,
)
from test_production_planner_worker_dispatch import (
    RecordingPlanner,
    RecordingRuntimeExecutionService,
    _dispatch_request,
)

SESSION_ID = "production-finalization-AFDE-6-21-001"
OBSERVATION_ID = "RUNTIME-OBSERVATION-AFDE-6.21-001"
EVENT_ID = "PRODUCTION-FINALIZATION-EVENT-AFDE-6.21-001"
TIMESTAMP = "2026-08-11T12:00:00+09:00"


def _finalizer(tmp_path, *, startup=None, history_store=None):
    adapter_calls = []

    def runner(argv, **kwargs):
        adapter_calls.append((argv, kwargs))
        return SimpleNamespace(returncode=0, stdout="controlled", stderr="")

    startup, target = startup or _startup(tmp_path, runner=runner)
    planner = RecordingPlanner()
    runtime_execution = RecordingRuntimeExecutionService()
    dispatcher = ProductionPlannerWorkerDispatcher(
        orchestrator=ProductionPlannerRuntimeOrchestrator(
            startup_composition=startup,
            authority_provider=BindingAuthorityProvider(),
            planner=planner,
            runtime_execution=runtime_execution,
        )
    )
    finalizer = ProductionGovernedResultFinalizer(
        dispatcher=dispatcher,
        history_store=history_store or RuntimeHistoryStore(tmp_path),
        session_id_provider=lambda: SESSION_ID,
        observation_id_provider=lambda: OBSERVATION_ID,
        event_id_provider=lambda: EVENT_ID,
        timestamp_provider=lambda: TIMESTAMP,
    )
    return finalizer, planner, runtime_execution, adapter_calls, target


def _finalize(finalizer):
    return finalizer.finalize(
        ProductionGovernedResultFinalizationRequest(
            dispatch_request=_dispatch_request(
                instruction="SECRET-COMMAND-MATERIAL must never be persisted"
            )
        )
    )


def test_full_operational_path_finalizes_once_and_survives_durable_requery(tmp_path):
    finalizer, planner, runtime_execution, adapter_calls, target = _finalizer(tmp_path)

    result = _finalize(finalizer)

    assert result.status is ProductionGovernedResultStatus.COMPLETED
    assert result.execution_outcome == "completed"
    assert len(runtime_execution.requests) == 1
    assert len(adapter_calls) == 1
    assert target.last_execution_result.status == "SUCCEEDED"
    assert result.dispatch_result.status is ProductionOrchestrationStatus.COMPLETED
    assert result.evidence is not None
    evidence = result.evidence
    worker = evidence.worker_execution_result
    observation = evidence.observation_result
    runtime = worker.runtime_execution_result
    event = evidence.collection_result.events[0]

    assert observation.worker_execution_result is worker
    assert observation.identity.observation_id == OBSERVATION_ID
    assert event.payload["observation_id"] == observation.identity.observation_id
    assert evidence.stream_result.events is evidence.collection_result.events
    assert evidence.stream_result.events[0] is event
    assert result.plan_id == planner.plans[0].plan_id == worker.worker_result.plan_id
    assert result.task_id == worker.worker_result.task_id
    assert result.worker_id == worker.worker_id == observation.identity.worker_id
    for name in ("capability_id", "adapter_id", "path_id", "projection_id", "binding_id"):
        assert getattr(result, name) == getattr(runtime, name)
        assert event.payload[name] == getattr(runtime, name)

    history_path = (
        Path(tmp_path) / "data" / "runtime_sessions" / SESSION_ID / "events.jsonl"
    )
    assert history_path.is_file()
    persisted_text = history_path.read_text(encoding="utf-8")
    assert "SECRET-COMMAND-MATERIAL" not in persisted_text
    assert "RUNTIME-EXECUTION-AUTHORITY" not in persisted_text

    fresh_summary = RuntimeHistoryStore(tmp_path).summary(result.session_id)
    assert fresh_summary["event_count"] == 1
    record = fresh_summary["events"][0]
    assert record["event_id"] == EVENT_ID
    assert record["session_id"] == SESSION_ID
    assert record["task_id"] == result.task_id
    assert record["worker_id"] == result.worker_id
    assert record["status"] == "completed"
    for name in (
        "plan_id", "observation_id", "capability_id", "adapter_id",
        "path_id", "projection_id", "binding_id", "execution_status",
    ):
        assert record["metadata"][name] == event.payload[name]


def test_actual_denied_path_persists_truthful_status_without_fake_evidence(tmp_path):
    action = _action(
        tmp_path,
        action_type=ToolActionType.FILE_WRITE,
        purpose="Prove finalization denial",
        target="../outside.py",
        arguments={"content": "blocked"},
    )
    startup = _startup(tmp_path, action=action)
    finalizer, _, runtime_execution, adapter_calls, target = _finalizer(
        tmp_path, startup=startup
    )

    result = _finalize(finalizer)

    assert result.status is ProductionGovernedResultStatus.REJECTED
    assert result.dispatch_result.worker_execution_result is None
    assert result.worker_id is None
    assert result.evidence is None
    assert result.history_record is not None
    assert result.history_summary["event_count"] == 1
    assert result.history_record["status"] == "rejected"
    assert result.history_record["worker_id"] is None
    assert "observation_id" not in result.history_record["metadata"]
    assert len(runtime_execution.requests) == 1
    assert adapter_calls == []
    assert target.last_execution_result.status == "DENIED"


class FailingHistoryStore(RuntimeHistoryStore):
    def append(self, event):
        raise OSError("private filesystem detail")


def test_persistence_failure_fails_closed_without_second_execution(tmp_path):
    store = FailingHistoryStore(tmp_path)
    finalizer, _, runtime_execution, adapter_calls, _ = _finalizer(
        tmp_path, history_store=store
    )

    result = _finalize(finalizer)

    assert result.status is ProductionGovernedResultStatus.FINALIZATION_FAILED
    assert result.evidence is None
    assert result.history_record is None
    assert result.history_summary is None
    assert result.finalization_error == "finalization failed safely: OSError"
    assert len(runtime_execution.requests) == 1
    assert len(adapter_calls) == 1


@pytest.mark.parametrize(
    ("provider", "value", "message"),
    [
        ("session_id_provider", "unsafe/session", "session_id"),
        ("observation_id_provider", "unsafe", "observation_id"),
        ("event_id_provider", " event", "event_id"),
        ("timestamp_provider", "2026-08-11T00:00:00", "timestamp"),
    ],
)
def test_invalid_generated_values_fail_before_runtime(
    tmp_path, provider, value, message
):
    finalizer, _, runtime_execution, adapter_calls, _ = _finalizer(tmp_path)
    setattr(finalizer, f"_{provider}", lambda: value)

    with pytest.raises(
        InvalidProductionGovernedResultFinalizationRequestError, match=message
    ):
        _finalize(finalizer)

    assert runtime_execution.requests == []
    assert adapter_calls == []


def test_wrong_top_level_request_type_is_rejected_without_runtime(tmp_path):
    finalizer, _, runtime_execution, adapter_calls, _ = _finalizer(tmp_path)

    with pytest.raises(InvalidProductionGovernedResultFinalizationRequestError):
        finalizer.finalize(_dispatch_request())

    assert runtime_execution.requests == []
    assert adapter_calls == []
