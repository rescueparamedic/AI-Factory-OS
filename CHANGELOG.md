# Sprint AFDE-2 Changelog

## AFDE-4.8 Knowledge Foundation Provider MVP (Unreleased)

- Added a governed machine-readable Registry snapshot with the existing 12
  Document, 3 Knowledge, and `CAP-KNOW-0001` entries.
- Added immutable typed Registry, Capability Context, and Gap models.
- Added a repository-contained UTF-8 JSON loader and fail-closed validation for
  schema, IDs, enums, paths, bindings, conflicts, cycles, and implementation
  consistency.
- Added deterministic read-only Document, Knowledge, Capability, priority,
  context, and gap Provider APIs for future Resolver injection.
- Advanced `CAP-KNOW-0001` from M2 Designed to M3 Implemented without claiming
  M4 validation or operational integration.
- Added focused tests for valid queries, malformed and invalid Registries,
  containment, byte invariance, and architecture boundaries.
- Preserved Runtime, Product Layer, Planner, Resolver, Tool Adapter, CLI,
  Desktop, Evidence, and all public contracts.
- Added no external dependency, network access, Markdown search, RAG, vector
  database, embedding, or multimodal behavior.

## AFDE-4.7 Knowledge Foundation Architecture (Unreleased)

- Added the Knowledge Foundation architecture boundary between Capability and
  Capability Resolver.
- Added Document/Knowledge Management, Knowledge Registry, Capability Registry,
  Document Governance, and AI Reference Policy v1 standards.
- Registered `CAP-KNOW-0001` as architecture-approved at M2 while explicitly
  retaining `not_implemented` implementation status.
- Added initial authoritative Document and Knowledge entries, source bindings,
  lifecycle and authority models, conflict/supersession rules, validation
  requirements, and Knowledge/Capability Gap handling.
- Updated the canonical AFDE and Product Layer architecture, Master Index,
  Decision Log, and Project Status without changing code or public contracts.
- Preserved Runtime, Product Layer, Planner, Resolver, Tool Adapter, Evidence,
  Beta Execute, Desktop, merge, deployment, and external-call behavior.

## AFDE-4.5 AI Development Engine Product Layer

- Added the internal `afde.product` package with `ProductRunView`,
  `DevelopmentRunService`, and Operator-result projection.
- Reused the existing Operator and Runtime path for product coordination and
  read-only presentation.
- Preserved Beta Execute, Desktop, Runtime lifecycle, Approval, ToolAction, and
  Evidence contracts.
- Added focused product model, presenter, and service tests.

## AFDE-4.4 Desktop Operator UX MVP (Unreleased)

- Reworked the existing single Desktop window into a Korean-labeled
  project-folder, AI-task, and run flow without changing the Runtime or public
  CLI contract.
- Added Korean display-only status mapping, input-ready Run behavior, a
  prominent primary action, and clear completed-Evidence access while
  preserving the detailed execution log.
- Added offscreen Qt coverage for labels, step titles, status rendering, input
  readiness, busy controls, completed controls, and detailed result fields.
- Verified 33 focused Desktop tests, 714 passed full tests with 2 explicit live
  skips, compileall, pip consistency, diff integrity, a rebuilt Windows onedir
  EXE, GUI launch, packaged Mock Evidence flow, Open Evidence, and zero orphan
  packaged processes.

## AFDE-4.3B Windows EXE Packaging (Unreleased)

- Added a reproducible PyInstaller 6.21.0 and PySide6 6.11.1 windowed
  onedir definition for `AI Factory Desktop.exe`.
- Added a bounded PowerShell build command and source/frozen path helpers
  without relocating workspace or Evidence data.
- Reused the existing AFDE CLI JSON and exit-code contract in frozen mode
  without changing Runtime lifecycle or public CLI behavior.
- Added deterministic packaging tests and a read-only Windows PR artifact
  workflow with no Release, deployment, signing, or merge automation.
- Verified the local build, GUI launch, normal exit, zero orphan processes,
  705 passed tests, 2 explicit live-test skips, compileall, pip consistency,
  and diff integrity. Interactive packaged Mock flow still requires manual
  validation, and clean Windows PC validation is not yet verified.

## AFDE-4.3A AI Factory Desktop MVP (Unreleased)

- Added the optional PySide6 `AI Factory Desktop` single-window entry point at
  `python -m afde.desktop` without changing the default CLI dependency set.
- Reused the official `afde.cli execute --json` contract through a background
  QThread worker with the Provider fixed to offline deterministic `mock`.
- Added workspace/request validation, Idle-to-Completed/Failed UI states,
  structured logs, absolute Evidence handling, and default Windows file open.
- Added Qt-independent application and state regression coverage plus minimal
  Desktop installation, operation, scope, and packaging documentation.

## AFDE-4.2 Beta Evidence Inspection And Recovery (Unreleased)

- Added a read-only `execution-evidence` CLI for human and direct JSON
  inspection of persisted Beta execution Evidence.
- Added explicit invalid, missing, and unreadable Evidence exit codes plus
  workspace containment, link rejection, and defensive secret redaction.
