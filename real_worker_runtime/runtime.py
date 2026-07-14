from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from hashlib import sha256
import json
from pathlib import Path
from uuid import uuid4

from sprint_auto_runner import SprintAutoRunner

from .approval_resume import RuntimeApprovalStore, action_fingerprint, request_from_record
from .artifact_store import ArtifactStore
from .controlled_execution import ActionType, ControlledExecutor, ExecutionRequest
from .dashboard import TerminalDashboard
from .errors import (
    InvalidRoleResult, RevisionLimitExceeded, RoleExecutionError,
    RuntimeSessionError,
)
from .event_stream import EventStream
from .execution_truth import apply_execution_truth_contract, claimed_qa_failures
from .message_bus import MessageBus
from .models import RuntimeSession, WorkerResult, WorkerState
from .provider_bridge import ProviderBridge
from .runtime_pipeline import PipelineState, RuntimePipeline
from .runtime_orchestrator import RuntimeOrchestrator
from .role_execution import (
    RoleExecutionRequest, RoleExecutionResult, RoleExecutionState,
    RoleExecutor, RuntimeRole,
)
from .runtime_task import RuntimeTask
from .worker_context import WorkerContext
from .worker_registry import WorkerRegistry
from .workers import BaseWorker


class RealWorkerRuntime:
    def __init__(self, root=".", role_executor_factory=None):
        self.root = Path(root).resolve()
        self.role_executor_factory = role_executor_factory

    def run(
        self, request, provider="mock", live=True, include_approval_demo=False,
        max_revisions=1, model=None, allow_live_api=False, openai_client=None,
        enable_controlled_execution=False,
    ):
        selected = ProviderBridge(self.root, model, allow_live_api, openai_client)
        selected.select(provider)
        sid = f"RWS-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{uuid4().hex[:6]}"
        sprint = f"DEMO-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        workers = {item.worker_id: ("queued" if item.order == 1 else "waiting") for item in WorkerRegistry().list()}
        session = RuntimeSession(sid, sprint, request, provider, "running", _now(), _now(), workers)
        store = ArtifactStore(self.root, sid)
        store.json("session.json", session.to_dict())
        EventStream(store).emit("RUNTIME_CREATED", detail=request)
        settings = {
            "model": model, "allow_live_api": allow_live_api,
            "enable_controlled_execution": enable_controlled_execution,
            "include_approval_demo": include_approval_demo, "max_revisions": max_revisions,
            "live": live,
        }
        context = WorkerContext(
            request=request,
            task_metadata={
                "session_id": sid,
                "sprint_id": sprint,
                "provider": provider,
            },
            runtime_evidence=session.execution_verification,
        )
        return self._continue(session, context, selected, settings, 0, 0)

    def _role_executor(self, selected):
        if self.role_executor_factory is None:
            return RoleExecutor(selected)
        executor = self.role_executor_factory(selected)
        if not hasattr(executor, "execute"):
            raise RoleExecutionError("role executor factory returned an invalid executor")
        return executor

    def approval_show(self, approval_id: str) -> dict:
        return RuntimeApprovalStore(self.root).load(approval_id)

    def approval_reject(self, approval_id: str) -> dict:
        store = RuntimeApprovalStore(self.root)
        record = store.load(approval_id)
        session = self._load_session(record["session_id"])
        self._validate_pending_session(session, record)
        rejected = store.reject(approval_id)
        session.status = "blocked"
        session.current_activity = "Controlled execution approval rejected"
        session.pending_approval = _approval_summary(rejected)
        session.updated_at = _now()
        artifact_store = ArtifactStore(self.root, session.session_id)
        events = EventStream(artifact_store)
        if session.runtime_tasks:
            task = RuntimeTask.from_value(session.runtime_tasks[-1])
            context = WorkerContext(
                request=session.request,
                runtime_task=task,
                runtime_pipeline=RuntimePipeline.from_value(
                    session.runtime_pipelines[-1] if session.runtime_pipelines else None
                ),
                revision=int(task.orchestration_metadata.get("revision_count", 0)),
            )
            if task.role_executions:
                orchestrator = RuntimeOrchestrator(
                    context,
                    max_revisions=int(task.orchestration_metadata.get("max_revisions", 1)),
                )
                role_result = orchestrator.record_approval_role_outcome(
                    record["source_worker"], completed=False,
                    error="controlled action approval rejected",
                )
                _sync_runtime_task(session, context, artifact_store)
                _emit_role_event(events, "ROLE_EXECUTION_FAILED", role_result)
            _fail_task(session, context, artifact_store, events, record["source_worker"],
                       "controlled action approval rejected")
        artifact_store.json("session.json", session.to_dict())
        events.emit("APPROVAL_REJECTED", record["source_worker"], approval_id)
        return rejected

    def approval_approve(self, approval_id: str, openai_client=None):
        approval_store = RuntimeApprovalStore(self.root)
        record = approval_store.load(approval_id)
        session = self._load_session(record["session_id"])
        self._validate_pending_session(session, record)
        continuation = self._load_continuation(session.session_id)
        request = request_from_record(record)
        self._validate_continuation(continuation, session, record, request)
        settings = continuation["settings"]
        selected = ProviderBridge(self.root, settings.get("model"), settings.get("allow_live_api", False), openai_client)
        selected.select(session.provider)
        context = WorkerContext.from_value(continuation["context"])
        approved = approval_store.approve(approval_id)
        artifact_store = ArtifactStore(self.root, session.session_id)
        events = EventStream(artifact_store)
        task = context.runtime_task
        events.emit(
            "APPROVAL_GRANTED", request.source_worker, approval_id,
            **_task_event_fields(task),
        )
        if context.runtime_pipeline is not None:
            context.runtime_pipeline.mark_approved()
            _sync_runtime_pipeline(session, context, artifact_store)
            _emit_pipeline_event(
                events, "TaskApproved", context, request.source_worker,
                "exact controlled action approval granted",
                {"approval_request_id": approval_id},
            )
        observed = ControlledExecutor(self.root).execute_approved(request, approved)
        consumed = approval_store.consume(approved)
        events.emit("APPROVAL_CONSUMED", request.source_worker, approval_id)
        session.pending_approval = _approval_summary(consumed)
        evidence = {"verified_changed_files": [], "verified_test_executions": [], "execution_evidence": [observed]}
        if observed.get("status") == "SUCCEEDED" and observed.get("changed"):
            evidence["verified_changed_files"].append(observed["relative_path"])
        _merge_execution_evidence(session, evidence)
        self._replace_worker_truth_output(session, context, request.source_worker, evidence)
        if observed.get("status") != "SUCCEEDED":
            if task is not None and task.role_executions:
                orchestrator = RuntimeOrchestrator(
                    context, max_revisions=int(settings.get("max_revisions", 1)),
                )
                role_result = orchestrator.record_approval_role_outcome(
                    request.source_worker, completed=False,
                    output=context.outputs.get(request.source_worker, {}),
                    error=f"approved controlled execution failed: {observed.get('status')}",
                    evidence_references=["runtime_task:execution_evidence"],
                )
                _sync_runtime_task(session, context, artifact_store)
                _emit_role_event(events, "ROLE_RESULT_RECORDED", role_result)
                _emit_role_event(events, "ROLE_EXECUTION_FAILED", role_result)
            _fail_task(session, context, artifact_store, events, request.source_worker,
                       "approved controlled execution failed", observed)
            session.status = "failed"
            session.error = f"Approved execution failed safely: {observed.get('status')}"
            session.updated_at = _now()
            artifact_store.json("session.json", session.to_dict())
            events.emit("APPROVED_EXECUTION_FAILED", request.source_worker, observed.get("status", "failed"))
            return session
        if task is not None and task.role_executions:
            orchestrator = RuntimeOrchestrator(
                context, max_revisions=int(settings.get("max_revisions", 1)),
            )
            role_result = orchestrator.record_approval_role_outcome(
                request.source_worker, completed=True,
                output=context.outputs.get(request.source_worker, {}),
                evidence_references=[
                    "approval_record:consumed",
                    "runtime_task:execution_evidence",
                ],
            )
            _sync_runtime_task(session, context, artifact_store)
            _emit_role_event(events, "ROLE_RESULT_RECORDED", role_result)
            _emit_role_event(events, "ROLE_EXECUTION_COMPLETED", role_result)
            _emit_role_event(events, "ROLE_HANDOFF_REQUESTED", role_result)
            result_handoff = orchestrator.create_result_handoff(
                role_result, RuntimeRole.QA,
                validation_metadata=_handoff_validation_metadata(role_result),
            )
            _sync_runtime_task(session, context, artifact_store)
            _emit_result_handoff_event(events, "RESULT_HANDOFF_CREATED", result_handoff)
        if task is not None:
            task.transition(WorkerState.RESUMED, "approved action executed", observed)
            _sync_runtime_task(session, context, artifact_store)
        if context.runtime_pipeline is not None:
            orchestrator = RuntimeOrchestrator(
                context, max_revisions=int(settings.get("max_revisions", 1)),
            )
            decision = orchestrator.approval_resumed(request.source_worker)
            _emit_orchestration_decision(events, context, decision)
            _forward_pipeline(
                session, context, artifact_store, events,
                decision.target_state, "approval_guardian", decision.target_worker,
                "approved controlled action completed; forwarding to QA",
            )
        session.workers[request.source_worker] = "completed"
        session.status = "running"
        session.current_activity = "Approved action executed; runtime resuming"
        events.emit("RUNTIME_RESUMED", request.source_worker, approval_id)
        return self._continue(
            session, context, selected, settings,
            int(continuation["next_worker_index"]), int(continuation.get("revisions", 0)),
        )

    def _continue(self, session, context, selected, settings, start_index, revisions):
        context = WorkerContext.from_value(context)
        if int(context.revision) != int(revisions):
            raise RuntimeSessionError("runtime continuation revision state mismatch")
        store = ArtifactStore(self.root, session.session_id)
        events = EventStream(store)
        bus = MessageBus(store, session)
        dashboard = TerminalDashboard(settings.get("live", False))
        controlled = ControlledExecutor(self.root) if settings.get("enable_controlled_execution") else None
        role_executor = self._role_executor(selected)
        orchestrator = RuntimeOrchestrator(
            context, max_revisions=int(settings.get("max_revisions", 1)),
        )
        for index, definition in enumerate(
            orchestrator.worker_definitions(start_index), start=start_index,
        ):
            for worker_id in session.workers:
                if session.workers[worker_id] == "queued":
                    session.workers[worker_id] = "waiting"
            session.workers[definition.worker_id] = "running"
            session.current_activity = f"{definition.role} is working..."
            session.progress = index * 20 + 10
            context.task_metadata["current_worker_id"] = definition.worker_id
            context.update_runtime_evidence(session.execution_verification)
            task = context.runtime_task
            if definition.worker_id == "development_worker" and task is not None:
                task.transition(WorkerState.RUNNING, "developer worker started")
                _sync_runtime_task(session, context, store)
                events.emit(
                    "TASK_STARTED", definition.worker_id, "developer worker started",
                    **_task_event_fields(task),
                )
            elif definition.worker_id == "qa_worker" and task is not None:
                task.transition(WorkerState.QA, "QA worker started")
                _sync_runtime_task(session, context, store)
            _start_pipeline_worker(session, context, store, events, definition.worker_id)
            dashboard.render(session)
            events.emit("WORKER_STARTED", definition.worker_id)
            role = RuntimeRole.from_worker(definition.worker_id)
            role_request = None
            role_result = None
            if role is not None:
                provisional_task_id = (
                    context.runtime_task.id if context.runtime_task is not None
                    else f"TASK-{uuid4().hex}"
                )
                role_request = orchestrator.build_role_request(
                    definition.worker_id, task_id=provisional_task_id,
                )
                if role_request.input_handoff_id:
                    _sync_runtime_task(session, context, store)
                    _emit_role_handoff_delivery(events, role_request)
                _emit_role_request_event(events, "ROLE_EXECUTION_STARTED", role_request)
                try:
                    role_result = orchestrator.invoke_role(
                        role_executor, role_request, definition,
                    )
                except (InvalidRoleResult, RoleExecutionError) as exc:
                    role_result = _failed_role_result(role_request, str(exc))
                if role is RuntimeRole.PLANNER and context.runtime_task is None:
                    _initialize_runtime_task(
                        session, context, provisional_task_id, store, events,
                    )
                    orchestrator = RuntimeOrchestrator(
                        context, max_revisions=int(settings.get("max_revisions", 1)),
                    )
                result = role_result.to_worker_result()
            else:
                result = BaseWorker(definition, selected).execute(context)
            pending_request = None
            pending_observation = None
            evidence = {"verified_changed_files": [], "verified_test_executions": [], "execution_evidence": []}
            if result.status == "completed":
                evidence, pending_request, pending_observation = _execute_proposals(
                    controlled, definition.worker_id, result.output, self.root
                )
                result.output, findings = apply_execution_truth_contract(definition.worker_id, result.output, evidence)
                session.truth_contract_findings.extend(findings)
                _merge_execution_evidence(session, evidence)
            if role_result is not None and role_request is not None:
                role_result.output = dict(result.output)
                role_result.evidence_references = _role_evidence_references(
                    role_result, evidence,
                )
                if pending_request is not None:
                    _set_role_waiting_approval(role_result)
                try:
                    role_result = orchestrator.record_role_result(
                        role_result, role_request,
                    )
                except (InvalidRoleResult, RoleExecutionError) as exc:
                    role_result = _failed_role_result(role_request, str(exc))
                    orchestrator.record_role_result(role_result, role_request)
                    result = role_result.to_worker_result()
                _sync_runtime_task(session, context, store)
                _emit_role_event(events, "ROLE_RESULT_RECORDED", role_result)
                _emit_role_event(
                    events,
                    "ROLE_EXECUTION_FAILED"
                    if role_result.state is RoleExecutionState.FAILED
                    else "ROLE_EXECUTION_COMPLETED",
                    role_result,
                )
                if role_result.handoff_target:
                    _emit_role_event(events, "ROLE_HANDOFF_REQUESTED", role_result)
            session.results.append(asdict(result))
            context.record_worker_output(definition.worker_id, result.output)
            context.update_runtime_evidence(session.execution_verification)
            if definition.worker_id == "planning_worker" and result.status == "completed":
                _complete_planning_task(
                    session, context, result.output, store, events,
                )
                orchestrator = RuntimeOrchestrator(
                    context, max_revisions=int(settings.get("max_revisions", 1)),
                )
                result_handoff = orchestrator.create_result_handoff(
                    role_result, RuntimeRole.DEVELOPER,
                    validation_metadata=_handoff_validation_metadata(role_result),
                )
                _sync_runtime_task(session, context, store)
                _emit_result_handoff_event(events, "RESULT_HANDOFF_CREATED", result_handoff)
                decision = orchestrator.handoff_after(definition.worker_id)
                _emit_orchestration_decision(events, context, decision)
            elif context.runtime_task is not None and definition.worker_id in {"development_worker", "qa_worker"}:
                context.runtime_task.record_output(definition.worker_id, result.output)
                for item in evidence.get("execution_evidence", []):
                    context.runtime_task.record_evidence(item)
                _sync_runtime_task(session, context, store)
            if result.status != "completed":
                _fail_task(session, context, store, events, definition.worker_id,
                           "worker execution failed")
                session.status = "failed"
                session.error = result.error
                events.emit("PROVIDER_ERROR", definition.worker_id, result.error)
                break
            session.workers[definition.worker_id] = "completed"
            bus.publish(definition.worker_id, "runtime", "WORKER_OUTPUT", result.summary, result.output)
            metadata = result.output.get("_provider", {})
            events.emit("WORKER_COMPLETED", definition.worker_id, json.dumps(metadata) if metadata else "")
            _complete_pipeline_worker(context, events, definition.worker_id)
            if pending_request is not None:
                return self._pause_for_approval(
                    session, context, settings, revisions, index + 1,
                    pending_request, pending_observation or {}, store, events,
                )
            if definition.worker_id == "development_worker":
                result_handoff = orchestrator.create_result_handoff(
                    role_result, RuntimeRole.QA,
                    validation_metadata=_handoff_validation_metadata(role_result),
                )
                _sync_runtime_task(session, context, store)
                _emit_result_handoff_event(events, "RESULT_HANDOFF_CREATED", result_handoff)
                decision = orchestrator.handoff_after(definition.worker_id)
                _emit_orchestration_decision(events, context, decision)
                _forward_pipeline(
                    session, context, store, events,
                    decision.target_state, definition.worker_id, decision.target_worker,
                    "development completed; forwarding to QA",
                )
            if definition.worker_id == "qa_worker" and claimed_qa_failures(result.output):
                events.emit(
                    "QA_COMPLETED", definition.worker_id, "QA requested revision",
                    **_task_event_fields(context.runtime_task),
                )
                revision_reason = _qa_revision_reason(result.output)
                qa_reference = _latest_role_result_reference(context.runtime_task)
                try:
                    decision = orchestrator.request_revision(
                        revision_reason, qa_reference,
                    )
                except RevisionLimitExceeded as exc:
                    _sync_runtime_task(session, context, store)
                    _emit_qa_decision_event(
                        events, "REVISION_LIMIT_EXCEEDED",
                        orchestrator.latest_qa_revision_decision,
                    )
                    events.emit(
                        "ORCHESTRATION_ERROR", definition.worker_id, str(exc),
                        **_task_event_fields(context.runtime_task),
                    )
                    _fail_task(session, context, store, events, definition.worker_id,
                               str(exc))
                    session.status = "failed"
                    session.error = str(exc)
                    break
                revisions = orchestrator.revision_count
                result_handoff = orchestrator.create_result_handoff(
                    role_result, RuntimeRole.DEVELOPER,
                    validation_metadata={
                        **_handoff_validation_metadata(role_result),
                        "qa_outcome": "revision_requested",
                    },
                    revision_reason=revision_reason,
                )
                _sync_runtime_task(session, context, store)
                _emit_qa_decision_event(
                    events, "QA_REVISION_REQUESTED",
                    orchestrator.latest_qa_revision_decision,
                )
                _emit_result_handoff_event(events, "RESULT_HANDOFF_CREATED", result_handoff)
                _emit_orchestration_decision(events, context, decision)
                events.emit(
                    "REVISION_STARTED", "development_worker", f"revision {revisions}",
                    **_task_event_fields(context.runtime_task),
                )
                outcome = self._run_revision(
                    session, context, selected, controlled, bus, events, orchestrator,
                    settings, role_executor,
                )
                if outcome is not True:
                    if outcome is not False:
                        return outcome
                    break
            elif definition.worker_id == "qa_worker":
                events.emit(
                    "QA_COMPLETED", definition.worker_id, "QA completed",
                    **_task_event_fields(context.runtime_task),
                )
                qa_reference = _latest_role_result_reference(context.runtime_task)
                qa_decision = orchestrator.accept_qa(
                    "QA accepted development result", qa_reference,
                )
                result_handoff = orchestrator.create_result_handoff(
                    role_result, RuntimeRole.DOCUMENTATION,
                    validation_metadata={
                        **_handoff_validation_metadata(role_result),
                        "qa_outcome": "accepted",
                    },
                )
                _sync_runtime_task(session, context, store)
                _emit_qa_decision_event(events, "QA_ACCEPTED", qa_decision.to_dict())
                _emit_result_handoff_event(events, "RESULT_HANDOFF_CREATED", result_handoff)
                decision = orchestrator.handoff_after(definition.worker_id)
                _emit_orchestration_decision(events, context, decision)
                _forward_pipeline(
                    session, context, store, events,
                    decision.target_state, definition.worker_id, decision.target_worker,
                    "QA completed; forwarding to Documentation",
                )
            elif definition.worker_id == "documentation_worker":
                _complete_task(session, context, store, events)
                decision = orchestrator.handoff_after(definition.worker_id)
                _emit_orchestration_decision(events, context, decision)
                _forward_pipeline(
                    session, context, store, events,
                    decision.target_state, definition.worker_id, decision.target_worker,
                    "documentation completed; pipeline done",
                )
            session.progress = (index + 1) * 20
            session.current_activity = result.summary
            dashboard.render(session)
        return self._finalize(session, context, settings, store, events, dashboard)

    def _run_revision(
        self, session, context, selected, controlled, bus, events, orchestrator,
        settings, role_executor,
    ):
        while True:
            for retry_definition in orchestrator.revision_workers():
                retry_id = retry_definition.worker_id
                session.workers[retry_id] = "running"
                session.current_activity = f"{retry_definition.role} is revising..."
                task = context.runtime_task
                if task is not None:
                    target = (
                        WorkerState.RUNNING
                        if retry_id == "development_worker" else WorkerState.QA
                    )
                    task.transition(target, f"{retry_id} revision started")
                    _sync_runtime_task(session, context, events.store)
                    if retry_id == "development_worker":
                        _emit_pipeline_event(
                            events, "TaskRejected", context, "qa_worker",
                            "QA rejected development output for revision",
                        )
                        _forward_pipeline(
                            session, context, events.store, events,
                            PipelineState.DEVELOPING, "qa_worker", "development_worker",
                            "QA requested development revision",
                            {"revision_count": orchestrator.revision_count},
                        )
                        events.emit(
                            "TASK_STARTED", retry_id, "development revision started",
                            **_task_event_fields(task),
                        )
                _start_pipeline_worker(session, context, events.store, events, retry_id)
                role_request = orchestrator.build_role_request(retry_id)
                if role_request.input_handoff_id:
                    _sync_runtime_task(session, context, events.store)
                    _emit_role_handoff_delivery(events, role_request)
                    if retry_id == "development_worker":
                        events.emit(
                            "REVISION_RESUMED", retry_id,
                            f"revision {orchestrator.revision_count} delivered to Developer",
                            **_task_event_fields(context.runtime_task),
                        )
                _emit_role_request_event(
                    events, "ROLE_EXECUTION_STARTED", role_request,
                )
                try:
                    role_result = orchestrator.invoke_role(
                        role_executor, role_request, retry_definition,
                    )
                except (InvalidRoleResult, RoleExecutionError) as exc:
                    role_result = _failed_role_result(role_request, str(exc))
                retry = role_result.to_worker_result()
                evidence = {
                    "verified_changed_files": [], "verified_test_executions": [],
                    "execution_evidence": [],
                }
                pending = None
                observation = None
                if retry.status == "completed":
                    evidence, pending, observation = _execute_proposals(
                        controlled, retry_id, retry.output, self.root,
                    )
                    retry.output, findings = apply_execution_truth_contract(
                        retry_id, retry.output, evidence,
                    )
                    session.truth_contract_findings.extend(findings)
                    _merge_execution_evidence(session, evidence)
                role_result.output = dict(retry.output)
                role_result.evidence_references = _role_evidence_references(
                    role_result, evidence,
                )
                if pending is not None:
                    _set_role_waiting_approval(role_result)
                try:
                    role_result = orchestrator.record_role_result(
                        role_result, role_request,
                    )
                except (InvalidRoleResult, RoleExecutionError) as exc:
                    role_result = _failed_role_result(role_request, str(exc))
                    orchestrator.record_role_result(role_result, role_request)
                    retry = role_result.to_worker_result()
                _sync_runtime_task(session, context, events.store)
                _emit_role_event(events, "ROLE_RESULT_RECORDED", role_result)
                _emit_role_event(
                    events,
                    "ROLE_EXECUTION_FAILED"
                    if role_result.state is RoleExecutionState.FAILED
                    else "ROLE_EXECUTION_COMPLETED",
                    role_result,
                )
                if role_result.handoff_target:
                    _emit_role_event(events, "ROLE_HANDOFF_REQUESTED", role_result)
                session.results.append(asdict(retry))
                context.record_worker_output(retry_id, retry.output)
                context.update_runtime_evidence(session.execution_verification)
                if context.runtime_task is not None:
                    context.runtime_task.record_output(retry_id, retry.output)
                    for item in evidence.get("execution_evidence", []):
                        context.runtime_task.record_evidence(item)
                    _sync_runtime_task(session, context, events.store)
                bus.publish(
                    retry_id, "runtime", "WORKER_OUTPUT", retry.summary, retry.output,
                )
                if retry.status != "completed":
                    _fail_task(
                        session, context, events.store, events, retry_id,
                        "revision worker failed",
                    )
                    session.status = "failed"
                    session.error = retry.error
                    events.emit("PROVIDER_ERROR", retry_id, retry.error)
                    return False
                session.workers[retry_id] = "completed"
                metadata = retry.output.get("_provider", {})
                events.emit(
                    "WORKER_COMPLETED", retry_id,
                    json.dumps(metadata) if metadata else "",
                )
                if retry_id == "qa_worker":
                    events.emit(
                        "QA_COMPLETED", retry_id, "revision QA completed",
                        **_task_event_fields(context.runtime_task),
                    )
                _complete_pipeline_worker(context, events, retry_id)
                if pending is not None:
                    return self._pause_for_approval(
                        session, context, settings, orchestrator.revision_count,
                        orchestrator.worker_index("qa_worker"), pending,
                        observation or {}, events.store, events,
                    )
                if retry_id == "development_worker":
                    result_handoff = orchestrator.create_result_handoff(
                        role_result, RuntimeRole.QA,
                        validation_metadata={
                            **_handoff_validation_metadata(role_result),
                            "revision_count": orchestrator.revision_count,
                        },
                    )
                    _sync_runtime_task(session, context, events.store)
                    _emit_result_handoff_event(
                        events, "RESULT_HANDOFF_CREATED", result_handoff,
                    )
                    decision = orchestrator.handoff_after(retry_id)
                    _emit_orchestration_decision(events, context, decision)
                    _forward_pipeline(
                        session, context, events.store, events,
                        decision.target_state, retry_id, decision.target_worker,
                        "development revision completed; forwarding to QA",
                        {"revision_count": orchestrator.revision_count},
                    )
            if not claimed_qa_failures(context["outputs"]["qa_worker"]):
                qa_reference = _latest_role_result_reference(context.runtime_task)
                qa_decision = orchestrator.accept_qa(
                    "QA accepted revised development result", qa_reference,
                )
                result_handoff = orchestrator.create_result_handoff(
                    role_result, RuntimeRole.DOCUMENTATION,
                    validation_metadata={
                        **_handoff_validation_metadata(role_result),
                        "qa_outcome": "accepted",
                    },
                )
                _sync_runtime_task(session, context, events.store)
                _emit_qa_decision_event(events, "QA_ACCEPTED", qa_decision.to_dict())
                _emit_result_handoff_event(
                    events, "RESULT_HANDOFF_CREATED", result_handoff,
                )
                decision = orchestrator.handoff_after("qa_worker")
                _emit_orchestration_decision(events, context, decision)
                _forward_pipeline(
                    session, context, events.store, events,
                    decision.target_state, "qa_worker", decision.target_worker,
                    "revision QA completed; forwarding to Documentation",
                )
                return True
            revision_reason = _qa_revision_reason(context["outputs"]["qa_worker"])
            qa_reference = _latest_role_result_reference(context.runtime_task)
            try:
                decision = orchestrator.request_revision(
                    revision_reason, qa_reference,
                )
            except RevisionLimitExceeded as exc:
                _sync_runtime_task(session, context, events.store)
                _emit_qa_decision_event(
                    events, "REVISION_LIMIT_EXCEEDED",
                    orchestrator.latest_qa_revision_decision,
                )
                events.emit(
                    "ORCHESTRATION_ERROR", "qa_worker", str(exc),
                    **_task_event_fields(context.runtime_task),
                )
                _fail_task(session, context, events.store, events, "qa_worker", str(exc))
                session.status = "failed"
                session.error = str(exc)
                return False
            result_handoff = orchestrator.create_result_handoff(
                role_result, RuntimeRole.DEVELOPER,
                validation_metadata={
                    **_handoff_validation_metadata(role_result),
                    "qa_outcome": "revision_requested",
                },
                revision_reason=revision_reason,
            )
            _sync_runtime_task(session, context, events.store)
            _emit_qa_decision_event(
                events, "QA_REVISION_REQUESTED",
                orchestrator.latest_qa_revision_decision,
            )
            _emit_result_handoff_event(
                events, "RESULT_HANDOFF_CREATED", result_handoff,
            )
            _emit_orchestration_decision(events, context, decision)
            events.emit(
                "REVISION_STARTED", "development_worker",
                f"revision {orchestrator.revision_count}",
                **_task_event_fields(context.runtime_task),
            )

    def _pause_for_approval(
        self, session, context, settings, revisions, next_index,
        request, observation, store, events,
    ):
        record = RuntimeApprovalStore(self.root).create(
            request, session.session_id, session.sprint_id, observation
        )
        session.status = "waiting_approval"
        session.workers[request.source_worker] = "waiting_approval"
        session.current_activity = "Human approval required for controlled existing-file edit"
        session.pending_approval = _approval_summary(record)
        session.updated_at = _now()
        task = context.runtime_task
        if task is not None:
            task.transition(WorkerState.WAITING_APPROVAL, "controlled action requires approval", observation)
            _sync_runtime_task(session, context, store)
        if context.runtime_pipeline is not None:
            orchestrator = RuntimeOrchestrator(
                context, max_revisions=int(settings.get("max_revisions", 1)),
            )
            decision = orchestrator.approval_required(request.source_worker)
            _emit_orchestration_decision(events, context, decision)
            _forward_pipeline(
                session, context, store, events,
                decision.target_state, request.source_worker, decision.target_worker,
                "controlled action requires Product Owner approval",
                {"approval_request_id": record["approval_request_id"]},
            )
        store.json("continuation.json", {
            "session_id": session.session_id,
            "approval_request_id": record["approval_request_id"],
            "execution_request_id": request.request_id,
            "action_fingerprint": action_fingerprint(request),
            "next_worker_index": next_index,
            "revisions": revisions,
            "context": context.to_dict(),
            "settings": settings,
        })
        _write_partial_artifacts(store, context, session)
        store.json("session.json", session.to_dict())
        events.emit("APPROVAL_PENDING", request.source_worker, record["approval_request_id"])
        events.emit(
            "APPROVAL_REQUESTED", request.source_worker, record["approval_request_id"],
            **_task_event_fields(task),
        )
        events.emit("RUNTIME_WAITING_APPROVAL", request.source_worker, request.relative_path or "command")
        return session

    def _finalize(self, session, context, settings, store, events, dashboard):
        definition_path = store.json("runtime_sprint.json", {
            "sprint_id": session.sprint_id, "title": "Runtime validation", "version": "1",
            "steps": [{"step_id": "RUNTIME-CHECK", "name": "Python runtime", "command": "python --version", "cwd": str(self.root), "environment": "local"}],
        })
        runner_run = SprintAutoRunner(self.root).start(definition_path)
        session.runner_run_id = runner_run.run_id
        if runner_run.status != "completed":
            session.status = runner_run.status
        if settings.get("include_approval_demo"):
            from approval_guardian import ApprovalGuardian, ApprovalRequest
            for command in ("git reset --hard", "git push origin develop"):
                decision = ApprovalGuardian(self.root).evaluate(ApprovalRequest(command=command, cwd=str(self.root), branch="feature/demo"))
                events.emit("APPROVAL_DEMO", detail=f"{command}: {decision.decision.value}")
        if session.status == "running":
            session.status = "completed"
        if session.execution_verification["verified_changed_files"] and session.execution_verification["verified_test_executions"]:
            session.execution_verification["status"] = "VERIFIED"
        session.execution_verification["findings"] = [item["classification"] for item in session.truth_contract_findings]
        session.progress = 100 if session.status == "completed" else session.progress
        session.updated_at = _now()
        _sync_runtime_task(session, context, store)
        _sync_runtime_pipeline(session, context, store)
        _write_partial_artifacts(store, context, session)
        report = _truthful_report(session, context)
        if not any(item["type"] == "final_report" for item in session.artifacts):
            session.artifacts.append({"type": "final_report", "path": str(store.text("final_report.md", report))})
        else:
            store.text("final_report.md", report)
        store.json("artifact_index.json", session.artifacts)
        store.json("session.json", session.to_dict())
        events.emit("RUNTIME_COMPLETED", detail=session.status)
        dashboard.render(session)
        return session

    def _replace_worker_truth_output(self, session, context, worker_id, evidence):
        original = context["outputs"].get(worker_id, {})
        normalized, findings = apply_execution_truth_contract(worker_id, original, evidence)
        context.record_worker_output(worker_id, normalized)
        context.update_runtime_evidence(session.execution_verification)
        if context.runtime_task is not None:
            context.runtime_task.record_output(worker_id, normalized)
        session.truth_contract_findings = [
            item for item in session.truth_contract_findings
            if not (worker_id == "development_worker" and item.get("classification") == "UNVERIFIED_FILE_CHANGE_CLAIM")
        ]
        session.truth_contract_findings.extend(findings)
        for result in reversed(session.results):
            if result.get("worker_id") == worker_id:
                result["output"] = normalized
                break

    def _load_session(self, session_id):
        if not isinstance(session_id, str) or not session_id.startswith("RWS-"):
            raise RuntimeSessionError("approval session mismatch")
        try:
            data = self.status(session_id)
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeSessionError("approval session is missing or invalid") from exc
        return RuntimeSession(**data)

    def _load_continuation(self, session_id):
        path = self.root / "data" / "runtime_sessions" / session_id / "continuation.json"
        if not path.is_file():
            raise RuntimeSessionError("pending runtime continuation is missing")
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeSessionError("pending runtime continuation is corrupt") from exc

    @staticmethod
    def _validate_pending_session(session, record):
        if session.status != "waiting_approval":
            raise RuntimeSessionError("runtime session is not WAITING_APPROVAL")
        pending = session.pending_approval or {}
        if pending.get("approval_request_id") != record.get("approval_request_id"):
            raise RuntimeSessionError("approval belongs to another pending session action")
        if record.get("session_id") != session.session_id:
            raise RuntimeSessionError("approval session mismatch")

    @staticmethod
    def _validate_continuation(continuation, session, record, request):
        checks = {
            "session_id": session.session_id,
            "approval_request_id": record["approval_request_id"],
            "execution_request_id": request.request_id,
            "action_fingerprint": action_fingerprint(request),
        }
        for key, expected in checks.items():
            if continuation.get(key) != expected:
                raise RuntimeSessionError(f"continuation {key} mismatch")

    def status(self, sid):
        path = self.root / "data" / "runtime_sessions" / sid / "session.json"
        return json.loads(path.read_text(encoding="utf-8"))

    def report(self, sid):
        return (self.root / "data" / "runtime_sessions" / sid / "final_report.md").read_text(encoding="utf-8")

    def cancel(self, sid):
        data = self.status(sid)
        if data["status"] in {"completed", "failed", "blocked", "cancelled"}:
            raise ValueError("cannot cancel terminal session")
        data["status"] = "cancelled"
        ArtifactStore(self.root, sid).json("session.json", data)
        return data


