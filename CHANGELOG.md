# Sprint AFDE-2 Changelog

## AFDE-3.0 Sprint 5 Runtime Lifecycle Finalization

- Extended `RuntimeTask` with typed lifecycle status, append-only validated
  transitions, per-role attempt records, normalized failures, and a final
  execution summary.
- Added deterministic completed, failed, blocked, and waiting-approval
  finalization while retaining the existing worker and pipeline states.
- Distinguished QA rejection/revision exhaustion from QA execution failure and
  prevented Documentation or later roles after required-stage failure.
- Preserved approval continuation state and added paused/blocked summaries
  without moving or duplicating the AFDE-2.7 approval boundary.
- Added safe error normalization and lifecycle transition events without
  storing provider credentials, raw authorization data, or sensitive prompts.

## AFDE-3.0 Sprint 4 Multi-Agent Result Handoff and QA Revision Loop

- Added typed `AgentResultHandoff`, `QARevisionDecision`, handoff state, and QA
  outcome models.
- Added an append-only result handoff ledger synchronized between
  `RuntimeTask` and `WorkerContext`.
- Connected Planner output to Developer, Developer output to QA, QA revision
  output back to Developer, revised Developer output to QA, and accepted QA
  output to Documentation through explicit handoffs.
- Persisted QA revision reasons and counts without replacing the Sprint 2
  bounded revision authority.
- Added deterministic handoff creation/delivery, QA revision, revision resume,
  revision limit, and QA acceptance events.
- Preserved AFDE-2.7 approval pause/resume, Guardian, controlled execution,
  Execution Truth, provider contracts, and all prior role/pipeline events.

## AFDE-3.0 Sprint 3 Agent Role Execution

- Added typed `RuntimeRole`, `RoleExecutionRequest`, role-specific execution
  results, and role execution state/history models.
- Added one `RoleExecutor` boundary over the existing `BaseWorker` and
  `ProviderBridge`, supporting deterministic injected executors without a
  second provider registry.
- Extended `RuntimeOrchestrator` to build role requests, invoke the executor,
  validate task/role/worker identity and handoffs, and append normalized role
  results to `RuntimeTask`.
- Added role start, result, completion/failure, and handoff-request events to
  the existing runtime stream.
- Preserved approval pause/resume/reject, bounded QA revision, Guardian,
  controlled execution, Execution Truth, and provider contracts.
- Delayed terminal task completion until Documentation succeeds after QA pass,
  allowing Documentation failure to remain a truthful task failure.

## AFDE-3.0 Sprint 2 Multi-Agent Runtime Orchestrator

- Added an explicit `RuntimeOrchestrator` inside `real_worker_runtime` to own
  deterministic worker routing without replacing the existing runtime engine.
- Routed worker execution through the registered pipeline owners and recorded
  append-only orchestration decisions in `RuntimeTask` and the runtime event
  stream.
- Added a persisted, deterministic QA revision counter and safe explicit
  failure when the configured revision limit is exhausted.
- Extended revision execution to support multiple bounded Developer-to-QA
  cycles and approval pause/resume during a revised controlled action.
- Preserved provider contracts, Guardian decisions, controlled execution,
  Execution Truth, and AFDE-2.7 approval binding and consumption semantics.

## AFDE-3.0 Sprint 1 Multi-Agent Development Pipeline Foundation

- Added an additive `RuntimePipeline` connecting Planner, Developer, QA,
  Documentation, and the existing conditional approval boundary.
- Added validated `PLANNED`, `ASSIGNED`, `DEVELOPING`, `QA_PENDING`,
  `DOCUMENTING`, `APPROVAL_PENDING`, and `DONE` pipeline states.
- Extended `RuntimeTask` with current ownership and append-only handoff
  metadata while retaining its AFDE-2.9 worker lifecycle.
- Added task assignment, start, completion, forwarding, rejection, and
  approval events to the existing runtime event stream.
- Preserved the AFDE-2.7 controlled-action approval position before QA rather
  than moving or duplicating the security boundary.

## AFDE-2.9 Runtime Task and Worker State Engine

- Added a typed `RuntimeTask` carrying worker ownership, priority,
  dependencies, inputs, outputs, runtime evidence, and transition history.
- Extended `WorkerState` with the validated Planning-to-QA lifecycle while
  preserving existing worker and session state values.
- Connected normalized Planner output to a persisted task passed to the
  Developer through the AFDE-2.8 `WorkerContext`.
- Added task-scoped runtime events without replacing AFDE-2.7 approval events
  or changing approval, Guardian, controlled-execution, or Execution Truth
  semantics.

## AFDE-2.8 PR-1 Worker Context

- Expanded the runtime-owned `WorkerContext` with planner output, task
  metadata, runtime evidence, and prior worker artifacts.
- Passed one typed context through the Planner-to-Developer boundary while
  retaining the provider-facing mapping contract.
- Added JSON-safe context persistence and restoration across the existing
  AFDE-2.7 approval/resume path.
- Added focused creation, propagation, legacy-mapping, and resume coverage.

## AFDE-2.7 Human Approval Resume and Controlled Existing-File Edit

- Added persisted, exact, single-use approval records for existing-file edits.
- Added `waiting_approval` pause and cross-process runtime continuation.
- Added approval show, approve/resume, and reject CLI commands.
- Added pre-image protection, replay rejection, and runtime approval evidence.
- Preserved AFDE-2.6 new-file and bounded-command behavior.
- Completed the explicitly authorized live lifecycle with one exact existing-file
  write, one runtime-observed bounded pytest execution, and Execution Truth
  `VERIFIED`; the dedicated fixture was restored to its LF baseline afterward.

## AFDE-2.6 Real AI Provider

- Added an opt-in OpenAI Responses API provider with environment-only credentials.
- Added model, timeout, retry, usage, request ID, and structured error handling.
- Preserved deterministic mock execution and offline test behavior.
- Connected OpenAI to the five-worker runtime, revision loop, events, artifacts,
  and the `factory-demo` CLI.

## Added

- AFDE Environment Checker
- Real AI Worker Bootstrap
- CLI commands:
  - `env-check`
  - `bootstrap-worker`
- Development docs for environment checking and worker bootstrap
- Unit tests for AFDE-2

## AFDE-2.3 Approval Guardian v2

### Added

- Deterministic `AUTO_APPROVE`, `ASK_USER`, and `DENY` command classification
- Quote-aware chained-command and shell-wrapper analysis
- Repository, branch, working-tree, and environment context guards
- Redacted decision audit records and ExecPolicy compatibility adapter
- AFDE `approval-check` CLI command
- 86 focused Guardian policy and integration tests

## AFDE-2.4 Sprint Auto Runner

### Added

- Approval-guarded Sprint JSON loader and deterministic run state machine
- AUTO_APPROVE execution, ASK_USER persistence/resume, and DENY blocking
- Non-shell executor with timeout, output capture, and redaction
- Atomic JSON state and JSONL lifecycle audit records
- AFDE sprint validate, run, status, resume, cancel, JSON, and dry-run CLI
- 64 focused Runner tests and demo Sprint definition

## AFDE-2.5 Real AI Worker Runtime

- Added five-worker Demo, dashboard, mock provider, messages/events/artifacts,
  Runner/Guardian validation, revision loop, runtime CLI, and 53 focused tests.

## Safety

- External AI calls remain opt-in. AFDE-2.7 used only the explicitly authorized
  controlled live validation and persisted no provider credential values.
