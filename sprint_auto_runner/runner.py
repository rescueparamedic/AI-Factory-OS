from __future__ import annotations

from datetime import datetime
from hashlib import sha256
import json
from pathlib import Path
import re
import subprocess
from typing import Any
from uuid import uuid4

from approval_guardian import ApprovalDecision, ApprovalGuardian
from approval_guardian.audit import command_fingerprint, redact_command

from .approval_bridge import ApprovalBridge
from .audit import SprintAuditLogger
from .errors import SprintResumeError, SprintRunnerError
from .loader import SprintDefinitionLoader
from .models import RunStatus, SprintDefinition, SprintRun, SprintStep, StepResult, StepStatus
from .state_store import SprintStateStore
from .step_executor import StepExecutor


TERMINAL_STATUSES = {
    RunStatus.BLOCKED.value,
    RunStatus.COMPLETED.value,
    RunStatus.CANCELLED.value,
}


class SprintAutoRunner:
    def __init__(
        self,
        repository_root: str | Path = ".",
        guardian: ApprovalGuardian | None = None,
        executor: StepExecutor | None = None,
    ) -> None:
        self.repository_root = Path(repository_root).resolve()
        self.loader = SprintDefinitionLoader()
        self.store = SprintStateStore(self.repository_root)
        self.audit = SprintAuditLogger(self.repository_root)
        self.bridge = ApprovalBridge(guardian or ApprovalGuardian(self.repository_root))
        self.executor = executor or StepExecutor()

    def validate(self, definition_path: str | Path) -> SprintDefinition:
        return self.loader.load(definition_path)

    def dry_run(self, definition_path: str | Path) -> dict[str, Any]:
        definition = self.loader.load(definition_path)
        branch = self._git("branch", "--show-current")
        results = []
        for step in definition.steps:
            cwd = self._step_cwd(step)
            decision = self.bridge.evaluate(step, str(cwd), branch, "DRY-RUN")
            results.append(
                {
                    "step_id": step.step_id,
                    "name": step.name,
                    "decision": decision.decision.value,
                    "rule_id": decision.rule_id,
                    "reason": decision.reason,
                    "normalized_command": decision.normalized_command,
                }
            )
        return {
            "mode": "dry_run",
            "sprint_id": definition.sprint_id,
            "definition_fingerprint": definition.fingerprint,
            "branch": branch,
            "steps": results,
        }

    def start(self, definition_path: str | Path) -> SprintRun:
        definition = self.loader.load(definition_path)
        now = _now()
        run = SprintRun(
            run_id=f"SPR-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{uuid4().hex[:8]}",
            sprint_id=definition.sprint_id,
            branch=self._git("branch", "--show-current"),
            status=RunStatus.CREATED.value,
            current_step_index=0,
            started_at=now,
            updated_at=now,
            completed_at=None,
            last_error="",
            resume_token=uuid4().hex,
            definition_path=definition.source_path,
            definition_fingerprint=definition.fingerprint,
            head_sha=self._git("rev-parse", "HEAD"),
            step_results=[StepResult(step_id=step.step_id) for step in definition.steps],
        )
        self.store.save(run)
        if not self._try_record(run, "SPRINT_RUN_CREATED"):
            first = definition.steps[0]
            result = run.step_results[0]
            result.normalized_command = first.command
            result.command_fingerprint = command_fingerprint(first.command)
            result.context_fingerprint = self._context_fingerprint(
                first, str(self._step_cwd(first)), run.branch, first.command
            )
            return self._wait_for_audit(run, first, result)
        return self._continue(run, definition)

    def status(self, run_id: str) -> SprintRun:
        return self.store.load(run_id)

    def resume(self, run_id: str, approval: dict[str, str]) -> SprintRun:
        run = self.store.load(run_id)
        if run.status != RunStatus.WAITING_APPROVAL.value or not run.pending_approval:
            raise SprintResumeError("run is not waiting for approval")
        definition = self.loader.load(run.definition_path)
        self._verify_definition(run, definition)
        step = definition.steps[run.current_step_index]
        if approval.get("step_id") != step.step_id or approval.get("decision") != "approved":
            raise SprintResumeError("approval must explicitly approve the currently waiting step")
        if not approval.get("approved_by"):
            raise SprintResumeError("approved_by is required")

        cwd = self._step_cwd(step)
        current_branch = self._git("branch", "--show-current")
        reevaluated = self.bridge.evaluate(step, str(cwd), current_branch, run.run_id)
        current_context = self._context_fingerprint(step, str(cwd), current_branch, reevaluated.normalized_command)
        pending = run.pending_approval
        if pending.get("step_id") != step.step_id:
            raise SprintResumeError("pending approval step does not match current step")
        if pending.get("command_fingerprint") != command_fingerprint(reevaluated.normalized_command):
            raise SprintResumeError("command changed after approval was requested")
        if pending.get("context_fingerprint") != current_context:
            raise SprintResumeError("execution context changed; previous approval is invalid")
        if reevaluated.decision is ApprovalDecision.DENY:
            result = run.step_results[run.current_step_index]
            result.status = StepStatus.DENIED.value
            result.decision = reevaluated.decision.value
            result.rule_id = reevaluated.rule_id
            result.reason = reevaluated.reason
            run.status = RunStatus.BLOCKED.value
            run.last_error = reevaluated.reason
            run.pending_approval = None
            self._save(run)
            self._record(run, "SPRINT_STEP_DENIED", step=step, approval=reevaluated)
            return run
        if reevaluated.decision is ApprovalDecision.ASK_USER and reevaluated.rule_id != pending.get("rule_id"):
            raise SprintResumeError("approval rule changed; a new approval is required")

        self._record(
            run,
            "SPRINT_RUN_RESUMED",
            step=step,
            approval=reevaluated,
            actor=approval["approved_by"],
            result=approval.get("reason", "approved by user"),
        )
        run.pending_approval = None
        run.status = RunStatus.RUNNING.value
        if not self._execute(run, definition, step, reevaluated):
            return run
        return self._continue(run, definition)

    def cancel(self, run_id: str, actor: str = "user") -> SprintRun:
        run = self.store.load(run_id)
        if run.status in TERMINAL_STATUSES:
            raise SprintRunnerError(f"cannot cancel run in terminal status: {run.status}")
        run.status = RunStatus.CANCELLED.value
        run.completed_at = _now()
        run.pending_approval = None
        self._save(run)
        self._record(run, "SPRINT_RUN_CANCELLED", actor=actor)
        return run

    def _continue(self, run: SprintRun, definition: SprintDefinition) -> SprintRun:
        self._verify_definition(run, definition)
        run.status = RunStatus.RUNNING.value
        self._save(run)
        while run.current_step_index < len(definition.steps):
            index = run.current_step_index
            step = definition.steps[index]
            result = run.step_results[index]
            if result.status == StepStatus.PASSED.value:
                run.current_step_index += 1
                continue

            cwd = self._step_cwd(step)
            result.status = StepStatus.EVALUATING.value
            self._save(run)
            approval = self.bridge.evaluate(step, str(cwd), run.branch, run.run_id)
            result.decision = approval.decision.value
            result.rule_id = approval.rule_id
            result.reason = approval.reason
            result.normalized_command = approval.normalized_command
            result.command_fingerprint = command_fingerprint(approval.normalized_command)
            result.context_fingerprint = self._context_fingerprint(step, str(cwd), run.branch, approval.normalized_command)

            if not self._try_record(run, "SPRINT_STEP_EVALUATED", step=step, approval=approval):
                return self._wait_for_audit(run, step, result)
            if approval.decision is ApprovalDecision.DENY:
                result.status = StepStatus.DENIED.value
                run.status = RunStatus.BLOCKED.value
                run.last_error = approval.reason
                self._save(run)
                self._record(run, "SPRINT_STEP_DENIED", step=step, approval=approval)
                return run
            if approval.decision is ApprovalDecision.ASK_USER:
                result.status = StepStatus.WAITING_APPROVAL.value
                run.status = RunStatus.WAITING_APPROVAL.value
                run.pending_approval = {
                    "step_id": step.step_id,
                    "rule_id": approval.rule_id,
                    "reason": approval.reason,
                    "redacted_command": redact_command(approval.normalized_command),
                    "command_fingerprint": result.command_fingerprint,
                    "context_fingerprint": result.context_fingerprint,
                }
                self._save(run)
                self._record(run, "SPRINT_STEP_WAITING_APPROVAL", step=step, approval=approval)
                return run

            result.status = StepStatus.AUTO_APPROVED.value
            self._save(run)
            if not self._try_record(run, "SPRINT_STEP_AUTO_APPROVED", step=step, approval=approval):
                return self._wait_for_audit(run, step, result)
            if not self._execute(run, definition, step, approval):
                return run
            if run.status == RunStatus.FAILED.value:
                return run

        run.status = RunStatus.COMPLETED.value
        run.completed_at = _now()
        self._save(run)
        self._record(run, "SPRINT_RUN_COMPLETED")
        return run

    def _execute(self, run: SprintRun, definition: SprintDefinition, step: SprintStep, approval: Any) -> bool:
        index = run.current_step_index
        result = run.step_results[index]
        result.status = StepStatus.RUNNING.value
        self._save(run)
        if not self._try_record(run, "SPRINT_STEP_STARTED", step=step, approval=approval):
            self._wait_for_audit(run, step, result)
            return False
        execution = self.executor.execute(step, str(self._step_cwd(step)))
        result.exit_code = execution.exit_code
        result.stdout = _redact_output(execution.stdout)
        result.stderr = _redact_output(execution.stderr)
        result.duration_ms = execution.duration_ms
        result.started_at = execution.started_at
        result.completed_at = execution.completed_at
        passed = execution.exit_code in step.expected_exit_codes
        result.status = StepStatus.PASSED.value if passed else StepStatus.FAILED.value
        event = "SPRINT_STEP_COMPLETED" if passed else "SPRINT_STEP_FAILED"
        audit_saved = self._try_record(
            run,
            event,
            step=step,
            approval=approval,
            exit_code=execution.exit_code,
            duration_ms=execution.duration_ms,
            result=result.status,
        )
        if not audit_saved:
            run.status = RunStatus.FAILED.value
            run.last_error = "Step executed but completion audit could not be recorded; automatic retry is disabled."
            run.completed_at = _now()
            self._save(run)
            return False
        if passed or step.continue_on_failure:
            run.current_step_index += 1
            run.status = RunStatus.RUNNING.value
        else:
            run.status = RunStatus.FAILED.value
            run.last_error = f"step {step.step_id} exited with {execution.exit_code}"
            run.completed_at = _now()
        self._save(run)
        return True

    def _wait_for_audit(self, run: SprintRun, step: SprintStep, result: StepResult) -> SprintRun:
        result.status = StepStatus.WAITING_APPROVAL.value
        result.decision = ApprovalDecision.ASK_USER.value
        result.rule_id = "AGV2-A999"
        result.reason = "Runner audit could not be recorded; execution stopped fail-closed."
        run.status = RunStatus.WAITING_APPROVAL.value
        run.last_error = result.reason
        run.pending_approval = {
            "step_id": step.step_id,
            "rule_id": result.rule_id,
            "reason": result.reason,
            "redacted_command": redact_command(result.normalized_command),
            "command_fingerprint": result.command_fingerprint,
            "context_fingerprint": result.context_fingerprint,
        }
        self._save(run)
        return run

    def _step_cwd(self, step: SprintStep) -> Path:
        path = Path(step.cwd)
        return (path if path.is_absolute() else self.repository_root / path).resolve()

    def _verify_definition(self, run: SprintRun, definition: SprintDefinition) -> None:
        if definition.fingerprint != run.definition_fingerprint:
            raise SprintResumeError("sprint definition changed after the run was created")
        if len(definition.steps) != len(run.step_results):
            raise SprintResumeError("run state does not match sprint definition")

    def _context_fingerprint(self, step: SprintStep, cwd: str, branch: str, normalized: str) -> str:
        payload = {
            "branch": branch,
            "head": self._git("rev-parse", "HEAD"),
            "cwd": cwd,
            "environment": step.environment,
            "command": normalized,
        }
        return sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()

    def _git(self, *arguments: str) -> str:
        result = subprocess.run(
            ["git", *arguments],
            cwd=self.repository_root,
            capture_output=True,
            text=True,
            timeout=5,
            shell=False,
        )
        return result.stdout.strip() if result.returncode == 0 else ""

    def _save(self, run: SprintRun) -> None:
        run.updated_at = _now()
        self.store.save(run)

    def _try_record(self, run: SprintRun, event: str, **kwargs: Any) -> bool:
        try:
            self._record(run, event, **kwargs)
            return True
        except OSError:
            return False

    def _record(
        self,
        run: SprintRun,
        event: str,
        step: SprintStep | None = None,
        approval: Any | None = None,
        **fields: Any,
    ) -> None:
        self.audit.record(
            run.run_id,
            event,
            sprint_id=run.sprint_id,
            step_id=step.step_id if step else "",
            decision=getattr(getattr(approval, "decision", None), "value", ""),
            rule_id=getattr(approval, "rule_id", ""),
            reason=getattr(approval, "reason", ""),
            command=step.command if step else "",
            cwd=str(self._step_cwd(step)) if step else str(self.repository_root),
            branch=run.branch,
            environment=step.environment if step else "",
            **fields,
        )


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _redact_output(value: str) -> str:
    redacted = redact_command(value)
    redacted = re.sub(
        r"-----BEGIN [^-]*PRIVATE KEY-----.*?-----END [^-]*PRIVATE KEY-----",
        "[REDACTED PRIVATE KEY]",
        redacted,
        flags=re.DOTALL | re.IGNORECASE,
    )
    return redacted