def _execute_proposals(executor, worker_id, output, root):
    evidence = {"verified_changed_files": [], "verified_test_executions": [], "execution_evidence": []}
    if executor is None:
        return evidence, None, None
    if worker_id == "development_worker":
        for item in output.get("proposed_file_writes", []):
            if not isinstance(item, dict):
                continue
            relative_path = item.get("relative_path", "")
            expected_hash = _current_hash(root, relative_path)
            request = ExecutionRequest.file_write(
                relative_path, item.get("content", ""), worker_id,
                item.get("purpose", ""), expected_hash,
            )
            observed = executor.execute(request)
            evidence["execution_evidence"].append(observed)
            if observed.get("status") == "WAITING_APPROVAL":
                return evidence, request, observed
            if observed.get("status") == "SUCCEEDED" and observed.get("changed"):
                evidence["verified_changed_files"].append(observed["relative_path"])
    if worker_id == "qa_worker":
        for item in output.get("requested_test_executions", []):
            if not isinstance(item, dict) or not isinstance(item.get("argv"), list):
                continue
            request = ExecutionRequest.command_run(item["argv"], worker_id, item.get("purpose", ""))
            observed = executor.execute(request)
            evidence["execution_evidence"].append(observed)
            if observed.get("status") in {"SUCCEEDED", "FAILED"}:
                evidence["verified_test_executions"].append(observed)
    return evidence, None, None


