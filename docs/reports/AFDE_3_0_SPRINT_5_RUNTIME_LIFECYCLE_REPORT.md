# AFDE-3.0 Sprint 5 Runtime Lifecycle Report

## Objective and baseline

Sprint 5 completes the AFDE-3.0 multi-agent runtime lifecycle with
deterministic finalization, structured failure propagation, ordered transition
history, approval-wait evidence, and a final execution summary. Work started
from verified `origin/develop` commit
`7546487699b79495fd4f8ad1b39bd06dd638e895`; local and remote `main` remained
at `9b3637dea7e71868e05d8a66b500787f3f70b623`.

## Existing architecture reused

- Existing lifecycle state owner: `RuntimeTask` and its established
  `WorkerState` history.
- Existing role-state owner: append-only typed role results in
  `RuntimeTask.role_executions`, coordinated by `RuntimeOrchestrator`.
- Existing handoff storage: `ResultHandoffLedger` backed by `RuntimeTask` and
  mirrored through `WorkerContext` for approval continuation.
- Existing revision-state owner: `RuntimeTask.orchestration_metadata`, with the
  bound enforced by `RuntimeOrchestrator`.
- Existing approval boundary: AFDE-2.7 `RuntimeApprovalStore`, Approval
  Guardian, and `ControlledExecutor`; no new classifier or approval event is
  introduced.
- Existing exception behavior: provider/worker errors become failed role
  results and invalid typed results fail closed.
- Sprint 5 extension points: additive fields and methods on `RuntimeTask`,
  additive role-failure metadata, result persistence in `RuntimeOrchestrator`,
  and finalization hooks at existing runtime success, failure, and approval
  boundaries.

No competing task, context, pipeline, orchestrator, provider, audit, or state
machine owner was created.

## Runtime terminal and role lifecycle semantics

The run-level lifecycle reuses `RuntimeState` and supports `created`, `pending`
(legacy construction compatibility), `queued`, `running`, `waiting_approval`,
`revising`, `completed`, `failed`, `blocked`, and `cancelled`. Only validated transitions are appended;
duplicate transitions and terminal restart attempts raise the existing
`InvalidTaskTransition` failure. Sequence numbers are monotonically assigned
by the authoritative task.

Planner, Developer, QA, and Documentation attempts persist role, attempt,
revision index, start/completion timestamps, final attempt status, result
reference, and failure reference. Initial and revised role results remain in
their original append-only stores.

`completed` is assigned only after Documentation and runtime finalization
succeed. Required-role failure, invalid result, unexpected normalized runtime
exception, Documentation failure, or QA revision exhaustion produces `failed`.
Approval pause produces `waiting_approval`; rejection retains the existing
session `blocked` meaning. No subsequent work runs from a paused or terminal
lifecycle.

The implemented transition policy is:

- `created -> queued | cancelled`
- `pending -> queued | running | waiting_approval | blocked | failed | cancelled`
- `queued -> running | blocked | cancelled`
- `running -> waiting_approval | revising | completed | failed | blocked | cancelled`
- `waiting_approval -> running | failed | blocked | cancelled`
- `revising -> running | failed | blocked | cancelled`
- `completed`, `failed`, `blocked`, and `cancelled` are terminal in the current
  runtime policy.

## Append-only transitions and failure propagation

Each transition records sequence, timestamp, task identity, from/to status,
stage, role, attempt, revision index, stable reason code, bounded safe message,
and safe metadata. The same transitions emit
`RUNTIME_LIFECYCLE_TRANSITION` on the existing event stream.

Normalized failures expose `error_type`, `error_code`, `message`, `stage`,
`actor`, `retryable`, `cause`, and `metadata`, plus attempt, revision index,
and timestamp. The legacy `failure_code`, `role`, `exception_type`,
`safe_message`, and `cause_reference` keys remain as compatibility aliases.
Stable codes include `RUNTIME_ILLEGAL_TRANSITION`, `RUNTIME_WORKER_FAILURE`,
`RUNTIME_ROLE_EXECUTION_FAILURE`, `RUNTIME_PIPELINE_FAILURE`,
`RUNTIME_APPROVAL_REJECTED`, `RUNTIME_APPROVAL_REQUIRED`,
`RUNTIME_REVISION_LIMIT_EXCEEDED`, `RUNTIME_CONTROLLED_EXECUTION_BLOCKED`, and
`RUNTIME_INVALID_RESULT_HANDOFF`. Credential-like fragments are redacted. Planner failure prevents
all later roles; Developer failure prevents QA and Documentation; QA execution
failure remains different from a revision request; Documentation failure
prevents completed finalization.

## QA revision exhaustion

Sprint 2's persisted maximum remains unchanged. Each revision keeps its role
results, handoffs, QA decision, reason, and count. Exhaustion adds stable
`qa_revision_exhausted` failure evidence, finalizes the runtime as failed, and
does not invoke Documentation or create another revision handoff.

## Approval waiting behavior

An approval-required controlled action still executes no protected operation,
persists the exact AFDE-2.7 continuation, moves the lifecycle to
`waiting_approval`, appends a transition, and derives a paused summary. Exact
approval resumes the same task through the existing continuation. Rejection
preserves the existing blocked session behavior. Guardian classification,
binding, consumption, and audit semantics are unchanged.

## Final execution summary

`RuntimeSession.execution_summary` mirrors the authoritative
`RuntimeTask.execution_summary` for completed, failed, blocked, and paused
outcomes. It is derived from persisted state and contains task ID, status,
timestamps, current stage, latest role statuses, revision bound/count, result
references, transition count, safe failure or approval details, and the
Documentation result reference only on successful completion.

## Backward compatibility and security

All new dataclass fields are defaulted and serialization readers accept older
snapshots. RuntimePipeline, RuntimeOrchestrator, RuntimeTask, WorkerContext,
typed role contracts, RoleExecutor, result handoff, QA revision, providers,
CLI, approval/Guardian, controlled execution, and Execution Truth behavior
remain additive and compatible. No live API call, credential, authorization
header, release, deployment, or protected-branch modification is part of this
Sprint.

## Tests and validation

- Pre-implementation baseline: `405 passed, 1 skipped`.
- Sprint 5 focused tests: `20 passed`.
- Compatibility matrix: `233 passed` across RuntimePipeline,
  RuntimeOrchestrator, RoleExecutor, handoff/revision, approval, Guardian,
  controlled execution, Execution Truth, and provider behavior.
- Full pytest: `428 passed, 1 skipped`.
- Compile validation: PASS for `approval_guardian`, `afde`,
  `real_worker_runtime`, `sprint_auto_runner`, and `tests`.
- Exact 14-file scope secret scan: PASS; no high-confidence credential
  patterns. Broad marker hits were reviewed as redaction logic, synthetic test
  data, identifiers, or prior documentation.
- `git diff --check`: PASS.

## Known limitations

Durable approval resume across arbitrary process recovery, crash-safe storage,
SQLite persistence, concurrent locking, distributed workers, tamper-evident
audit chains, cancellation propagation, per-role timeout policy, and role or
provider retry policy remain explicitly out of scope.

## Rollback plan

Revert the Sprint 5 feature commit(s) from `develop` if later approved for
merge. Existing fields and artifacts remain readable because Sprint 5 removes
no prior schema or public interface. Preserve runtime evidence before any
rollback; do not rewrite branch history.