- Replaced failed Beta execution recovery guidance with the executable
  Evidence inspection command while preserving existing Runtime history.
- Added deterministic, network-free regression coverage for completed and
  failed Evidence inspection, recovery, sanitization, and byte invariance.

## AFDE-4.0.2 Full Regression Validation

- Added Runtime Session Boundary Validation for status(), report(), and
  cancel(), rejecting absolute, traversal, separator-bearing, and session-root
  escape paths.
- Added one canonical SESSION_CANCELLED Runtime Cancel Event with status
  cancelled through the existing Event Stream and History structure.
- Separated the Dashboard Cancelled Status from Failed while preserving the
  existing failed-session projection.
- Added deterministic Regression Validation for Runtime Cancel, Session
  Boundary, CLI Exit Code, and Evidence Consistency release gates.

## AFDE-4.0.1 Beta Runtime Hardening

- Standardized expected Runtime CLI failures with explicit Status, Error,
  Cause, Next action, Evidence, and Session ID fields for human and JSON paths.
- Preserved the established Beta exit-code contract while making Runtime
  success, invalid request, missing session, execution failure, and evidence
  failure outcomes explicit.
- Added validated `--workspace` support to the existing runtime status, report,
  and cancel commands without changing their default current-directory behavior.
- Added actionable guidance using existing Runtime history, status, provider,
  and help commands; unexpected internal exceptions remain visible for debugging.
- Added deterministic, network-free Runtime CLI hardening regression coverage.

## AFDE-3.14 Beta Readiness Validation

- Added one official afde execute Beta CLI over the existing Planner, Provider,
  ProviderRuntimeBridge, RealExecutionPipeline, and single-worker adapter
  contracts.
- Added unique execution/session/request identities and atomic bounded evidence
  at data/runtime_sessions/<session_id>/execution_evidence.json.
- Added normalized, sanitized planning/provider/bridge/worker/evidence failure
  results with stable CLI exit codes.
- Added deterministic full-path Mock E2E, three-run repeatability, failure
  matrix, secret-leakage, and explicitly opted-in live OpenAI coverage.
- Documented the AFDE-4.0 Beta execution contract, acceptance checklist, E2E
  scenarios, and known limitations without changing legacy Runtime commands.

## AFDE-3.12 Real AI Provider Integration

- Added a minimal immutable provider contract and deterministic mock provider.
- Added an explicit-opt-in OpenAI Responses provider with environment-based
  credentials and normalized response metadata.
- Added exact provider factory selection without fallback or provider routing.
- Preserved the existing structured Worker Runtime adapter while recording
  provider, model, and execution mode in Runtime evidence and history.
- Added provider model, mock, factory, CLI selection, and live API protection
  tests without introducing autonomous behavior or UI changes.

## AFDE-3.11 Execution Planner MVP

- Added deterministic rule-based Goal to ExecutionPlan to ExecutionTask
  generation with no AI provider usage.
- Added persisted plan create/show services, JSON serialization, and minimal
  duplicate ID, missing dependency, and cycle validation.
- Added nested `plan create` and `plan show` CLI commands with JSON output.
- Added a read-only Runtime Dashboard Execution Plan Summary for the latest
  valid persisted plan.
- Added focused model, planner, validation, CLI, and Dashboard tests plus the
  Planner MVP product guide.

## AFDE-3.10 Operator Workflow MVP

- Added a thin `afde.operator` application layer that delegates to the existing
  Runtime, Provider, Approval Guardian, Controlled Execution, History, and
  Dashboard components.
- Added read-only PASS/WARN/FAIL preflight checks with provider/live opt-in,
  repository dirty-state, workspace, execution-boundary, runtime-path, and
  credential-safe output reporting.
- Added `operator-preflight`, `operator-run`, `operator-status`,
  `operator-approve`, `operator-reject`, and `operator-resume` with stable JSON
  projections, exact next commands, evidence hints, and semantic exit codes.
- Split exact approval recording from Runtime resume while retaining the legacy
  approve-and-resume API and all existing policy, context, preimage, and
  single-use revalidation behavior.
- Added a deterministic network-free acceptance flow, focused operator tests,
  byte-invariance coverage, and a PowerShell operator quickstart.

## AFDE-3.9 Runtime History Foundation

- Extended the existing RuntimeEvent and EventStream path with required event
  identity, session, type, actor, status, worker, and metadata fields while
  preserving legacy event fields.
- Added a lightweight append-only RuntimeHistoryStore over each session's
  existing `events.jsonl`, with stable chronological reads, session validation,
  filters, safe copies, legacy normalization, and JSON/CSV representation.
- Added read-only Dashboard history/error projections and `runtime-history`,
  `runtime-events`, and `runtime-export` CLI commands.
- Reused existing Runtime lifecycle event calls without changing RuntimePipeline,
  approval policy, Controlled Execution, or runtime state transitions.

## AFDE-3.8 Operations Center

- Added pure `OperationsAnalytics` projections for deterministic comparison,
  KPIs, stage duration provenance, approval delays, failure summaries,
  staleness, and explainable advisory bottleneck findings.