def _initialize_runtime_task(session, context, task_id, store, events):
    task = RuntimeTask(
        id=task_id, worker="development_worker",
        inputs={"request": context.request}, owner="planning_worker",
    )
    context.runtime_task = task
    context.runtime_pipeline = RuntimePipeline(task.id)
    events.emit(
        "TASK_CREATED", task.worker, "Planner role execution initialized task",
        **_task_event_fields(task),
    )
    _sync_runtime_task(session, context, store)
    _sync_runtime_pipeline(session, context, store)


def _complete_planning_task(session, context, planner_output, store, events):
    raw_priority = planner_output.get("priority", 0)
    priority = raw_priority if isinstance(raw_priority, int) and not isinstance(raw_priority, bool) else 0
    raw_dependencies = planner_output.get("dependencies", [])
    dependencies = [item for item in raw_dependencies if isinstance(item, str)] \
        if isinstance(raw_dependencies, list) else []
    task = context.runtime_task
    if task is None or context.runtime_pipeline is None:
        raise RuntimeSessionError("Planner role completed without an initialized task")
    task.priority = priority
    task.dependencies = dependencies
    task.inputs["planner_output"] = dict(planner_output)
    task.transition(WorkerState.READY, "planner output converted to runtime task")
    context.runtime_pipeline.transition(
        PipelineState.ASSIGNED, "development_worker",
        "Planner assigned task to Developer",
    )
    handoff = task.handoff(
        "development_worker", "Planner forwarded task to Developer",
        {"pipeline_state": PipelineState.ASSIGNED.value},
    )
    _sync_runtime_task(session, context, store)
    _sync_runtime_pipeline(session, context, store)
    _emit_pipeline_event(
        events, "TaskAssigned", context, "development_worker",
        "Planner assigned task to Developer", handoff,
    )
    _emit_pipeline_event(
        events, "TaskForwarded", context, "planning_worker",
        "Planner forwarded task to Developer", handoff,
    )


