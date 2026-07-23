# Decision Log

## 2026-07-23 - AFDE-4.8 Read-only Knowledge Foundation Provider

- Implemented `CAP-KNOW-0001` as an internal read-only Provider and advanced it
  from M2 Designed to M3 Implemented without claiming M4 validation.
- Adopted one governed JSON snapshot containing separate Document, Knowledge,
  and Capability collections plus authority and reference-priority metadata.
- Kept official Markdown documents as Source of Record; the JSON Registry is an
  index and neither copies full source content nor stores execution settings.
- Added immutable typed models, a repository-contained UTF-8 JSON loader,
  cross-registry fail-closed validation, deterministic queries,
  Resolver-ready `CapabilityContext`, and structured gaps.
- Distinguished an invalid Registry, which raises a validation error, from a
  valid unmet Capability requirement, which returns an explicit Gap.
- Omitted self-referential source Commit metadata from the MVP snapshot; Git
  history remains the authoritative revision audit.
- Added no Resolver selection, Runtime call, Worker execution, Planner or
  Product Layer change, Tool Adapter behavior, file mutation, network call,
  Markdown search, RAG, vector database, embedding, or multimodal behavior.
- Preserved every existing public contract and Runtime lifecycle.
- Capability Resolver, Tool Adapter implementation, operational integration,
  and M4 validation remain separately approved future work.

## 2026-07-23 - AFDE-4.7 Knowledge Foundation Architecture

- Added Knowledge Foundation between Capability and Capability Resolver as a
  governed architecture boundary for official document discovery, knowledge
  validity, capability metadata, reference authority, and gap reporting.
- Established Document, Knowledge, and Capability Registry standards as
  repository indexes that never replace Source of Record documents,
  implementation, Runtime state, or Evidence.
- Registered `CAP-KNOW-0001` as `architecture_approved`, maturity `M2`, and
  `not_implemented`; capability status, maturity, and implementation truth
  remain independent.
- Required Active Knowledge and Registry entries to bind official Active source
  documents and required document and registry changes to be reviewed as one
  governance unit.
- Established AI reference eligibility, priority, scope, status, conflict,
  missing-knowledge, external-source, and traceability rules.
- Preserved Runtime, Product Layer, Planner, Capability Resolver, Tool Adapter,
  Evidence, Beta Execute, Desktop, and all public contracts unchanged.
- Deferred machine-readable registries, validation services, query APIs,
  Resolver and Adapter implementation, RAG, vector databases, embeddings, and
  multimodal execution to separately approved Sprints.
- Retained `develop` as Source of Truth, feature-branch workflow, Merge Commit
  only policy, and explicit user approval before merge.

## 2026-07-18 - AFDE-3.9 Reuse the Existing Event Ledger

- Keep session `events.jsonl` as the single append-only event ledger instead of
  adding a database, parallel history file, event bus, or analytics store.
- Extend RuntimeEvent additively and preserve `event`, `detail`, `task_id`,
  `state`, and `payload` for Runtime and Dashboard compatibility.
- Route EventStream writes through RuntimeHistoryStore so all existing Session,
  Worker, Approval, QA, failure, and completion emissions gain the new model
  without changing RuntimePipeline transitions or approval execution behavior.
- Normalize legacy records only when read. Deterministic `EVT-LEGACY-*` IDs and
  canonical types are projections and never rewrite historical bytes.
- Keep history CLI exports on stdout and Dashboard access read-only; history
  does not become authority for current runtime state.

## 2026-07-17 - AFDE-3.8 Pure Snapshot Operations Analytics

- Adopted `OperationsAnalytics` as a deterministic transport-neutral projection
  over copied Dashboard Snapshots; it has no RuntimePipeline dependency, cache,
  database, ingestion path, background job, or persistence.
- Limited comparison to 2 through 5 unique IDs from validated session discovery;
  malformed discovered sessions remain visible as Unavailable.
- Required honest duration provenance (`measured`, `inferred`, `unavailable`),
  explicit KPI denominators, centralized thresholds, and explainable advisory
  findings rather than opaque scores or AI-generated root-cause claims.
- Kept comparison selection in URL presentation state and coupled consolidated
  analytics refresh to the existing runtime poll cycle with overlap and stale
  response guards.
- Kept reports read-only and data-equivalent to Operations APIs; Blob downloads
  are browser-local and the HTTP server writes no export file.

## 2026-07-16 - AFDE-3.7 Validated Session Discovery and Presentation Tools

- Discover sessions directly from existing runtime-session directories and
  derive summaries through `RuntimeDashboard.snapshot`; do not add a registry.
- Validate selected IDs syntactically and against discovery results before
  asking the snapshot provider for data. Never accept or return filesystem paths.
- Keep search, filters, sorting, selected-session URL state, dialog state, and
  statistics in the browser presentation layer only; never persist them as
  runtime or analytics state.
- Preserve one guarded runtime poll. Permit a lower-frequency `/sessions` read
  with its own overlap guard because it does not poll or duplicate runtime state.
- Keep evidence detail metadata-only and use text-created DOM plus focus-return
  dialog behavior for safe accessible inspection.

## 2026-07-16 - AFDE-3.6 Live Presentation State

- Preserve Dashboard Snapshot as the only browser data projection and continue
  one complete `/runtime` GET per refresh; individual cards do not poll.
- Treat the last successful snapshot as presentation continuity only. A failed
  request changes connection messaging but never replaces the visible runtime
  data or becomes authoritative state.
- Prevent overlapping requests with one in-flight guard, reschedule only after
  completion, abort on unload, and allow manual refresh through the identical
  read-only request path.
- Keep evidence metadata-only. Only available artifacts resolved inside the
  runtime session directory are projected, and no preview/file-serving route
  is introduced.
