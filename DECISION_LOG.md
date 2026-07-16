# Decision Log

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