def _complete_task(session, context, store, events):
    task = context.runtime_task
    if task is None or task.state in {WorkerState.COMPLETED, WorkerState.FAILED}:
        return
    task.transition(WorkerState.COMPLETED, "documentation role completed after QA pass")
    _sync_runtime_task(session, context, store)
    events.emit(
        "TASK_COMPLETED", task.worker, "runtime task completed",
        **_task_event_fields(task),
    )


def _fail_task(session, context, store, events, worker_id, reason, evidence=None):
    task = context.runtime_task
    if task is None:
        return
    if task.state not in {WorkerState.COMPLETED, WorkerState.FAILED}:
        task.transition(WorkerState.FAILED, reason, evidence)
        _sync_runtime_task(session, context, store)
        events.emit(
            "TASK_FAILED", worker_id, reason,
            **_task_event_fields(task),
        )
    if context.runtime_pipeline is not None:
        context.runtime_pipeline.mark_rejected()
        _sync_runtime_pipeline(session, context, store)
        _emit_pipeline_event(
            events, "TaskRejected", context, worker_id, reason,
            evidence or {},
        )


def _sync_runtime_task(session, context, store):
    task = context.runtime_task
    if task is None:
        return
    snapshot = task.to_dict()
    session.runtime_tasks = [
        snapshot if item.get("id") == task.id else item
        for item in session.runtime_tasks
    ]
    if not any(item.get("id") == task.id for item in session.runtime_tasks):
        session.runtime_tasks.append(snapshot)
    path = store.json("runtime_task.json", snapshot)
    if not any(item["type"] == "runtime_task.json" for item in session.artifacts):
        session.artifacts.append({"type": "runtime_task.json", "path": str(path)})