- Use semantic sections, text-bearing status badges, visible keyboard focus,
  an ARIA live region, responsive breakpoints, and reduced-motion handling as
  the accessibility baseline.

## 2026-07-16 - AFDE-3.5 Snapshot-Backed Web Boundary

- `DashboardAPI` is the only web-facing data adapter and consumes
  `RuntimeDashboard.snapshot`; HTTP handlers never access RuntimePipeline.
- `/runtime` returns one complete snapshot so browser refresh does not
  duplicate polling across cards. Component endpoints are additive views over
  the same snapshot interface.
- The embedded HTTP transport binds only to localhost and permits GET/HEAD;
  mutation methods fail with JSON 405 responses.
- Static HTML/CSS/JS remains dependency-free and treats API values as text,
  with a same-origin Content Security Policy and no action controls.
- The API remains transport-neutral so later WebSocket, SSE, authentication,
  RBAC, remote, and multi-session adapters can wrap it without parsing HTML.

## 2026-07-16 - AFDE-3.4 Live Dashboard Separation

- RuntimeDashboard remains the reusable read-only snapshot provider over
  RuntimePipeline; polling and terminal presentation cannot mutate runtime.
- LiveDashboardController owns interval validation, bounds, sleeping,
  interruption, and last-valid-snapshot recovery without owning state.
- TerminalLiveDashboardRenderer consumes structured snapshots and is not an
  execution or persistence layer.
- Progress prefers an explicit RuntimePipeline value, then existing explicit
  RuntimeSession progress, then a documented deterministic lifecycle mapping;
  absent state is reported as unavailable.
- The standard library is sufficient. A browser/WebSocket dashboard,
  authentication, and remote aggregation are deferred.

## 2026-07-16 - AFDE-3.3 Read-Only Runtime Dashboard

- RuntimePipeline remains the authoritative delivery-stage state; dashboard
  worker status is a projection and cannot transition the pipeline.
- Existing session approval, event-stream, and artifact references are reused
  for queue, timeline, and evidence views.
- The MVP uses an on-demand CLI snapshot in text or JSON and invokes only
  read-only Git commands for repository status.
- Approval and Release are display stages only; no new runtime worker,
  approval policy, or release execution authority is introduced.

## 2026-07-15 - AFDE-3.2 Structured Automation Boundary

- `ToolAction` is the canonical worker-to-runtime automation contract; raw
  text is never interpreted as executable authority.
- Approval Guardian and ControlledExecutor remain the sole protected
  side-effect policies and boundary.
- Structured actions bind exact repository, cwd, branch, task, session, stage,
  revision, worker, target, and payload evidence before execution.
- Existing proposal fields remain compatible only when `actions` is absent.
- Merge, deployment, release, destructive Git, protected push, and secret input
  are excluded rather than modeled as approvable bridge actions.

## 2026-07-15 — AFDE-3.1 Central Runtime Approval Enforcement

- `ApprovalDecision` and `ApprovalGuardian` remain canonical; no second
  approval classifier is introduced.
- `ControlledExecutor` is the final permission check for real runtime file and
  command side effects.
- AUTO_APPROVE requires durable evidence and agreement between Guardian and
  Controlled Execution; either DENY wins.
- Human approval is bound to deterministic action and context fingerprints
  and revalidated immediately before execution.
- Sprint Auto Runner retains its existing boundary to prevent double execution.

## 2026-07-14 — AFDE-3.0 Runtime Lifecycle Finalization

- AFDE-3.0 Multi-Agent Runtime adopts deterministic lifecycle finalization,
  structured role failure propagation, and append-only runtime transition
  history.
- `RuntimeTask` remains the sole lifecycle owner; `WorkerContext` remains the
  serialized continuation carrier and `RuntimeOrchestrator` remains the role,
  handoff, and bounded-revision coordinator.
- Existing WorkerState and RuntimePipeline transitions remain authoritative for
  their established contracts. The lifecycle status is an additive run-level
  projection with fail-closed transition validation.
- Final summaries are derived from persisted task evidence and never infer
  success from provider claims.

## 2026-07-12 — AFDE-2.7 Human Approval Resume

- Reused atomic Runtime JSON for approval and continuation records.
- Bound approval to session, execution request, normalized payload, target,
  pre-image hash, and a canonical single-use fingerprint.
- Kept existing-file replacement as `ASK_USER`; `AGV2-S004` is unchanged.
- Required runtime-owned edits/evidence and fail-closed pre-image mismatch.

## 2026-07-11 — Approval Guardian v2

- Adopted three decisions: `AUTO_APPROVE`, `ASK_USER`, and `DENY`.
- Adopted fail-closed classification with deny-overrides precedence.
- Allowed verified low-risk actions only within feature-branch workflows.
- Kept the existing release `ApprovalGate` unchanged and added Guardian as a
  command-policy layer.
- Reused the existing JSON audit directory with command redaction and
  fingerprinting.
- Kept Safe Approval Policy v1 compatibility behind `ExecPolicyAdapter`; the
  v1 policy itself is not duplicated because it is not yet on `develop`.

## 2026-07-11 — Sprint Auto Runner

- Adopted a persisted Sprint state machine with mandatory Guardian evaluation
  before every process execution.
- Limited automatic progress to AUTO_APPROVE decisions in verified feature
  workflows; ASK_USER persists and stops, while DENY permanently blocks.
- Explicitly denied direct push to `main`, `master`, and `develop` in the Runner.
- Kept merge as a user-approved operation and excluded automatic merge.
- Chose additive integration instead of replacing all legacy executors.

## 2026-07-11 — Real AI Worker Runtime MVP

- Prioritized an executable deterministic mock Demo.
- Reused Runner/Guardian and prohibited silent real-provider fallback.
