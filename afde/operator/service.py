"""Thin operator application service over existing AFDE components."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from approval_guardian.audit import redact_command
from real_worker_runtime import RealWorkerRuntime, RuntimeDashboard, RuntimeHistoryStore
from real_worker_runtime.errors import (
    ProviderConfigurationError, RuntimeErrorBase, RuntimeSessionError,
)

from .errors import (
    OperatorExecutionFailed, OperatorInputError, OperatorNotFound,
    OperatorPreflightBlocked,
)
from .models import OperatorResult, PreflightResult
from .preflight import OperatorPreflight


MOCK_WORKFLOW_MARKER = "[approval-resume-mvp]"


class OperatorService:
    def __init__(self, workspace: str | Path = ".") -> None:
        self.workspace = Path(workspace).expanduser().resolve()
        self.runtime = RealWorkerRuntime(self.workspace)

    def preflight(
        self, provider: str = "mock", allow_live_api: bool = False,
    ) -> PreflightResult:
        return OperatorPreflight(
            self.workspace, provider, allow_live_api,
        ).run()

    def run(
        self, request: str, provider: str = "mock", *,
        allow_live_api: bool = False, model: str | None = None,
    ) -> OperatorResult:
        request = self._request(request)
        provider = str(provider or "mock").lower()
        readiness = self.preflight(provider, allow_live_api)
        if readiness.blocking:
            raise OperatorPreflightBlocked(
                "operator preflight is blocked: " + ", ".join(
                    item.name for item in readiness.checks if item.status == "FAIL"
                )
            )
        runtime_request = (
            f"{MOCK_WORKFLOW_MARKER} {request}"
            if provider == "mock" and MOCK_WORKFLOW_MARKER not in request else request
        )
        try:
            session = self.runtime.run(
                runtime_request, provider=provider, live=False,
                allow_live_api=allow_live_api, model=model,
                enable_controlled_execution=True,
            )
        except ProviderConfigurationError as exc:
            raise OperatorPreflightBlocked(str(exc)) from exc
        except RuntimeErrorBase as exc:
            raise OperatorExecutionFailed(str(exc)) from exc
        return self._project(session.to_dict(), request_override=request)

    def status(self, session_id: str) -> OperatorResult:
        return self._project(self._session(session_id))

    def approve(self, session_id: str, approval_id: str) -> OperatorResult:
        session = self._session(session_id)
        self._require_approval(session, approval_id)
        try:
            self.runtime.approval_grant(approval_id, approved_by="operator")
        except RuntimeSessionError as exc:
            raise self._runtime_error(exc) from exc
        return self._project(self._session(session_id))

    def reject(
        self, session_id: str, approval_id: str, reason: str,
    ) -> OperatorResult:
        reason = self._reason(reason)
        session = self._session(session_id)
        self._require_approval(session, approval_id)
        try:
            self.runtime.approval_reject(approval_id, reason=reason)
        except RuntimeSessionError as exc:
            raise self._runtime_error(exc) from exc
        return self._project(self._session(session_id))

    def resume(self, session_id: str) -> OperatorResult:
        session = self._session(session_id)
        if session.get("status") in {"completed", "failed", "blocked", "cancelled"}:
            raise OperatorInputError("terminal sessions cannot be resumed")
        pending = session.get("pending_approval") or {}
        approval_id = pending.get("approval_request_id")
        if not approval_id:
            raise OperatorInputError("session has no approval to resume")
        if pending.get("status") != "APPROVED":
            raise OperatorInputError(
                "approval must be granted with operator-approve before resume"
            )
        try:
            resumed = self.runtime.approval_resume(approval_id)
        except RuntimeSessionError as exc:
            raise self._runtime_error(exc) from exc
        return self._project(resumed.to_dict())

    def _session(self, session_id: str) -> dict[str, Any]:
        if not isinstance(session_id, str) or not session_id.startswith("RWS-"):
            raise OperatorNotFound("runtime session not found")
        try:
            value = self.runtime.status(session_id)
        except (FileNotFoundError, OSError, ValueError) as exc:
            raise OperatorNotFound("runtime session not found") from exc
        if not isinstance(value, dict):
            raise OperatorNotFound("runtime session not found")
        return value

    @staticmethod
    def _require_approval(session: Mapping[str, Any], approval_id: str) -> None:
        pending = session.get("pending_approval") or {}
        if pending.get("approval_request_id") != approval_id:
            raise OperatorNotFound("approval not found for session")

    def _project(
        self, session: Mapping[str, Any], request_override: str | None = None,
    ) -> OperatorResult:
        session_id = str(session.get("session_id") or "")
        internal = str(session.get("status") or "failed").lower()
        pending = session.get("pending_approval") or {}
        status = _operator_status(internal, pending)
        approval_id = pending.get("approval_request_id")
        next_action = _next_action(
            status, session_id, approval_id, pending, self.workspace,
        )
        request = redact_command(
            request_override if request_override is not None else
            str(session.get("request") or "").replace(MOCK_WORKFLOW_MARKER, "").strip()
        )
        evidence = _evidence(session)
        evidence.extend(self._read_only_evidence(session_id))
        return OperatorResult(
            status=status,
            session_id=session_id,
            request=request,
            provider=str(session.get("provider") or "unknown"),
            approval_id=approval_id,
            summary=_summary(status, session),
            next_action=next_action,
            evidence=tuple(evidence),
            dashboard_hint=(
                "python -m afde.cli runtime-dashboard "
                f"--session-id {session_id} {_workspace_flag(self.workspace)}"
            ),
            history_hint=(
                "python -m afde.cli runtime-history "
                f"--session-id {session_id} {_workspace_flag(self.workspace)}"
            ),
        )

    def _read_only_evidence(self, session_id: str) -> list[dict[str, str]]:
        """Project existing history/dashboard evidence without persistence."""
        values: list[dict[str, str]] = []
        try:
            history = RuntimeHistoryStore(self.workspace).summary(session_id)
            values.append({
                "type": "runtime_history",
                "reference": f"{history['event_count']} persisted events",
            })
        except (FileNotFoundError, OSError, ValueError):
            pass
        try:
            dashboard = RuntimeDashboard(self.workspace).snapshot(session_id)
            values.append({
                "type": "dashboard_projection",
                "reference": str(dashboard.get("runtime_status", "Unavailable")),
            })
        except (FileNotFoundError, OSError, ValueError):
            pass
        return values

    @staticmethod
    def _request(value: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise OperatorInputError("request must not be empty")
        result = value.strip()
        if len(result) > 4000:
            raise OperatorInputError("request must not exceed 4000 characters")
        return redact_command(result)

    @staticmethod
    def _reason(value: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise OperatorInputError("rejection reason must not be empty")
        return redact_command(value.strip())[:500]

    @staticmethod
    def _runtime_error(error: RuntimeSessionError):
        if "unknown approval" in str(error).lower():
            return OperatorNotFound("approval not found")
        return OperatorExecutionFailed(str(error))


def _operator_status(internal: str, pending: Mapping[str, Any]) -> str:
    if internal in {"waiting", "waiting_approval"}:
        return "waiting_approval"
    if internal in {"blocked", "cancelled"}:
        return "blocked"
    if internal == "completed":
        return "completed"
    if internal == "failed":
        return "failed"
    if pending and pending.get("status") in {"PENDING", "APPROVED"}:
        return "waiting_approval"
    return "running"


def _next_action(
    status: str, session_id: str, approval_id: str | None,
    pending: Mapping[str, Any], workspace: Path,
) -> str:
    workspace_flag = _workspace_flag(workspace)
    if status == "waiting_approval" and approval_id:
        if pending.get("status") == "APPROVED":
            return (
                "python -m afde.cli operator-resume "
                f"--session-id {session_id} {workspace_flag}"
            )
        return (
            "python -m afde.cli operator-approve "
            f"--session-id {session_id} --approval-id {approval_id} "
            f"{workspace_flag}"
        )
    if status == "blocked":
        return (
            "python -m afde.cli operator-status "
            f"--session-id {session_id} {workspace_flag}"
        )
    return ""


def _workspace_flag(workspace: Path) -> str:
    return '--workspace "{}"'.format(str(workspace).replace('"', ''))


def _summary(status: str, session: Mapping[str, Any]) -> str:
    if status == "waiting_approval":
        return "Controlled file write is waiting for exact operator approval."
    if status == "completed":
        return "Operator workflow completed with persisted Runtime evidence."
    if status == "blocked":
        return "Operator workflow is blocked; inspect status and history evidence."
    if status == "failed":
        return redact_command(str(session.get("error") or "Operator workflow failed."))
    return redact_command(str(session.get("current_activity") or "Operator workflow is running."))


def _evidence(session: Mapping[str, Any]) -> list[dict[str, Any]]:
    values: list[dict[str, Any]] = []
    for artifact in session.get("artifacts", []):
        if isinstance(artifact, Mapping):
            values.append({
                "type": str(artifact.get("type") or "artifact"),
                "reference": str(artifact.get("path") or ""),
            })
    verification = session.get("execution_verification")
    if isinstance(verification, Mapping):
        for path in verification.get("verified_changed_files", []):
            values.append({"type": "verified_changed_file", "reference": str(path)})
        for item in verification.get("execution_evidence", []):
            if isinstance(item, Mapping) and item.get("request_id"):
                values.append({
                    "type": "execution_evidence",
                    "reference": str(item["request_id"]),
                })
    return values