def _sync_runtime_pipeline(session, context, store):
    pipeline = context.runtime_pipeline
    if pipeline is None:
        return
    snapshot = pipeline.to_dict()
    session.runtime_pipelines = [
        snapshot if item.get("task_id") == pipeline.task_id else item
        for item in session.runtime_pipelines
    ]
    if not any(item.get("task_id") == pipeline.task_id for item in session.runtime_pipelines):
        session.runtime_pipelines.append(snapshot)
    path = store.json("runtime_pipeline.json", snapshot)
    if not any(item["type"] == "runtime_pipeline.json" for item in session.artifacts):
        session.artifacts.append({"type": "runtime_pipeline.json", "path": str(path)})


def _start_pipeline_worker(session, context, store, events, worker_id):
    pipeline = context.runtime_pipeline
    if pipeline is None or worker_id not in {
        "development_worker", "qa_worker", "documentation_worker",
    }:
        return
    if worker_id == "development_worker" and pipeline.state == PipelineState.ASSIGNED:
        pipeline.transition(
            PipelineState.DEVELOPING, worker_id, "Developer started assigned task",
        )
        _sync_runtime_pipeline(session, context, store)
    _emit_pipeline_event(
        events, "TaskStarted", context, worker_id,
        f"{worker_id} started pipeline work",
    )