- Added validated JSON `/operations`, `/compare`, and `/operations-report`
  routes for 2 to 5 discovered sessions with safe malformed-session fallback.
- Added an accessible responsive Operations Center with URL-only multi-session
  selection, consolidated refresh, stale-response rejection, filtering,
  sorting, visible limits, and JSON/CSV Blob export.
- Preserved RuntimePipeline/Dashboard Snapshot authority, GET/HEAD-only
  localhost security, evidence metadata containment, and all existing dashboard
  and CLI behavior without a database, dependency, or mutation boundary.

## AFDE-3.7 Interactive Operations Dashboard

- Added `GET /sessions` discovery over existing persisted runtime sessions,
  returning safe summaries without paths, a registry, or a database.
- Added validated `session_id` query selection and browser session switching
  without server restart or filesystem input.
- Added global search, panel filters, stable sorting, session-aware URL state,
  metadata detail dialogs, snapshot-derived statistics, and compact navigation.
- Added independent low-frequency session-list refresh with overlap prevention,
  retained one guarded runtime request per interval, and bounded timeline output.
- Added keyboard/focus/Escape dialog behavior, ARIA result/session messaging,
  responsive controls, and read-only/malformed/traversal/byte-invariance tests.

## AFDE-3.6 Live Web Dashboard

- Upgraded the browser skeleton into a responsive live operations console
  with dedicated runtime, current operation, worker progress, lifecycle,
  approval, timeline, evidence, repository, and connection views.
- Added status badges for all runtime states, honest progress provenance,
  richer approval/timeline/evidence metadata, and repository availability and
  commit fields while retaining the AFDE-3.5 API routes.
- Added a single non-overlapping `/runtime` polling loop with last-valid-view
  preservation, visible disconnect/recovery state, unload cleanup, and a
  read-only manual refresh.
- Strengthened safe rendering, CSP form denial, session-contained evidence
  identifiers, keyboard focus, ARIA refresh announcements, responsive layouts,
  and reduced-motion behavior.
- Added focused AFDE-3.6 compatibility, rendering, polling, traversal,
  mutation-rejection, serialization, and persisted-byte invariance coverage.

## AFDE-3.5 Web Dashboard Foundation

- Added a reusable read-only `DashboardAPI` with JSON runtime, session,
  workers, timeline, approval queue, evidence, repository, and config views.
- Added a standard-library, localhost-only embedded HTTP server with GET/HEAD
  support, JSON 404/405 errors, security headers, and no mutation methods.
- Added a responsive browser dashboard skeleton with Runtime, Workers,
  Timeline, Approval Queue, Evidence, and Repository cards.
- Added configurable single-endpoint browser polling over the AFDE-3.4
  Dashboard Snapshot and a `runtime-dashboard-web` CLI command.
- Added API, HTTP, serialization, polling, rendering, and byte-level
  read-only coverage without introducing dependencies.

## AFDE-3.4 Live Terminal Dashboard

- Added safely copied dashboard snapshots with current stage, task, worker,
  status, evidence, repository state, timestamp, and progress provenance.
- Added a reusable bounded polling controller with configurable intervals,
  maximum refreshes/duration, refresh-error recovery, and clean Ctrl+C exit.
- Added a dependency-free terminal live renderer with ANSI clearing only on
  supported terminals and safe no-clear or redirected-output fallback.
- Added `runtime-dashboard --live`, `--refresh-interval`,
  `--max-refreshes`, `--max-duration`, and `--no-clear`.
- Preserved existing non-live text and JSON output behavior.

## AFDE-3.3 Runtime Dashboard MVP

- Added a read-only persisted runtime dashboard with Running, Waiting,
  Completed, and Failed status projection.
- Added Development, QA, Documentation, Approval, and Release worker rows with
  current task and progress derived from the existing RuntimePipeline.
- Added pending approval, chronological event, available evidence, and Git
  repository views plus text and JSON CLI output.
- Added completed, waiting-approval, failed, rendering, evidence, event, and
  CLI dashboard coverage.

## AFDE-3.2 Codex Automation Bridge

- Added the strict structured `ToolAction` contract and deterministic action
  fingerprints for file, command, test, and bounded Git operations.
- Added context binding, adapter dispatch, persistent duplicate prevention,
  redacted evidence, and AUTO/ASK/DENY runtime continuation behavior.
- Reused Approval Guardian and ControlledExecutor as the only protected
  side-effect boundary; legacy proposals remain an absent-actions fallback.
- Added deterministic mock CLI demos and action evidence inspection.

## AFDE-3.1 Safe Auto Approval Engine

- Added normalized runtime approval context and deterministic action/context
  fingerprints at the existing ControlledExecutor boundary.
- Required existing Controlled Execution and Approval Guardian permission plus
  durable pre-execution evidence before automatic side effects.
- Added exact context revalidation, stale-context invalidation, approver
  evidence, and single-use consumption.
- Extended waiting state/CLI evidence with safe reason, action summary,
  `RUNTIME_APPROVAL_REQUIRED`, and exact-resume guidance.

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
