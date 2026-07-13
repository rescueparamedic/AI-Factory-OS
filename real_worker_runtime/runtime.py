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
from .errors import RuntimeSessionError
from .event_stream import EventStream
from .execution_truth import apply_execution_truth_contract, claimed_qa_failures
from .message_bus import MessageBus
from .models import RuntimeSession
from .provider_bridge import ProviderBridge
from .worker_context import WorkerContext
from .worker_registry import WorkerRegistry
from .workers import BaseWorker


class RealWorkerRuntime:
    def __init__(self, root="."):
        self.root = Path(root).resolve()

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
        artifact_store.json("session.json", session.to_dict())
        EventStream(artifact_store).emit("APPROVAL_REJECTED", record["source_worker"], approval_id)
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
        approved = approval_store.approve(approval_id)
        artifact_store = ArtifactStore(self.root, session.session_id)
        events = EventStream(artifact_store)
        events.emit("APPROVAL_GRANTED", request.source_worker, approval_id)
        observed = ControlledExecutor(self.root).execute_approved(request, approved)
        consumed = approval_store.consume(approved)
        events.emit("APPROVAL_CONSUMED", request.source_worker, approval_id)
        session.pending_approval = _approval_summary(consumed)
        evidence = {"verified_changed_files": [], "verified_test_executions": [], "execution_evidence": [observed]}
        if observed.get("status") == "SUCCEEDED" and observed.get("changed"):
            evidence["verified_changed_files"].append(observed["relative_path"])
        _merge_execution_evidence(session, evidence)
        context = WorkerContext.from_value(continuation["context"])
        self._replace_worker_truth_output(session, context, request.source_worker, evidence)
        if observed.get("status") != "SUCCEEDED":
            session.status = "failed"
            session.error = f"Approved execution failed safely: {observed.get('status')}"
            session.updated_at = _now()
            artifact_store.json("session.json", session.to_dict())
            events.emit("APPROVED_EXECUTION_FAILED", request.source_worker, observed.get("status", "failed"))
            return session
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
        store = ArtifactStore(self.root, session.session_id)
        events = EventStream(store)
        bus = MessageBus(store, session)
        dashboard = TerminalDashboard(settings.get("live", False))
        controlled = ControlledExecutor(self.root) if settings.get("enable_controlled_execution") else None
        definitions = WorkerRegistry().list()
        for index in range(start_index, len(definitions)):
            definition = definitions[index]
            for worker_id in session.workers:
                if session.workers[worker_id] == "queued":
                    session.workers[worker_id] = "waiting"
            session.workers[definition.worker_id] = "running"
            session.current_activity = f"{definition.role} is working..."
            session.progress = index * 20 + 10
            context.task_metadata["current_worker_id"] = definition.worker_id
            context.update_runtime_evidence(session.execution_verification)
            dashboard.render(session)
            events.emit("WORKER_STARTED", definition.worker_id)
            result = BaseWorker(definition, selected).execute(context)
            pending_request = None
            pending_observation = None
            if result.status == "completed":
                evidence, pending_request, pending_observation = _execute_proposals(
                    controlled, definition.worker_id, result.output, self.root
                )
                result.output, findings = apply_execution_truth_contract(definition.worker_id, result.output, evidence)
                session.truth_contract_findings.extend(findings)
                _merge_execution_evidence(session, evidence)
            session.results.append(asdict(result))
            context.record_worker_output(definition.worker_id, result.output)
            context.update_runtime_evidence(session.execution_verification)
            if result.status != "completed":
                session.status = "failed"
                session.error = result.error
                events.emit("PROVIDER_ERROR", definition.worker_id, result.error)
                break
            session.workers[definition.worker_id] = "completed"
            bus.publish(definition.worker_id, "runtime", "WORKER_OUTPUT", result.summary, result.output)
            metadata = result.output.get("_provider", {})
            events.emit("WORKER_COMPLETED", definition.worker_id, json.dumps(metadata) if metadata else "")
            if pending_request is not None:
                return self._pause_for_approval(
                    session, context, settings, revisions, index + 1,
                    pending_request, pending_observation or {}, store, events,
                )
            if definition.worker_id == "qa_worker" and claimed_qa_failures(result.output):
                if revisions >= settings.get("max_revisions", 1):
                    session.status = "failed"
                    session.error = "QA failed after maximum revisions"
                    break
                revisions += 1
                context["revision"] = revisions
                events.emit("REVISION_STARTED", "development_worker", f"revision {revisions}")
                if not self._run_revision(session, context, selected, controlled, bus, events):
                    break
            session.progress = (index + 1) * 20
            session.current_activity = result.summary
            dashboard.render(session)
        return self._finalize(session, context, settings, store, events, dashboard)

    def _run_revision(self, session, context, selected, controlled, bus, events):
        for retry_id in ("development_worker", "qa_worker"):
            retry_definition = next(item for item in WorkerRegistry().list() if item.worker_id == retry_id)
            retry = BaseWorker(retry_definition, selected).execute(context)
            if retry.status == "completed":
                evidence, pending, _ = _execute_proposals(controlled, retry_id, retry.output, self.root)
                if pending is not None:
                    session.status = "failed"
                    session.error = "Approval pause during revision is not supported"
                    return False
                retry.output, findings = apply_execution_truth_contract(retry_id, retry.output, evidence)
                session.truth_contract_findings.extend(findings)
                _merge_execution_evidence(session, evidence)
            session.results.append(asdict(retry))
            context.record_worker_output(retry_id, retry.output)
            context.update_runtime_evidence(session.execution_verification)
            bus.publish(retry_id, "runtime", "WORKER_OUTPUT", retry.summary, retry.output)
        if claimed_qa_failures(context["outputs"]["qa_worker"]):
            session.status = "failed"
            session.error = "QA revision failed"
            return False
        return True

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