def _complete_pipeline_worker(context, events, worker_id):
    if context.runtime_pipeline is None or worker_id not in {
        "development_worker", "qa_worker", "documentation_worker",
    }:
        return
    _emit_pipeline_event(
        events, "TaskCompleted", context, worker_id,
        f"{worker_id} completed pipeline work",
    )


def _forward_pipeline(
    session, context, store, events, target_state,
    source_worker, target_worker, reason, metadata=None,
):
    pipeline = context.runtime_pipeline
    task = context.runtime_task
    if pipeline is None or task is None:
        return
    pipeline.transition(target_state, target_worker, reason, metadata)
    handoff = task.handoff(
        target_worker, reason,
        {"pipeline_state": pipeline.state.value, **dict(metadata or {})},
    )
    _sync_runtime_task(session, context, store)
    _sync_runtime_pipeline(session, context, store)
    _emit_pipeline_event(
        events, "TaskForwarded", context, source_worker, reason, handoff,
    )


def _emit_pipeline_event(events, name, context, worker_id, detail, payload=None):
    task = context.runtime_task
    pipeline = context.runtime_pipeline
    if task is None or pipeline is None:
        return
    events.emit(
        name, worker_id, detail,
        task_id=task.id,
        state=pipeline.state.value,
        payload={
            "owner": task.owner,
            "pipeline_state": pipeline.state.value,
            **dict(payload or {}),
        },
    )


def _emit_orchestration_decision(events, context, decision):
    task = context.runtime_task
    if task is None:
        return
    events.emit(
        "ORCHESTRATION_DECISION", decision.source_worker, decision.reason,
        task_id=task.id,
        state=decision.target_state.value,
        payload={
            "action": decision.action.value,
            "source_worker": decision.source_worker,
            "target_worker": decision.target_worker,
            "target_state": decision.target_state.value,
            **dict(decision.metadata),
        },
    )


def _failed_role_result(request: RoleExecutionRequest, error: str) -> RoleExecutionResult:
    now = _now()
    return RoleExecutionResult(
        task_id=request.task_id, role=request.role, worker_id=request.worker_id,
        state=RoleExecutionState.FAILED, output={}, evidence_references=[],
        handoff_target="", started_at=now, completed_at=now,
        summary=f"{request.role.value} role execution failed", error=error,
    )


def _set_role_waiting_approval(result: RoleExecutionResult) -> None:
    result.state = RoleExecutionState.WAITING_APPROVAL
    result.handoff_target = "approval_guardian"
    result.summary = "Developer role is waiting for controlled-action approval"
    result.history.append({
        "state": result.state.value,
        "timestamp": _now(),
        "handoff_target": result.handoff_target,
        "error": "",
    })


def _role_evidence_references(result, evidence):
    references = list(result.evidence_references)
    for key in (
        "verified_changed_files", "verified_test_executions", "execution_evidence",
    ):
        if evidence.get(key):
            references.append(f"runtime_evidence:{key}")
    return list(dict.fromkeys(references))


def _emit_role_request_event(events, name, request):
    events.emit(
        name, request.worker_id, f"{request.role.value} role execution started",
        task_id=request.task_id, state=request.task_state,
        payload={
            "role": request.role.value,
            "revision": request.revision,
            "pipeline_state": request.pipeline_state,
        },
    )


def _emit_role_event(events, name, result):
    events.emit(
        name, result.worker_id, result.summary,
        task_id=result.task_id, state=result.state.value,
        payload={
            "role": result.role.value,
            "handoff_target": result.handoff_target,
            "evidence_references": list(result.evidence_references),
            "error": result.error,
        },
    )


def _handoff_validation_metadata(result):
    return {
        "role_result_state": result.state.value,
        "worker_id": result.worker_id,
        "evidence_references": list(result.evidence_references),
        "has_error": bool(result.error),
    }


def _latest_role_result_reference(task):
    if task is None or not task.role_executions:
        return ""
    return f"runtime_task:role_executions[{len(task.role_executions) - 1}]"


def _qa_revision_reason(output):
    issues = output.get("issues", [])
    if isinstance(issues, list):
        reasons = [item for item in issues if isinstance(item, str) and item]
        if reasons:
            return "; ".join(reasons[:10])
    results = output.get("claimed_test_results", {})
    recommendation = results.get("recommendation") if isinstance(results, dict) else None
    return str(recommendation or "QA requested development revision")


def _emit_result_handoff_event(events, name, handoff):
    events.emit(
        name, handoff.producer_role.worker_id,
        f"{handoff.producer_role.value} result handed to {handoff.consumer_role.value}",
        task_id=handoff.task_id, state="result_handoff",
        payload={
            "handoff_id": handoff.handoff_id,
            "producer_role": handoff.producer_role.value,
            "consumer_role": handoff.consumer_role.value,
            "result_reference": handoff.result_reference,
            "validation_metadata": dict(handoff.validation_metadata),
            "revision_count": handoff.revision_count,
            "revision_reason": handoff.revision_reason,
        },
    )


def _emit_role_handoff_delivery(events, request):
    events.emit(
        "RESULT_HANDOFF_DELIVERED", request.worker_id,
        f"result handoff delivered to {request.role.value}",
        task_id=request.task_id, state=request.task_state,
        payload={
            "handoff_id": request.input_handoff_id,
            "consumer_role": request.role.value,
            "result_reference": request.input_result_reference,
        },
    )


def _emit_qa_decision_event(events, name, decision):
    if not decision:
        return
    events.emit(
        name, "qa_worker", decision["reason"],
        task_id=decision["task_id"], state=decision["outcome"],
        payload={
            "revision_count": decision["revision_count"],
            "max_revisions": decision["max_revisions"],
            "qa_result_reference": decision["qa_result_reference"],
        },
    )


def _task_event_fields(task):
    if task is None:
        return {}
    return {
        "task_id": task.id,
        "state": task.state.value,
        "payload": {"priority": task.priority, "dependencies": list(task.dependencies)},
    }


def _current_hash(root, relative_path):
    candidate = Path(relative_path)
    if candidate.is_absolute():
        return None
    target = (Path(root) / candidate).resolve()
    try:
        target.relative_to(Path(root).resolve())
    except ValueError:
        return None
    return sha256(target.read_bytes()).hexdigest() if target.is_file() else None


def _merge_execution_evidence(session, evidence):
    session.execution_verification["verified_changed_files"].extend(evidence.get("verified_changed_files", []))
    session.execution_verification["verified_test_executions"].extend(evidence.get("verified_test_executions", []))
    session.execution_verification.setdefault("evidence", []).extend(evidence.get("execution_evidence", []))


def _write_partial_artifacts(store, context, session):
    artifacts = {
        "plan.json": context["outputs"].get("planning_worker", {}),
        "implementation.json": context["outputs"].get("development_worker", {}),
        "qa_report.json": context["outputs"].get("qa_worker", {}),
    }
    for name, data in artifacts.items():
        path = store.json(name, data)
        if not any(item["type"] == name for item in session.artifacts):
            session.artifacts.append({"type": name, "path": str(path)})


def _approval_summary(record):
    return {
        "approval_request_id": record["approval_request_id"],
        "execution_request_id": record["execution_request_id"],
        "action_type": record["action_type"],
        "target": record["target"],
        "action_fingerprint": record["action_fingerprint"],
        "policy_classification": record["guardian_policy_classification"],
        "guardian_rule_id": record["guardian_rule_id"],
        "guardian_reason": record["guardian_reason"],
        "status": record["status"],
    }


def _truthful_report(session, context):
    plan = context["outputs"].get("planning_worker", {})
    implementation = context["outputs"].get("development_worker", {})
    qa = context["outputs"].get("qa_worker", {})
    documentation = context["outputs"].get("documentation_worker", {})
    findings = ", ".join(sorted({item["classification"] for item in session.truth_contract_findings})) or "None"
    return (
        "# Real Worker Runtime Report\n\n"
        f"Session: `{session.session_id}`\n\nOrchestration status: **{session.status.upper()}**\n\n"
        f"Execution verification: **{session.execution_verification['status']}**\n\nRequest: {session.request}\n\n"
        "## Plan\n\n" + "\n".join(f"- {item}" for item in plan.get("tasks", [])) + "\n\n"
        "## Provider Development Claims\n\n"
        f"{implementation.get('implementation_summary', '')}\n\nProposed files: {implementation.get('proposed_files', [])}\n\n"
        f"Runtime-verified changed files: {implementation.get('verified_changed_files', [])}\n\n"
        "## Provider QA Claims\n\n"
        f"Claimed test commands: {qa.get('claimed_test_commands', [])}\n\nClaimed results: {qa.get('claimed_test_results', {})}\n\n"
        f"Runtime-verified test executions: {qa.get('verified_test_executions', [])}\n\n"
        "## Provider Documentation Claim (Not Runtime Verification)\n\n"
        f"{documentation.get('user_summary', '')}\n\n## Truth Contract Findings\n\n{findings}\n\n"
        f"Workers: {len(session.workers)}\nMessages: {len(session.messages)}\nRunner: `{session.runner_run_id}`\n"
    )


def _now():
    return datetime.now().astimezone().isoformat(timespec="seconds")
